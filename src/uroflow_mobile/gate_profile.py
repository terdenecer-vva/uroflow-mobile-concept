from __future__ import annotations

import csv
import re
from pathlib import Path

MIN_MATCH_SCORE = 0.84

CLINICAL_FIELD_ALIASES: dict[str, list[str]] = {
    "app_qmax_ml_s": [
        "qmax_app",
        "app_qmax",
        "pred_qmax_ml_s",
        "estimated_qmax_ml_s",
    ],
    "ref_qmax_ml_s": ["qmax_ref", "reference_qmax_ml_s", "ref_qmax"],
    "app_qavg_ml_s": ["qavg_app", "app_qavg", "pred_qavg_ml_s"],
    "ref_qavg_ml_s": ["qavg_ref", "reference_qavg_ml_s", "ref_qavg"],
    "app_vvoid_ml": ["vvoid_app", "pred_vvoid_ml", "estimated_vvoid_ml", "app_vvoid"],
    "ref_vvoid_ml": ["vvoid_ref", "reference_vvoid_ml", "ref_vvoid"],
    "app_t_start_s": ["flow_start_time_s", "app_start_time_s", "start_app_s"],
    "ref_t_start_s": ["ref_flow_start_time_s", "ref_start_time_s", "start_ref_s"],
    "app_t_end_s": ["flow_end_time_s", "app_end_time_s", "end_app_s"],
    "ref_t_end_s": ["ref_flow_end_time_s", "ref_end_time_s", "end_ref_s"],
    "quality_status": ["quality_status_code", "signal_quality_status", "quality_label"],
    "cohort": ["cohort_label", "cohort_name", "setting", "setting_label"],
    "subgroup": ["sex", "sex_at_birth", "group"],
    "flush_pred": ["flush_detected", "artifact_flush_pred"],
    "flush_truth": ["artifact_flush_truth", "flush_gt"],
    "full_frame_stored": ["privacy_full_frame_stored", "store_full_frame"],
}

BENCH_FIELD_ALIASES: dict[str, list[str]] = {
    "scenario": ["test_scenario", "condition", "scenario_name"],
    "app_qmax_ml_s": ["qmax_app", "app_qmax", "pred_qmax_ml_s"],
    "ref_qmax_ml_s": ["qmax_ref", "reference_qmax_ml_s"],
    "not_in_water_truth": ["artifact_not_in_water_truth", "not_in_water_gt"],
    "not_in_water_pred": ["artifact_not_in_water_pred", "not_in_water_detected"],
    "is_valid_truth": ["valid_truth", "truth_valid"],
    "is_valid_pred": ["valid_pred", "pred_valid"],
    "quality_status": ["signal_quality_status", "quality_status_code"],
}

DEFAULT_QUALITY_VALUE_MAP = {
    "quality_status": {
        "1": "valid",
        "2": "repeat",
        "3": "reject",
    }
}


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.strip().lower())


def _best_alias_score(header: str, aliases: list[str]) -> float:
    header_norm = _normalize(header)
    best_score = 0.0

    for alias in aliases:
        alias_norm = _normalize(alias)
        if not alias_norm:
            continue
        if header_norm == alias_norm:
            return 1.0
        if len(alias_norm) >= 4 and (
            alias_norm in header_norm or header_norm in alias_norm
        ):
            best_score = max(best_score, 0.95)

    return best_score


def load_csv_headers(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            return []
        return [name for name in reader.fieldnames if name is not None and name.strip()]


def suggest_column_map(
    headers: list[str],
    canonical_aliases: dict[str, list[str]],
    min_score: float = MIN_MATCH_SCORE,
) -> dict[str, str]:
    used_headers: set[str] = set()
    result: dict[str, str] = {}

    for canonical_field, aliases in canonical_aliases.items():
        candidates = [canonical_field, *aliases]
        best_header = None
        best_score = 0.0
        for header in headers:
            if header in used_headers:
                continue
            score = _best_alias_score(header, candidates)
            if score > best_score:
                best_score = score
                best_header = header

        if best_header is None or best_score < min_score:
            continue
        used_headers.add(best_header)
        if best_header != canonical_field:
            result[best_header] = canonical_field

    return dict(sorted(result.items(), key=lambda item: item[0].lower()))


def build_profile_template(
    profile_name: str,
    clinical_headers: list[str] | None = None,
    bench_headers: list[str] | None = None,
) -> dict[str, object]:
    clinical_map = suggest_column_map(clinical_headers or [], CLINICAL_FIELD_ALIASES)
    bench_map = suggest_column_map(bench_headers or [], BENCH_FIELD_ALIASES)

    return {
        "version": 1,
        "profiles": {
            profile_name: {
                "meta": {
                    "generated_from": {
                        "clinical_headers": clinical_headers or [],
                        "bench_headers": bench_headers or [],
                    }
                },
                "clinical": {
                    "column_map": clinical_map,
                    "value_map": DEFAULT_QUALITY_VALUE_MAP,
                },
                "bench": {
                    "column_map": bench_map,
                    "value_map": DEFAULT_QUALITY_VALUE_MAP,
                },
            }
        },
    }
