from __future__ import annotations

import csv
import json
from pathlib import Path

from uroflow_mobile.cli import main as cli_main


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


def test_cli_build_gate_metrics_and_evaluate_g0_and_bench_g0(tmp_path: Path) -> None:
    clinical_path = tmp_path / "clinical.csv"
    bench_path = tmp_path / "bench.csv"
    metrics_path = tmp_path / "gate_metrics.json"

    clinical_rows = [
        {
            "cohort": "clinic",
            "quality_status": "valid",
            "ref_qmax_ml_s": 20,
            "app_qmax_ml_s": 21,
            "ref_qavg_ml_s": 12,
            "app_qavg_ml_s": 11,
            "ref_vvoid_ml": 300,
            "app_vvoid_ml": 315,
            "ref_t_start_s": 0.0,
            "app_t_start_s": 0.1,
            "ref_t_end_s": 20.0,
            "app_t_end_s": 20.2,
            "full_frame_stored": 0,
        },
        {
            "cohort": "clinic",
            "quality_status": "valid",
            "ref_qmax_ml_s": 18,
            "app_qmax_ml_s": 17,
            "ref_qavg_ml_s": 10,
            "app_qavg_ml_s": 11,
            "ref_vvoid_ml": 280,
            "app_vvoid_ml": 270,
            "ref_t_start_s": 0.0,
            "app_t_start_s": 0.2,
            "ref_t_end_s": 18.0,
            "app_t_end_s": 17.8,
            "full_frame_stored": 0,
        },
        {
            "cohort": "clinic",
            "quality_status": "repeat",
            "ref_qmax_ml_s": 25,
            "app_qmax_ml_s": 23,
            "ref_qavg_ml_s": 14,
            "app_qavg_ml_s": 13,
            "ref_vvoid_ml": 350,
            "app_vvoid_ml": 325,
            "ref_t_start_s": 0.0,
            "app_t_start_s": 0.2,
            "ref_t_end_s": 22.0,
            "app_t_end_s": 22.4,
            "full_frame_stored": 0,
        },
        {
            "cohort": "clinic",
            "quality_status": "valid",
            "ref_qmax_ml_s": 22,
            "app_qmax_ml_s": 21,
            "ref_qavg_ml_s": 13,
            "app_qavg_ml_s": 12,
            "ref_vvoid_ml": 330,
            "app_vvoid_ml": 315,
            "ref_t_start_s": 0.0,
            "app_t_start_s": 0.2,
            "ref_t_end_s": 21.0,
            "app_t_end_s": 21.2,
            "full_frame_stored": 0,
        },
        {
            "cohort": "clinic",
            "quality_status": "valid",
            "ref_qmax_ml_s": 19,
            "app_qmax_ml_s": 20,
            "ref_qavg_ml_s": 11,
            "app_qavg_ml_s": 10,
            "ref_vvoid_ml": 290,
            "app_vvoid_ml": 300,
            "ref_t_start_s": 0.0,
            "app_t_start_s": 0.1,
            "ref_t_end_s": 19.0,
            "app_t_end_s": 19.3,
            "full_frame_stored": 0,
        },
    ]
    bench_rows = [
        {
            "scenario": "quiet_lab",
            "ref_qmax_ml_s": 10,
            "app_qmax_ml_s": 11,
            "not_in_water_truth": 1,
            "not_in_water_pred": 1,
        },
        {
            "scenario": "quiet_lab",
            "ref_qmax_ml_s": 12,
            "app_qmax_ml_s": 13,
            "not_in_water_truth": 1,
            "not_in_water_pred": 1,
        },
        {
            "scenario": "noise_fan",
            "ref_qmax_ml_s": 10,
            "app_qmax_ml_s": 12,
            "not_in_water_truth": 1,
            "not_in_water_pred": 1,
        },
        {
            "scenario": "noise_flush",
            "ref_qmax_ml_s": 14,
            "app_qmax_ml_s": 16,
            "not_in_water_truth": 1,
            "not_in_water_pred": 1,
        },
    ]

    _write_csv(clinical_path, clinical_rows)
    _write_csv(bench_path, bench_rows)

    build_exit_code = cli_main(
        [
            "build-gate-metrics",
            "--clinical-csv",
            str(clinical_path),
            "--bench-csv",
            str(bench_path),
            "--output-json",
            str(metrics_path),
        ]
    )
    assert build_exit_code == 0

    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert "metrics" in payload
    assert payload["metrics"]["valid_rate_clinic"] >= 0.8

    gate_exit_code = cli_main(
        [
            "evaluate-gates",
            str(metrics_path),
            "--config-json",
            "docs/project-package-v1.5/gates-config-v1.json",
            "--gates",
            "G0",
            "BENCH_G0",
        ]
    )
    assert gate_exit_code == 0


