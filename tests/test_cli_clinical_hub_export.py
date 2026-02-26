from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient
from pytest import raises

from uroflow_mobile.cli import _load_api_key_policy_map
from uroflow_mobile.cli import main as cli_main
from uroflow_mobile.clinical_hub import create_clinical_hub_app


def _payload(
    *,
    session_id: str = "session-cli-001",
    sync_id: str | None = None,
    platform: str = "android",
    quality_status: str = "repeat",
) -> dict[str, object]:
    return {
        "session": {
            "session_id": session_id,
            "sync_id": sync_id,
            "site_id": "SITE-001",
            "subject_id": "SUBJ-002",
            "operator_id": "OP-01",
            "attempt_number": 1,
            "measured_at": "2026-02-24T10:30:00Z",
            "platform": platform,
            "device_model": "Pixel 8",
            "app_version": "0.2.0",
            "capture_mode": "water_impact",
        },
        "app": {
            "metrics": {
                "qmax_ml_s": 17.0,
                "qavg_ml_s": 9.2,
                "vvoid_ml": 280.0,
            },
            "quality_status": quality_status,
        },
        "reference": {
            "metrics": {
                "qmax_ml_s": 18.1,
                "qavg_ml_s": 9.8,
                "vvoid_ml": 289.0,
            }
        },
    }


def _pilot_report_payload() -> dict[str, object]:
    return {
        "site_id": "SITE-001",
        "report_date": "2026-02-24",
        "report_type": "g1_eval",
        "package_version": "v2.5",
        "model_id": "fusion-v0.3",
        "dataset_id": "pilot-ds-001",
        "payload": {"valid_rate": 0.9, "mae_qmax": 1.8},
    }


def _capture_package_payload(
    *,
    session_id: str,
    sync_id: str | None,
    paired_measurement_id: int | None,
) -> dict[str, object]:
    return {
        "session": {
            "session_id": session_id,
            "sync_id": sync_id,
            "site_id": "SITE-001",
            "subject_id": "SUBJ-002",
            "operator_id": "OP-01",
            "attempt_number": 1,
            "measured_at": "2026-02-24T10:30:00Z",
            "platform": "android",
            "device_model": "Pixel 8",
            "app_version": "0.2.0",
            "capture_mode": "water_impact",
        },
        "package_type": "capture_contract_json",
        "capture_payload": {
            "schema_version": "ios_capture_v1",
            "session": {"session_id": session_id},
            "samples": [{"t_s": 0.0, "audio_rms_dbfs": -40.0}],
        },
        "paired_measurement_id": paired_measurement_id,
        "notes": "capture package for export join test",
    }


