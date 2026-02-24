from __future__ import annotations

import json
from pathlib import Path

from uroflow_mobile.cli import main as cli_main


def _g0_metrics() -> dict[str, object]:
    return {
        "valid_rate_clinic": 0.82,
        "qmax_mae_ml_s": 2.8,
        "qmax_bias_abs_ml_s": 1.2,
        "vvoid_mape_pct": 14.0,
        "qavg_mae_ml_s": 2.0,
        "dt_start_median_abs_s": 0.2,
        "dt_end_median_abs_s": 0.4,
        "privacy_full_frame_storage_rate": 0.0,
    }


def test_cli_evaluate_gates_passes_for_g0(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics.json"
    output_json = tmp_path / "gate_summary.json"
    metrics_path.write_text(
        json.dumps(_g0_metrics(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    exit_code = cli_main(
        [
            "evaluate-gates",
            str(metrics_path),
            "--gates",
            "G0",
            "--output-json",
            str(output_json),
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["overall_passed"] is True
    assert payload["evaluated_gates"] == ["G0"]


def test_cli_evaluate_gates_fails_when_rule_not_met(tmp_path: Path) -> None:
    metrics = _g0_metrics()
    metrics["qmax_mae_ml_s"] = 4.5

    metrics_path = tmp_path / "metrics_fail.json"
    output_json = tmp_path / "gate_summary_fail.json"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    exit_code = cli_main(
        [
            "evaluate-gates",
            str(metrics_path),
            "--gates",
            "G0",
            "--output-json",
            str(output_json),
        ]
    )

    assert exit_code == 1
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["overall_passed"] is False


def test_cli_evaluate_gates_with_custom_config(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics_custom.json"
    config_path = tmp_path / "gates_config_custom.json"
    output_json = tmp_path / "gate_summary_custom.json"

    metrics_path.write_text(
        json.dumps({"metrics": {"foo": 3.0}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    config_path.write_text(
        json.dumps(
            {
                "config_version": "custom-1",
                "gates": {
                    "CUSTOM": {
                        "description": "Custom gate",
                        "rules": [
                            {
                                "id": "foo_min",
                                "metric": "foo",
                                "op": ">=",
                                "value": 2.0,
                            }
                        ],
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    exit_code = cli_main(
        [
            "evaluate-gates",
            str(metrics_path),
            "--config-json",
            str(config_path),
            "--gates",
            "CUSTOM",
            "--output-json",
            str(output_json),
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["config_version"] == "custom-1"
    assert payload["overall_passed"] is True
    assert payload["evaluated_gates"] == ["CUSTOM"]
