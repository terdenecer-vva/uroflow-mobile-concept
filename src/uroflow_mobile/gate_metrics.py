from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from statistics import mean, stdev
from typing import Any

TRUE_VALUES = {"1", "true", "yes", "y", "on", "pass", "passed", "valid"}
FALSE_VALUES = {"0", "false", "no", "n", "off", "fail", "failed", "invalid", "reject"}


def load_mapping_profile(path: Path) -> dict[str, Any]:
    """Load mapping profile document from YAML or JSON file."""

    if not path.exists():
        raise FileNotFoundError(path)

    suffix = path.suffix.strip().lower()
    raw_text = path.read_text(encoding="utf-8")

    if suffix == ".json":
        payload = json.loads(raw_text)
    else:
        try:
            import yaml
        except ModuleNotFoundError as error:
            raise ModuleNotFoundError(
                "PyYAML is required for --profile-yaml support. Install package 'PyYAML'."
            ) from error
        payload = yaml.safe_load(raw_text)

    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("mapping profile document must be an object")
    return payload


def select_mapping_profile(
    profile_document: dict[str, Any], profile_name: str | None = None
) -> tuple[str, dict[str, Any]]:
    """Select one profile from profile document."""

    profiles = profile_document.get("profiles")
    if isinstance(profiles, dict):
        if not profiles:
            raise ValueError("mapping profile 'profiles' is empty")
        if profile_name is None:
            if len(profiles) != 1:
                names = ", ".join(sorted(str(key) for key in profiles))
                raise ValueError(
                    "profile document contains multiple profiles; specify --profile-name "
                    f"one of: {names}"
                )
            profile_name = str(next(iter(profiles)))
        profile_payload = profiles.get(profile_name)
        if not isinstance(profile_payload, dict):
            raise ValueError(f"profile '{profile_name}' is not present in mapping document")
        return str(profile_name), profile_payload

    if profile_name is not None:
        raise ValueError("profile_name was provided but mapping file has no 'profiles' section")
    return "default", profile_document


def _normalize_key(value: str) -> str:
    return value.strip().lower()


def _key_lookup(row: dict[str, object]) -> dict[str, str]:
    return {_normalize_key(key): key for key in row}


def _pick_value(row: dict[str, object], aliases: list[str]) -> object | None:
    lookup = _key_lookup(row)
    for alias in aliases:
        row_key = lookup.get(_normalize_key(alias))
        if row_key is None:
            continue
        return row.get(row_key)
    return None


def _parse_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if math.isfinite(number):
            return number
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if not math.isfinite(number):
        return None
    return number


def _parse_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if not text:
        return None
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    return None


def _parse_quality_is_valid(value: object) -> bool | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"valid", "pass", "ok"}:
        return True
    if text in {"repeat", "reject", "invalid", "fail"}:
        return False
    return _parse_bool(value)


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(mean(values))


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    values_sorted = sorted(values)
    middle = len(values_sorted) // 2
    if len(values_sorted) % 2 == 1:
        return float(values_sorted[middle])
    left = values_sorted[middle - 1]
    right = values_sorted[middle]
    return float((left + right) / 2.0)


def _loa95_abs(differences: list[float]) -> float | None:
    if not differences:
        return None
    bias = mean(differences)
    sigma = stdev(differences) if len(differences) > 1 else 0.0
    low = bias - 1.96 * sigma
    high = bias + 1.96 * sigma
    return float(max(abs(low), abs(high)))


def _ratio(part: int, total: int) -> float | None:
    if total <= 0:
        return None
    return float(part / total)


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return [dict(row) for row in reader]


def _detect_metric_value_table(rows: list[dict[str, object]]) -> bool:
    if not rows:
        return False
    lookup = _key_lookup(rows[0])
    return "metric" in lookup and "value" in lookup


def _coerce_scalar(value: object) -> object:
    bool_value = _parse_bool(value)
    if bool_value is not None:
        return bool_value
    float_value = _parse_float(value)
    if float_value is not None:
        return float_value
    return str(value).strip()


def _extract_metric_value_rows(rows: list[dict[str, object]]) -> dict[str, object]:
    metrics: dict[str, object] = {}
    if not rows:
        return metrics
    for row in rows:
        metric_name = _pick_value(row, ["metric", "metric_name", "name"])
        metric_value = _pick_value(row, ["value", "metric_value"])
        if metric_name is None or metric_value is None:
            continue
        key = str(metric_name).strip()
        if not key:
            continue
        metrics[key] = _coerce_scalar(metric_value)
    return metrics


