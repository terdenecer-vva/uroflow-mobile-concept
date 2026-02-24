#!/usr/bin/env python3
"""Extract bench BOM v0.2 workbook into analysis-ready CSV artifacts."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--xlsx-path",
        type=Path,
        required=True,
        help="Path to Uroflow_Bench_BOM_Variants_v0.2.xlsx",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/bench-package-v0.2"),
        help="Output directory for extracted CSV files",
    )
    return parser.parse_args()


def normalize_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.6g}"
    return str(value).strip()


def read_sheet_rows(workbook, sheet_name: str) -> tuple[list[str], list[list[str]]]:
    worksheet = workbook[sheet_name]
    header = [normalize_cell(cell.value) for cell in worksheet[1]]
    rows = []
    for row_number in range(2, worksheet.max_row + 1):
        values = [normalize_cell(cell.value) for cell in worksheet[row_number]]
        if not any(values):
            continue
        rows.append(values)
    return header, rows


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Missing dependency openpyxl. Install with `pip install openpyxl`."
        ) from exc

    workbook = openpyxl.load_workbook(args.xlsx_path, data_only=True)

    overview_header, overview_rows = read_sheet_rows(workbook, "Overview")
    write_csv(args.output_dir / "bench_overview_v0.2.csv", overview_header, overview_rows)

    bom_rows: list[list[str]] = []
    bom_header: list[str] | None = None
    for sheet_name in ("BOM_Low", "BOM_Mid", "BOM_High"):
        header, rows = read_sheet_rows(workbook, sheet_name)
        level = sheet_name.split("_", 1)[1].lower()
        if bom_header is None:
            bom_header = ["Уровень", *header]
        for row in rows:
            bom_rows.append([level, *row])
    write_csv(args.output_dir / "bench_bom_flat_v0.2.csv", bom_header or [], bom_rows)

    line_item_rows = [
        row
        for row in bom_rows
        if len(row) >= 7
        and row[1]
        and row[2]
        and row[1] != "Примечание:"
    ]
    write_csv(args.output_dir / "bench_bom_line_items_v0.2.csv", bom_header or [], line_item_rows)

    summary = defaultdict(lambda: {"required": 0, "optional": 0, "total": 0})
    for row in line_item_rows:
        level = row[0]
        required = row[5].lower()
        summary[level]["total"] += 1
        if required == "да":
            summary[level]["required"] += 1
        else:
            summary[level]["optional"] += 1
    summary_rows = [
        [level, str(values["total"]), str(values["required"]), str(values["optional"])]
        for level, values in sorted(summary.items())
    ]
    write_csv(
        args.output_dir / "bench_bom_summary_v0.2.csv",
        ["Уровень", "Всего позиций", "Обязательных", "Опциональных"],
        summary_rows,
    )

    wiring_header, wiring_rows = read_sheet_rows(workbook, "Wiring")
    write_csv(args.output_dir / "bench_wiring_v0.2.csv", wiring_header, wiring_rows)

    mechanics_header, mechanics_rows = read_sheet_rows(workbook, "Mechanics")
    write_csv(args.output_dir / "bench_mechanics_v0.2.csv", mechanics_header, mechanics_rows)

    print(f"Workbook extracted to: {args.output_dir}")
    print(f"Overview rows: {len(overview_rows)}")
    print(f"BOM rows: {len(bom_rows)}")
    print(f"BOM line items: {len(line_item_rows)}")
    print(f"Wiring rows: {len(wiring_rows)}")
    print(f"Mechanics rows: {len(mechanics_rows)}")


if __name__ == "__main__":
    main()
