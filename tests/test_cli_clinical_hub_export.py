from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from uroflow_mobile.cli import main as cli_main
from uroflow_mobile.clinical_hub import create_clinical_hub_app


def _payload() -> dict[str, object]:
    return {
        "session": {
            "session_id": "session-cli-001",
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
        "app": {
            "metrics": {
                "qmax_ml_s": 17.0,
                "qavg_ml_s": 9.2,
                "vvoid_ml": 280.0,
            },
            "quality_status": "repeat",
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
