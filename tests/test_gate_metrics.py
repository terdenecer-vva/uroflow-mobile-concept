from __future__ import annotations

from pathlib import Path

import pytest

from uroflow_mobile.gate_metrics import (
    build_gate_metrics,
    load_mapping_profile,
    select_mapping_profile,
)


def _clinical_rows() -> list[dict[str, object]]:
    return [
        {
            "cohort": "clinic",
            "quality_status": "valid",
            "sex": "m",
            "ref_qmax_ml_s": "20",
            "app_qmax_ml_s": "21",
            "ref_qavg_ml_s": "12",
            "app_qavg_ml_s": "11",
            "ref_vvoid_ml": "300",
            "app_vvoid_ml": "315",
            "ref_t_start_s": "0.0",
            "app_t_start_s": "0.1",
            "ref_t_end_s": "20.0",
            "app_t_end_s": "20.2",
            "full_frame_stored": "0",
            "flush_truth": "1",
            "flush_pred": "1",
        },
        {
            "cohort": "clinic",
            "quality_status": "valid",
            "sex": "f",
            "ref_qmax_ml_s": "18",
            "app_qmax_ml_s": "17",
            "ref_qavg_ml_s": "10",
            "app_qavg_ml_s": "11",
            "ref_vvoid_ml": "280",
            "app_vvoid_ml": "270",
            "ref_t_start_s": "0.0",
            "app_t_start_s": "0.2",
            "ref_t_end_s": "18.0",
            "app_t_end_s": "17.8",
            "full_frame_stored": "0",
            "flush_truth": "0",
            "flush_pred": "0",
        },
        {
            "cohort": "clinic",
            "quality_status": "repeat",
            "sex": "m",
            "ref_qmax_ml_s": "25",
            "app_qmax_ml_s": "22",
            "ref_qavg_ml_s": "14",
            "app_qavg_ml_s": "12",
            "ref_vvoid_ml": "350",
            "app_vvoid_ml": "320",
            "ref_t_start_s": "0.0",
            "app_t_start_s": "0.4",
            "ref_t_end_s": "22.0",
            "app_t_end_s": "22.6",
            "full_frame_stored": "0",
            "flush_truth": "1",
            "flush_pred": "0",
        },
        {
            "cohort": "clinic",
            "quality_status": "valid",
            "sex": "f",
            "ref_qmax_ml_s": "22",
            "app_qmax_ml_s": "21",
            "ref_qavg_ml_s": "13",
            "app_qavg_ml_s": "12",
            "ref_vvoid_ml": "330",
            "app_vvoid_ml": "315",
            "ref_t_start_s": "0.0",
            "app_t_start_s": "0.1",
            "ref_t_end_s": "21.0",
            "app_t_end_s": "21.1",
            "full_frame_stored": "0",
            "flush_truth": "0",
            "flush_pred": "0",
        },
        {
            "cohort": "home",
            "quality_status": "valid",
            "sex": "f",
            "ref_qmax_ml_s": "19",
            "app_qmax_ml_s": "20",
            "ref_qavg_ml_s": "11",
            "app_qavg_ml_s": "10",
            "ref_vvoid_ml": "290",
            "app_vvoid_ml": "300",
            "ref_t_start_s": "0.0",
            "app_t_start_s": "0.2",
            "ref_t_end_s": "19.0",
            "app_t_end_s": "19.4",
            "full_frame_stored": "0",
            "flush_truth": "0",
            "flush_pred": "0",
        },
    ]


