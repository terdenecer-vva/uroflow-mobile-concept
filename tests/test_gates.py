from __future__ import annotations

from uroflow_mobile.gates import evaluate_release_gates, gate_summary_to_dict


def _metrics_for_g0() -> dict[str, object]:
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


def test_evaluate_release_gates_passes_g0() -> None:
    summary = evaluate_release_gates(metrics=_metrics_for_g0(), gates=["G0"])

    assert summary.passed is True
    assert summary.evaluated_gates == ["G0"]
    assert len(summary.gate_results) == 1
    assert summary.gate_results[0].passed is True


def test_evaluate_release_gates_fails_with_missing_metric() -> None:
    metrics = _metrics_for_g0()
    summary = evaluate_release_gates(metrics=metrics, gates=["G1"])

    assert summary.passed is False
    failed_rules = [
        rule
        for gate in summary.gate_results
        for rule in gate.rule_results
        if not rule.passed
    ]
    assert any("is missing" in rule.reason for rule in failed_rules)


def test_evaluate_release_gates_any_of_accepts_second_condition() -> None:
    metrics = _metrics_for_g0()
    metrics["vvoid_mape_pct"] = 30.0
    metrics["vvoid_mae_ml"] = 25.0

    summary = evaluate_release_gates(metrics=metrics, gates=["G0"])

    assert summary.passed is True


def test_gate_summary_to_dict_contains_expected_fields() -> None:
    summary = evaluate_release_gates(metrics=_metrics_for_g0(), gates=["G0"])
    payload = gate_summary_to_dict(summary)

    assert payload["config_version"] == "1.0"
    assert payload["overall_passed"] is True
    assert payload["gate_results"][0]["gate"] == "G0"
