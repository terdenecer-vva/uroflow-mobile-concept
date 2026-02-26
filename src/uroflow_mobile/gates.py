from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_GATES_CONFIG: dict[str, Any] = {
    "config_version": "1.0",
    "gates": {
        "G0": {
            "description": "Pilot readiness gate",
            "rules": [
                {
                    "id": "valid_rate_clinic",
                    "metric": "valid_rate_clinic",
                    "op": ">=",
                    "value": 0.80,
                },
                {
                    "id": "qmax_mae",
                    "metric": "qmax_mae_ml_s",
                    "op": "<=",
                    "value": 3.0,
                },
                {
                    "id": "qmax_bias_abs",
                    "metric": "qmax_bias_abs_ml_s",
                    "op": "<=",
                    "value": 2.0,
                },
                {
                    "id": "vvoid_error",
                    "any_of": [
                        {
                            "metric": "vvoid_mape_pct",
                            "op": "<=",
                            "value": 15.0,
                        },
                        {
                            "metric": "vvoid_mae_ml",
                            "op": "<=",
                            "value": 30.0,
                        },
                    ],
                },
                {
                    "id": "qavg_mae",
                    "metric": "qavg_mae_ml_s",
                    "op": "<=",
                    "value": 2.5,
                },
                {
                    "id": "timing_start",
                    "metric": "dt_start_median_abs_s",
                    "op": "<=",
                    "value": 0.3,
                },
                {
                    "id": "timing_end",
                    "metric": "dt_end_median_abs_s",
                    "op": "<=",
                    "value": 0.5,
                },
                {
                    "id": "privacy_full_frame_storage",
                    "metric": "privacy_full_frame_storage_rate",
                    "op": "==",
                    "value": 0.0,
                },
            ],
        },
        "G1": {
            "description": "Pivotal readiness gate",
            "rules": [
                {
                    "id": "valid_rate_clinic",
                    "metric": "valid_rate_clinic",
                    "op": ">=",
                    "value": 0.85,
                },
                {
                    "id": "valid_rate_home",
                    "metric": "valid_rate_home",
                    "op": ">=",
                    "value": 0.70,
                },
                {
                    "id": "qmax_loa95",
                    "metric": "qmax_loa95_abs_ml_s",
                    "op": "<=",
                    "value": 5.0,
                },
                {
                    "id": "vvoid_loa95",
                    "metric": "vvoid_loa95_abs_ml",
                    "op": "<=",
                    "value": 40.0,
                },
                {
                    "id": "qmax_mae",
                    "metric": "qmax_mae_ml_s",
                    "op": "<=",
                    "value": 2.5,
                },
                {
                    "id": "vvoid_error",
                    "any_of": [
                        {
                            "metric": "vvoid_mape_pct",
                            "op": "<=",
                            "value": 10.0,
                        },
                        {
                            "metric": "vvoid_mae_ml",
                            "op": "<=",
                            "value": 20.0,
                        },
                    ],
                },
                {
                    "id": "subgroup_robustness",
                    "metric": "subgroup_max_mae_ratio",
                    "op": "<=",
                    "value": 1.5,
                },
                {
                    "id": "flush_detector_recall",
                    "metric": "flush_recall",
                    "op": ">=",
                    "value": 0.95,
                },
            ],
        },
        "G2": {
            "description": "Release gate",
            "rules": [
                {
                    "id": "verification_suite_pass",
                    "metric": "verification_suite_pass",
                    "op": "==",
                    "value": True,
                },
                {
                    "id": "regression_suite_pass",
                    "metric": "regression_suite_pass",
                    "op": "==",
                    "value": True,
                },
                {
                    "id": "residual_risk_acceptable",
                    "metric": "residual_risk_acceptable",
                    "op": "==",
                    "value": True,
                },
                {
                    "id": "release_cr_approved",
                    "metric": "release_cr_approved",
                    "op": "==",
                    "value": True,
                },
                {
                    "id": "pms_process_active",
                    "metric": "pms_process_active",
                    "op": "==",
                    "value": True,
                },
            ],
        },
        "BENCH_G0": {
            "description": "Bench gate G0",
            "rules": [
                {
                    "id": "qmax_mae_quiet",
                    "metric": "bench_qmax_mae_quiet_ml_s",
                    "op": "<=",
                    "value": 2.0,
                },
                {
                    "id": "qmax_mae_noise",
                    "metric": "bench_qmax_mae_noise_ml_s",
                    "op": "<=",
                    "value": 2.5,
                },
                {
                    "id": "not_in_water_sensitivity",
                    "metric": "not_in_water_sensitivity",
                    "op": ">=",
                    "value": 0.90,
                },
            ],
        },
        "BENCH_G1": {
            "description": "Bench gate G1",
            "rules": [
                {
                    "id": "qmax_mae_multi_toilet",
                    "metric": "bench_qmax_mae_multi_toilet_ml_s",
                    "op": "<=",
                    "value": 2.5,
                }
            ],
        },
        "BENCH_G2": {
            "description": "Bench gate G2",
            "rules": [
                {
                    "id": "stress_false_valid_rate",
                    "metric": "stress_false_valid_rate",
                    "op": "<=",
                    "value": 0.02,
                }
            ],
        },
    },
}


@dataclass(frozen=True)
class RuleEvaluation:
    """Evaluation result of one rule."""

    rule_id: str
    passed: bool
    reason: str
    actual: object | None
    expected: object | None


@dataclass(frozen=True)
class GateEvaluation:
    """Evaluation result of one gate."""

    gate: str
    passed: bool
    description: str
    rule_results: list[RuleEvaluation]


