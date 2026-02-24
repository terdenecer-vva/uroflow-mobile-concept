#!/usr/bin/env python3
"""Generate OpenClinica import profile from canonical EDC v1.1 files."""

from __future__ import annotations

import argparse
import csv
import re
import xml.etree.ElementTree as et
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

ODM_NS = "http://www.cdisc.org/ns/odm/v1.3"
et.register_namespace("", ODM_NS)

STUDY_OID = "STUDY.UFLOW.SMARTPHONE"
METADATA_OID = "MDV.UFLOW.EDC.V1_1"
EVENT_OID = "SE.UFLOW.VISIT"
EVENT_NAME = "Uroflow Visit"

SECTION_ORDER = [
    "identification",
    "capture_setup",
    "screening",
    "test_conditions",
    "event_timing",
    "reference_uroflow",
    "app_output",
    "quality",
    "pvr",
    "privacy_export",
    "safety",
    "derived",
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

FIELD_TYPE_TO_ODM = {
    "int": "integer",
    "float": "float",
    "datetime": "datetime",
    "bool": "text",
    "enum": "text",
    "enum[]": "text",
    "float[]": "text",
    "string": "text",
}

FIELD_TYPE_TO_RESPONSE = {
    "bool": "single_select",
    "enum": "single_select",
    "enum[]": "multi_select",
    "float[]": "json_text",
}


@dataclass
class CanonicalField:
    name: str
    section: str
    field_type: str
    units: str
    required_level: str
    codelist: str
    description_ru: str
    phi_sensitive: str

    @property
    def is_required(self) -> bool:
        return self.required_level == "M"

    @property
    def response_type(self) -> str:
        return FIELD_TYPE_TO_RESPONSE.get(self.field_type, "text")

    @property
    def odm_data_type(self) -> str:
        return FIELD_TYPE_TO_ODM.get(self.field_type, "text")

    @property
    def effective_codelist(self) -> str:
        if self.codelist:
            return self.codelist
        if self.field_type == "bool":
            return "YES_NO"
        return ""


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
        default=Path("docs/edc-v1.1/openclinica"),
        help="Output directory for OpenClinica package",
    )
    return parser.parse_args()


def sanitize_oid(raw: str, prefix: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]", "_", raw).upper()
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    truncated = normalized[:36]
    return f"{prefix}.{truncated}"


def section_sort_key(section: str) -> tuple[int, str]:
    if section in SECTION_ORDER:
        return (SECTION_ORDER.index(section), section)
    return (999, section)


