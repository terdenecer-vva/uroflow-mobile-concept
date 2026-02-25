from __future__ import annotations

import json
from pathlib import Path

from uroflow_mobile.cli import main as cli_main


def _payload() -> dict[str, object]:
    return {
        "schema_version": "ios_capture_v1",
        "session": {
            "session_id": "cli-session-001",
            "sync_id": "sync-cli-session-001",
            "started_at": "2026-02-24T11:00:00Z",
            "mode": "water_impact",
            "calibration": {
                "ml_per_mm": 8.0,
                "min_depth_confidence": 0.6,
            },
        },
        "samples": [
            {
                "t_s": 0.0,
                "depth_level_mm": 0.0,
                "rgb_level_mm": 0.0,
                "depth_confidence": 0.95,
                "audio_rms_dbfs": -40.0,
                "motion_norm": 0.02,
                "roi_valid": True,
            },
            {
                "t_s": 1.0,
                "depth_level_mm": 4.0,
                "rgb_level_mm": 4.1,
                "depth_confidence": 0.93,
                "audio_rms_dbfs": -33.0,
                "motion_norm": 0.02,
                "roi_valid": True,
            },
            {
                "t_s": 2.0,
                "depth_level_mm": None,
                "rgb_level_mm": 8.2,
                "depth_confidence": 0.2,
                "audio_rms_dbfs": -30.0,
                "motion_norm": 0.03,
                "roi_valid": True,
            },
            {
                "t_s": 3.0,
                "depth_level_mm": 12.0,
                "rgb_level_mm": 12.0,
                "depth_confidence": 0.9,
                "audio_rms_dbfs": -29.0,
                "motion_norm": 0.02,
                "roi_valid": True,
            },
            {
                "t_s": 4.0,
                "depth_level_mm": 16.0,
                "rgb_level_mm": 16.1,
                "depth_confidence": 0.91,
                "audio_rms_dbfs": -29.0,
                "motion_norm": 0.02,
                "roi_valid": True,
            },
            {
                "t_s": 5.0,
                "depth_level_mm": 20.0,
                "rgb_level_mm": 20.0,
                "depth_confidence": 0.92,
                "audio_rms_dbfs": -29.0,
                "motion_norm": 0.02,
                "roi_valid": True,
            },
        ],
    }


def test_cli_analyze_capture_session_writes_outputs(tmp_path: Path) -> None:
    capture_path = tmp_path / "capture.json"
    output_csv = tmp_path / "session_curve.csv"
    output_json = tmp_path / "session_summary.json"

    capture_path.write_text(
        json.dumps(_payload(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    exit_code = cli_main(
        [
            "analyze-capture-session",
            str(capture_path),
            "--output-csv",
            str(output_csv),
            "--output-json",
            str(output_json),
            "--ml-per-mm",
            "10",
        ]
    )

    assert exit_code == 0
    assert output_csv.exists()
    assert output_json.exists()

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["session"]["session_id"] == "cli-session-001"
    assert payload["session"]["sync_id"] == "sync-cli-session-001"
    assert payload["session"]["ml_per_mm"] == 10.0
    assert payload["event_detection"]["detected"] in {True, False}
    assert payload["signal_quality"]["status"] in {"valid", "repeat", "reject"}
    assert payload["signal_quality"]["score"] >= 0.0
    assert payload["summary"]["voided_volume_ml"] > 0.0
