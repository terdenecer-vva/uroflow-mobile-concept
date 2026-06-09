#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "mobile_dependency_review_v0.1"
RISK_ID = "SEC-003"

NATIVE_SURFACE_REVIEW: dict[str, dict[str, Any]] = {
    "@react-native-async-storage/async-storage": {
        "surfaces": ["local_queue_storage"],
        "controls": ["pending queue storage tests", "PHI redaction gates"],
    },
    "@react-native-community/netinfo": {
        "surfaces": ["network_state"],
        "controls": ["connectivity restore sync tests"],
    },
    "expo-audio": {
        "surfaces": ["microphone", "temporary_audio_file"],
        "controls": ["microphone permission text", "raw audio temp cleanup"],
    },
    "expo-camera": {
        "surfaces": ["camera"],
        "controls": ["camera permission text", "ROI-only derived features"],
    },
    "expo-device": {
        "surfaces": ["device_identity"],
        "controls": ["release/device traceability tests"],
    },
    "expo-file-system": {
        "surfaces": ["local_file_system"],
        "controls": ["raw media retention tests"],
    },
    "expo-secure-store": {
        "surfaces": ["secure_secret_storage"],
        "controls": ["API key secure storage tests"],
    },
    "expo-sensors": {
        "surfaces": ["motion_imu"],
        "controls": ["runtime motion quality gates"],
    },
}

LOW_RISK_NATIVE_REVIEW_ALLOWLIST = {
    "expo",
    "expo-asset",
    "expo-splash-screen",
    "expo-status-bar",
    "react",
    "react-native",
}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _traceability(env: dict[str, str]) -> dict[str, str]:
    return {
        "git_sha": env.get("GITHUB_SHA", "local"),
        "git_ref": env.get("GITHUB_REF", "local"),
        "git_run_id": env.get("GITHUB_RUN_ID", "local"),
        "workflow": env.get("GITHUB_WORKFLOW", "local"),
    }


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _check(
    checks: list[dict[str, Any]],
    check_id: str,
    passed: bool,
    evidence: str,
    *,
    severity: str = "error",
) -> None:
    checks.append(
        {
            "id": check_id,
            "status": "pass" if passed else "fail",
            "severity": severity,
            "evidence": evidence,
        }
    )


def _dependency_entry(
    *,
    name: str,
    dependency_type: str,
    declared: str,
    locked_declared: str | None,
    lock_entry: dict[str, Any],
) -> dict[str, Any]:
    return {
        "name": name,
        "dependency_type": dependency_type,
        "declared": declared,
        "lockfile_declared": locked_declared,
        "installed_version": lock_entry.get("version"),
        "resolved_present": isinstance(lock_entry.get("resolved"), str)
        and bool(lock_entry.get("resolved", "").strip()),
        "integrity_present": isinstance(lock_entry.get("integrity"), str)
        and bool(lock_entry.get("integrity", "").strip()),
        "native_sensitive_surface": NATIVE_SURFACE_REVIEW.get(name, {}).get(
            "surfaces", []
        ),
    }


def _collect_direct_dependencies(
    package_payload: dict[str, Any],
    lock_payload: dict[str, Any],
    *,
    dependency_type: str,
) -> list[dict[str, Any]]:
    package_key = "dependencies" if dependency_type == "production" else "devDependencies"
    declared = _as_dict(package_payload.get(package_key))
    packages = _as_dict(lock_payload.get("packages"))
    lock_root = _as_dict(packages.get(""))
    locked_declared = _as_dict(lock_root.get(package_key))

    rows: list[dict[str, Any]] = []
    for name in sorted(declared):
        lock_entry = _as_dict(packages.get(f"node_modules/{name}"))
        rows.append(
            _dependency_entry(
                name=name,
                dependency_type=dependency_type,
                declared=str(declared[name]),
                locked_declared=locked_declared.get(name),
                lock_entry=lock_entry,
            )
        )
    return rows