def load_fields(path: Path) -> list[CanonicalField]:
    fields = []
    with path.open("r", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            fields.append(
                CanonicalField(
                    name=row["field_name"],
                    section=row["section"],
                    field_type=row["type"],
                    units=row["units"],
                    required_level=row["required_level"],
                    codelist=row["codelist"],
                    description_ru=row["description_ru"],
                    phi_sensitive=row["phi_sensitive"],
                )
            )
    return fields


def load_codelists(path: Path) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open("r", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            grouped[row["list_name"]].append(row)
    for list_name in grouped:
        grouped[list_name].sort(key=lambda row: row["canonical_code"])
    return grouped


def build_item_dictionary_rows(fields: list[CanonicalField]) -> list[dict[str, str]]:
    rows = []
    sorted_fields = sorted(fields, key=lambda item: (section_sort_key(item.section), item.name))
    for field in sorted_fields:
        fallback_title = field.section.replace("_", " ").title()
        rows.append(
            {
                "item_oid": sanitize_oid(field.name, "I"),
                "field_name": field.name,
                "form_name": field.section,
                "section_title": SECTION_TITLES.get(field.section, fallback_title),
                "odm_data_type": field.odm_data_type,
                "response_type": field.response_type,
                "required": "yes" if field.is_required else "no",
                "code_list_oid": sanitize_oid(field.effective_codelist, "CL")
                if field.effective_codelist
                else "",
                "units": field.units,
                "phi_sensitive": field.phi_sensitive,
                "label_ru": field.description_ru or field.name,
            }
        )
    return rows


def build_codelist_rows(codelists: dict[str, list[dict[str, str]]]) -> list[dict[str, str]]:
    rows = []
    for list_name in sorted(codelists):
        code_list_oid = sanitize_oid(list_name, "CL")
        for row in codelists[list_name]:
            rows.append(
                {
                    "code_list_oid": code_list_oid,
                    "list_name": list_name,
                    "coded_value": row["canonical_code"],
                    "decode_en": row["label_en"],
                    "decode_ru": row["label_ru"],
                }
            )
    return rows


def build_event_form_map_rows(fields: list[CanonicalField]) -> list[dict[str, str]]:
    rows = []
    sections = sorted({field.section for field in fields}, key=section_sort_key)
    for section in sections:
        rows.append(
            {
                "study_event_oid": EVENT_OID,
                "study_event_name": EVENT_NAME,
                "form_oid": sanitize_oid(section, "F"),
                "form_name": SECTION_TITLES.get(section, section.replace("_", " ").title()),
                "item_group_oid": sanitize_oid(section, "IG"),
                "item_group_name": SECTION_TITLES.get(section, section.replace("_", " ").title()),
                "repeating": "no",
            }
        )
    return rows


def qname(tag: str) -> str:
    return f"{{{ODM_NS}}}{tag}"


def build_odm_xml(
    fields: list[CanonicalField],
    codelists: dict[str, list[dict[str, str]]],
) -> et.ElementTree:

    root = et.Element(
        qname("ODM"),
        {
            "FileType": "Snapshot",
            "Granularity": "Metadata",
            "ODMVersion": "1.3.2",
            "CreationDateTime": "2026-02-24T00:00:00",
        },
    )
    study = et.SubElement(root, qname("Study"), {"OID": STUDY_OID})
    globals_node = et.SubElement(study, qname("GlobalVariables"))
    et.SubElement(globals_node, qname("StudyName")).text = "Uroflow Smartphone EDC"
    et.SubElement(globals_node, qname("StudyDescription")).text = "OpenClinica profile v1.1"
    et.SubElement(globals_node, qname("ProtocolName")).text = "UFLOW-EDC-V1_1"

    metadata = et.SubElement(
        study,
        qname("MetaDataVersion"),
        {"OID": METADATA_OID, "Name": "Uroflow EDC v1.1", "Description": "Auto-generated profile"},
    )

    protocol = et.SubElement(metadata, qname("Protocol"))
    et.SubElement(
        protocol,
        qname("StudyEventRef"),
        {"StudyEventOID": EVENT_OID, "Mandatory": "Yes"},
    )

    sections = sorted({field.section for field in fields}, key=section_sort_key)
    et.SubElement(
        metadata,
        qname("StudyEventDef"),
        {
            "OID": EVENT_OID,
            "Name": EVENT_NAME,
            "Repeating": "No",
            "Type": "Scheduled",
        },
    )
    study_event_def = metadata.findall(qname("StudyEventDef"))[-1]

    fields_by_section: dict[str, list[CanonicalField]] = defaultdict(list)
    for field in fields:
        fields_by_section[field.section].append(field)
    for section in fields_by_section:
        fields_by_section[section].sort(key=lambda item: item.name)

    for order_number, section in enumerate(sections, start=1):
        form_oid = sanitize_oid(section, "F")
        item_group_oid = sanitize_oid(section, "IG")
        section_title = SECTION_TITLES.get(section, section.replace("_", " ").title())

        et.SubElement(
            study_event_def,
            qname("FormRef"),
            {"FormOID": form_oid, "Mandatory": "Yes", "OrderNumber": str(order_number)},
        )

        form_def = et.SubElement(
            metadata,
            qname("FormDef"),
            {"OID": form_oid, "Name": section_title},
        )
        et.SubElement(
            form_def,
            qname("ItemGroupRef"),
            {"ItemGroupOID": item_group_oid, "Mandatory": "Yes", "OrderNumber": "1"},
        )

        item_group_def = et.SubElement(
            metadata,
            qname("ItemGroupDef"),
            {"OID": item_group_oid, "Name": section_title, "Repeating": "No"},
        )

        section_fields = fields_by_section[section]
        for index, field in enumerate(section_fields, start=1):
            item_oid = sanitize_oid(field.name, "I")
            et.SubElement(
                item_group_def,
                qname("ItemRef"),
                {
                    "ItemOID": item_oid,
                    "Mandatory": "Yes" if field.is_required else "No",
                    "OrderNumber": str(index),
                },
            )

    for field in sorted(fields, key=lambda item: (section_sort_key(item.section), item.name)):
        item_oid = sanitize_oid(field.name, "I")
        item_def = et.SubElement(
            metadata,
            qname("ItemDef"),
            {"OID": item_oid, "Name": field.name, "DataType": field.odm_data_type},
        )
        question = et.SubElement(item_def, qname("Question"))
        et.SubElement(question, qname("TranslatedText"), {"xml:lang": "ru"}).text = (
            field.description_ru or field.name
        )
        if field.effective_codelist:
            et.SubElement(
                item_def,
                qname("CodeListRef"),
                {"CodeListOID": sanitize_oid(field.effective_codelist, "CL")},
            )

    for list_name in sorted(codelists):
        code_list_oid = sanitize_oid(list_name, "CL")
        code_list = et.SubElement(
            metadata,
            qname("CodeList"),
            {"OID": code_list_oid, "Name": list_name, "DataType": "text"},
        )
        for row in codelists[list_name]:
            item = et.SubElement(
                code_list,
                qname("CodeListItem"),
                {"CodedValue": row["canonical_code"]},
            )
            decode = et.SubElement(item, qname("Decode"))
            translated = et.SubElement(decode, qname("TranslatedText"), {"xml:lang": "en"})
            translated.text = row["label_en"]

    return et.ElementTree(root)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_readme(output_dir: Path, item_count: int, list_count: int) -> None:
    text = "\n".join(
        [
            "# OpenClinica Import Profile v1.1",
            "",
            "Generated by `scripts/generate_openclinica_profile_v1_1.py`.",
            "",
            "## Files",
            f"- `openclinica_item_dictionary_v1.1.csv` ({item_count} items)",
            f"- `openclinica_code_lists_v1.1.csv` ({list_count} codelist entries)",
            "- `openclinica_event_form_map_v1.1.csv` (section-to-form mapping)",
            "- `openclinica_odm_v1.1.xml` (ODM metadata snapshot)",
            "",
            "## Import workflow",
            "1. Open OpenClinica study setup in a non-production environment.",
            "2. Import `openclinica_odm_v1.1.xml` into metadata designer.",
            "3. Verify forms and item order against `openclinica_event_form_map_v1.1.csv`.",
            "4. Validate codelists and required flags before production promotion.",
            "",
            "## Notes",
            "- `enum[]` fields are exported as text with multi-select semantics.",
            "- `float[]` fields are exported as text for serialized arrays.",
            "",
            "## Regeneration",
            "```bash",
            "python3 scripts/generate_openclinica_profile_v1_1.py \\",
            "  --dictionary docs/edc-v1.1/canonical_data_dictionary_v1.1.csv \\",
            "  --codelists docs/edc-v1.1/canonical_codelists_v1.1.csv \\",
            "  --output-dir docs/edc-v1.1/openclinica",
            "```",
        ]
    )
    (output_dir / "README.md").write_text(text + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    fields = load_fields(args.dictionary)
    codelists = load_codelists(args.codelists)

    item_rows = build_item_dictionary_rows(fields)
    codelist_rows = build_codelist_rows(codelists)
    event_form_rows = build_event_form_map_rows(fields)

    write_csv(
        args.output_dir / "openclinica_item_dictionary_v1.1.csv",
        [
            "item_oid",
            "field_name",
            "form_name",
            "section_title",
            "odm_data_type",
            "response_type",
            "required",
            "code_list_oid",
            "units",
            "phi_sensitive",
            "label_ru",
        ],
        item_rows,
    )
    write_csv(
        args.output_dir / "openclinica_code_lists_v1.1.csv",
        ["code_list_oid", "list_name", "coded_value", "decode_en", "decode_ru"],
        codelist_rows,
    )
    write_csv(
        args.output_dir / "openclinica_event_form_map_v1.1.csv",
        [
            "study_event_oid",
            "study_event_name",
            "form_oid",
            "form_name",
            "item_group_oid",
            "item_group_name",
            "repeating",
        ],
        event_form_rows,
    )

    tree = build_odm_xml(fields, codelists)
    et.indent(tree, space="  ")
    xml_path = args.output_dir / "openclinica_odm_v1.1.xml"
    xml_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)

    write_readme(args.output_dir, item_count=len(item_rows), list_count=len(codelist_rows))

    print(f"Generated OpenClinica profile in: {args.output_dir}")
    print(f"Items: {len(item_rows)} | Codelist rows: {len(codelist_rows)}")


if __name__ == "__main__":
    main()