def test_cli_build_gate_metrics_with_profile_mapping(tmp_path: Path) -> None:
    clinical_path = tmp_path / "clinical_codes.csv"
    profile_path = tmp_path / "profiles.yaml"
    metrics_path = tmp_path / "metrics.json"

    _write_csv(
        clinical_path,
        [
            {
                "cohort": "clinic",
                "quality_status": 1,
                "ref_qmax_ml_s": 20,
                "app_qmax_ml_s": 21,
            },
            {
                "cohort": "clinic",
                "quality_status": 2,
                "ref_qmax_ml_s": 20,
                "app_qmax_ml_s": 21,
            },
            {
                "cohort": "clinic",
                "quality_status": 3,
                "ref_qmax_ml_s": 20,
                "app_qmax_ml_s": 19,
            },
        ],
    )
    profile_path.write_text(
        (
            "version: 1\n"
            "profiles:\n"
            "  redcap_v1:\n"
            "    clinical:\n"
            "      value_map:\n"
            "        quality_status:\n"
            "          \"1\": valid\n"
            "          \"2\": repeat\n"
            "          \"3\": reject\n"
        ),
        encoding="utf-8",
    )

    build_exit_code = cli_main(
        [
            "build-gate-metrics",
            "--clinical-csv",
            str(clinical_path),
            "--profile-yaml",
            str(profile_path),
            "--profile-name",
            "redcap_v1",
            "--output-json",
            str(metrics_path),
        ]
    )
    assert build_exit_code == 0

    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert payload["sources"]["profile_name"] == "redcap_v1"
    assert payload["metrics"]["valid_rate_clinic"] == 1.0 / 3.0


