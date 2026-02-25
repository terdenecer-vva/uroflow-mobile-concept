from __future__ import annotations

import csv
from pathlib import Path

from fastapi.testclient import TestClient
from pytest import approx

from uroflow_mobile.clinical_hub import (
    create_clinical_hub_app,
    export_audit_events_to_csv,
    export_paired_measurements_to_csv,
    export_pilot_automation_reports_to_csv,
)


def _payload(session_id: str = "session-001") -> dict[str, object]:
    return {
        "session": {
            "session_id": session_id,
            "site_id": "SITE-001",
            "subject_id": "SUBJ-001",
            "operator_id": "OP-01",
            "attempt_number": 1,
            "measured_at": "2026-02-24T10:15:00Z",
            "platform": "ios",
            "device_model": "iPhone15,3",
            "app_version": "0.2.0",
            "capture_mode": "water_impact",
        },
        "app": {
            "metrics": {
                "qmax_ml_s": 19.3,
                "qavg_ml_s": 10.1,
                "vvoid_ml": 312.0,
                "flow_time_s": 21.4,
                "tqmax_s": 5.2,
            },
            "quality_status": "valid",
            "quality_score": 86.0,
            "model_id": "fusion-v0.2",
        },
        "reference": {
            "metrics": {
                "qmax_ml_s": 19.9,
                "qavg_ml_s": 10.4,
                "vvoid_ml": 318.0,
                "flow_time_s": 21.1,
                "tqmax_s": 5.0,
            },
            "device_model": "Uroflow Classic",
            "device_serial": "UF-123456",
        },
        "notes": "paired baseline",
    }


def _pilot_report_payload(
    site_id: str = "SITE-001",
    report_type: str = "qa_summary",
) -> dict[str, object]:
    return {
        "site_id": site_id,
        "report_date": "2026-02-24",
        "report_type": report_type,
        "package_version": "v2.5",
        "model_id": "fusion-v0.3",
        "dataset_id": "pilot-ds-001",
        "payload": {"valid_rate": 0.91, "n_total": 120, "n_valid": 109},
        "notes": "nightly import",
    }


def test_clinical_hub_crud_and_csv_export(tmp_path: Path) -> None:
    db_path = tmp_path / "clinical_hub.db"
    app = create_clinical_hub_app(db_path)

    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        created = client.post("/api/v1/paired-measurements", json=_payload())
        assert created.status_code == 201
        created_body = created.json()
        assert created_body["id"] == 1
        assert created_body["session"]["session_id"] == "session-001"
        assert created_body["app"]["quality_status"] == "valid"

        listing = client.get("/api/v1/paired-measurements")
        assert listing.status_code == 200
        listing_body = listing.json()
        assert len(listing_body) == 1
        assert listing_body[0]["session_id"] == "session-001"
        assert listing_body[0]["platform"] == "ios"

        detailed = client.get("/api/v1/paired-measurements/1")
        assert detailed.status_code == 200
        detailed_body = detailed.json()
        assert detailed_body["reference"]["metrics"]["qmax_ml_s"] == 19.9

        csv_response = client.get("/api/v1/paired-measurements.csv")
        assert csv_response.status_code == 200
        assert "session-001" in csv_response.text
        assert csv_response.headers["content-type"].startswith("text/csv")

        created_2 = client.post(
            "/api/v1/paired-measurements",
            json={
                **_payload(session_id="session-002"),
                "app": {
                    **_payload()["app"],
                    "quality_status": "repeat",
                    "metrics": {
                        "qmax_ml_s": 15.0,
                        "qavg_ml_s": 8.0,
                        "vvoid_ml": 260.0,
                        "flow_time_s": 20.0,
                        "tqmax_s": 4.0,
                    },
                },
                "reference": {
                    "metrics": {
                        "qmax_ml_s": 16.0,
                        "qavg_ml_s": 8.4,
                        "vvoid_ml": 270.0,
                        "flow_time_s": 19.0,
                        "tqmax_s": 4.4,
                    }
                },
            },
        )
        assert created_2.status_code == 201

        summary_valid = client.get("/api/v1/comparison-summary")
        assert summary_valid.status_code == 200
        summary_valid_body = summary_valid.json()
        assert summary_valid_body["records_matched_filters"] == 2
        assert summary_valid_body["records_considered"] == 1
        assert summary_valid_body["quality_distribution"]["valid"] == 1
        assert summary_valid_body["quality_distribution"]["repeat"] == 1
        qmax_summary = next(
            item for item in summary_valid_body["metrics"] if item["metric"] == "qmax_ml_s"
        )
        assert qmax_summary["paired_samples"] == 1
        assert qmax_summary["mean_error"] == approx(-0.6)

        summary_all = client.get("/api/v1/comparison-summary", params={"quality_status": "all"})
        assert summary_all.status_code == 200
        summary_all_body = summary_all.json()
        assert summary_all_body["records_considered"] == 2
        qmax_summary_all = next(
            item for item in summary_all_body["metrics"] if item["metric"] == "qmax_ml_s"
        )
        assert qmax_summary_all["paired_samples"] == 2
        assert qmax_summary_all["mean_absolute_error"] == approx(0.8)

    output_csv = tmp_path / "paired_export.csv"
    exported_rows = export_paired_measurements_to_csv(db_path=db_path, output_csv=output_csv)

    assert exported_rows == 2
    assert output_csv.exists()

    with output_csv.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    assert len(rows) == 2
    assert {row["session_id"] for row in rows} == {"session-001", "session-002"}
    assert {row["app_quality_status"] for row in rows} == {"valid", "repeat"}


