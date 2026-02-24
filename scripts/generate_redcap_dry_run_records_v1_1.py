#!/usr/bin/env python3
"""Generate REDCap dry-run records for EDC v1.1 profile verification."""

from __future__ import annotations

import argparse
import copy
import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RedcapField:
    name: str
    field_type: str
    choices: list[tuple[str, str]]
    required: bool
    validation: str
    branching: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dictionary",
        type=Path,
        default=Path("docs/edc-v1.1/redcap/redcap_data_dictionary_v1.1.csv"),
        help="Path to generated REDCap Data Dictionary v1.1",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("docs/edc-v1.1/redcap/redcap_dry_run_records_v1.1.csv"),
        help="Output CSV path with dry-run records",
    )
    parser.add_argument(
        "--output-scenarios",
        type=Path,
        default=Path("docs/edc-v1.1/redcap/redcap_dry_run_scenarios_v1.1.csv"),
        help="Output CSV path with scenario descriptions",
    )
    return parser.parse_args()


def parse_choices(raw_value: str) -> list[tuple[str, str]]:
    if not raw_value:
        return []
    choices = []
    for token in raw_value.split("|"):
        token = token.strip()
        if not token or "," not in token:
            continue
        code, label = token.split(",", 1)
        choices.append((code.strip(), label.strip()))
    return choices


