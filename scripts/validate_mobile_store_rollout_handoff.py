#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "mobile_store_rollout_handoff_v0.1"
BLOCKED_STATUS = "blocked_external"
DISTRIBUTABLE_CHANNEL_STATUSES = {"ready_for_upload", "submitted", "distributed"}
ALLOWED_CHANNEL_STATUSES = {BLOCKED_STATUS, *DISTRIBUTABLE_CHANNEL_STATUSES}
ALLOWED_CHECK_STATUSES = {"pass", BLOCKED_STATUS}
REQUIRED_HANDOFF_CHECK_IDS = (
    "mobile_release_manifest_archived",
    "mobile_release_readiness_archived",
    "mobile_release_notes_archived",
    "mobile_dependency_review_archived",
    "mobile_external_readiness_packet_archived",
    "mobile_device_smoke_template_validation_archived",
    "device_smoke_evidence_linked",
    "no_secrets_in_handoff",
)
REQUIRED_SMOKE_EVIDENCE_PLATFORMS = ("android", "ios")
REQUIRED_CHANNELS: dict[tuple[str, str], tuple[str, ...]] = {
    (
        "ios",
        "testflight_internal",
    ): (
        "apple_developer_access",
        "ios_signing_credentials",
        "testflight_internal_group",
        "eas_ios_build_uploaded",
        "build_metadata_matches_manifest",
        "privacy_strings_reviewed",
        "tester_install_instructions_sent",
    ),
    (
        "android",
        "play_internal_testing",
    ): (
        "google_play_access",
        "android_signing_credentials",
        "play_internal_track",
        "eas_android_build_uploaded",
        "build_metadata_matches_manifest",
        "permissions_reviewed",
        "tester_install_instructions_sent",
    ),
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
HTTPS_RE = re.compile(r"^https://[^\s]+$")


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


def _is_sha256(value: str) -> bool:
    return SHA256_RE.fullmatch(value) is not None


def _is_https_url(value: str) -> bool:
    return HTTPS_RE.fullmatch(value) is not None


def _string_list(values: Any) -> list[str]:
    return [_read_text(value) for value in _as_list(values) if _read_text(value)]


def _check_map(checks: list[Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw_check in checks:
        check = _as_dict(raw_check)
        check_id = _read_text(check.get("id"))
        if check_id:
            result[check_id] = check
    return result


def _validate_release(release: dict[str, Any], errors: list[str]) -> None:
    required_text_fields = (
        "git_sha",
        "app_version",
        "build_profile",
        "build_channel",
        "mobile_release_manifest_sha256",
        "mobile_release_readiness_sha256",
        "mobile_release_notes_sha256",
        "mobile_dependency_review_sha256",
        "mobile_external_readiness_packet_sha256",
        "mobile_device_smoke_template_summary_sha256",
    )
    for field in required_text_fields:
        if not _read_text(release.get(field)):
            errors.append(f"release.{field} is required")

    for field in (
        "mobile_release_manifest_sha256",
        "mobile_release_readiness_sha256",
        "mobile_release_notes_sha256",
        "mobile_dependency_review_sha256",
        "mobile_external_readiness_packet_sha256",
        "mobile_device_smoke_template_summary_sha256",
    ):
        digest = _read_text(release.get(field))
        if digest and not _is_sha256(digest):
            errors.append(f"release.{field} must be a lowercase SHA-256 hex digest")


def _validate_handoff_checks(
    checks: list[Any], rollout_status: str, errors: list[str]
) -> None:
    checks_by_id = _check_map(checks)
    for check_id in REQUIRED_HANDOFF_CHECK_IDS:
        check = checks_by_id.get(check_id)
        if check is None:
            errors.append(f"handoff_checks missing required check {check_id!r}")
            continue
        status = _read_text(check.get("status")).lower()
        if status not in ALLOWED_CHECK_STATUSES:
            errors.append(
                f"handoff_checks[{check_id}].status must be one of "
                f"{sorted(ALLOWED_CHECK_STATUSES)!r}"
            )
        if rollout_status != BLOCKED_STATUS and status != "pass":
            errors.append(f"handoff_checks[{check_id}].status must be 'pass'")
        if not _read_text(check.get("evidence")):
            errors.append(f"handoff_checks[{check_id}].evidence is required")


def _validate_device_smoke_evidence(
    evidence: dict[str, Any],
    handoff_checks: list[Any],
    rollout_status: str,
    errors: list[str],
) -> str:
    status = _read_text(evidence.get("status")).lower()
    if status not in ALLOWED_CHECK_STATUSES:
        errors.append(
            "device_smoke_evidence.status must be one of "
            f"{sorted(ALLOWED_CHECK_STATUSES)!r}"
        )

    checks = _check_map(handoff_checks)
    linked_check_status = _read_text(
        _as_dict(checks.get("device_smoke_evidence_linked")).get("status")
    ).lower()
    if status and linked_check_status and status != linked_check_status:
        errors.append(
            "device_smoke_evidence.status must match "
            "handoff_checks[device_smoke_evidence_linked].status"
        )

    if rollout_status != BLOCKED_STATUS and status != "pass":
        errors.append("device_smoke_evidence.status must be 'pass' for distributable rollout")

    for field in (
        "mobile_device_smoke_log_sha256",
        "mobile_device_smoke_summary_sha256",
    ):
        digest = _read_text(evidence.get(field))
        if status == "pass" and not digest:
            errors.append(f"device_smoke_evidence.{field} is required")
        if digest and not _is_sha256(digest):
            errors.append(
                f"device_smoke_evidence.{field} must be a lowercase SHA-256 hex digest"
            )

    summary_url = _read_text(evidence.get("summary_url"))
    if status == "pass" and not summary_url:
        errors.append("device_smoke_evidence.summary_url is required")
    if summary_url and not _is_https_url(summary_url):
        errors.append("device_smoke_evidence.summary_url must be an https URL")

    validated_at_utc = _read_text(evidence.get("validated_at_utc"))
    if status == "pass" and not validated_at_utc:
        errors.append("device_smoke_evidence.validated_at_utc is required")
    if validated_at_utc and not _is_iso_timestamp(validated_at_utc):
        errors.append("device_smoke_evidence.validated_at_utc must be ISO-8601")

    platforms_seen = sorted(
        {
            platform.lower()
            for platform in _string_list(evidence.get("platforms_seen"))
        }
    )
    if status == "pass":
        for platform in REQUIRED_SMOKE_EVIDENCE_PLATFORMS:
            if platform not in platforms_seen:
                errors.append(f"device_smoke_evidence.platforms_seen must include {platform}")

    validator_summary_status = _read_text(evidence.get("validator_summary_status")).lower()
    if status == "pass" and validator_summary_status != "pass":
        errors.append("device_smoke_evidence.validator_summary_status must be 'pass'")
    if validator_summary_status and validator_summary_status not in ALLOWED_CHECK_STATUSES:
        errors.append(
            "device_smoke_evidence.validator_summary_status must be one of "
            f"{sorted(ALLOWED_CHECK_STATUSES)!r}"
        )

    blockers = _string_list(evidence.get("blockers"))
    if status == BLOCKED_STATUS and not blockers:
        errors.append("device_smoke_evidence.blockers must explain external blockers")

    return status or "missing"


def _validate_ready_channel_fields(
    channel: dict[str, Any], prefix: str, errors: list[str]
) -> None:
    artifact = _as_dict(channel.get("build_artifact"))
    submission = _as_dict(channel.get("store_submission"))

    for field in ("eas_build_id", "eas_build_url", "store_build_number", "artifact_sha256"):
        if not _read_text(artifact.get(field)):
            errors.append(f"{prefix}.build_artifact.{field} is required")

    eas_build_url = _read_text(artifact.get("eas_build_url"))
    if eas_build_url and not _is_https_url(eas_build_url):
        errors.append(f"{prefix}.build_artifact.eas_build_url must be an https URL")

    artifact_sha = _read_text(artifact.get("artifact_sha256"))
    if artifact_sha and not _is_sha256(artifact_sha):
        errors.append(f"{prefix}.build_artifact.artifact_sha256 must be a SHA-256 hex digest")

    for field in ("store_console_url", "submitted_at_utc", "submitted_by", "tester_group_or_track"):
        if not _read_text(submission.get(field)):
            errors.append(f"{prefix}.store_submission.{field} is required")

    store_console_url = _read_text(submission.get("store_console_url"))
    if store_console_url and not _is_https_url(store_console_url):
        errors.append(f"{prefix}.store_submission.store_console_url must be an https URL")

    submitted_at = _read_text(submission.get("submitted_at_utc"))
    if submitted_at and not _is_iso_timestamp(submitted_at):
        errors.append(f"{prefix}.store_submission.submitted_at_utc must be ISO-8601")


def _validate_channel(channel: dict[str, Any], index: int, errors: list[str]) -> tuple[str, str]:
    prefix = f"channels[{index}]"
    platform = _read_text(channel.get("platform")).lower()
    distribution_channel = _read_text(channel.get("distribution_channel")).lower()
    key = (platform, distribution_channel)
    if key not in REQUIRED_CHANNELS:
        errors.append(f"{prefix} must be one of {sorted(REQUIRED_CHANNELS)!r}")

    status = _read_text(channel.get("status")).lower()
    if status not in ALLOWED_CHANNEL_STATUSES:
        errors.append(f"{prefix}.status must be one of {sorted(ALLOWED_CHANNEL_STATUSES)!r}")

    for field in ("owner", "account_status"):
        if not _read_text(channel.get(field)):
            errors.append(f"{prefix}.{field} is required")

    tester_scope = _as_dict(channel.get("tester_scope"))
    for field in ("name", "audience", "install_instruction_url"):
        if not _read_text(tester_scope.get(field)):
            errors.append(f"{prefix}.tester_scope.{field} is required")

    blockers = [_read_text(blocker) for blocker in _as_list(channel.get("blockers"))]
    blockers = [blocker for blocker in blockers if blocker]
    if status == BLOCKED_STATUS and not blockers:
        errors.append(f"{prefix}.blockers must explain external blockers")

    checks_by_id = _check_map(_as_list(channel.get("checks")))
    required_checks = REQUIRED_CHANNELS.get(key, ())
    blocked_required_checks = 0
    for check_id in required_checks:
        check = checks_by_id.get(check_id)
        if check is None:
            errors.append(f"{prefix}.checks missing required check {check_id!r}")
            continue
        check_status = _read_text(check.get("status")).lower()
        if check_status not in ALLOWED_CHECK_STATUSES:
            errors.append(
                f"{prefix}.checks[{check_id}].status must be one of "
                f"{sorted(ALLOWED_CHECK_STATUSES)!r}"
            )
        if check_status == BLOCKED_STATUS:
            blocked_required_checks += 1
        if status != BLOCKED_STATUS and check_status != "pass":
            errors.append(f"{prefix}.checks[{check_id}].status must be 'pass'")
        if not _read_text(check.get("evidence")):
            errors.append(f"{prefix}.checks[{check_id}].evidence is required")

    if status == BLOCKED_STATUS and required_checks and blocked_required_checks == 0:
        errors.append(f"{prefix}.checks must include at least one blocked_external required check")

    if status != BLOCKED_STATUS:
        _validate_ready_channel_fields(channel, prefix, errors)

    return key


def validate_rollout_handoff(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION!r}")

    prepared_at_utc = _read_text(payload.get("prepared_at_utc"))
    if not _is_iso_timestamp(prepared_at_utc):
        errors.append("prepared_at_utc must be an ISO-8601 timestamp")

    rollout_status = _read_text(payload.get("rollout_status")).lower()
    if rollout_status not in ALLOWED_CHANNEL_STATUSES:
        errors.append(f"rollout_status must be one of {sorted(ALLOWED_CHANNEL_STATUSES)!r}")

    handoff_checks = _as_list(payload.get("handoff_checks"))
    _validate_release(_as_dict(payload.get("release")), errors)
    _validate_handoff_checks(handoff_checks, rollout_status, errors)
    device_smoke_evidence_status = _validate_device_smoke_evidence(
        _as_dict(payload.get("device_smoke_evidence")),
        handoff_checks,
        rollout_status,
        errors,
    )

    channels = [_as_dict(channel) for channel in _as_list(payload.get("channels"))]
    if not channels:
        errors.append("channels must contain iOS TestFlight and Android Play Internal handoffs")

    channels_seen: set[tuple[str, str]] = set()
    blocked_channels: list[str] = []
    for index, channel in enumerate(channels):
        key = _validate_channel(channel, index, errors)
        if key[0] and key[1]:
            channels_seen.add(key)
            if _read_text(channel.get("status")).lower() == BLOCKED_STATUS:
                blocked_channels.append(f"{key[0]}:{key[1]}")

    if rollout_status != BLOCKED_STATUS and blocked_channels:
        errors.append(
            "rollout_status cannot be distributable while channels remain blocked_external"
        )

    for key in REQUIRED_CHANNELS:
        if key not in channels_seen:
            errors.append(f"channels must include {key[0]} {key[1]} handoff")

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "fail" if errors else "pass",
        "rollout_status": rollout_status,
        "channels_seen": sorted(f"{platform}:{channel}" for platform, channel in channels_seen),
        "blocked_channels": sorted(blocked_channels),
        "device_smoke_evidence_status": device_smoke_evidence_status,
        "required_channels": sorted(
            f"{platform}:{channel}" for platform, channel in REQUIRED_CHANNELS
        ),
        "required_handoff_check_ids": list(REQUIRED_HANDOFF_CHECK_IDS),
        "required_channel_check_ids": {
            f"{platform}:{channel}": list(check_ids)
            for (platform, channel), check_ids in sorted(REQUIRED_CHANNELS.items())
        },
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate mobile TestFlight/Play Internal rollout handoff evidence."
    )
    parser.add_argument("handoff", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = json.loads(args.handoff.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("rollout handoff root must be a JSON object")

    summary = validate_rollout_handoff(payload)
    encoded = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
