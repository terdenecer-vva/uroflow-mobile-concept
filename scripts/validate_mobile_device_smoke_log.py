#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "mobile_device_smoke_log_v0.1"
REQUIRED_PLATFORMS = ("ios", "android")
REQUIRED_SMOKE_CHECK_IDS = (
    "app_launch",
    "api_connection_check",
    "capture_start_stop",
    "contract_payload_ready",
    "paired_measurement_submit",
    "capture_package_submit",
    "offline_queue_retains_jobs",
    "connectivity_restore_sync",
    "raw_media_disabled",
    "device_logs_reviewed_no_phi",
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _read_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _is_iso_timestamp(value: str) -> bool:
    if not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _validate_release(release: dict[str, Any], errors: list[str]) -> None:
    required_text_fields = (
        "git_sha",
        "app_version",
        "build_profile",
        "build_channel",
        "mobile_release_manifest_sha256",
    )
    for field in required_text_fields:
        if not _read_text(release.get(field)):
            errors.append(f"release.{field} is required")

    manifest_sha = _read_text(release.get("mobile_release_manifest_sha256")).lower()
    if manifest_sha and SHA256_RE.fullmatch(manifest_sha) is None:
        errors.append(
            "release.mobile_release_manifest_sha256 must be a lowercase SHA-256 hex digest"
        )


def _check_map(device: dict[str, Any]) -> dict[str, dict[str, Any]]:
    checks: dict[str, dict[str, Any]] = {}
    for raw_check in _as_list(device.get("checks")):
        check = _as_dict(raw_check)
        check_id = _read_text(check.get("id"))
        if check_id:
            checks[check_id] = check
    return checks


def _validate_device(device: dict[str, Any], index: int, errors: list[str]) -> str:
    prefix = f"devices[{index}]"
    platform = _read_text(device.get("platform")).lower()
    if platform not in REQUIRED_PLATFORMS:
        errors.append(f"{prefix}.platform must be one of {REQUIRED_PLATFORMS!r}")

    for field in ("device_model", "os_version", "install_source", "app_build"):
        if not _read_text(device.get(field)):
            errors.append(f"{prefix}.{field} is required")

    checks = _check_map(device)
    for check_id in REQUIRED_SMOKE_CHECK_IDS:
        check = checks.get(check_id)
        if check is None:
            errors.append(f"{prefix}.checks missing required check {check_id!r}")
            continue
        status = _read_text(check.get("status")).lower()
        if status != "pass":
            errors.append(f"{prefix}.checks[{check_id}].status must be 'pass'")
        if not _read_text(check.get("evidence")):
            errors.append(f"{prefix}.checks[{check_id}].evidence is required")

    return platform


def validate_smoke_log(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION!r}")

    tested_at_utc = _read_text(payload.get("tested_at_utc"))
    if not _is_iso_timestamp(tested_at_utc):
        errors.append("tested_at_utc must be an ISO-8601 timestamp")

    _validate_release(_as_dict(payload.get("release")), errors)

    devices = [_as_dict(device) for device in _as_list(payload.get("devices"))]
    if not devices:
        errors.append("devices must contain at least one iOS and one Android device")

    platforms_seen: set[str] = set()
    for index, device in enumerate(devices):
        platform = _validate_device(device, index, errors)
        if platform:
            platforms_seen.add(platform)

    for platform in REQUIRED_PLATFORMS:
        if platform not in platforms_seen:
            errors.append(f"devices must include at least one {platform} smoke run")

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "fail" if errors else "pass",
        "device_count": len(devices),
        "platforms_seen": sorted(platforms_seen),
        "required_check_ids": list(REQUIRED_SMOKE_CHECK_IDS),
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate mobile physical-device smoke evidence for release handoff."
    )
    parser.add_argument("smoke_log", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = json.loads(args.smoke_log.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("smoke log root must be a JSON object")

    summary = validate_smoke_log(payload)
    encoded = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
