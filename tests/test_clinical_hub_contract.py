from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from uroflow_mobile.clinical_hub import create_clinical_hub_app


def test_clinical_hub_openapi_contract_contains_core_paths(tmp_path: Path) -> None:
    db_path = tmp_path / "clinical_hub_contract_openapi.db"
    app = create_clinical_hub_app(
        db_path,
        api_key_policy_map={"op-site-1-key": {"role": "operator", "site_id": "SITE-001"}},
    )

    with TestClient(app) as client:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        payload = response.json()

    assert payload.get("openapi")
    paths = payload.get("paths", {})
    assert "/api/v1/paired-measurements" in paths
    assert "/api/v1/capture-packages" in paths
    assert "/api/v1/pilot-automation-reports" in paths
    assert "/api/v1/comparison-summary" in paths
    assert "/api/v1/audit-events" in paths


def test_clinical_hub_openapi_contract_contains_core_schemas(tmp_path: Path) -> None:
    db_path = tmp_path / "clinical_hub_contract_schema.db"
    app = create_clinical_hub_app(db_path)

    with TestClient(app) as client:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        payload = response.json()

    schemas = (
        payload.get("components", {})
        .get("schemas", {})
    )
    assert "PairedMeasurementCreate" in schemas
    assert "CapturePackageCreate" in schemas
    assert "PilotAutomationReportCreate" in schemas

    paired_required = schemas["PairedMeasurementCreate"].get("required", [])
    assert "session" in paired_required
    assert "app" in paired_required
    assert "reference" in paired_required
