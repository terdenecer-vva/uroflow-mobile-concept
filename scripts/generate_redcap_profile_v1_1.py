#!/usr/bin/env python3
"""Generate REDCap import profile from canonical EDC v1.1 files."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

REDCAP_COLUMNS = [
    "Variable / Field Name",
    "Form Name",
    "Section Header",
    "Field Type",
    "Field Label",
    "Choices, Calculations, OR Slider Labels",
    "Field Note",
    "Text Validation Type OR Show Slider Number",
    "Text Validation Min",
    "Text Validation Max",
    "Identifier?",
    "Branching Logic (Show field only if...)",
    "Required Field?",
    "Custom Alignment",
    "Question Number (surveys only)",
    "Matrix Group Name",
    "Matrix Ranking?",
    "Field Annotation",
]

SECTION_TITLES = {
    "identification": "Identification",
    "capture_setup": "Capture Setup",
    "screening": "Screening",
    "test_conditions": "Test Conditions",
    "event_timing": "Event Timing",
    "reference_uroflow": "Reference Uroflow",
    "app_output": "Smartphone App Output",
    "quality": "Quality and Artifacts",
    "pvr": "PVR",
    "privacy_export": "Privacy and Export",
    "safety": "Safety",
    "derived": "Derived Metrics",
}

BOOL_FIELDS_WITH_DROPDOWN = {
    "lidar_available",
    "toilet_scan_done",
    "pour_calibration_done",
    "consent_signed",
    "void_into_water",
    "phone_on_support",
    "flush_during_recording",
    "pvr_available",
    "media_saved",
    "media_consent",
    "ae_occurred",
    "ae_related",
    "repeat_required",
    "protocol_deviation",
    "flush_detected",
}

LONG_TEXT_FIELDS = {
    "medications",
    "comments_conditions",
    "ref_artifacts",
    "quality_notes",
    "notes_clinician",
    "ae_description",
    "q_curve_series",
    "q_curve_uncertainty_series",
}

DERIVED_FORMULAS = {
    "delta_qmax": "[app_qmax_ml_s] - [ref_qmax_ml_s]",
    "delta_qavg": "[app_qavg_ml_s] - [ref_qavg_ml_s]",
    "delta_vvoid": "[app_vvoid_ml] - [ref_vvoid_ml]",
    "abs_pct_error_qmax": "if([ref_qmax_ml_s]=0,'',abs([delta_qmax])/[ref_qmax_ml_s]*100)",
}

BRANCHING_BY_FIELD = {
    "pvr_method": "[pvr_available]='{YES_NO_YES}'",
    "pvr_ml": "[pvr_available]='{YES_NO_YES}'",
    "pvr_delay_min": "[pvr_available]='{YES_NO_YES}'",
    "repeat_reason": "([quality_status]='{QUALITY_STATUS_REPEAT}' or "
    "[quality_status]='{QUALITY_STATUS_REJECT}')",
    "deviation_comment": "[protocol_deviation]='{YES_NO_YES}'",
    "pour_calibration_volume_ml": "[pour_calibration_done]='{YES_NO_YES}'",
    "quality_notes": "[quality_status]='{QUALITY_STATUS_REJECT}'",
    "ae_description": "[ae_occurred]='{YES_NO_YES}'",
    "ae_related": "[ae_occurred]='{YES_NO_YES}'",
}

LIST_CODE_ORDER = {
    "QUALITY_STATUS": ["valid", "repeat", "reject"],
    "FLOW_PATTERN": ["bell", "plateau", "intermittent", "other"],
    "ROI_VISIBILITY": ["ok", "partial", "lost"],
    "QUALITY_FLAGS": [
        "noise",
        "motion",
        "roi_lost",
        "not_in_water",
        "flush",
        "low_volume",
        "other",
    ],
    "VOID_INTO_WATER": ["yes", "no", "unsure"],
    "SEX_AT_BIRTH": ["male", "female"],
    "VOIDING_POSITION": ["male_standing", "male_sitting", "female_sitting"],
}

IDENTIFIER_FIELDS = {"subject_id", "visit_datetime"}
HIDDEN_FIELDS = {"q_curve_series", "q_curve_uncertainty_series"}


@dataclass
class CanonicalField:
    name: str
    section: str
    field_type: str
    units: str
    required_level: str
    codelist: str
    description_ru: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dictionary",
        type=Path,
        default=Path("docs/edc-v1.1/canonical_data_dictionary_v1.1.csv"),
        help="Path to canonical_data_dictionary_v1.1.csv",
    )
    parser.add_argument(
        "--codelists",
        type=Path,
        default=Path("docs/edc-v1.1/canonical_codelists_v1.1.csv"),
        help="Path to canonical_codelists_v1.1.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/edc-v1.1/redcap"),
        help="Output directory for REDCap package",
    )
    return parser.parse_args()


def load_canonical_fields(path: Path) -> list[CanonicalField]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                CanonicalField(
                    name=row["field_name"],
                    section=row["section"],
                    field_type=row["type"],
                    units=row["units"],
                    required_level=row["required_level"],
                    codelist=row["codelist"],
                    description_ru=row["description_ru"],
                )
            )
    return rows


def load_codelists(path: Path) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open("r", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            grouped[row["list_name"]].append(row)
    for list_name in grouped:
        grouped[list_name].sort(key=lambda item: item["canonical_code"])
    return grouped


def build_redcap_codes(codelists: dict[str, list[dict[str, str]]]) -> dict[str, dict[str, str]]:
    redcap_codes: dict[str, dict[str, str]] = {}
    for list_name, rows in codelists.items():
        code_map: dict[str, str] = {}
        if list_name == "YES_NO":
            code_map["yes"] = "1"
            code_map["no"] = "0"
        else:
            ordered_codes = ordered_list_codes(list_name, rows)
            for idx, canonical_code in enumerate(ordered_codes, start=1):
                code_map[canonical_code] = str(idx)
        redcap_codes[list_name] = code_map
    return redcap_codes


def choices_string(list_name: str, rows: list[dict[str, str]], code_map: dict[str, str]) -> str:
    parts = []
    ordered_codes = ["yes", "no"] if list_name == "YES_NO" else ordered_list_codes(list_name, rows)
    for canonical_code in ordered_codes:
        if canonical_code not in code_map:
            continue
        row = next(row for row in rows if row["canonical_code"] == canonical_code)
        label = row["label_en"] or canonical_code.replace("_", " ").title()
        parts.append(f"{code_map[canonical_code]}, {label}")
    return " | ".join(parts)


def resolve_branching(
    field_name: str,
    redcap_codes: dict[str, dict[str, str]],
) -> str:
    template = BRANCHING_BY_FIELD.get(field_name, "")
    if not template:
        return ""
    replacements = {
        "{YES_NO_YES}": redcap_codes["YES_NO"]["yes"],
        "{QUALITY_STATUS_REPEAT}": redcap_codes["QUALITY_STATUS"]["repeat"],
        "{QUALITY_STATUS_REJECT}": redcap_codes["QUALITY_STATUS"]["reject"],
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    return template


def ordered_list_codes(list_name: str, rows: list[dict[str, str]]) -> list[str]:
    canonical_codes = [row["canonical_code"] for row in rows]
    preferred = LIST_CODE_ORDER.get(list_name, [])
    if not preferred:
        return canonical_codes
    ordered = [code for code in preferred if code in canonical_codes]
    ordered.extend(code for code in canonical_codes if code not in ordered)
    return ordered


def redcap_field_type(field: CanonicalField) -> str:
    if field.name in DERIVED_FORMULAS:
        return "calc"
    if field.field_type == "enum[]":
        return "checkbox"
    if field.field_type == "enum":
        return "dropdown"
    if field.field_type == "bool":
        return "yesno"
    if field.field_type == "datetime":
        return "text"
    if field.field_type in {"float", "int"}:
        return "text"
    if field.field_type == "float[]":
        return "notes"
    if field.name in LONG_TEXT_FIELDS:
        return "notes"
    return "text"


def text_validation(field: CanonicalField) -> tuple[str, str, str]:
    if field.field_type == "datetime":
        return ("datetime_ymd", "", "")
    if field.field_type == "int":
        return ("integer", "", "")
    if field.field_type == "float":
        return ("number", "", "")
    return ("", "", "")


def field_note(field: CanonicalField) -> str:
    note_parts = []
    if field.units and field.units != "-":
        note_parts.append(f"Units: {field.units}")
    if field.required_level == "C":
        note_parts.append("Conditional field.")
    return " ".join(note_parts)


def required_flag(field: CanonicalField) -> str:
    if field.name in DERIVED_FORMULAS:
        return ""
    if field.field_type in {"enum[]", "float[]"}:
        return ""
    if field.required_level == "M":
        return "y"
    return ""


def build_rows(
    fields: list[CanonicalField],
    codelists: dict[str, list[dict[str, str]]],
    redcap_codes: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    rows.append(
        {
            "Variable / Field Name": "record_id",
            "Form Name": "identification",
            "Section Header": "Record",
            "Field Type": "text",
            "Field Label": "Record ID",
            "Choices, Calculations, OR Slider Labels": "",
            "Field Note": "Autogenerated import profile v1.1",
            "Text Validation Type OR Show Slider Number": "",
            "Text Validation Min": "",
            "Text Validation Max": "",
            "Identifier?": "",
            "Branching Logic (Show field only if...)": "",
            "Required Field?": "y",
            "Custom Alignment": "",
            "Question Number (surveys only)": "",
            "Matrix Group Name": "",
            "Matrix Ranking?": "",
            "Field Annotation": "",
        }
    )

    sorted_fields = sorted(fields, key=lambda item: (item.section, item.name))
    previous_section = None

    for field in sorted_fields:
        section_header = ""
        if field.section != previous_section:
            fallback_title = field.section.replace("_", " ").title()
            section_header = SECTION_TITLES.get(field.section, fallback_title)
        previous_section = field.section

        field_type = redcap_field_type(field)
        choices = ""
        if field_type in {"dropdown", "checkbox"} and field.codelist in codelists:
            choices = choices_string(
                field.codelist,
                codelists[field.codelist],
                redcap_codes[field.codelist],
            )
        if field_type == "calc":
            choices = DERIVED_FORMULAS[field.name]

        validation, val_min, val_max = text_validation(field)
        branching = resolve_branching(field.name, redcap_codes)
        annotation = "@HIDDEN" if field.name in HIDDEN_FIELDS else ""

        row = {
            "Variable / Field Name": field.name,
            "Form Name": field.section,
            "Section Header": section_header,
            "Field Type": field_type,
            "Field Label": field.description_ru or field.name,
            "Choices, Calculations, OR Slider Labels": choices,
            "Field Note": field_note(field),
            "Text Validation Type OR Show Slider Number": validation,
            "Text Validation Min": val_min,
            "Text Validation Max": val_max,
            "Identifier?": "y" if field.name in IDENTIFIER_FIELDS else "",
            "Branching Logic (Show field only if...)": branching,
            "Required Field?": required_flag(field),
            "Custom Alignment": "",
            "Question Number (surveys only)": "",
            "Matrix Group Name": "quality_reason_binary"
            if field.name.startswith("qr_") and field.field_type == "bool"
            else "",
            "Matrix Ranking?": "",
            "Field Annotation": annotation,
        }
        rows.append(row)

    return rows


def build_choice_code_map_rows(
    codelists: dict[str, list[dict[str, str]]],
    redcap_codes: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    rows = []
    for list_name in sorted(codelists):
        for item in codelists[list_name]:
            canonical_code = item["canonical_code"]
            if canonical_code not in redcap_codes[list_name]:
                continue
            rows.append(
                {
                    "list_name": list_name,
                    "canonical_code": canonical_code,
                    "redcap_code": redcap_codes[list_name][canonical_code],
                    "label_en": item["label_en"],
                    "label_ru": item["label_ru"],
                }
            )
    return rows


def build_branching_rows(
    redcap_codes: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    rows = []
    for field_name in sorted(BRANCHING_BY_FIELD):
        rows.append(
            {
                "field_name": field_name,
                "branching_logic": resolve_branching(field_name, redcap_codes),
            }
        )
    return rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_readme(output_dir: Path, row_count: int) -> None:
    readme = output_dir / "README.md"
    text = "\n".join(
        [
            "# REDCap Import Profile v1.1",
            "",
            "Generated by `scripts/generate_redcap_profile_v1_1.py`.",
            "",
            "## Files",
            f"- `redcap_data_dictionary_v1.1.csv` ({row_count} rows including `record_id`)",
            "- `redcap_choice_code_map_v1.1.csv` (canonical value to REDCap code map)",
            "- `redcap_branching_logic_v1.1.csv` (resolved conditional display logic)",
            "",
            "## Import workflow",
            "1. Create a new REDCap project in Development mode.",
            "2. Open *Data Dictionary* -> *Upload File*.",
            "3. Upload `redcap_data_dictionary_v1.1.csv`.",
            "4. Validate branching logic for PVR/repeat/deviation/AE fields.",
            "5. Freeze codebook and move project to Production after UAT.",
            "",
            "## Regeneration",
            "```bash",
            "python3 scripts/generate_redcap_profile_v1_1.py \\",
            "  --dictionary docs/edc-v1.1/canonical_data_dictionary_v1.1.csv \\",
            "  --codelists docs/edc-v1.1/canonical_codelists_v1.1.csv \\",
            "  --output-dir docs/edc-v1.1/redcap",
            "```",
        ]
    )
    readme.write_text(text + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    fields = load_canonical_fields(args.dictionary)
    codelists = load_codelists(args.codelists)
    redcap_codes = build_redcap_codes(codelists)

    dictionary_rows = build_rows(fields, codelists, redcap_codes)
    choice_map_rows = build_choice_code_map_rows(codelists, redcap_codes)
    branching_rows = build_branching_rows(redcap_codes)

    write_csv(args.output_dir / "redcap_data_dictionary_v1.1.csv", REDCAP_COLUMNS, dictionary_rows)
    write_csv(
        args.output_dir / "redcap_choice_code_map_v1.1.csv",
        ["list_name", "canonical_code", "redcap_code", "label_en", "label_ru"],
        choice_map_rows,
    )
    write_csv(
        args.output_dir / "redcap_branching_logic_v1.1.csv",
        ["field_name", "branching_logic"],
        branching_rows,
    )
    write_readme(args.output_dir, row_count=len(dictionary_rows))

    print(f"Generated REDCap profile in: {args.output_dir}")
    print(f"Dictionary rows: {len(dictionary_rows)}")


if __name__ == "__main__":
    main()