def _bench_rows() -> list[dict[str, object]]:
    return [
        {
            "scenario": "quiet_lab",
            "ref_qmax_ml_s": "10",
            "app_qmax_ml_s": "11",
            "not_in_water_truth": "1",
            "not_in_water_pred": "1",
        },
        {
            "scenario": "quiet_lab",
            "ref_qmax_ml_s": "12",
            "app_qmax_ml_s": "13",
            "not_in_water_truth": "0",
            "not_in_water_pred": "0",
        },
        {
            "scenario": "noise_fan",
            "ref_qmax_ml_s": "10",
            "app_qmax_ml_s": "12",
            "not_in_water_truth": "1",
            "not_in_water_pred": "1",
        },
        {
            "scenario": "noise_flush",
            "ref_qmax_ml_s": "14",
            "app_qmax_ml_s": "16",
            "not_in_water_truth": "1",
            "not_in_water_pred": "1",
        },
        {
            "scenario": "multi_toilet_a",
            "ref_qmax_ml_s": "15",
            "app_qmax_ml_s": "16",
            "not_in_water_truth": "0",
            "not_in_water_pred": "0",
        },
        {
            "scenario": "multi_toilet_b",
            "ref_qmax_ml_s": "20",
            "app_qmax_ml_s": "21",
            "not_in_water_truth": "1",
            "not_in_water_pred": "1",
        },
        {
            "scenario": "stress_case",
            "is_valid_truth": "0",
            "is_valid_pred": "1",
        },
        {
            "scenario": "stress_case",
            "is_valid_truth": "0",
            "is_valid_pred": "0",
        },
    ]


def test_build_gate_metrics_from_rows() -> None:
    metrics = build_gate_metrics(
        clinical_rows=_clinical_rows(),
        bench_rows=_bench_rows(),
    )

    assert metrics["qmax_mae_ml_s"] == pytest.approx(1.4, abs=1e-6)
    assert metrics["qmax_bias_abs_ml_s"] == pytest.approx(0.6, abs=1e-6)
    assert metrics["qavg_mae_ml_s"] == pytest.approx(1.2, abs=1e-6)
    assert metrics["vvoid_mae_ml"] == pytest.approx(16.0, abs=1e-6)
    assert metrics["vvoid_mape_pct"] == pytest.approx(5.027, abs=1e-3)
    assert metrics["dt_start_median_abs_s"] == pytest.approx(0.2, abs=1e-6)
    assert metrics["dt_end_median_abs_s"] == pytest.approx(0.2, abs=1e-6)
    assert metrics["valid_rate_clinic"] == pytest.approx(0.75, abs=1e-6)
    assert metrics["valid_rate_home"] == pytest.approx(1.0, abs=1e-6)
    assert metrics["privacy_full_frame_storage_rate"] == pytest.approx(0.0, abs=1e-6)
    assert metrics["flush_recall"] == pytest.approx(0.5, abs=1e-6)
    assert metrics["subgroup_max_mae_ratio"] == pytest.approx(2.0, abs=1e-6)

    assert metrics["bench_qmax_mae_quiet_ml_s"] == pytest.approx(1.0, abs=1e-6)
    assert metrics["bench_qmax_mae_noise_ml_s"] == pytest.approx(2.0, abs=1e-6)
    assert metrics["bench_qmax_mae_multi_toilet_ml_s"] == pytest.approx(1.0, abs=1e-6)
    assert metrics["not_in_water_sensitivity"] == pytest.approx(1.0, abs=1e-6)
    assert metrics["stress_false_valid_rate"] == pytest.approx(0.5, abs=1e-6)


def test_build_gate_metrics_applies_overrides() -> None:
    metrics = build_gate_metrics(
        clinical_rows=[{"metric": "qmax_mae_ml_s", "value": "4.1"}],
        overrides={"qmax_mae_ml_s": 2.2, "verification_suite_pass": True},
    )

    assert metrics["qmax_mae_ml_s"] == 2.2
    assert metrics["verification_suite_pass"] is True


