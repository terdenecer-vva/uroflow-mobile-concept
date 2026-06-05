from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from uroflow_mobile.clinical_hub import create_clinical_hub_app


def _paired_payload() -> dict[str, object]:
    return {
        "session": {
            "session_id": "session-nightly-001",
            "sync_id": "sync-nightly-001",
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
            "model_id": "fusion-v0.3",
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
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_build_clinical_hub_nightly_snapshot_outputs_comparison_gate_and_manifest(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "clinical_hub.db"
    app = create_clinical_hub_app(db_path)
    with TestClient(app) as client:
        created = client.post("/api/v1/paired-measurements", json=_paired_payload())
        assert created.status_code == 201

    gate_summary = tmp_path / "gate_summary_source.json"
    gate_summary.write_text(
        json.dumps(
            {
                "overall_passed": True,
                "evaluated_gates": ["G0"],
                "config_version": "test-gates-v1",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "nightly_snapshot"
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_clinical_hub_nightly_snapshot.py",
            "--db-path",
            str(db_path),
            "--output-dir",
            str(output_dir),
            "--gate-summary-json",
            str(gate_summary),
            "--report-date",
            "2026-02-25",
            "--site-id",
            "SITE-001",
            "--quality-status",
            "valid",
            "--package-version",
            "v2.8",
            "--model-id",
            "fusion-v0.3",
            "--dataset-id",
            "nightly-001",
        ],
        check=True,
        cwd=Path.cwd(),
        env=env,
        text=True,
        capture_output=True,
    )

    assert "Clinical Hub nightly snapshot exported" in result.stdout
    method_summary_path = output_dir / "method_comparison_summary.json"
    copied_gate_summary_path = output_dir / "gate_summary.json"
    manifest_path = output_dir / "clinical_hub_nightly_snapshot_manifest.json"
    assert method_summary_path.exists()
    assert copied_gate_summary_path.exists()
    assert manifest_path.exists()

    method_summary = json.loads(method_summary_path.read_text(encoding="utf-8"))
    assert method_summary["records_considered"] == 1
    assert method_summary["filters"]["site_id"] == "SITE-001"
    assert any(metric["metric"] == "qmax_ml_s" for metric in method_summary["metrics"])

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "clinical_hub_nightly_snapshot_v1"
    assert manifest["report_date"] == "2026-02-25"
    assert manifest["site_id"] == "SITE-001"
    assert manifest["dataset_id"] == "nightly-001"
    reports_by_type = {report["report_type"]: report for report in manifest["reports"]}
    assert set(reports_by_type) == {"method_comparison_summary", "gate_summary"}
    assert reports_by_type["method_comparison_summary"]["sha256"] == _sha256(
        method_summary_path
    )
    assert reports_by_type["gate_summary"]["sha256"] == _sha256(copied_gate_summary_path)
    assert "--method-comparison-summary-json" in manifest["post_command"]
    assert "--gate-summary-json" in manifest["post_command"]


def test_post_pilot_reports_collector_accepts_method_comparison_summary(tmp_path: Path) -> None:
    script_path = Path("scripts/post_pilot_reports_to_clinical_hub.py")
    spec = importlib.util.spec_from_file_location("post_pilot_reports", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    method_summary = tmp_path / "method_comparison_summary.json"
    gate_summary = tmp_path / "gate_summary.json"
    method_summary.write_text('{"records_considered": 1}', encoding="utf-8")
    gate_summary.write_text('{"overall_passed": true}', encoding="utf-8")

    reports = module._collect_reports(  # type: ignore[attr-defined]
        SimpleNamespace(
            qa_summary_json=None,
            g1_eval_json=None,
            tfl_summary_json=None,
            drift_summary_json=None,
            gate_summary_json=str(gate_summary),
            method_comparison_summary_json=str(method_summary),
        )
    )

    assert [(report.report_type, report.path.name) for report in reports] == [
        ("gate_summary", "gate_summary.json"),
        ("method_comparison_summary", "method_comparison_summary.json"),
    ]