def _parse_column_map(payload: object) -> dict[str, str]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("column_map must be an object")

    result: dict[str, str] = {}
    source_keys_seen: set[str] = set()
    for source_key, target_key in payload.items():
        if not isinstance(source_key, str) or not isinstance(target_key, str):
            raise ValueError("column_map keys and values must be strings")
        source = source_key.strip()
        target = target_key.strip()
        if not source or not target:
            raise ValueError("column_map entries must have non-empty source and target")

        source_key_normalized = source.lower()
        if source_key_normalized in source_keys_seen:
            raise ValueError(f"column_map contains duplicate source column '{source}'")
        source_keys_seen.add(source_key_normalized)
        result[source] = target
    return result


def _parse_value_map(payload: object) -> dict[str, dict[str, object]]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("value_map must be an object")

    parsed: dict[str, dict[str, object]] = {}
    for field_name, mapping_payload in payload.items():
        if not isinstance(mapping_payload, dict):
            raise ValueError(f"value_map entry for '{field_name}' must be an object")
        mapping: dict[str, object] = {}
        for raw_value, mapped_value in mapping_payload.items():
            mapping[str(raw_value).strip()] = mapped_value
        parsed[str(field_name).strip()] = mapping
    return parsed


def _merge_value_maps(
    base: dict[str, dict[str, object]],
    update: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    merged: dict[str, dict[str, object]] = {key: dict(value) for key, value in base.items()}
    for field_name, field_map in update.items():
        current = merged.setdefault(field_name, {})
        current.update(field_map)
    return merged


def _build_profile_mappings(
    profile: dict[str, Any] | None,
    section: str,
) -> tuple[dict[str, str], dict[str, dict[str, object]]]:
    if not profile:
        return {}, {}

    sections: list[dict[str, object]] = []
    sections.append(profile)

    common = profile.get("common")
    if common is not None:
        if not isinstance(common, dict):
            raise ValueError("profile.common must be an object")
        sections.append(common)

    section_payload = profile.get(section)
    if section_payload is not None:
        if not isinstance(section_payload, dict):
            raise ValueError(f"profile.{section} must be an object")
        sections.append(section_payload)

    column_map: dict[str, str] = {}
    value_map: dict[str, dict[str, object]] = {}
    for item in sections:
        column_map.update(_parse_column_map(item.get("column_map")))
        value_map = _merge_value_maps(value_map, _parse_value_map(item.get("value_map")))

    target_to_sources: dict[str, list[str]] = {}
    for source, target in column_map.items():
        target_to_sources.setdefault(target.lower(), []).append(source)
    duplicate_targets = {
        target: sources for target, sources in target_to_sources.items() if len(sources) > 1
    }
    if duplicate_targets:
        duplicates = "; ".join(
            f"{target} <- {', '.join(sorted(sources))}"
            for target, sources in sorted(duplicate_targets.items(), key=lambda item: item[0])
        )
        raise ValueError(f"column_map has ambiguous duplicate targets: {duplicates}")
    return column_map, value_map


def _apply_profile_to_rows(
    rows: list[dict[str, object]],
    profile: dict[str, Any] | None,
    section: str,
) -> list[dict[str, object]]:
    column_map, value_map = _build_profile_mappings(profile=profile, section=section)
    if not column_map and not value_map:
        return rows

    normalized_column_map = {source.lower(): target for source, target in column_map.items()}
    remapped_rows: list[dict[str, object]] = []

    for row in rows:
        mapped_row = dict(row)
        row_lookup = _key_lookup(mapped_row)

        for source_lower, target_key in normalized_column_map.items():
            source_key = row_lookup.get(source_lower)
            if source_key is None:
                continue
            source_value = mapped_row.get(source_key)
            target_exists = target_key in mapped_row
            target_value = mapped_row.get(target_key)
            target_is_empty = target_value is None or target_value == ""
            if not target_exists or target_is_empty:
                mapped_row[target_key] = source_value

        mapped_lookup = _key_lookup(mapped_row)
        for field_name, field_map in value_map.items():
            field_key = mapped_lookup.get(field_name.lower())
            if field_key is None:
                continue
            raw_value = mapped_row.get(field_key)
            raw_text = "" if raw_value is None else str(raw_value).strip()
            mapped_value = field_map.get(raw_text)
            if mapped_value is None and raw_text:
                mapped_value = field_map.get(raw_text.lower())
            if mapped_value is not None:
                mapped_row[field_key] = mapped_value

        remapped_rows.append(mapped_row)

    return remapped_rows


def _cohort(row: dict[str, object]) -> str:
    value = _pick_value(row, ["cohort", "setting", "environment", "site_mode"])
    text = str(value).strip().lower() if value is not None else ""
    if "home" in text:
        return "home"
    return "clinic"


def _scenario_bucket(row: dict[str, object]) -> str:
    value = _pick_value(row, ["scenario", "test_scenario", "condition"])
    text = str(value).strip().lower() if value is not None else ""
    if any(token in text for token in {"noise", "noisy", "fan", "flush", "music"}):
        return "noise"
    if any(token in text for token in {"multi", "toilet", "cross_site", "cross-site"}):
        return "multi_toilet"
    if "stress" in text:
        return "stress"
    return "quiet"


def _compute_clinical_metrics(rows: list[dict[str, object]]) -> dict[str, object]:
    metrics: dict[str, object] = {}
    if not rows:
        return metrics

    qmax_abs_errors: list[float] = []
    qmax_diffs: list[float] = []
    qavg_abs_errors: list[float] = []
    vvoid_abs_errors: list[float] = []
    vvoid_abs_pct_errors: list[float] = []
    vvoid_diffs: list[float] = []
    dt_start_abs_errors: list[float] = []
    dt_end_abs_errors: list[float] = []
    privacy_events = 0
    privacy_total = 0
    valid_counts = {"clinic": 0, "home": 0}
    total_counts = {"clinic": 0, "home": 0}
    subgroup_qmax_errors: dict[str, list[float]] = {}
    flush_tp = 0
    flush_fn = 0

    for row in rows:
        ref_qmax = _parse_float(
            _pick_value(
                row,
                [
                    "ref_qmax_ml_s",
                    "qmax_ref",
                    "reference_qmax_ml_s",
                ],
            )
        )
        app_qmax = _parse_float(
            _pick_value(
                row,
                [
                    "app_qmax_ml_s",
                    "qmax_app",
                    "pred_qmax_ml_s",
                    "estimated_qmax_ml_s",
                ],
            )
        )
        if ref_qmax is not None and app_qmax is not None:
            diff = app_qmax - ref_qmax
            qmax_diffs.append(diff)
            abs_error = abs(diff)
            qmax_abs_errors.append(abs_error)

            subgroup_value = _pick_value(row, ["subgroup", "sex", "group"])
            subgroup_name = str(subgroup_value).strip().lower() if subgroup_value else ""
            if subgroup_name:
                subgroup_qmax_errors.setdefault(subgroup_name, []).append(abs_error)

        ref_qavg = _parse_float(
            _pick_value(
                row,
                [
                    "ref_qavg_ml_s",
                    "qavg_ref",
                    "reference_qavg_ml_s",
                ],
            )
        )
        app_qavg = _parse_float(
            _pick_value(
                row,
                [
                    "app_qavg_ml_s",
                    "qavg_app",
                    "pred_qavg_ml_s",
                    "estimated_qavg_ml_s",
                ],
            )
        )
        if ref_qavg is not None and app_qavg is not None:
            qavg_abs_errors.append(abs(app_qavg - ref_qavg))

        ref_vvoid = _parse_float(
            _pick_value(
                row,
                [
                    "ref_vvoid_ml",
                    "vvoid_ref",
                    "reference_vvoid_ml",
                ],
            )
        )
        app_vvoid = _parse_float(
            _pick_value(
                row,
                [
                    "app_vvoid_ml",
                    "vvoid_app",
                    "pred_vvoid_ml",
                    "estimated_vvoid_ml",
                ],
            )
        )
        if ref_vvoid is not None and app_vvoid is not None:
            diff = app_vvoid - ref_vvoid
            vvoid_diffs.append(diff)
            vvoid_abs_errors.append(abs(diff))
            if ref_vvoid != 0:
                vvoid_abs_pct_errors.append(abs(diff) / abs(ref_vvoid) * 100.0)

        ref_start = _parse_float(
            _pick_value(row, ["ref_t_start_s", "ref_start_time_s", "start_ref_s"])
        )
        app_start = _parse_float(
            _pick_value(row, ["app_t_start_s", "app_start_time_s", "start_app_s"])
        )
        if ref_start is not None and app_start is not None:
            dt_start_abs_errors.append(abs(app_start - ref_start))

        ref_end = _parse_float(_pick_value(row, ["ref_t_end_s", "ref_end_time_s", "end_ref_s"]))
        app_end = _parse_float(_pick_value(row, ["app_t_end_s", "app_end_time_s", "end_app_s"]))
        if ref_end is not None and app_end is not None:
            dt_end_abs_errors.append(abs(app_end - ref_end))

        full_frame = _parse_bool(
            _pick_value(
                row,
                [
                    "full_frame_stored",
                    "privacy_full_frame_stored",
                    "store_full_frame",
                ],
            )
        )
        if full_frame is not None:
            privacy_total += 1
            if full_frame:
                privacy_events += 1

        quality_is_valid = _parse_quality_is_valid(
            _pick_value(row, ["quality_status", "signal_quality_status", "quality_label"])
        )
        cohort = _cohort(row)
        if quality_is_valid is not None:
            total_counts[cohort] += 1
            if quality_is_valid:
                valid_counts[cohort] += 1

        flush_truth = _parse_bool(
            _pick_value(
                row,
                [
                    "flush_truth",
                    "artifact_flush_truth",
                    "flush_gt",
                ],
            )
        )
        flush_pred = _parse_bool(
            _pick_value(
                row,
                [
                    "flush_pred",
                    "artifact_flush_pred",
                    "flush_detected",
                ],
            )
        )
        if flush_truth is True:
            if flush_pred is True:
                flush_tp += 1
            elif flush_pred is False:
                flush_fn += 1

    metrics["qmax_mae_ml_s"] = _mean(qmax_abs_errors)
    qmax_bias = _mean(qmax_diffs)
    metrics["qmax_bias_abs_ml_s"] = abs(qmax_bias) if qmax_bias is not None else None
    metrics["qmax_loa95_abs_ml_s"] = _loa95_abs(qmax_diffs)

    metrics["qavg_mae_ml_s"] = _mean(qavg_abs_errors)
    metrics["vvoid_mae_ml"] = _mean(vvoid_abs_errors)
    metrics["vvoid_mape_pct"] = _mean(vvoid_abs_pct_errors)
    metrics["vvoid_loa95_abs_ml"] = _loa95_abs(vvoid_diffs)
    metrics["dt_start_median_abs_s"] = _median(dt_start_abs_errors)
    metrics["dt_end_median_abs_s"] = _median(dt_end_abs_errors)

    valid_rate_clinic = _ratio(valid_counts["clinic"], total_counts["clinic"])
    if valid_rate_clinic is not None:
        metrics["valid_rate_clinic"] = valid_rate_clinic

    valid_rate_home = _ratio(valid_counts["home"], total_counts["home"])
    if valid_rate_home is not None:
        metrics["valid_rate_home"] = valid_rate_home

    privacy_rate = _ratio(privacy_events, privacy_total)
    if privacy_rate is not None:
        metrics["privacy_full_frame_storage_rate"] = privacy_rate

    if flush_tp + flush_fn > 0:
        metrics["flush_recall"] = flush_tp / (flush_tp + flush_fn)

    subgroup_maes = [
        _mean(values)
        for values in subgroup_qmax_errors.values()
        if values and _mean(values) is not None
    ]
    if len(subgroup_maes) >= 2:
        max_mae = max(subgroup_maes)
        min_mae = min(subgroup_maes)
        if min_mae > 0:
            metrics["subgroup_max_mae_ratio"] = max_mae / min_mae

    return {key: value for key, value in metrics.items() if value is not None}


def _compute_bench_metrics(rows: list[dict[str, object]]) -> dict[str, object]:
    metrics: dict[str, object] = {}
    if not rows:
        return metrics

    if _detect_metric_value_table(rows):
        return _extract_metric_value_rows(rows)

    qmax_errors_by_bucket: dict[str, list[float]] = {
        "quiet": [],
        "noise": [],
        "multi_toilet": [],
    }
    not_in_water_tp = 0
    not_in_water_fn = 0
    invalid_truth_total = 0
    false_valid_count = 0

    for row in rows:
        ref_qmax = _parse_float(
            _pick_value(row, ["ref_qmax_ml_s", "qmax_ref", "reference_qmax_ml_s"])
        )
        app_qmax = _parse_float(
            _pick_value(row, ["app_qmax_ml_s", "qmax_app", "pred_qmax_ml_s"])
        )
        if ref_qmax is not None and app_qmax is not None:
            bucket = _scenario_bucket(row)
            if bucket in qmax_errors_by_bucket:
                qmax_errors_by_bucket[bucket].append(abs(app_qmax - ref_qmax))

        not_in_water_truth = _parse_bool(
            _pick_value(
                row,
                [
                    "not_in_water_truth",
                    "artifact_not_in_water_truth",
                    "not_in_water_gt",
                ],
            )
        )
        not_in_water_pred = _parse_bool(
            _pick_value(
                row,
                [
                    "not_in_water_pred",
                    "artifact_not_in_water_pred",
                    "not_in_water_detected",
                ],
            )
        )
        if not_in_water_truth is True:
            if not_in_water_pred is True:
                not_in_water_tp += 1
            elif not_in_water_pred is False:
                not_in_water_fn += 1

        truth_valid = _parse_bool(
            _pick_value(
                row,
                [
                    "is_valid_truth",
                    "valid_truth",
                    "truth_valid",
                ],
            )
        )
        pred_valid = _parse_bool(_pick_value(row, ["is_valid_pred", "valid_pred", "pred_valid"]))
        if pred_valid is None:
            pred_valid = _parse_quality_is_valid(
                _pick_value(row, ["quality_status", "signal_quality_status"])
            )
        if truth_valid is False and pred_valid is not None:
            invalid_truth_total += 1
            if pred_valid:
                false_valid_count += 1

    quiet_mae = _mean(qmax_errors_by_bucket["quiet"])
    noise_mae = _mean(qmax_errors_by_bucket["noise"])
    multi_mae = _mean(qmax_errors_by_bucket["multi_toilet"])
    if quiet_mae is not None:
        metrics["bench_qmax_mae_quiet_ml_s"] = quiet_mae
    if noise_mae is not None:
        metrics["bench_qmax_mae_noise_ml_s"] = noise_mae
    if multi_mae is not None:
        metrics["bench_qmax_mae_multi_toilet_ml_s"] = multi_mae

    if not_in_water_tp + not_in_water_fn > 0:
        metrics["not_in_water_sensitivity"] = not_in_water_tp / (
            not_in_water_tp + not_in_water_fn
        )
    if invalid_truth_total > 0:
        metrics["stress_false_valid_rate"] = false_valid_count / invalid_truth_total

    return metrics


def _extract_metrics_from_tfl_summary(payload: dict[str, object]) -> dict[str, object]:
    metrics: dict[str, object] = {}

    n_total = _parse_float(payload.get("n_total"))
    n_valid = _parse_float(payload.get("n_valid"))
    if n_total and n_total > 0 and n_valid is not None:
        metrics["valid_rate_clinic"] = float(n_valid / n_total)

    metrics_payload = payload.get("metrics")
    if not isinstance(metrics_payload, dict):
        return metrics

    qmax_payload = metrics_payload.get("Qmax")
    if isinstance(qmax_payload, dict):
        qmax_mae = _parse_float(qmax_payload.get("mae"))
        qmax_bias = _parse_float(qmax_payload.get("bias"))
        loa_low = _parse_float(qmax_payload.get("loa_low"))
        loa_high = _parse_float(qmax_payload.get("loa_high"))
        if qmax_mae is not None:
            metrics["qmax_mae_ml_s"] = qmax_mae
        if qmax_bias is not None:
            metrics["qmax_bias_abs_ml_s"] = abs(qmax_bias)
        if loa_low is not None and loa_high is not None:
            metrics["qmax_loa95_abs_ml_s"] = max(abs(loa_low), abs(loa_high))

    qavg_payload = metrics_payload.get("Qavg")
    if isinstance(qavg_payload, dict):
        qavg_mae = _parse_float(qavg_payload.get("mae"))
        if qavg_mae is not None:
            metrics["qavg_mae_ml_s"] = qavg_mae

    vvoid_payload = metrics_payload.get("Vvoid")
    if isinstance(vvoid_payload, dict):
        vvoid_mae = _parse_float(vvoid_payload.get("mae"))
        vvoid_mape = _parse_float(vvoid_payload.get("mape"))
        loa_low = _parse_float(vvoid_payload.get("loa_low"))
        loa_high = _parse_float(vvoid_payload.get("loa_high"))
        if vvoid_mae is not None:
            metrics["vvoid_mae_ml"] = vvoid_mae
        if vvoid_mape is not None:
            metrics["vvoid_mape_pct"] = vvoid_mape
        if loa_low is not None and loa_high is not None:
            metrics["vvoid_loa95_abs_ml"] = max(abs(loa_low), abs(loa_high))

    flow_payload = metrics_payload.get("FlowTime")
    if isinstance(flow_payload, dict):
        flow_mae = _parse_float(flow_payload.get("mae"))
        if flow_mae is not None:
            metrics["flow_time_mae_s"] = flow_mae

    return metrics


def _extract_metrics_from_drift_summary(payload: dict[str, object]) -> dict[str, object]:
    metrics: dict[str, object] = {}
    overall = payload.get("overall")
    if not isinstance(overall, dict):
        return metrics

    qmax_mae = _parse_float(overall.get("Qmax_mae"))
    if qmax_mae is not None:
        metrics["qmax_mae_ml_s"] = qmax_mae

    vvoid_mape = _parse_float(overall.get("Vvoid_mape"))
    if vvoid_mape is not None:
        metrics["vvoid_mape_pct"] = vvoid_mape

    return metrics


def _extract_metrics_from_g1_eval(payload: dict[str, object]) -> dict[str, object]:
    metrics: dict[str, object] = {}

    mapping = {
        "valid_rate": "valid_rate_clinic",
        "mae_qmax": "qmax_mae_ml_s",
        "mae_qavg": "qavg_mae_ml_s",
        "mape_vvoid": "vvoid_mape_pct",
        "mae_flowtime": "flow_time_mae_s",
    }
    for source_key, metric_key in mapping.items():
        source_value = payload.get(source_key)
        value: float | None = None
        if isinstance(source_value, dict):
            value = _parse_float(source_value.get("value"))
        else:
            value = _parse_float(source_value)
        if value is not None:
            metrics[metric_key] = value

    counts = payload.get("_counts")
    if (
        "valid_rate_clinic" not in metrics
        and isinstance(counts, dict)
        and _parse_float(counts.get("n_total"))
    ):
        n_total = _parse_float(counts.get("n_total"))
        n_valid = _parse_float(counts.get("n_valid"))
        if n_total and n_total > 0 and n_valid is not None:
            metrics["valid_rate_clinic"] = float(n_valid / n_total)

    return metrics


def _extract_metrics_from_qa_summary(payload: dict[str, object]) -> dict[str, object]:
    metrics: dict[str, object] = {}
    n_checked = _parse_float(payload.get("n_records_checked"))
    n_pass = _parse_float(payload.get("n_pass"))
    if n_checked and n_checked > 0 and n_pass is not None:
        metrics["valid_rate_clinic"] = float(n_pass / n_checked)

    n_fail = _parse_float(payload.get("n_fail"))
    if n_checked and n_checked > 0 and n_fail is not None:
        metrics["qa_fail_rate"] = float(n_fail / n_checked)

    return metrics


def _merge_metric_backfill(
    base_metrics: dict[str, object],
    backfill_metrics: dict[str, object],
) -> None:
    for key, value in backfill_metrics.items():
        if key in base_metrics:
            continue
        base_metrics[key] = value


def build_gate_metrics(
    clinical_rows: list[dict[str, object]] | None = None,
    bench_rows: list[dict[str, object]] | None = None,
    mapping_profile: dict[str, Any] | None = None,
    qa_summary: dict[str, object] | None = None,
    tfl_summary: dict[str, object] | None = None,
    drift_summary: dict[str, object] | None = None,
    g1_eval: dict[str, object] | None = None,
    overrides: dict[str, object] | None = None,
) -> dict[str, object]:
    metrics: dict[str, object] = {}
    if clinical_rows:
        mapped_clinical = _apply_profile_to_rows(
            clinical_rows,
            profile=mapping_profile,
            section="clinical",
        )
        if _detect_metric_value_table(mapped_clinical):
            metrics.update(_extract_metric_value_rows(mapped_clinical))
        else:
            metrics.update(_compute_clinical_metrics(mapped_clinical))
    if bench_rows:
        mapped_bench = _apply_profile_to_rows(
            bench_rows,
            profile=mapping_profile,
            section="bench",
        )
        metrics.update(_compute_bench_metrics(mapped_bench))
    if tfl_summary:
        _merge_metric_backfill(metrics, _extract_metrics_from_tfl_summary(tfl_summary))
    if drift_summary:
        _merge_metric_backfill(metrics, _extract_metrics_from_drift_summary(drift_summary))
    if g1_eval:
        _merge_metric_backfill(metrics, _extract_metrics_from_g1_eval(g1_eval))
    if qa_summary:
        _merge_metric_backfill(metrics, _extract_metrics_from_qa_summary(qa_summary))
    if overrides:
        metrics.update(overrides)
    return metrics