def test_build_gate_metrics_applies_profile_value_mapping() -> None:
    rows = [
        {
            "cohort": "clinic",
            "quality_status": "1",
            "ref_qmax_ml_s": "20",
            "app_qmax_ml_s": "21",
        },
        {
            "cohort": "clinic",
            "quality_status": "2",
            "ref_qmax_ml_s": "20",
            "app_qmax_ml_s": "22",
        },
        {
            "cohort": "clinic",
            "quality_status": "3",
            "ref_qmax_ml_s": "20",
            "app_qmax_ml_s": "19",
        },
    ]

    metrics_without_profile = build_gate_metrics(clinical_rows=rows)
    assert metrics_without_profile["valid_rate_clinic"] == pytest.approx(1.0, abs=1e-6)

    profile = {
        "clinical": {
            "value_map": {
                "quality_status": {
                    "1": "valid",
                    "2": "repeat",
                    "3": "reject",
                }
            }
        }
    }
    metrics_with_profile = build_gate_metrics(clinical_rows=rows, mapping_profile=profile)
    assert metrics_with_profile["valid_rate_clinic"] == pytest.approx(1.0 / 3.0, abs=1e-6)


def test_build_gate_metrics_backfills_from_pilot_automation_json() -> None:
    tfl_summary = {
        "n_total": 20,
        "n_valid": 18,
        "metrics": {
            "Qmax": {
                "mae": 1.5,
                "bias": -0.4,
                "loa_low": -2.2,
                "loa_high": 1.4,
            },
            "Qavg": {"mae": 0.7},
            "Vvoid": {
                "mae": 12.0,
                "mape": 8.0,
                "loa_low": -25.0,
                "loa_high": 22.0,
            },
            "FlowTime": {"mae": 1.2},
        },
    }
    drift_summary = {"overall": {"Qmax_mae": 1.8, "Vvoid_mape": 9.5}}
    g1_eval = {
        "valid_rate": {"value": 0.91},
        "mae_qmax": {"value": 1.4},
        "mape_vvoid": {"value": 7.9},
    }
    qa_summary = {
        "n_records_checked": 20,
        "n_pass": 16,
        "n_fail": 2,
    }

    metrics = build_gate_metrics(
        tfl_summary=tfl_summary,
        drift_summary=drift_summary,
        g1_eval=g1_eval,
        qa_summary=qa_summary,
    )

    assert metrics["valid_rate_clinic"] == pytest.approx(0.9, abs=1e-6)
    assert metrics["qmax_mae_ml_s"] == pytest.approx(1.5, abs=1e-6)
    assert metrics["qmax_bias_abs_ml_s"] == pytest.approx(0.4, abs=1e-6)
    assert metrics["qmax_loa95_abs_ml_s"] == pytest.approx(2.2, abs=1e-6)
    assert metrics["vvoid_mae_ml"] == pytest.approx(12.0, abs=1e-6)
    assert metrics["vvoid_mape_pct"] == pytest.approx(8.0, abs=1e-6)
    assert metrics["vvoid_loa95_abs_ml"] == pytest.approx(25.0, abs=1e-6)
    assert metrics["flow_time_mae_s"] == pytest.approx(1.2, abs=1e-6)
    assert metrics["qa_fail_rate"] == pytest.approx(0.1, abs=1e-6)


def test_build_gate_metrics_backfill_does_not_override_csv_metrics() -> None:
    metrics = build_gate_metrics(
        clinical_rows=[{"metric": "qmax_mae_ml_s", "value": "2.0"}],
        g1_eval={"mae_qmax": {"value": 1.0}},
    )

    assert metrics["qmax_mae_ml_s"] == pytest.approx(2.0, abs=1e-6)


def test_load_and_select_mapping_profile(tmp_path: Path) -> None:
    profile_path = tmp_path / "profiles.yaml"
    profile_path.write_text(
        (
            "version: 1\n"
            "profiles:\n"
            "  redcap_v1:\n"
            "    clinical:\n"
            "      value_map:\n"
            "        quality_status:\n"
            "          \"1\": valid\n"
            "  openclinica_v1:\n"
            "    clinical:\n"
            "      value_map:\n"
            "        quality_status:\n"
            "          \"1\": valid\n"
        ),
        encoding="utf-8",
    )

    document = load_mapping_profile(profile_path)
    name, profile = select_mapping_profile(document, profile_name="openclinica_v1")

    assert name == "openclinica_v1"
    assert profile["clinical"]["value_map"]["quality_status"]["1"] == "valid"
