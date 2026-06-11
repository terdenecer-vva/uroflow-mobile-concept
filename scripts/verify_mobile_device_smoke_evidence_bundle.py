#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "mobile_device_smoke_evidence_bundle_v0.1"
SMOKE_LOG_SCHEMA_VERSION = "mobile_device_smoke_log_v0.1"
REQUIRED_PLATFORMS = ("android", "ios")


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _read_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _normalized_string_list(value: Any) -> list[str]:
    return sorted(
        {
            item.strip().lower()
            for item in _as_list(value)
            if isinstance(item, str) and item.strip()
        }
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _compare_field(
    errors: list[str], prefix: str, field: str, actual: Any, expected: Any
) -> None:
    if actual != expected:
        errors.append(f"{prefix}.{field} mismatch: actual={actual!r}, expected={expected!r}")


def verify_device_smoke_evidence_bundle(
    *,
    device_smoke_log_json: Path,
    device_smoke_summary_json: Path,
    store_rollout_handoff_json: Path,
    store_rollout_summary_json: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    smoke_summary = _load_json(device_smoke_summary_json)
    handoff = _load_json(store_rollout_handoff_json)
    handoff_summary = _load_json(store_rollout_summary_json)
    evidence = _as_dict(handoff.get("device_smoke_evidence"))

    smoke_log_sha = _sha256_file(device_smoke_log_json)
    smoke_summary_sha = _sha256_file(device_smoke_summary_json)
    smoke_platforms = _normalized_string_list(smoke_summary.get("platforms_seen"))
    evidence_platforms = _normalized_string_list(evidence.get("platforms_seen"))

    if smoke_summary.get("schema_version") != SMOKE_LOG_SCHEMA_VERSION:
        errors.append(
            "mobile_device_smoke_summary.schema_version must be "
            f"{SMOKE_LOG_SCHEMA_VERSION!r}"
        )
    if smoke_summary.get("status") != "pass":
        errors.append("mobile_device_smoke_summary.status must be 'pass'")
    if smoke_summary.get("errors") not in ([], None):
        errors.append("mobile_device_smoke_summary.errors must be empty")
    _compare_field(
        errors,
        "mobile_device_smoke_summary",
        "smoke_log_sha256",
        smoke_summary.get("smoke_log_sha256"),
        smoke_log_sha,
    )
    for platform in REQUIRED_PLATFORMS:
        if platform not in smoke_platforms:
            errors.append(
                f"mobile_device_smoke_summary.platforms_seen must include {platform}"
            )

    if evidence.get("status") != "pass":
        errors.append("store_rollout_handoff.device_smoke_evidence.status must be 'pass'")
    _compare_field(
        errors,
        "store_rollout_handoff.device_smoke_evidence",
        "validator_summary_status",
        _read_text(evidence.get("validator_summary_status")).lower(),
        smoke_summary.get("status"),
    )
    _compare_field(
        errors,
        "store_rollout_handoff.device_smoke_evidence",
        "platforms_seen",
        evidence_platforms,
        smoke_platforms,
    )
    _compare_field(
        errors,
        "store_rollout_handoff.device_smoke_evidence",
        "mobile_device_smoke_log_sha256",
        _read_text(evidence.get("mobile_device_smoke_log_sha256")).lower(),
        smoke_log_sha,
    )
    _compare_field(
        errors,
        "store_rollout_handoff.device_smoke_evidence",
        "mobile_device_smoke_summary_sha256",
        _read_text(evidence.get("mobile_device_smoke_summary_sha256")).lower(),
        smoke_summary_sha,
    )

    if handoff_summary.get("status") != "pass":
        errors.append("store_rollout_handoff.summary.status must be 'pass'")
    _compare_field(
        errors,
        "store_rollout_handoff.summary",
        "device_smoke_evidence_status",
        handoff_summary.get("device_smoke_evidence_status"),
        evidence.get("status"),
    )
    _compare_field(
        errors,
        "store_rollout_handoff.summary",
        "device_smoke_evidence_validator_summary_status",
        handoff_summary.get("device_smoke_evidence_validator_summary_status"),
        _read_text(evidence.get("validator_summary_status")).lower(),
    )
    _compare_field(
        errors,
        "store_rollout_handoff.summary",
        "device_smoke_evidence_platforms_seen",
        handoff_summary.get("device_smoke_evidence_platforms_seen"),
        evidence_platforms,
    )
    _compare_field(
        errors,
        "store_rollout_handoff.summary",
        "device_smoke_evidence_log_sha256",
        handoff_summary.get("device_smoke_evidence_log_sha256"),
        _read_text(evidence.get("mobile_device_smoke_log_sha256")).lower(),
    )
    _compare_field(
        errors,
        "store_rollout_handoff.summary",
        "device_smoke_evidence_summary_sha256",
        handoff_summary.get("device_smoke_evidence_summary_sha256"),
        _read_text(evidence.get("mobile_device_smoke_summary_sha256")).lower(),
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "fail" if errors else "pass",
        "smoke_log_sha256": smoke_log_sha,
        "smoke_summary_sha256": smoke_summary_sha,
        "smoke_summary_status": smoke_summary.get("status"),
        "device_count": smoke_summary.get("device_count"),
        "platforms_seen": smoke_platforms,
        "device_smoke_evidence_status": evidence.get("status"),
        "device_smoke_evidence_validator_summary_status": _read_text(
            evidence.get("validator_summary_status")
        ).lower(),
        "device_smoke_evidence_platforms_seen": evidence_platforms,
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify filled physical-device smoke evidence matches the store rollout "
            "handoff receipt."
        )
    )
    parser.add_argument("--device-smoke-log-json", type=Path, required=True)
    parser.add_argument("--device-smoke-summary-json", type=Path, required=True)
    parser.add_argument("--store-rollout-handoff-json", type=Path, required=True)
    parser.add_argument("--store-rollout-summary-json", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = verify_device_smoke_evidence_bundle(
        device_smoke_log_json=args.device_smoke_log_json,
        device_smoke_summary_json=args.device_smoke_summary_json,
        store_rollout_handoff_json=args.store_rollout_handoff_json,
        store_rollout_summary_json=args.store_rollout_summary_json,
    )
    encoded = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
