#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

TRACEABILITY_FIELDS = ("git_sha", "git_ref", "git_run_id", "workflow")
DEPENDENCY_REVIEW_SCHEMA_VERSION = "mobile_dependency_review_v0.1"
EXTERNAL_READINESS_PACKET_SCHEMA_VERSION = "mobile_external_readiness_packet_v0.1"
SMOKE_TEMPLATE_SUMMARY_SCHEMA_VERSION = "mobile_device_smoke_log_v0.1"
READINESS_SUMMARY_FIELDS = (
    "status",
    "local_checks_status",
    "external_readiness_status",
    "authenticated_eas_status",
    "clinical_hub_live_api_status",
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [item for item in _as_list(value) if isinstance(item, str)]


def _read_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _local_check_counts(readiness: dict[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for check in _as_list(readiness.get("local_checks")):
        if isinstance(check, dict):
            counts[str(check.get("status", "unknown"))] += 1
    return dict(counts)


def _failed_local_checks(readiness: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for check in _as_list(readiness.get("local_checks")):
        if not isinstance(check, dict):
            continue
        check_id = check.get("id")
        if isinstance(check_id, str) and check.get("status") != "pass":
            failures.append(check_id)
    return failures


def _warning_local_checks(readiness: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for check in _as_list(readiness.get("local_checks")):
        if not isinstance(check, dict):
            continue
        check_id = check.get("id")
        if isinstance(check_id, str) and check.get("severity") == "warning":
            warnings.append(check_id)
    return warnings


def _item_statuses(items: Any) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for item in _as_list(items):
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        status = item.get("status")
        if isinstance(item_id, str) and isinstance(status, str):
            result.append({"id": item_id, "status": status})
    return result


def _next_action_ids(readiness: dict[str, Any]) -> list[str]:
    return [
        item["id"]
        for item in _as_list(readiness.get("next_actions"))
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]


def _compare_field(
    errors: list[str], prefix: str, field: str, actual: Any, expected: Any
) -> None:
    if actual != expected:
        errors.append(f"{prefix}.{field} mismatch: actual={actual!r}, expected={expected!r}")


def _validate_traceability(
    manifest: dict[str, Any],
    readiness: dict[str, Any],
    handoff: dict[str, Any],
    errors: list[str],
    *,
    expect_git_sha: str | None,
    expect_run_id: str | None,
) -> dict[str, Any]:
    manifest_traceability = _as_dict(manifest.get("traceability"))
    readiness_traceability = _as_dict(readiness.get("traceability"))
    handoff_release = _as_dict(handoff.get("release"))

    for field in TRACEABILITY_FIELDS:
        _compare_field(
            errors,
            "traceability",
            field,
            manifest_traceability.get(field),
            readiness_traceability.get(field),
        )

    _compare_field(
        errors,
        "store_rollout_handoff.release",
        "git_sha",
        handoff_release.get("git_sha"),
        manifest_traceability.get("git_sha"),
    )

    if expect_git_sha:
        _compare_field(
            errors,
            "expected",
            "git_sha",
            manifest_traceability.get("git_sha"),
            expect_git_sha,
        )
    if expect_run_id:
        _compare_field(
            errors,
            "expected",
            "git_run_id",
            manifest_traceability.get("git_run_id"),
            expect_run_id,
        )

    return manifest_traceability


def _validate_manifest_readiness_summary(
    manifest: dict[str, Any], readiness: dict[str, Any], errors: list[str]
) -> None:
    manifest_readiness = _as_dict(manifest.get("readiness"))
    for field in READINESS_SUMMARY_FIELDS:
        _compare_field(
            errors,
            "manifest.readiness",
            field,
            manifest_readiness.get(field),
            readiness.get(field),
        )

    _compare_field(
        errors,
        "manifest.readiness",
        "authenticated_eas_blockers",
        manifest_readiness.get("authenticated_eas_blockers"),
        readiness.get("authenticated_eas_blockers", []),
    )
    _compare_field(
        errors,
        "manifest.readiness",
        "local_check_counts",
        manifest_readiness.get("local_check_counts"),
        _local_check_counts(readiness),
    )
    _compare_field(
        errors,
        "manifest.readiness",
        "failed_local_checks",
        manifest_readiness.get("failed_local_checks"),
        _failed_local_checks(readiness),
    )
    _compare_field(
        errors,
        "manifest.readiness",
        "warning_local_checks",
        manifest_readiness.get("warning_local_checks"),
        _warning_local_checks(readiness),
    )
    _compare_field(
        errors,
        "manifest.readiness",
        "external_items",
        manifest_readiness.get("external_items"),
        _item_statuses(readiness.get("external_items")),
    )
    _compare_field(
        errors,
        "manifest.readiness",
        "manual_external_items",
        manifest_readiness.get("manual_external_items"),
        _item_statuses(readiness.get("manual_external_items")),
    )
    _compare_field(
        errors,
        "manifest.readiness",
        "next_action_ids",
        manifest_readiness.get("next_action_ids"),
        _next_action_ids(readiness),
    )

    if readiness.get("local_checks_status") != "pass":
        errors.append("readiness.local_checks_status must be 'pass'")
    if _failed_local_checks(readiness):
        errors.append("readiness.local_checks must not contain failed checks")


def _validate_release_notes(
    manifest: dict[str, Any], release_notes: Path, errors: list[str]
) -> str:
    release_notes_summary = _as_dict(manifest.get("release_notes"))
    actual_sha = _sha256_file(release_notes)
    _compare_field(
        errors,
        "manifest.release_notes",
        "sha256",
        release_notes_summary.get("sha256"),
        actual_sha,
    )
    _compare_field(
        errors,
        "manifest.release_notes",
        "bytes",
        release_notes_summary.get("bytes"),
        release_notes.stat().st_size,
    )
    if release_notes_summary.get("present") is not True:
        errors.append("manifest.release_notes.present must be true")
    return actual_sha


def _validate_smoke_template_summary(
    smoke_template_summary: Path, errors: list[str]
) -> str:
    summary = _load_json(smoke_template_summary)
    if summary.get("schema_version") != SMOKE_TEMPLATE_SUMMARY_SCHEMA_VERSION:
        errors.append(
            "mobile_device_smoke_template_summary.schema_version must be "
            f"{SMOKE_TEMPLATE_SUMMARY_SCHEMA_VERSION!r}"
        )
    if summary.get("status") != "pass":
        errors.append("mobile_device_smoke_template_summary.status must be 'pass'")
    if summary.get("errors") not in ([], None):
        errors.append("mobile_device_smoke_template_summary.errors must be empty")
    return _sha256_file(smoke_template_summary)


def _validate_dependency_review(
    dependency_review_json: Path, expected_traceability: dict[str, Any], errors: list[str]
) -> str:
    payload = _load_json(dependency_review_json)
    if payload.get("schema_version") != DEPENDENCY_REVIEW_SCHEMA_VERSION:
        errors.append(
            "mobile_dependency_review.schema_version must be "
            f"{DEPENDENCY_REVIEW_SCHEMA_VERSION!r}"
        )
    if payload.get("status") != "pass":
        errors.append("mobile_dependency_review.status must be 'pass'")
    if payload.get("failed_checks") != []:
        errors.append("mobile_dependency_review.failed_checks must be empty")

    dependency_traceability = _as_dict(payload.get("traceability"))
    for field in TRACEABILITY_FIELDS:
        _compare_field(
            errors,
            "mobile_dependency_review.traceability",
            field,
            dependency_traceability.get(field),
            expected_traceability.get(field),
        )

    audit = _as_dict(payload.get("audit"))
    if audit.get("status") != "pass":
        errors.append("mobile_dependency_review.audit.status must be 'pass'")
    vulnerabilities = _as_dict(audit.get("vulnerabilities"))
    if vulnerabilities.get("total") != 0:
        errors.append("mobile_dependency_review.audit.vulnerabilities.total must be 0")

    return _sha256_file(dependency_review_json)


def _expected_external_readiness_packet_status(
    readiness: dict[str, Any], required_actions: list[dict[str, Any]]
) -> str:
    if readiness.get("local_checks_status") != "pass":
        return "not_ready"
    if required_actions:
        return "blocked_external"
    if readiness.get("external_readiness_status") == "pass":
        return "ready"
    return "blocked_external"


def _required_action_values(
    required_actions: list[dict[str, Any]], field: str
) -> list[str]:
    return sorted(
        {
            item
            for action in required_actions
            for item in _string_list(action.get(field))
        }
    )


def _validate_external_readiness_packet(
    external_readiness_packet_json: Path,
    readiness: dict[str, Any],
    expected_traceability: dict[str, Any],
    errors: list[str],
) -> str:
    packet = _load_json(external_readiness_packet_json)
    if packet.get("schema_version") != EXTERNAL_READINESS_PACKET_SCHEMA_VERSION:
        errors.append(
            "mobile_external_readiness_packet.schema_version must be "
            f"{EXTERNAL_READINESS_PACKET_SCHEMA_VERSION!r}"
        )

    packet_traceability = _as_dict(packet.get("traceability"))
    for field in TRACEABILITY_FIELDS:
        _compare_field(
            errors,
            "mobile_external_readiness_packet.traceability",
            field,
            packet_traceability.get(field),
            expected_traceability.get(field),
        )

    for field in READINESS_SUMMARY_FIELDS:
        packet_field = "readiness_status" if field == "status" else field
        _compare_field(
            errors,
            "mobile_external_readiness_packet",
            packet_field,
            packet.get(packet_field),
            readiness.get(field),
        )
    _compare_field(
        errors,
        "mobile_external_readiness_packet",
        "authenticated_eas_blockers",
        packet.get("authenticated_eas_blockers"),
        readiness.get("authenticated_eas_blockers", []),
    )

    required_actions = [
        action for action in _as_list(packet.get("required_actions")) if isinstance(action, dict)
    ]
    _compare_field(
        errors,
        "mobile_external_readiness_packet",
        "status",
        packet.get("status"),
        _expected_external_readiness_packet_status(readiness, required_actions),
    )

    summary = _as_dict(packet.get("summary"))
    external_items = [
        item for item in _as_list(packet.get("external_items")) if isinstance(item, dict)
    ]
    manual_external_items = [
        item
        for item in _as_list(packet.get("manual_external_items"))
        if isinstance(item, dict)
    ]
    _compare_field(
        errors,
        "mobile_external_readiness_packet.summary",
        "external_item_count",
        summary.get("external_item_count"),
        len(external_items),
    )
    _compare_field(
        errors,
        "mobile_external_readiness_packet.summary",
        "manual_external_item_count",
        summary.get("manual_external_item_count"),
        len(manual_external_items),
    )
    _compare_field(
        errors,
        "mobile_external_readiness_packet.summary",
        "required_action_count",
        summary.get("required_action_count"),
        len(required_actions),
    )
    for field in ("secret_names", "variable_names", "file_paths"):
        _compare_field(
            errors,
            "mobile_external_readiness_packet.summary",
            field,
            summary.get(field),
            _required_action_values(required_actions, field),
        )

    return _sha256_file(external_readiness_packet_json)


def _validate_store_rollout_handoff(
    manifest: dict[str, Any],
    readiness: Path,
    manifest_path: Path,
    release_notes_sha: str,
    dependency_review_sha: str,
    external_readiness_packet_sha: str,
    smoke_template_summary_sha: str,
    handoff: dict[str, Any],
    handoff_summary: dict[str, Any],
    errors: list[str],
) -> None:
    handoff_release = _as_dict(handoff.get("release"))
    release = _as_dict(manifest.get("release"))
    _compare_field(
        errors,
        "store_rollout_handoff.release",
        "build_profile",
        handoff_release.get("build_profile"),
        release.get("profile"),
    )
    _compare_field(
        errors,
        "store_rollout_handoff.release",
        "build_channel",
        handoff_release.get("build_channel"),
        release.get("channel"),
    )
    _compare_field(
        errors,
        "store_rollout_handoff.release",
        "mobile_release_manifest_sha256",
        handoff_release.get("mobile_release_manifest_sha256"),
        _sha256_file(manifest_path),
    )
    _compare_field(
        errors,
        "store_rollout_handoff.release",
        "mobile_release_readiness_sha256",
        handoff_release.get("mobile_release_readiness_sha256"),
        _sha256_file(readiness),
    )
    _compare_field(
        errors,
        "store_rollout_handoff.release",
        "mobile_release_notes_sha256",
        handoff_release.get("mobile_release_notes_sha256"),
        release_notes_sha,
    )
    _compare_field(
        errors,
        "store_rollout_handoff.release",
        "mobile_dependency_review_sha256",
        handoff_release.get("mobile_dependency_review_sha256"),
        dependency_review_sha,
    )
    _compare_field(
        errors,
        "store_rollout_handoff.release",
        "mobile_external_readiness_packet_sha256",
        handoff_release.get("mobile_external_readiness_packet_sha256"),
        external_readiness_packet_sha,
    )
    _compare_field(
        errors,
        "store_rollout_handoff.release",
        "mobile_device_smoke_template_summary_sha256",
        handoff_release.get("mobile_device_smoke_template_summary_sha256"),
        smoke_template_summary_sha,
    )

    if handoff_summary.get("status") != "pass":
        errors.append("store_rollout_handoff.summary.status must be 'pass'")
    if sorted(handoff_summary.get("required_channels", [])) != [
        "android:play_internal_testing",
        "ios:testflight_internal",
    ]:
        errors.append("store_rollout_handoff.summary.required_channels mismatch")

    device_smoke_evidence = _as_dict(handoff.get("device_smoke_evidence"))
    device_smoke_evidence_status = device_smoke_evidence.get("status")
    if not isinstance(device_smoke_evidence_status, str) or not device_smoke_evidence_status:
        errors.append("store_rollout_handoff.device_smoke_evidence.status is required")
    _compare_field(
        errors,
        "store_rollout_handoff.summary",
        "device_smoke_evidence_status",
        handoff_summary.get("device_smoke_evidence_status"),
        device_smoke_evidence_status,
    )
    _compare_field(
        errors,
        "store_rollout_handoff.summary",
        "device_smoke_evidence_validator_summary_status",
        handoff_summary.get("device_smoke_evidence_validator_summary_status"),
        _read_text(device_smoke_evidence.get("validator_summary_status")).lower(),
    )
    _compare_field(
        errors,
        "store_rollout_handoff.summary",
        "device_smoke_evidence_platforms_seen",
        handoff_summary.get("device_smoke_evidence_platforms_seen"),
        sorted(
            {
                platform.strip().lower()
                for platform in _string_list(device_smoke_evidence.get("platforms_seen"))
                if platform.strip()
            }
        ),
    )
    _compare_field(
        errors,
        "store_rollout_handoff.summary",
        "device_smoke_evidence_log_sha256",
        handoff_summary.get("device_smoke_evidence_log_sha256"),
        _read_text(device_smoke_evidence.get("mobile_device_smoke_log_sha256")).lower(),
    )
    _compare_field(
        errors,
        "store_rollout_handoff.summary",
        "device_smoke_evidence_summary_sha256",
        handoff_summary.get("device_smoke_evidence_summary_sha256"),
        _read_text(device_smoke_evidence.get("mobile_device_smoke_summary_sha256")).lower(),
    )


def verify_release_bundle(
    *,
    manifest_json: Path,
    readiness_json: Path,
    release_notes: Path,
    dependency_review_json: Path,
    external_readiness_packet_json: Path,
    smoke_template_summary_json: Path,
    store_rollout_handoff_json: Path,
    store_rollout_summary_json: Path,
    expect_git_sha: str | None = None,
    expect_run_id: str | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    manifest = _load_json(manifest_json)
    readiness = _load_json(readiness_json)
    handoff = _load_json(store_rollout_handoff_json)
    handoff_summary = _load_json(store_rollout_summary_json)

    traceability = _validate_traceability(
        manifest,
        readiness,
        handoff,
        errors,
        expect_git_sha=expect_git_sha,
        expect_run_id=expect_run_id,
    )
    _validate_manifest_readiness_summary(manifest, readiness, errors)
    release_notes_sha = _validate_release_notes(manifest, release_notes, errors)
    dependency_review_sha = _validate_dependency_review(
        dependency_review_json, traceability, errors
    )
    external_readiness_packet_sha = _validate_external_readiness_packet(
        external_readiness_packet_json, readiness, traceability, errors
    )
    smoke_template_summary_sha = _validate_smoke_template_summary(
        smoke_template_summary_json, errors
    )
    _validate_store_rollout_handoff(
        manifest,
        readiness_json,
        manifest_json,
        release_notes_sha,
        dependency_review_sha,
        external_readiness_packet_sha,
        smoke_template_summary_sha,
        handoff,
        handoff_summary,
        errors,
    )

    return {
        "status": "fail" if errors else "pass",
        "traceability": traceability,
        "readiness_status": readiness.get("status"),
        "local_check_counts": _local_check_counts(readiness),
        "external_readiness_status": readiness.get("external_readiness_status"),
        "store_rollout_status": handoff_summary.get("rollout_status"),
        "store_rollout_blocked_channels": handoff_summary.get("blocked_channels", []),
        "device_smoke_evidence_status": handoff_summary.get(
            "device_smoke_evidence_status"
        ),
        "device_smoke_evidence_validator_summary_status": handoff_summary.get(
            "device_smoke_evidence_validator_summary_status"
        ),
        "device_smoke_evidence_platforms_seen": handoff_summary.get(
            "device_smoke_evidence_platforms_seen", []
        ),
        "device_smoke_evidence_log_sha256": handoff_summary.get(
            "device_smoke_evidence_log_sha256"
        ),
        "device_smoke_evidence_summary_sha256": handoff_summary.get(
            "device_smoke_evidence_summary_sha256"
        ),
        "artifact_sha256": {
            "mobile_release_manifest": _sha256_file(manifest_json),
            "mobile_release_readiness": _sha256_file(readiness_json),
            "mobile_release_notes": release_notes_sha,
            "mobile_dependency_review": dependency_review_sha,
            "mobile_external_readiness_packet": external_readiness_packet_sha,
            "mobile_device_smoke_template_summary": smoke_template_summary_sha,
            "mobile_store_rollout_handoff": _sha256_file(store_rollout_handoff_json),
            "mobile_store_rollout_handoff_summary": _sha256_file(
                store_rollout_summary_json
            ),
        },
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify Mobile Build release artifacts belong to one coherent bundle."
    )
    parser.add_argument("--manifest-json", type=Path, required=True)
    parser.add_argument("--readiness-json", type=Path, required=True)
    parser.add_argument("--release-notes", type=Path, required=True)
    parser.add_argument("--dependency-review-json", type=Path, required=True)
    parser.add_argument("--external-readiness-packet-json", type=Path, required=True)
    parser.add_argument("--smoke-template-summary-json", type=Path, required=True)
    parser.add_argument("--store-rollout-handoff-json", type=Path, required=True)
    parser.add_argument("--store-rollout-summary-json", type=Path, required=True)
    parser.add_argument("--expect-git-sha")
    parser.add_argument("--expect-run-id")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = verify_release_bundle(
        manifest_json=args.manifest_json,
        readiness_json=args.readiness_json,
        release_notes=args.release_notes,
        dependency_review_json=args.dependency_review_json,
        external_readiness_packet_json=args.external_readiness_packet_json,
        smoke_template_summary_json=args.smoke_template_summary_json,
        store_rollout_handoff_json=args.store_rollout_handoff_json,
        store_rollout_summary_json=args.store_rollout_summary_json,
        expect_git_sha=args.expect_git_sha,
        expect_run_id=args.expect_run_id,
    )
    encoded = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
