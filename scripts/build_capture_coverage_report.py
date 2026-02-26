#!/usr/bin/env python3
"""Build capture coverage CSV/PDF and SHA-256 manifest for CI workflow."""

from __future__ import annotations

import argparse
import csv
import hashlib
import sqlite3
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


@dataclass
class CoverageFilters:
    site_id: str = ""
    sync_id: str = ""
    subject_id: str = ""
    operator_id: str = ""
    platform: str = ""
    capture_mode: str = ""
    quality_status: str = "all"


def _norm(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _to_int(value: Any) -> int | None:
    text = _norm(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _paired_matches_filters(row: dict[str, Any], filters: CoverageFilters) -> bool:
    if filters.site_id and _norm(row.get("site_id")) != filters.site_id:
        return False
    if filters.sync_id and _norm(row.get("sync_id")) != filters.sync_id:
        return False
    if filters.subject_id and _norm(row.get("subject_id")) != filters.subject_id:
        return False
    if filters.operator_id and _norm(row.get("operator_id")) != filters.operator_id:
        return False
    if filters.platform and _norm(row.get("platform")) != filters.platform:
        return False
    if filters.capture_mode and _norm(row.get("capture_mode")) != filters.capture_mode:
        return False
    return not (
        filters.quality_status != "all"
        and _norm(row.get("app_quality_status")).lower() != filters.quality_status
    )


def _capture_matches_filters(row: dict[str, Any], filters: CoverageFilters) -> bool:
    if filters.site_id and _norm(row.get("site_id")) != filters.site_id:
        return False
    if filters.sync_id and _norm(row.get("sync_id")) != filters.sync_id:
        return False
    if filters.subject_id and _norm(row.get("subject_id")) != filters.subject_id:
        return False
    if filters.operator_id and _norm(row.get("operator_id")) != filters.operator_id:
        return False
    if filters.platform and _norm(row.get("platform")) != filters.platform:
        return False
    return not (
        filters.capture_mode and _norm(row.get("capture_mode")) != filters.capture_mode
    )


def _fetch_csv_rows(url: str, headers: dict[str, str]) -> list[dict[str, Any]]:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read().decode("utf-8")
    return [dict(row) for row in csv.DictReader(payload.splitlines())]


def load_rows_from_api(
    base_url: str,
    api_key: str,
    filters: CoverageFilters,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = base_url.rstrip("/")
    if not base:
        raise ValueError("--api-base-url is required when --source-mode=api")

    headers: dict[str, str] = {}
    if api_key:
        headers["x-api-key"] = api_key

    server_query: dict[str, str] = {}
    if filters.site_id:
        server_query["site_id"] = filters.site_id
    if filters.sync_id:
        server_query["sync_id"] = filters.sync_id
    if filters.operator_id:
        server_query["operator_id"] = filters.operator_id

    query = urllib.parse.urlencode(server_query)
    paired_url = f"{base}/api/v1/paired-measurements.csv"
    capture_url = f"{base}/api/v1/capture-packages.csv"
    if query:
        paired_url = f"{paired_url}?{query}"
        capture_url = f"{capture_url}?{query}"

    paired_rows = [
        row
        for row in _fetch_csv_rows(paired_url, headers)
        if _paired_matches_filters(row, filters)
    ]
    capture_rows = [
        row
        for row in _fetch_csv_rows(capture_url, headers)
        if _capture_matches_filters(row, filters)
    ]
    return paired_rows, capture_rows


def load_rows_from_db(
    db_path: Path,
    filters: CoverageFilters,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not db_path.exists():
        raise FileNotFoundError(f"DB file does not exist: {db_path}")

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        paired_rows = [
            dict(row)
            for row in connection.execute(
                """
                SELECT
                    id,
                    session_id,
                    sync_id,
                    site_id,
                    subject_id,
                    operator_id,
                    attempt_number,
                    platform,
                    capture_mode,
                    app_quality_status
                FROM paired_measurements
                """
            )
        ]
        capture_rows = [
            dict(row)
            for row in connection.execute(
                """
                SELECT
                    id,
                    session_id,
                    sync_id,
                    site_id,
                    subject_id,
                    operator_id,
                    attempt_number,
                    platform,
                    capture_mode,
                    paired_measurement_id
                FROM capture_packages
                """
            )
        ]

    paired_rows = [row for row in paired_rows if _paired_matches_filters(row, filters)]
    capture_rows = [row for row in capture_rows if _capture_matches_filters(row, filters)]
    return paired_rows, capture_rows


def build_summary_row(
    paired_rows: list[dict[str, Any]],
    capture_rows: list[dict[str, Any]],
    filters: CoverageFilters,
) -> dict[str, Any]:
    capture_by_pair_id: set[int] = set()
    capture_by_identity: set[tuple[str, int, str, str, str]] = set()

    for row in capture_rows:
        paired_measurement_id = _to_int(row.get("paired_measurement_id"))
        if paired_measurement_id is not None:
            capture_by_pair_id.add(paired_measurement_id)

        identity = (
            _norm(row.get("session_id")),
            _to_int(row.get("attempt_number")) or 0,
            _norm(row.get("site_id")),
            _norm(row.get("subject_id")),
            _norm(row.get("sync_id")),
        )
        capture_by_identity.add(identity)

    quality_distribution = {"valid": 0, "repeat": 0, "reject": 0}
    match_distribution = {"paired_id": 0, "session_identity": 0, "none": 0}

    for row in paired_rows:
        quality_status = _norm(row.get("app_quality_status")).lower()
        if quality_status in quality_distribution:
            quality_distribution[quality_status] += 1

        paired_id = _to_int(row.get("id")) or 0
        identity = (
            _norm(row.get("session_id")),
            _to_int(row.get("attempt_number")) or 0,
            _norm(row.get("site_id")),
            _norm(row.get("subject_id")),
            _norm(row.get("sync_id")),
        )

        if paired_id in capture_by_pair_id:
            match_distribution["paired_id"] += 1
        elif identity in capture_by_identity:
            match_distribution["session_identity"] += 1
        else:
            match_distribution["none"] += 1

    paired_total = len(paired_rows)
    paired_without_capture = match_distribution["none"]
    paired_with_capture = paired_total - paired_without_capture
    coverage_ratio = (paired_with_capture / paired_total) if paired_total > 0 else 0.0

    generated_at = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    return {
        "generated_at": generated_at,
        "site_id": filters.site_id,
        "sync_id": filters.sync_id,
        "subject_id": filters.subject_id,
        "operator_id": filters.operator_id,
        "platform": filters.platform,
        "capture_mode": filters.capture_mode,
        "quality_status": filters.quality_status,
        "paired_total": paired_total,
        "paired_with_capture": paired_with_capture,
        "paired_without_capture": paired_without_capture,
        "coverage_ratio": f"{coverage_ratio:.6f}",
        "quality_valid": quality_distribution["valid"],
        "quality_repeat": quality_distribution["repeat"],
        "quality_reject": quality_distribution["reject"],
        "match_paired_id": match_distribution["paired_id"],
        "match_session_identity": match_distribution["session_identity"],
        "match_none": match_distribution["none"],
    }


def write_outputs(
    summary_row: dict[str, Any],
    output_csv: Path,
    output_pdf: Path,
    sha256_file: Path,
) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    sha256_file.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "generated_at",
        "site_id",
        "sync_id",
        "subject_id",
        "operator_id",
        "platform",
        "capture_mode",
        "quality_status",
        "paired_total",
        "paired_with_capture",
        "paired_without_capture",
        "coverage_ratio",
        "quality_valid",
        "quality_repeat",
        "quality_reject",
        "match_paired_id",
        "match_session_identity",
        "match_none",
    ]

    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(summary_row)

    payload = output_csv.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    sha256_file.write_text(f"{digest}  {output_csv.name}\n", encoding="utf-8")

    sheet = canvas.Canvas(str(output_pdf), pagesize=A4)
    _, height = A4
    y = [height - 42]

    def line(text: str, step: int = 16) -> None:
        sheet.drawString(42, y[0], text)
        y[0] -= step

    line("Capture Coverage Summary")
    line(f"Generated at: {summary_row['generated_at']}")
    line(f"Site: {summary_row['site_id'] or '-'}")
    line(f"Sync ID: {summary_row['sync_id'] or '-'}")
    line(f"Quality status: {summary_row['quality_status']}")
    y[0] -= 6
    line(
        f"Paired total: {summary_row['paired_total']}, "
        f"with capture: {summary_row['paired_with_capture']}, "
        f"without capture: {summary_row['paired_without_capture']}"
    )
    line(f"Coverage ratio: {float(summary_row['coverage_ratio']) * 100:.1f}%")
    line(
        "Quality distribution: "
        f"valid={summary_row['quality_valid']}, "
        f"repeat={summary_row['quality_repeat']}, "
        f"reject={summary_row['quality_reject']}"
    )
    line(
        "Match modes: "
        f"paired_id={summary_row['match_paired_id']}, "
        f"session_identity={summary_row['match_session_identity']}, "
        f"none={summary_row['match_none']}"
    )
    sheet.showPage()
    sheet.save()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build capture coverage summary CSV/PDF from Clinical Hub API or DB.",
    )
    parser.add_argument("--source-mode", choices=["api", "db"], required=True)
    parser.add_argument("--db-path", help="SQLite DB path when source-mode=db")
    parser.add_argument("--api-base-url", help="Clinical Hub API base URL when source-mode=api")
    parser.add_argument("--api-key", default="", help="Optional API key for API requests")

    parser.add_argument("--site-id", default="")
    parser.add_argument("--sync-id", default="")
    parser.add_argument("--subject-id", default="")
    parser.add_argument("--operator-id", default="")
    parser.add_argument("--platform", default="")
    parser.add_argument("--capture-mode", default="")
    parser.add_argument(
        "--quality-status",
        choices=["all", "valid", "repeat", "reject"],
        default="all",
    )

    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-pdf", required=True)
    parser.add_argument("--sha256-file", required=True)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    filters = CoverageFilters(
        site_id=(args.site_id or "").strip(),
        sync_id=(args.sync_id or "").strip(),
        subject_id=(args.subject_id or "").strip(),
        operator_id=(args.operator_id or "").strip(),
        platform=(args.platform or "").strip(),
        capture_mode=(args.capture_mode or "").strip(),
        quality_status=(args.quality_status or "all").strip().lower() or "all",
    )

    if args.source_mode == "api":
        paired_rows, capture_rows = load_rows_from_api(
            base_url=(args.api_base_url or "").strip(),
            api_key=(args.api_key or "").strip(),
            filters=filters,
        )
    else:
        if not args.db_path:
            parser.error("--db-path is required when --source-mode=db")
        paired_rows, capture_rows = load_rows_from_db(
            db_path=Path(args.db_path),
            filters=filters,
        )

    summary_row = build_summary_row(paired_rows, capture_rows, filters)
    write_outputs(
        summary_row=summary_row,
        output_csv=Path(args.output_csv),
        output_pdf=Path(args.output_pdf),
        sha256_file=Path(args.sha256_file),
    )

    print(f"Capture coverage CSV saved: {args.output_csv}")
    print(f"Capture coverage PDF saved: {args.output_pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