def _dependency_lock_failures(rows: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    for row in rows:
        if row["declared"] != row.get("lockfile_declared"):
            failures.append(f"{row['name']}:declared_mismatch")
        if not row.get("installed_version"):
            failures.append(f"{row['name']}:missing_node_modules_entry")
    return failures


def _dependency_integrity_failures(rows: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    for row in rows:
        if not row.get("resolved_present"):
            failures.append(f"{row['name']}:missing_resolved")
        if not row.get("integrity_present"):
            failures.append(f"{row['name']}:missing_integrity")
    return failures


def _audit_summary(audit_payload: dict[str, Any]) -> dict[str, Any]:
    metadata = _as_dict(audit_payload.get("metadata"))
    vulnerabilities = _as_dict(metadata.get("vulnerabilities"))
    vulnerability_items = _as_dict(audit_payload.get("vulnerabilities"))
    total = int(vulnerabilities.get("total", len(vulnerability_items)) or 0)
    return {
        "audit_report_version": audit_payload.get("auditReportVersion"),
        "vulnerabilities": {
            "info": int(vulnerabilities.get("info", 0) or 0),
            "low": int(vulnerabilities.get("low", 0) or 0),
            "moderate": int(vulnerabilities.get("moderate", 0) or 0),
            "high": int(vulnerabilities.get("high", 0) or 0),
            "critical": int(vulnerabilities.get("critical", 0) or 0),
            "total": total,
        },
        "dependency_counts": _as_dict(metadata.get("dependencies")),
        "vulnerable_packages": sorted(vulnerability_items),
        "status": "pass" if total == 0 else "fail",
    }


def _native_review_candidates(package_payload: dict[str, Any]) -> set[str]:
    dependencies = _as_dict(package_payload.get("dependencies"))
    candidates: set[str] = set()
    for name in dependencies:
        if (
            name.startswith("expo-")
            or name.startswith("@react-native-")
            or name == "react-native"
        ):
            candidates.add(name)
    return candidates


def _native_review_rows(package_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    dependencies = _as_dict(package_payload.get("dependencies"))
    for name in sorted(dependencies):
        review = NATIVE_SURFACE_REVIEW.get(name)
        if review is None:
            continue
        rows.append(
            {
                "name": name,
                "surfaces": review["surfaces"],
                "release_controls": review["controls"],
            }
        )
    return rows


def build_dependency_review(
    *,
    package_json: Path,
    package_lock: Path,
    audit_json: Path,
    env: dict[str, str],
) -> dict[str, Any]:
    package_payload = _load_json(package_json)
    lock_payload = _load_json(package_lock)
    audit_payload = _load_json(audit_json)

    packages = _as_dict(lock_payload.get("packages"))
    lock_root = _as_dict(packages.get(""))
    production_rows = _collect_direct_dependencies(
        package_payload, lock_payload, dependency_type="production"
    )
    development_rows = _collect_direct_dependencies(
        package_payload, lock_payload, dependency_type="development"
    )
    all_rows = production_rows + development_rows

    production_lock_failures = _dependency_lock_failures(production_rows)
    development_lock_failures = _dependency_lock_failures(development_rows)
    integrity_failures = _dependency_integrity_failures(all_rows)
    audit = _audit_summary(audit_payload)

    native_candidates = _native_review_candidates(package_payload)
    unreviewed_native = sorted(
        native_candidates - set(NATIVE_SURFACE_REVIEW) - LOW_RISK_NATIVE_REVIEW_ALLOWLIST
    )
    native_review = _native_review_rows(package_payload)

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        "package_lock_root_matches_package",
        lock_root.get("name") == package_payload.get("name")
        and lock_root.get("version") == package_payload.get("version"),
        (
            f"package={package_payload.get('name')!r}/{package_payload.get('version')!r}, "
            f"lock={lock_root.get('name')!r}/{lock_root.get('version')!r}"
        ),
    )
    _check(
        checks,
        "direct_dependencies_locked",
        not production_lock_failures,
        f"failures={production_lock_failures!r}",
    )
    _check(
        checks,
        "direct_dev_dependencies_locked",
        not development_lock_failures,
        f"failures={development_lock_failures!r}",
    )
    _check(
        checks,
        "direct_dependency_integrity_present",
        not integrity_failures,
        f"failures={integrity_failures!r}",
    )
    _check(
        checks,
        "production_audit_no_known_vulnerabilities",
        audit["status"] == "pass",
        f"vulnerabilities={audit['vulnerabilities']!r}",
    )
    _check(
        checks,
        "native_sensitive_dependency_surface_reviewed",
        not unreviewed_native,
        f"unreviewed_native_dependencies={unreviewed_native!r}",
    )

    failed_checks = [check["id"] for check in checks if check["status"] != "pass"]
    remediation = []
    if production_lock_failures or development_lock_failures or integrity_failures:
        remediation.append(
            {
                "id": "refresh_mobile_lockfile",
                "command": "cd apps/field-mobile && npm install --package-lock-only",
            }
        )
    if audit["status"] != "pass":
        remediation.append(
            {
                "id": "remediate_mobile_prod_vulnerabilities",
                "command": "cd apps/field-mobile && npm audit --omit=dev",
            }
        )
    if unreviewed_native:
        remediation.append(
            {
                "id": "review_new_native_dependency_surface",
                "action": (
                    "Classify native surfaces in build_mobile_dependency_review.py "
                    "and update privacy/release controls before release."
                ),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "status": "fail" if failed_checks else "pass",
        "risk_traceability": {
            "risk_id": RISK_ID,
            "hazard": "Vulnerability in connected component",
            "verification": "Mobile dependency review artifact plus npm audit summary",
        },
        "traceability": _traceability(env),
        "package": {
            "name": package_payload.get("name"),
            "version": package_payload.get("version"),
            "node_engine": _as_dict(package_payload.get("engines")).get("node"),
        },
        "lockfile": {
            "path": str(package_lock),
            "sha256": _sha256_file(package_lock),
            "lockfile_version": lock_payload.get("lockfileVersion"),
            "direct_production_dependency_count": len(production_rows),
            "direct_development_dependency_count": len(development_rows),
            "locked_package_count": len(packages),
        },
        "audit": audit,
        "native_sensitive_dependency_surface": native_review,
        "direct_dependencies": all_rows,
        "checks": checks,
        "failed_checks": failed_checks,
        "remediation": remediation,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build mobile dependency and production audit release evidence."
    )
    parser.add_argument("--package-json", type=Path, required=True)
    parser.add_argument("--package-lock", type=Path, required=True)
    parser.add_argument("--audit-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    review = build_dependency_review(
        package_json=args.package_json,
        package_lock=args.package_lock,
        audit_json=args.audit_json,
        env=os.environ,
    )
    encoded = json.dumps(review, ensure_ascii=False, indent=2)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if review["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