def test_cli_build_gate_metrics_from_pilot_artifacts(tmp_path: Path) -> None:
    tfl_summary_path = tmp_path / "tfl_summary.json"
    drift_summary_path = tmp_path / "drift_summary.json"
    g1_eval_path = tmp_path / "g1_eval.json"
    qa_summary_path = tmp_path / "qa_summary.json"
    metrics_path = tmp_path / "metrics_from_artifacts.json"

    tfl_summary_path.write_text(
        json.dumps(
            {
                "n_total": 10,
                "n_valid": 9,
                "metrics": {
                    "Qmax": {
                        "mae": 1.6,
                        "bias": 0.3,
                        "loa_low": -1.9,
                        "loa_high": 2.5,
                    },
                    "Qavg": {"mae": 0.8},
                    "Vvoid": {
                        "mae": 10.0,
                        "mape": 7.5,
                        "loa_low": -30.0,
                        "loa_high": 28.0,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    drift_summary_path.write_text(
        json.dumps({"overall": {"Qmax_mae": 1.9, "Vvoid_mape": 8.0}}),
        encoding="utf-8",
    )
    g1_eval_path.write_text(
        json.dumps(
            {
                "valid_rate": {"value": 0.92},
                "mae_qmax": {"value": 1.4},
            }
        ),
        encoding="utf-8",
    )
    qa_summary_path.write_text(
        json.dumps({"n_records_checked": 10, "n_pass": 8, "n_fail": 1}),
        encoding="utf-8",
    )

    build_exit_code = cli_main(
        [
            "build-gate-metrics",
            "--tfl-summary-json",
            str(tfl_summary_path),
            "--drift-summary-json",
            str(drift_summary_path),
            "--g1-eval-json",
            str(g1_eval_path),
            "--qa-summary-json",
            str(qa_summary_path),
            "--output-json",
            str(metrics_path),
        ]
    )
    assert build_exit_code == 0

    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert payload["metrics"]["qmax_mae_ml_s"] == 1.6
    assert payload["metrics"]["valid_rate_clinic"] == 0.9
    assert payload["metrics"]["qa_fail_rate"] == 0.1
    assert payload["sources"]["tfl_summary_json"] == str(tfl_summary_path)


def test_cli_build_gate_metrics_and_evaluate_g1_holdout_v2_5(tmp_path: Path) -> None:
    clinical_path = tmp_path / "clinical_holdout.csv"
    bench_path = tmp_path / "bench_holdout.csv"
    metrics_path = tmp_path / "holdout_metrics.json"

    clinical_rows = [
        {
            "cohort": "clinic",
            "quality_status": "valid",
            "sex": "m",
            "ref_qmax_ml_s": 20,
            "app_qmax_ml_s": 21.1,
            "ref_vvoid_ml": 300,
            "app_vvoid_ml": 312,
        },
        {
            "cohort": "clinic",
            "quality_status": "valid",
            "sex": "m",
            "ref_qmax_ml_s": 18,
            "app_qmax_ml_s": 17.1,
            "ref_vvoid_ml": 280,
            "app_vvoid_ml": 272,
        },
        {
            "cohort": "clinic",
            "quality_status": "valid",
            "sex": "m",
            "ref_qmax_ml_s": 22,
            "app_qmax_ml_s": 22.8,
            "ref_vvoid_ml": 320,
            "app_vvoid_ml": 334,
        },
        {
            "cohort": "clinic",
            "quality_status": "valid",
            "sex": "m",
            "ref_qmax_ml_s": 19,
            "app_qmax_ml_s": 18.2,
            "ref_vvoid_ml": 295,
            "app_vvoid_ml": 286,
        },
        {
            "cohort": "clinic",
            "quality_status": "repeat",
            "sex": "m",
            "ref_qmax_ml_s": 21,
            "app_qmax_ml_s": 20.0,
            "ref_vvoid_ml": 310,
            "app_vvoid_ml": 302,
        },
        {
            "cohort": "clinic",
            "quality_status": "valid",
            "sex": "f",
            "ref_qmax_ml_s": 17,
            "app_qmax_ml_s": 18.2,
            "ref_vvoid_ml": 260,
            "app_vvoid_ml": 272,
        },
        {
            "cohort": "clinic",
            "quality_status": "valid",
            "sex": "f",
            "ref_qmax_ml_s": 16,
            "app_qmax_ml_s": 15.1,
            "ref_vvoid_ml": 250,
            "app_vvoid_ml": 243,
        },
        {
            "cohort": "clinic",
            "quality_status": "valid",
            "sex": "f",
            "ref_qmax_ml_s": 18,
            "app_qmax_ml_s": 19.0,
            "ref_vvoid_ml": 275,
            "app_vvoid_ml": 288,
        },
        {
            "cohort": "clinic",
            "quality_status": "valid",
            "sex": "f",
            "ref_qmax_ml_s": 20,
            "app_qmax_ml_s": 19.1,
            "ref_vvoid_ml": 305,
            "app_vvoid_ml": 296,
        },
        {
            "cohort": "clinic",
            "quality_status": "valid",
            "sex": "f",
            "ref_qmax_ml_s": 15,
            "app_qmax_ml_s": 16.0,
            "ref_vvoid_ml": 240,
            "app_vvoid_ml": 251,
        },
    ]
    bench_rows = [
        {"scenario": "multi_toilet_a", "ref_qmax_ml_s": 15, "app_qmax_ml_s": 16.0},
        {"scenario": "multi_toilet_b", "ref_qmax_ml_s": 18, "app_qmax_ml_s": 19.2},
        {"scenario": "multi_toilet_c", "ref_qmax_ml_s": 22, "app_qmax_ml_s": 23.0},
    ]

    _write_csv(clinical_path, clinical_rows)
    _write_csv(bench_path, bench_rows)

    build_exit_code = cli_main(
        [
            "build-gate-metrics",
            "--clinical-csv",
            str(clinical_path),
            "--bench-csv",
            str(bench_path),
            "--output-json",
            str(metrics_path),
        ]
    )
    assert build_exit_code == 0

    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert payload["metrics"]["valid_rate_clinic"] >= 0.85
    assert payload["metrics"]["subgroup_max_mae_ratio"] <= 1.5
    assert payload["metrics"]["bench_qmax_mae_multi_toilet_ml_s"] <= 2.5

    gate_exit_code = cli_main(
        [
            "evaluate-gates",
            str(metrics_path),
            "--config-json",
            "docs/project-package-v2.5/gates-config-v2.5.json",
            "--gates",
            "G1",
            "BENCH_G1",
        ]
    )
    assert gate_exit_code == 0