def load_fields(path: Path) -> list[RedcapField]:
    fields = []
    with path.open("r", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            name = row["Variable / Field Name"].strip()
            field_type = row["Field Type"].strip()
            choices = parse_choices(row["Choices, Calculations, OR Slider Labels"].strip())
            required = row["Required Field?"].strip().lower() == "y"
            validation = row["Text Validation Type OR Show Slider Number"].strip()
            branching = row["Branching Logic (Show field only if...)"].strip()
            fields.append(
                RedcapField(
                    name=name,
                    field_type=field_type,
                    choices=choices,
                    required=required,
                    validation=validation,
                    branching=branching,
                )
            )
    return fields


def field_default(field: RedcapField) -> str:
    if field.field_type == "yesno":
        return "0"
    if field.field_type == "dropdown":
        return field.choices[0][0] if field.choices else ""
    if field.field_type in {"text", "notes"}:
        if field.validation == "integer":
            return "1"
        if field.validation == "number":
            return "1.0"
        if field.validation == "datetime_ymd":
            return "2026-02-24 09:00"
        return f"sample_{field.name}"
    return ""


def checkbox_columns(fields: list[RedcapField]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for field in fields:
        if field.field_type != "checkbox":
            continue
        mapping[field.name] = [f"{field.name}___{code}" for code, _ in field.choices]
    return mapping


def ordered_columns(fields: list[RedcapField]) -> list[str]:
    columns = []
    for field in fields:
        if field.field_type == "calc":
            continue
        if field.field_type == "checkbox":
            columns.extend(f"{field.name}___{code}" for code, _ in field.choices)
            continue
        columns.append(field.name)
    if "record_id" in columns:
        columns.remove("record_id")
    return ["record_id", *columns]


def build_baseline_row(fields: list[RedcapField], columns: list[str]) -> dict[str, str]:
    row = {column: "" for column in columns}

    for field in fields:
        if field.field_type == "checkbox":
            for code, _ in field.choices:
                row[f"{field.name}___{code}"] = "0"

    for field in fields:
        if field.name == "record_id" or field.field_type in {"calc", "checkbox"}:
            continue
        if field.required and not field.branching:
            row[field.name] = field_default(field)

    baseline_values = {
        "record_id": "UFLOW-DRY-001",
        "study_id": "UFLOW-PILOT-01",
        "site_id": "SITE-001",
        "subject_id": "SUBJ-0001",
        "visit_id": "V1",
        "session_id": "SES-0001",
        "operator_id": "OP-01",
        "visit_datetime": "2026-02-24 09:15",
        "app_version": "0.1.0",
        "model_id": "fusion-v0.1",
        "model_version": "0.1.0",
        "model_hash": "sha256:samplehash001",
        "device_model": "iPhone15,3",
        "ios_version": "17.3",
        "capture_fps": "30",
        "audio_sample_rate_hz": "48000",
        "capture_mode": "3",
        "lidar_available": "1",
        "toilet_scan_done": "1",
        "recording_duration_s": "21.8",
        "flow_start_time_s": "1.2",
        "flow_end_time_s": "18.4",
        "q_curve_sampling_hz": "10",
        "q_curve_series": "[0,2.4,8.9,17.5,12.8,4.2,0]",
        "q_curve_uncertainty_series": "[0.1,0.2,0.3,0.3,0.2,0.2,0.1]",
        "age_years": "56",
        "height_cm": "177",
        "weight_kg": "83",
        "medications": "tamsulosin",
        "consent_signed": "1",
        "consent_level": "2",
        "attempt_number": "1",
        "void_into_water": "1",
        "environment_noise_level": "3",
        "lighting_level": "3",
        "noise_source": "none",
        "phone_on_support": "1",
        "flush_during_recording": "0",
        "comments_conditions": "baseline controlled run",
        "app_curve_class": "1",
        "ref_curve_class": "1",
        "ref_qmax_ml_s": "18.7",
        "ref_qavg_ml_s": "9.6",
        "ref_vvoid_ml": "312",
        "ref_flow_time_s": "17.9",
        "ref_tqmax_s": "5.1",
        "ref_artifacts": "none",
        "app_qmax_ml_s": "18.3",
        "app_qavg_ml_s": "9.1",
        "app_vvoid_ml": "305",
        "app_flow_time_s": "17.6",
        "app_tqmax_s": "5.3",
        "intermittency_index": "0.08",
        "quality_score": "88",
        "overall_uncertainty": "0.14",
        "motion_score": "0.02",
        "quality_notes": "",
        "repeat_reason": "",
        "deviation_comment": "",
        "pvr_delay_min": "",
        "pvr_ml": "",
        "notes_clinician": "no concerns",
        "ae_description": "",
    }
    row.update(baseline_values)
    return row


def set_checkbox_value(row: dict[str, str], field_name: str, code: str, value: str = "1") -> None:
    key = f"{field_name}___{code}"
    if key in row:
        row[key] = value


def build_scenarios(baseline: dict[str, str]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rows = []
    scenarios = []

    def add(record: dict[str, str], scenario_id: str, name: str, focus: str) -> None:
        record["record_id"] = scenario_id
        rows.append(record)
        scenarios.append({"record_id": scenario_id, "scenario_name": name, "focus_checks": focus})

    s1 = copy.deepcopy(baseline)
    s1["quality_status"] = "1"
    s1["repeat_required"] = "0"
    s1["pvr_available"] = "0"
    s1["protocol_deviation"] = "0"
    s1["ae_occurred"] = "0"
    add(s1, "UFLOW-DRY-001", "valid_baseline", "All mandatory fields, valid quality")

    s2 = copy.deepcopy(baseline)
    s2["subject_id"] = "SUBJ-0002"
    s2["session_id"] = "SES-0002"
    s2["quality_status"] = "2"
    s2["repeat_required"] = "1"
    s2["repeat_reason"] = "motion_blur_repeat"
    s2["quality_score"] = "49"
    s2["qr_motion"] = "1"
    set_checkbox_value(s2, "quality_flags", "2", "1")
    add(s2, "UFLOW-DRY-002", "repeat_due_motion", "Branching repeat_reason + motion artifact")

    s3 = copy.deepcopy(baseline)
    s3["subject_id"] = "SUBJ-0003"
    s3["session_id"] = "SES-0003"
    s3["quality_status"] = "3"
    s3["repeat_required"] = "1"
    s3["repeat_reason"] = "invalid_nonwater"
    s3["quality_notes"] = "impact outside water ROI"
    s3["quality_score"] = "32"
    s3["void_into_water"] = "2"
    s3["capture_mode"] = "1"
    s3["qr_not_in_water"] = "1"
    set_checkbox_value(s3, "quality_flags", "4", "1")
    add(s3, "UFLOW-DRY-003", "reject_non_water", "Reject flow + non-water fallback mode")

    s4 = copy.deepcopy(baseline)
    s4["subject_id"] = "SUBJ-0004"
    s4["session_id"] = "SES-0004"
    s4["pvr_available"] = "1"
    s4["pvr_method"] = "1"
    s4["pvr_delay_min"] = "7"
    s4["pvr_ml"] = "82"
    add(s4, "UFLOW-DRY-004", "with_pvr", "Branching PVR fields")

    s5 = copy.deepcopy(baseline)
    s5["subject_id"] = "SUBJ-0005"
    s5["session_id"] = "SES-0005"
    s5["protocol_deviation"] = "1"
    s5["deviation_comment"] = "phone moved after stream start"
    s5["phone_on_support"] = "0"
    s5["quality_status"] = "2"
    s5["repeat_required"] = "1"
    s5["repeat_reason"] = "protocol_deviation"
    set_checkbox_value(s5, "quality_flags", "2", "1")
    add(s5, "UFLOW-DRY-005", "protocol_deviation", "Deviation comment branching")

    s6 = copy.deepcopy(baseline)
    s6["subject_id"] = "SUBJ-0006"
    s6["session_id"] = "SES-0006"
    s6["ae_occurred"] = "1"
    s6["ae_description"] = "dizziness after void"
    s6["ae_related"] = "1"
    add(s6, "UFLOW-DRY-006", "ae_reported", "AE branching fields")

    s7 = copy.deepcopy(baseline)
    s7["subject_id"] = "SUBJ-0007"
    s7["session_id"] = "SES-0007"
    s7["pour_calibration_done"] = "1"
    s7["pour_calibration_volume_ml"] = "400"
    s7["toilet_fingerprint_id"] = "TFP-0007"
    add(s7, "UFLOW-DRY-007", "pour_calibrated", "Pour calibration conditional field")

    s8 = copy.deepcopy(baseline)
    s8["subject_id"] = "SUBJ-0008"
    s8["session_id"] = "SES-0008"
    s8["sex_at_birth"] = "2"
    s8["voiding_position"] = "3"
    s8["environment_noise_level"] = "1"
    s8["quality_score"] = "61"
    s8["qr_low_snr"] = "1"
    set_checkbox_value(s8, "quality_flags", "1", "1")
    add(s8, "UFLOW-DRY-008", "female_high_noise", "Noise artifacts in female sitting scenario")

    return rows, scenarios


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    args = parse_args()
    fields = load_fields(args.dictionary)
    columns = ordered_columns(fields)
    baseline = build_baseline_row(fields, columns)
    records, scenarios = build_scenarios(baseline)

    write_csv(args.output_csv, columns, records)
    write_csv(args.output_scenarios, ["record_id", "scenario_name", "focus_checks"], scenarios)

    print(f"Generated REDCap dry-run records: {args.output_csv}")
    print(f"Records: {len(records)}")


if __name__ == "__main__":
    main()
