#!/usr/bin/env python3
"""Build a deterministic fallback Clinical Hub DB for coverage workflow smoke runs."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from uroflow_mobile.clinical_hub import ensure_clinical_hub_schema

FIXTURE_PAIRED_TOTAL = 220
FIXTURE_MISSING_CAPTURE_COUNT = 20
FIXTURE_FALLBACK_MATCH_COUNT = 20


def build_fixture_db(db_path: Path) -> None:
    if db_path.exists():
        db_path.unlink()

    ensure_clinical_hub_schema(db_path)

    now = datetime.now(timezone.utc).replace(microsecond=0)

    with sqlite3.connect(db_path) as connection:
        capture_package_count = FIXTURE_PAIRED_TOTAL - FIXTURE_MISSING_CAPTURE_COUNT
        direct_match_count = capture_package_count - FIXTURE_FALLBACK_MATCH_COUNT

        for index in range(FIXTURE_PAIRED_TOTAL):
            measured_at = (now - timedelta(minutes=index)).isoformat().replace("+00:00", "Z")
            session_id = f"SESSION-COV-{index + 1:03d}"
            sync_id = f"SYNC-COV-{(index // 2) + 1:03d}"
            subject_id = f"SUBJ-{index + 1:03d}"
            platform = "ios" if index % 2 == 0 else "android"
            quality_status = "valid"
            if index % 40 == 39:
                quality_status = "repeat"
            elif index % 70 == 69:
                quality_status = "reject"

            paired_cursor = connection.execute(
                """
                INSERT INTO paired_measurements (
                    created_at,
                    measured_at,
                    session_id,
                    sync_id,
                    site_id,
                    subject_id,
                    operator_id,
                    attempt_number,
                    platform,
                    device_model,
                    app_version,
                    capture_mode,
                    app_quality_status,
                    app_quality_score,
                    app_model_id,
                    app_qmax_ml_s,
                    app_qavg_ml_s,
                    app_vvoid_ml,
                    app_flow_time_s,
                    app_tqmax_s,
                    ref_qmax_ml_s,
                    ref_qavg_ml_s,
                    ref_vvoid_ml,
                    ref_flow_time_s,
                    ref_tqmax_s,
                    ref_device_model,
                    ref_device_serial,
                    notes,
                    payload_json
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    measured_at,
                    measured_at,
                    session_id,
                    sync_id,
                    "SITE-001",
                    subject_id,
                    "OP-01",
                    1,
                    platform,
                    "fixture-device",
                    "0.1.0",
                    "water_impact",
                    quality_status,
                    92.0 - float(index),
                    "fixture-v1",
                    18.0 + float(index) * 0.2,
                    10.0 + float(index) * 0.1,
                    220.0 + float(index),
                    27.0 + float(index) * 0.1,
                    7.0 + float(index) * 0.1,
                    17.5 + float(index) * 0.2,
                    9.8 + float(index) * 0.1,
                    218.0 + float(index),
                    26.5 + float(index) * 0.1,
                    6.8 + float(index) * 0.1,
                    "ref-fixture",
                    f"REF-{index + 1:03d}",
                    "Generated fallback fixture for coverage workflow",
                    json.dumps({"fixture": True, "index": index}),
                ),
            )
            paired_id = int(paired_cursor.lastrowid)

            # Keep a deterministic healthy baseline:
            # - total paired rows above volume warning thresholds
            # - ~9.1% missing capture (hard gate remains green)
            # - a mix of direct and fallback capture matches.
            if index < capture_package_count:
                paired_measurement_id = paired_id if index < direct_match_count else None
                connection.execute(
                    """
                    INSERT INTO capture_packages (
                        created_at,
                        measured_at,
                        session_id,
                        sync_id,
                        site_id,
                        subject_id,
                        operator_id,
                        attempt_number,
                        platform,
                        device_model,
                        app_version,
                        capture_mode,
                        package_type,
                        paired_measurement_id,
                        notes,
                        capture_payload_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        measured_at,
                        measured_at,
                        session_id,
                        sync_id,
                        "SITE-001",
                        subject_id,
                        "OP-01",
                        1,
                        platform,
                        "fixture-device",
                        "0.1.0",
                        "water_impact",
                        "capture_contract_json",
                        paired_measurement_id,
                        "Generated fallback fixture package",
                        json.dumps(
                            {
                                "session": {"session_id": session_id, "sync_id": sync_id},
                                "fixture": True,
                                "index": index,
                            }
                        ),
                    ),
                )

        connection.commit()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build fallback Clinical Hub DB fixture for coverage workflow.",
    )
    parser.add_argument(
        "--db-path",
        required=True,
        help="Target SQLite database path.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    db_path = Path(args.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    build_fixture_db(db_path)
    print(f"Fixture DB created: {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