def test_paired_measurement_idempotent_resubmit_returns_existing(tmp_path: Path) -> None:
    db_path = tmp_path / "clinical_hub_idempotent.db"
    app = create_clinical_hub_app(db_path)

    with TestClient(app) as client:
        first = client.post("/api/v1/paired-measurements", json=_payload())
        assert first.status_code == 201
        assert first.json()["id"] == 1

        second = client.post("/api/v1/paired-measurements", json=_payload())
        assert second.status_code == 200
        assert second.json()["id"] == 1

        listing = client.get("/api/v1/paired-measurements")
        assert listing.status_code == 200
        assert len(listing.json()) == 1


def test_paired_measurement_conflict_on_same_identity_with_changed_payload(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "clinical_hub_conflict.db"
    app = create_clinical_hub_app(db_path)

    with TestClient(app) as client:
        created = client.post("/api/v1/paired-measurements", json=_payload())
        assert created.status_code == 201

        conflicting_payload = _payload()
        conflicting_payload["app"] = {
            **conflicting_payload["app"],  # type: ignore[index]
            "metrics": {
                **conflicting_payload["app"]["metrics"],  # type: ignore[index]
                "qmax_ml_s": 25.0,
            },
        }
        conflict = client.post("/api/v1/paired-measurements", json=conflicting_payload)
        assert conflict.status_code == 409
        assert "different payload" in conflict.json()["detail"]


def test_clinical_hub_api_key_and_audit_export(tmp_path: Path) -> None:
    db_path = tmp_path / "clinical_hub_auth.db"
    api_key = "pilot-secret-key"
    app = create_clinical_hub_app(db_path, api_key=api_key)

    with TestClient(app) as client:
        unauthorized = client.get("/api/v1/paired-measurements")
        assert unauthorized.status_code == 401

        headers = {"x-api-key": api_key}
        authorized = client.post("/api/v1/paired-measurements", json=_payload(), headers=headers)
        assert authorized.status_code == 201

        audit_list = client.get("/api/v1/audit-events", headers=headers)
        assert audit_list.status_code == 200
        events = audit_list.json()
        assert len(events) >= 2
        assert any(item["status_code"] == 401 for item in events)
        assert any(item["path"] == "/api/v1/paired-measurements" for item in events)

    audit_csv = tmp_path / "audit_export.csv"
    audit_rows = export_audit_events_to_csv(db_path=db_path, output_csv=audit_csv)
    assert audit_rows >= 2
    assert audit_csv.exists()

    with audit_csv.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    assert len(rows) >= 2
    assert any(row["status_code"] == "401" for row in rows)


def test_pilot_automation_reports_crud_and_csv_export(tmp_path: Path) -> None:
    db_path = tmp_path / "clinical_hub_reports.db"
    app = create_clinical_hub_app(db_path)

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/pilot-automation-reports",
            json=_pilot_report_payload(),
        )
        assert created.status_code == 201
        created_body = created.json()
        assert created_body["id"] == 1
        assert created_body["site_id"] == "SITE-001"
        assert created_body["report_type"] == "qa_summary"

        created_2 = client.post(
            "/api/v1/pilot-automation-reports",
            json=_pilot_report_payload(site_id="SITE-002", report_type="g1_eval"),
        )
        assert created_2.status_code == 201

        listing = client.get(
            "/api/v1/pilot-automation-reports",
            params={"site_id": "SITE-001", "report_type": "qa_summary"},
        )
        assert listing.status_code == 200
        list_body = listing.json()
        assert len(list_body) == 1
        assert list_body[0]["site_id"] == "SITE-001"

        detailed = client.get("/api/v1/pilot-automation-reports/1")
        assert detailed.status_code == 200
        detail_body = detailed.json()
        assert detail_body["payload"]["n_total"] == 120

        csv_response = client.get("/api/v1/pilot-automation-reports.csv")
        assert csv_response.status_code == 200
        assert "qa_summary" in csv_response.text
        assert csv_response.headers["content-type"].startswith("text/csv")

    output_csv = tmp_path / "pilot_reports_export.csv"
    exported_rows = export_pilot_automation_reports_to_csv(db_path=db_path, output_csv=output_csv)

    assert exported_rows == 2
    with output_csv.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    assert len(rows) == 2
    assert {row["report_type"] for row in rows} == {"qa_summary", "g1_eval"}