def _sha256_hex(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_cli_export_paired_measurements(tmp_path: Path) -> None:
    db_path = tmp_path / "clinical_hub.db"
    app = create_clinical_hub_app(db_path)

    with TestClient(app) as client:
        response = client.post("/api/v1/paired-measurements", json=_payload())
        assert response.status_code == 201

    output_csv = tmp_path / "paired.csv"
    sha256_file = tmp_path / "paired.csv.sha256"
    exit_code = cli_main(
        [
            "export-paired-measurements",
            "--db-path",
            str(db_path),
            "--output-csv",
            str(output_csv),
            "--sha256-file",
            str(sha256_file),
        ]
    )

    assert exit_code == 0
    assert output_csv.exists()

    with output_csv.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    assert len(rows) == 1
    assert rows[0]["session_id"] == "session-cli-001"
    assert rows[0]["platform"] == "android"
    assert sha256_file.exists()
    manifest_line = sha256_file.read_text(encoding="utf-8").strip()
    assert manifest_line == f"{_sha256_hex(output_csv)}  {output_csv.name}"


def test_cli_summarize_paired_measurements(tmp_path: Path) -> None:
    db_path = tmp_path / "clinical_hub.db"
    app = create_clinical_hub_app(db_path)

    with TestClient(app) as client:
        response_1 = client.post("/api/v1/paired-measurements", json=_payload())
        assert response_1.status_code == 201

        payload_2 = _payload()
        payload_2["session"] = {
            **payload_2["session"],  # type: ignore[index]
            "session_id": "session-cli-002",
        }
        payload_2["app"] = {
            **payload_2["app"],  # type: ignore[index]
            "quality_status": "reject",
        }
        response_2 = client.post("/api/v1/paired-measurements", json=payload_2)
        assert response_2.status_code == 201

    output_json = tmp_path / "summary.json"
    exit_code = cli_main(
        [
            "summarize-paired-measurements",
            "--db-path",
            str(db_path),
            "--quality-status",
            "all",
            "--output-json",
            str(output_json),
        ]
    )

    assert exit_code == 0
    assert output_json.exists()
    summary = json.loads(output_json.read_text(encoding="utf-8"))
    assert summary["records_considered"] == 2
    assert summary["quality_distribution"]["reject"] == 1
    assert any(metric["metric"] == "qmax_ml_s" for metric in summary["metrics"])


def test_cli_export_paired_with_capture(tmp_path: Path) -> None:
    db_path = tmp_path / "clinical_hub_join.db"
    app = create_clinical_hub_app(db_path)

    with TestClient(app) as client:
        paired_direct = _payload(session_id="session-cli-join-001", sync_id="sync-join-001")
        paired_fallback = _payload(session_id="session-cli-join-002", sync_id="sync-join-002")
        paired_missing = _payload(session_id="session-cli-join-003", sync_id="sync-join-003")

        paired_direct_response = client.post("/api/v1/paired-measurements", json=paired_direct)
        paired_fallback_response = client.post("/api/v1/paired-measurements", json=paired_fallback)
        paired_missing_response = client.post("/api/v1/paired-measurements", json=paired_missing)
        assert paired_direct_response.status_code == 201
        assert paired_fallback_response.status_code == 201
        assert paired_missing_response.status_code == 201

        paired_direct_id = int(paired_direct_response.json()["id"])

        direct_capture = _capture_package_payload(
            session_id="session-cli-join-001",
            sync_id="sync-join-001",
            paired_measurement_id=paired_direct_id,
        )
        fallback_capture = _capture_package_payload(
            session_id="session-cli-join-002",
            sync_id="sync-join-002",
            paired_measurement_id=None,
        )
        assert client.post("/api/v1/capture-packages", json=direct_capture).status_code == 201
        assert client.post("/api/v1/capture-packages", json=fallback_capture).status_code == 201

    output_csv = tmp_path / "paired_with_capture.csv"
    exit_code = cli_main(
        [
            "export-paired-with-capture",
            "--db-path",
            str(db_path),
            "--output-csv",
            str(output_csv),
        ]
    )

    assert exit_code == 0
    with output_csv.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    assert len(rows) == 3
    row_by_session = {row["session_id"]: row for row in rows}

    direct_row = row_by_session["session-cli-join-001"]
    assert direct_row["has_capture_package"] == "1"
    assert direct_row["capture_match_mode"] == "paired_id"
    assert direct_row["capture_id"] != ""

    fallback_row = row_by_session["session-cli-join-002"]
    assert fallback_row["has_capture_package"] == "1"
    assert fallback_row["capture_match_mode"] == "session_identity"
    assert fallback_row["capture_id"] != ""

    missing_row = row_by_session["session-cli-join-003"]
    assert missing_row["has_capture_package"] == "0"
    assert missing_row["capture_match_mode"] == "none"
    assert missing_row["capture_id"] == ""


def test_cli_export_capture_coverage_summary_csv(tmp_path: Path) -> None:
    db_path = tmp_path / "clinical_hub_coverage.db"
    app = create_clinical_hub_app(db_path)

    with TestClient(app) as client:
        paired_1 = client.post(
            "/api/v1/paired-measurements",
            json=_payload(session_id="session-coverage-cli-001", sync_id="sync-coverage-cli"),
        )
        paired_2 = client.post(
            "/api/v1/paired-measurements",
            json=_payload(session_id="session-coverage-cli-002", sync_id="sync-coverage-cli"),
        )
        assert paired_1.status_code == 201
        assert paired_2.status_code == 201

        capture = client.post(
            "/api/v1/capture-packages",
            json=_capture_package_payload(
                session_id="session-coverage-cli-001",
                sync_id="sync-coverage-cli",
                paired_measurement_id=int(paired_1.json()["id"]),
            ),
        )
        assert capture.status_code == 201

    output_csv = tmp_path / "coverage_summary.csv"
    exit_code = cli_main(
        [
            "export-capture-coverage-summary",
            "--db-path",
            str(db_path),
            "--sync-id",
            "sync-coverage-cli",
            "--quality-status",
            "all",
            "--output-csv",
            str(output_csv),
        ]
    )

    assert exit_code == 0
    with output_csv.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 1
    assert rows[0]["sync_id"] == "sync-coverage-cli"
    assert rows[0]["paired_total"] == "2"
    assert rows[0]["paired_with_capture"] == "1"
    assert rows[0]["paired_without_capture"] == "1"
    assert float(rows[0]["coverage_ratio"]) == 0.5


def test_cli_export_capture_coverage_summary_with_targets_report(tmp_path: Path) -> None:
    db_path = tmp_path / "clinical_hub_coverage_targets.db"
    app = create_clinical_hub_app(db_path)

    with TestClient(app) as client:
        paired = client.post(
            "/api/v1/paired-measurements",
            json=_payload(
                session_id="session-coverage-targets-001",
                sync_id="sync-coverage-targets",
                quality_status="valid",
            ),
        )
        assert paired.status_code == 201
        capture = client.post(
            "/api/v1/capture-packages",
            json=_capture_package_payload(
                session_id="session-coverage-targets-001",
                sync_id="sync-coverage-targets",
                paired_measurement_id=int(paired.json()["id"]),
            ),
        )
        assert capture.status_code == 201

    output_csv = tmp_path / "coverage_summary_targets.csv"
    gates_json = tmp_path / "coverage_gates.json"
    targets_config = Path("config/coverage_targets_config.v1.json")

    exit_code = cli_main(
        [
            "export-capture-coverage-summary",
            "--db-path",
            str(db_path),
            "--sync-id",
            "sync-coverage-targets",
            "--quality-status",
            "all",
            "--output-csv",
            str(output_csv),
            "--targets-config",
            str(targets_config),
            "--gates-output-json",
            str(gates_json),
        ]
    )

    assert exit_code == 0
    assert output_csv.exists()
    assert gates_json.exists()
    report = json.loads(gates_json.read_text(encoding="utf-8"))
    assert report["hard_passed"] is True
    assert report["warning_passed"] is False
    assert any(gate["metric"] == "coverage_ratio" for gate in report["gates"])


def test_cli_export_capture_coverage_summary_fails_on_hard_gate(tmp_path: Path) -> None:
    db_path = tmp_path / "clinical_hub_coverage_hard_fail.db"
    app = create_clinical_hub_app(db_path)

    with TestClient(app) as client:
        paired = client.post(
            "/api/v1/paired-measurements",
            json=_payload(
                session_id="session-coverage-hard-fail-001",
                sync_id="sync-coverage-hard-fail",
                quality_status="valid",
            ),
        )
        assert paired.status_code == 201

    output_csv = tmp_path / "coverage_summary_hard_fail.csv"
    targets_config = Path("config/coverage_targets_config.v1.json")

    exit_code = cli_main(
        [
            "export-capture-coverage-summary",
            "--db-path",
            str(db_path),
            "--sync-id",
            "sync-coverage-hard-fail",
            "--quality-status",
            "all",
            "--output-csv",
            str(output_csv),
            "--targets-config",
            str(targets_config),
            "--fail-on-hard-gates",
        ]
    )

    assert output_csv.exists()
    assert exit_code == 1


def test_cli_summarize_paired_measurements_with_sync_and_platform_filters(tmp_path: Path) -> None:
    db_path = tmp_path / "clinical_hub.db"
    app = create_clinical_hub_app(db_path)

    with TestClient(app) as client:
        android_synced = _payload(
            session_id="session-cli-android-001",
            sync_id="sync-android-001",
            platform="android",
            quality_status="valid",
        )
        ios_other = _payload(
            session_id="session-cli-ios-001",
            sync_id="sync-ios-001",
            platform="ios",
            quality_status="valid",
        )
        android_other_sync = _payload(
            session_id="session-cli-android-002",
            sync_id="sync-android-002",
            platform="android",
            quality_status="repeat",
        )
        assert client.post("/api/v1/paired-measurements", json=android_synced).status_code == 201
        assert client.post("/api/v1/paired-measurements", json=ios_other).status_code == 201
        assert (
            client.post("/api/v1/paired-measurements", json=android_other_sync).status_code
            == 201
        )

    output_json = tmp_path / "summary_filtered.json"
    exit_code = cli_main(
        [
            "summarize-paired-measurements",
            "--db-path",
            str(db_path),
            "--quality-status",
            "all",
            "--platform",
            "android",
            "--sync-id",
            "sync-android-001",
            "--operator-id",
            "OP-01",
            "--output-json",
            str(output_json),
        ]
    )

    assert exit_code == 0
    summary = json.loads(output_json.read_text(encoding="utf-8"))
    assert summary["records_considered"] == 1
    assert summary["filters"]["platform"] == "android"
    assert summary["filters"]["sync_id"] == "sync-android-001"
    assert summary["filters"]["operator_id"] == "OP-01"


def test_cli_export_audit_events(tmp_path: Path) -> None:
    db_path = tmp_path / "clinical_hub.db"
    app = create_clinical_hub_app(db_path, api_key="secret")

    with TestClient(app) as client:
        unauthorized = client.get("/api/v1/paired-measurements")
        assert unauthorized.status_code == 401

        authorized = client.post(
            "/api/v1/paired-measurements",
            json=_payload(),
            headers={"x-api-key": "secret"},
        )
        assert authorized.status_code == 201

    output_csv = tmp_path / "audit.csv"
    exit_code = cli_main(
        [
            "export-audit-events",
            "--db-path",
            str(db_path),
            "--output-csv",
            str(output_csv),
        ]
    )

    assert exit_code == 0
    with output_csv.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
    assert len(rows) >= 2
    assert any(row["status_code"] == "401" for row in rows)


def test_cli_export_pilot_automation_reports(tmp_path: Path) -> None:
    db_path = tmp_path / "clinical_hub.db"
    app = create_clinical_hub_app(db_path)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/pilot-automation-reports",
            json=_pilot_report_payload(),
        )
        assert response.status_code == 201

    output_csv = tmp_path / "pilot_reports.csv"
    exit_code = cli_main(
        [
            "export-pilot-automation-reports",
            "--db-path",
            str(db_path),
            "--output-csv",
            str(output_csv),
        ]
    )

    assert exit_code == 0
    with output_csv.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["report_type"] == "g1_eval"


def test_load_api_key_policy_map_from_json(tmp_path: Path) -> None:
    policy_path = tmp_path / "api_keys.json"
    policy_path.write_text(
        json.dumps(
            {
                "op-key": {"role": "operator", "site_id": "SITE-001"},
                "dm-key": {"role": "data_manager"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    policy_map = _load_api_key_policy_map(str(policy_path))
    assert policy_map is not None
    assert policy_map["op-key"]["role"] == "operator"
    assert policy_map["op-key"]["site_id"] == "SITE-001"
    assert policy_map["dm-key"]["role"] == "data_manager"


def test_load_api_key_policy_map_rejects_invalid_schema(tmp_path: Path) -> None:
    policy_path = tmp_path / "api_keys_invalid.json"
    policy_path.write_text(json.dumps({"op-key": ["bad"]}), encoding="utf-8")

    with raises(ValueError, match="must be a JSON object"):
        _load_api_key_policy_map(str(policy_path))
