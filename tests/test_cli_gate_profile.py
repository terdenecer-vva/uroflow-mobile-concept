from __future__ import annotations

import csv
import json
from pathlib import Path

from uroflow_mobile.cli import main as cli_main
from uroflow_mobile.gate_metrics import load_mapping_profile


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_cli_generate_profile_template_then_build_metrics(tmp_path: Path) -> None:
    clinical_path = tmp_path / "clinic_export.csv"
    profile_path = tmp_path / "profile.yaml"
    metrics_path = tmp_path / "metrics.json"

    _write_csv(
        clinical_path,
        [
            {
                "QMAX_APP": 20,
                "QMAX_REF": 19,
                "QUALITY_STATUS_CODE": 1,
            },
            {
                "QMAX_APP": 18,
                "QMAX_REF": 20,
                "QUALITY_STATUS_CODE": 2,
            },
        ],
    )

    generate_exit_code = cli_main(
        [
            "generate-gate-profile-template",
            "--clinical-csv",
            str(clinical_path),
            "--profile-name",
            "clinic_export_v1",
            "--output-yaml",
            str(profile_path),
        ]
    )
    assert generate_exit_code == 0

    profile_doc = load_mapping_profile(profile_path)
    profile = profile_doc["profiles"]["clinic_export_v1"]
    assert profile["clinical"]["column_map"]["QMAX_APP"] == "app_qmax_ml_s"
    assert profile["clinical"]["column_map"]["QMAX_REF"] == "ref_qmax_ml_s"

    build_exit_code = cli_main(
        [
            "build-gate-metrics",
            "--clinical-csv",
            str(clinical_path),
            "--profile-yaml",
            str(profile_path),
            "--profile-name",
            "clinic_export_v1",
            "--output-json",
            str(metrics_path),
        ]
    )
    assert build_exit_code == 0

    metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics_payload["metrics"]["qmax_mae_ml_s"] == 1.5
    assert metrics_payload["metrics"]["valid_rate_clinic"] == 0.5
