#!/usr/bin/env python3
"""Build a nightly Clinical Hub quality snapshot for optional report upload."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from uroflow_mobile.clinical_hub import build_method_comparison_summary

SNAPSHOT_SCHEMA_VERSION = "clinical_hub_nightly_snapshot_v1"
METHOD_COMPARISON_FILENAME = "method_comparison_summary.json"
GATE_SUMMARY_FILENAME = "gate_summary.json"
MANIFEST_FILENAME = "clinical_hub_nightly_snapshot_manifest.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", default="data/clinical_hub.db", help="Clinical Hub SQLite DB.")
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory for generated snapshot files.",
    )
    parser.add_argument(
        "--gate-summary-json",
        required=True,
        help="Gate summary JSON produced by uroflow-mobile evaluate-gates.",
    )
    parser.add_argument(
        "--report-date",
        help="Report date in YYYY-MM-DD format; defaults to UTC date.",
    )
    parser.add_argument("--site-id", help="Optional Clinical Hub site filter and report site_id.")
    parser.add_argument("--sync-id", help="Optional sync_id filter.")
    parser.add_argument("--subject-id", help="Optional subject filter.")
    parser.add_argument("--operator-id", help="Optional operator_id filter.")
    parser.add_argument("--platform", choices=["ios", "android"], help="Optional platform filter.")
    parser.add_argument(
        "--capture-mode",
        choices=["water_impact", "jet_in_air_assist", "fallback_non_water"],
        help="Optional capture mode filter.",
    )
    parser.add_argument(
        "--quality-status",
        choices=["valid", "repeat", "reject", "all"],
        default="valid",
        help="Quality status subset for method comparison (default: valid).",
    )
    parser.add_argument("--package-version", default="v2.8")
    parser.add_argument("--model-id")
    parser.add_argument("--dataset-id")
    parser.add_argument("--notes")
    return parser.parse_args()


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_hex(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative_to_output(path: Path, output_dir: Path) -> str:
    return str(path.relative_to(output_dir))


def _build_post_command(
    *,
    site_id: str | None,
    report_date: str,
    package_version: str | None,
    model_id: str | None,
    dataset_id: str | None,
    notes: str | None,
) -> list[str]:
    command = [
        "python",
        "scripts/post_pilot_reports_to_clinical_hub.py",
        "--base-url",
        "$CLINICAL_HUB_URL",
        "--api-key",
        "$CLINICAL_HUB_API_KEY",
        "--site-id",
        site_id or "$CLINICAL_HUB_SITE_ID",
        "--report-date",
        report_date,
    ]
    if package_version:
        command.extend(["--package-version", package_version])
    if model_id:
        command.extend(["--model-id", model_id])
    if dataset_id:
        command.extend(["--dataset-id", dataset_id])
    if notes:
        command.extend(["--notes", notes])
    command.extend(
        [
            "--method-comparison-summary-json",
            str(Path("$SNAPSHOT_DIR") / METHOD_COMPARISON_FILENAME),
            "--gate-summary-json",
            str(Path("$SNAPSHOT_DIR") / GATE_SUMMARY_FILENAME),
        ]
    )
    return command


def build_snapshot(
    *,
    db_path: Path,
    output_dir: Path,
    gate_summary_json: Path,
    report_date: str | None,
    site_id: str | None,
    sync_id: str | None,
    subject_id: str | None,
    operator_id: str | None,
    platform: str | None,
    capture_mode: str | None,
    quality_status: str,
    package_version: str | None,
    model_id: str | None,
    dataset_id: str | None,
    notes: str | None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    effective_report_date = report_date or datetime.now(timezone.utc).date().isoformat()
    normalized_quality_status = None if quality_status == "all" else quality_status

    summary = build_method_comparison_summary(
        db_path=db_path,
        site_id=site_id,
        sync_id=sync_id,
        subject_id=subject_id,
        operator_id=operator_id,
        platform=platform,  # type: ignore[arg-type]
        capture_mode=capture_mode,  # type: ignore[arg-type]
        quality_status=normalized_quality_status,  # type: ignore[arg-type]
    )
    method_payload = summary.model_dump(mode="json")
    method_path = output_dir / METHOD_COMPARISON_FILENAME
    _write_json(method_path, method_payload)

    gate_payload = _load_json_object(gate_summary_json, "gate summary JSON")
    gate_path = output_dir / GATE_SUMMARY_FILENAME
    _write_json(gate_path, gate_payload)

    reports = [
        {
            "report_type": "method_comparison_summary",
            "path": _relative_to_output(method_path, output_dir),
            "sha256": _sha256_hex(method_path),
            "records_matched_filters": method_payload.get("records_matched_filters"),
            "records_considered": method_payload.get("records_considered"),
        },
        {
            "report_type": "gate_summary",
            "path": _relative_to_output(gate_path, output_dir),
            "sha256": _sha256_hex(gate_path),
            "overall_passed": gate_payload.get("overall_passed"),
            "evaluated_gates": gate_payload.get("evaluated_gates"),
        },
    ]
    manifest = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "generated_at": _utc_timestamp(),
        "report_date": effective_report_date,
        "site_id": site_id,
        "package_version": package_version,
        "model_id": model_id,
        "dataset_id": dataset_id,
        "notes": notes,
        "filters": {
            "site_id": site_id,
            "sync_id": sync_id,
            "subject_id": subject_id,
            "operator_id": operator_id,
            "platform": platform,
            "capture_mode": capture_mode,
            "quality_status": quality_status,
        },
        "reports": reports,
        "post_command": _build_post_command(
            site_id=site_id,
            report_date=effective_report_date,
            package_version=package_version,
            model_id=model_id,
            dataset_id=dataset_id,
            notes=notes,
        ),
    }
    manifest_path = output_dir / MANIFEST_FILENAME
    manifest["manifest_path"] = _relative_to_output(manifest_path, output_dir)
    _write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    args = _parse_args()
    manifest = build_snapshot(
        db_path=Path(args.db_path),
        output_dir=Path(args.output_dir),
        gate_summary_json=Path(args.gate_summary_json),
        report_date=args.report_date,
        site_id=args.site_id,
        sync_id=args.sync_id,
        subject_id=args.subject_id,
        operator_id=args.operator_id,
        platform=args.platform,
        capture_mode=args.capture_mode,
        quality_status=args.quality_status,
        package_version=args.package_version,
        model_id=args.model_id,
        dataset_id=args.dataset_id,
        notes=args.notes,
    )
    print(f"Clinical Hub nightly snapshot exported: {Path(args.output_dir).resolve()}")
    print(f"Report date: {manifest['report_date']}")
    for report in manifest["reports"]:
        print(f"{report['report_type']}: {report['path']} sha256={report['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