@dataclass(frozen=True)
class GateEvaluationSummary:
    """Gate evaluation summary for one or more gates."""

    config_version: str
    evaluated_gates: list[str]
    passed: bool
    gate_results: list[GateEvaluation]


def _compare(actual: object, op: str, expected: object) -> bool:
    if op in {"<", "<=", ">", ">="}:
        actual_num = float(actual)
        expected_num = float(expected)
        if op == "<":
            return actual_num < expected_num
        if op == "<=":
            return actual_num <= expected_num
        if op == ">":
            return actual_num > expected_num
        return actual_num >= expected_num

    if op == "==":
        return actual == expected
    if op == "!=":
        return actual != expected

    raise ValueError(f"unsupported operation: {op}")


def _evaluate_condition(
    condition: dict[str, object],
    metrics: dict[str, object],
) -> RuleEvaluation:
    metric = str(condition["metric"])
    op = str(condition["op"])
    expected = condition.get("value")

    if metric not in metrics:
        return RuleEvaluation(
            rule_id=metric,
            passed=False,
            reason=f"metric '{metric}' is missing",
            actual=None,
            expected=expected,
        )

    actual = metrics[metric]
    try:
        passed = _compare(actual=actual, op=op, expected=expected)
    except (ValueError, TypeError):
        return RuleEvaluation(
            rule_id=metric,
            passed=False,
            reason=f"comparison failed for metric '{metric}'",
            actual=actual,
            expected=expected,
        )

    return RuleEvaluation(
        rule_id=metric,
        passed=passed,
        reason=f"{metric}: {actual} {op} {expected}",
        actual=actual,
        expected=expected,
    )


def _evaluate_rule(
    rule: dict[str, object],
    metrics: dict[str, object],
) -> RuleEvaluation:
    rule_id = str(rule.get("id", "rule"))

    if "any_of" in rule:
        raw_conditions = rule["any_of"]
        if not isinstance(raw_conditions, list):
            raise ValueError(f"rule '{rule_id}' any_of must be a list")

        condition_results: list[RuleEvaluation] = []
        for item in raw_conditions:
            if not isinstance(item, dict):
                raise ValueError(f"rule '{rule_id}' any_of entries must be objects")
            condition_results.append(_evaluate_condition(item, metrics=metrics))

        passed = any(result.passed for result in condition_results)
        reason = "; ".join(result.reason for result in condition_results)
        return RuleEvaluation(
            rule_id=rule_id,
            passed=passed,
            reason=reason,
            actual=None,
            expected="any_of",
        )

    if "all_of" in rule:
        raw_conditions = rule["all_of"]
        if not isinstance(raw_conditions, list):
            raise ValueError(f"rule '{rule_id}' all_of must be a list")

        condition_results = []
        for item in raw_conditions:
            if not isinstance(item, dict):
                raise ValueError(f"rule '{rule_id}' all_of entries must be objects")
            condition_results.append(_evaluate_condition(item, metrics=metrics))

        passed = all(result.passed for result in condition_results)
        reason = "; ".join(result.reason for result in condition_results)
        return RuleEvaluation(
            rule_id=rule_id,
            passed=passed,
            reason=reason,
            actual=None,
            expected="all_of",
        )

    return _evaluate_condition(rule, metrics=metrics)


def evaluate_release_gates(
    metrics: dict[str, object],
    config: dict[str, object] | None = None,
    gates: list[str] | None = None,
) -> GateEvaluationSummary:
    """Evaluate one or more release gates against metric values."""

    cfg = config or DEFAULT_GATES_CONFIG
    config_version = str(cfg.get("config_version", "unknown"))

    gate_map = cfg.get("gates")
    if not isinstance(gate_map, dict):
        raise ValueError("config must contain object field 'gates'")

    selected_gates = gates or list(gate_map.keys())
    gate_results: list[GateEvaluation] = []

    for gate_name in selected_gates:
        gate_obj = gate_map.get(gate_name)
        if not isinstance(gate_obj, dict):
            raise ValueError(f"gate '{gate_name}' is not present in config")

        description = str(gate_obj.get("description", ""))
        rules = gate_obj.get("rules")
        if not isinstance(rules, list):
            raise ValueError(f"gate '{gate_name}' must contain list field 'rules'")

        rule_results: list[RuleEvaluation] = []
        for rule in rules:
            if not isinstance(rule, dict):
                raise ValueError(f"gate '{gate_name}' has invalid rule entry")
            rule_results.append(_evaluate_rule(rule=rule, metrics=metrics))

        gate_passed = all(result.passed for result in rule_results)
        gate_results.append(
            GateEvaluation(
                gate=gate_name,
                passed=gate_passed,
                description=description,
                rule_results=rule_results,
            )
        )

    summary_passed = all(result.passed for result in gate_results)

    return GateEvaluationSummary(
        config_version=config_version,
        evaluated_gates=selected_gates,
        passed=summary_passed,
        gate_results=gate_results,
    )


def gate_summary_to_dict(summary: GateEvaluationSummary) -> dict[str, object]:
    """Convert gate summary to JSON-serializable payload."""

    return {
        "config_version": summary.config_version,
        "evaluated_gates": summary.evaluated_gates,
        "overall_passed": summary.passed,
        "gate_results": [
            {
                "gate": gate_result.gate,
                "description": gate_result.description,
                "passed": gate_result.passed,
                "rules": [
                    {
                        "rule_id": rule.rule_id,
                        "passed": rule.passed,
                        "reason": rule.reason,
                        "actual": rule.actual,
                        "expected": rule.expected,
                    }
                    for rule in gate_result.rule_results
                ],
            }
            for gate_result in summary.gate_results
        ],
    }
