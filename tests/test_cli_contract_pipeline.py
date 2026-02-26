from __future__ import annotations

import json
from pathlib import Path

from uroflow_mobile.cli import main as cli_main


def _capture_payload() -> dict[str, object]:
    return {
        "schema_version": "ios_capture_v1",
        "session": {
            "session_id": "it-pipeline-001",
            "sync_id": "sync-it-pipeline-001",
            "started_at": "2026-02-23T21:00:00Z",
            "mode": "water_impact",
            "calibration": {
                "ml_per_mm": 8.0,
            },
        },
        "samples": [
            {
                "t_s": 0.0,
                "depth_level_mm": 0.0,
                "rgb_level_mm": 0.0,
                "depth_confidence": 0.95,
                "roi_valid": True,
            },
            {
                "t_s": 0.5,
                "depth_level_mm": 1.8,
                "rgb_level_mm": 1.7,
                "depth_confidence": 0.9,
                "roi_valid": True,
            },
            {
                "t_s": 1.0,
                "depth_level_mm": None,
                "rgb_level_mm": 3.6,
                "depth_confidence": 0.2,
                "roi_valid": True,
            },
            {
                "t_s": 1.5,
                "depth_level_mm": 5.9,
                "rgb_level_mm": 5.7,
                "depth_confidence": 0.88,
                "roi_valid": True,
            },
        ],
    }


def test_capture_contract_to_fusion_summary_pipeline(tmp_path: Path) -> None:
    capture_path = tmp_path / "capture_contract.json"
    level_path = tmp_path / "level_payload.json"
    fusion_csv_path = tmp_path / "fusion_curve.csv"
    fusion_summary_path = tmp_path / "fusion_summary.json"

    capture_path.write_text(
        json.dumps(_capture_payload(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    validate_exit_code = cli_main(
        [
            "validate-capture-contract",
            str(capture_path),
            "--output-level-json",
            str(level_path),
        ]
    )
    assert validate_exit_code == 0
    assert level_path.exists()

    analyze_exit_code = cli_main(
        [
            "analyze-level-series",
            str(level_path),
            "--ml-per-mm",
            "8.0",
            "--output-csv",
            str(fusion_csv_path),
            "--output-json",
            str(fusion_summary_path),
        ]
    )

    assert analyze_exit_code == 0
    assert fusion_csv_path.exists()
    assert fusion_summary_path.exists()

    level_payload = json.loads(level_path.read_text(encoding="utf-8"))
    assert level_payload["meta"]["sync_id"] == "sync-it-pipeline-001"

    summary_payload = json.loads(fusion_summary_path.read_text(encoding="utf-8"))
    assert summary_payload["quality"]["status"] in {"valid", "repeat", "reject"}
    assert summary_payload["series_stats"]["mean_level_uncertainty_mm"] > 0
    assert summary_payload["series_stats"]["mean_volume_uncertainty_ml"] > 0
    assert summary_payload["series_stats"]["mean_flow_uncertainty_ml_s"] > 0
