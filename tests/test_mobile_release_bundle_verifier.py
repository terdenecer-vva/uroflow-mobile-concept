from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/verify_mobile_release_bundle.py")
GIT_SHA = "599254d39fd45be81d512f6a99744ed0f1e3b39d"
RUN_ID = "27038378926"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _valid_bundle(tmp_path: Path) -> dict[str, Path]:
    notes_path = tmp_path / "mobile-release-notes.md"
    notes_path.write_text(
        "# Uroflow Field Mobile Release Notes\n\nBundle verifier test notes.\n",
        encoding="utf-8",
    )
    dependency_review = {
        "schema_version": "mobile_dependency_review_v0.1",
        "status": "pass",
        "failed_checks": [],
        "traceability": {
            "git_sha": GIT_SHA,
            "git_ref": "refs/heads/main",
            "git_run_id": RUN_ID,
            "workflow": "Mobile Build",
        },
        "audit": {
            "status": "pass",
            "vulnerabilities": {
                "info": 0,
                "low": 0,
                "moderate": 0,
                "high": 0,
                "critical": 0,
                "total": 0,
            },
        },
    }
    dependency_review_path = tmp_path / "mobile-dependency-review.json"
    _write_json(dependency_review_path, dependency_review)
    smoke_template_summary = {
        "schema_version": "mobile_device_smoke_log_v0.1",
        "status": "pass",
        "device_count": 2,
        "platforms_seen": ["android", "ios"],
        "required_check_ids": ["app_launch"],
        "errors": [],
    }
    smoke_template_summary_path = tmp_path / "mobile-device-smoke-template-summary.json"
    _write_json(smoke_template_summary_path, smoke_template_summary)

    readiness = {
        "status": "ready_except_external_credentials",
        "local_checks_status": "pass",
        "external_readiness_status": "blocked",
        "authenticated_eas_status": "blocked",
        "authenticated_eas_blockers": ["expo_token", "eas_project_identity"],
        "clinical_hub_live_api_status": "missing",
        "traceability": {
            "git_sha": GIT_SHA,
            "git_ref": "refs/heads/main",
            "git_run_id": RUN_ID,
            "workflow": "Mobile Build",
        },
        "local_checks": [
            {"id": "mobile_store_rollout_handoff_template_present", "status": "pass"},
            {
                "id": "android_runtime_permissions_minimal",
                "status": "pass",
                "severity": "warning",
            },
        ],
        "external_items": [
            {"id": "expo_token", "status": "missing"},
            {"id": "eas_project_identity", "status": "missing"},
            {"id": "clinical_hub_live_api", "status": "missing"},
        ],
        "manual_external_items": [
            {"id": "apple_developer_account", "status": "manual_required"},
            {"id": "google_play_account", "status": "manual_required"},
        ],
        "next_actions": [
            {"id": "configure_expo_token"},
            {"id": "configure_eas_project_identity"},
        ],
    }
    readiness_path = tmp_path / "mobile-release-readiness.json"
    _write_json(readiness_path, readiness)

    manifest = {
        "release": {"profile": "preview", "channel": "preview"},
        "traceability": copy.deepcopy(readiness["traceability"]),
        "readiness": {
            "status": readiness["status"],
            "local_checks_status": readiness["local_checks_status"],
            "external_readiness_status": readiness["external_readiness_status"],
            "authenticated_eas_status": readiness["authenticated_eas_status"],
            "authenticated_eas_blockers": readiness["authenticated_eas_blockers"],
            "clinical_hub_live_api_status": readiness["clinical_hub_live_api_status"],
            "local_check_counts": {"pass": 2},
            "failed_local_checks": [],
            "warning_local_checks": ["android_runtime_permissions_minimal"],
            "external_items": [
                {"id": "expo_token", "status": "missing"},
                {"id": "eas_project_identity", "status": "missing"},
                {"id": "clinical_hub_live_api", "status": "missing"},
            ],
            "manual_external_items": [
                {"id": "apple_developer_account", "status": "manual_required"},
                {"id": "google_play_account", "status": "manual_required"},
            ],
            "next_action_ids": [
                "configure_expo_token",
                "configure_eas_project_identity",
            ],
        },
        "release_notes": {
            "present": True,
            "bytes": notes_path.stat().st_size,
            "sha256": _sha256(notes_path),
            "title": "Uroflow Field Mobile Release Notes",
        },
    }
    manifest_path = tmp_path / "mobile-release-manifest.json"
    _write_json(manifest_path, manifest)

    handoff = {
        "release": {
            "git_sha": GIT_SHA,
            "build_profile": "preview",
            "build_channel": "preview",
            "mobile_release_manifest_sha256": _sha256(manifest_path),
            "mobile_release_readiness_sha256": _sha256(readiness_path),
            "mobile_release_notes_sha256": _sha256(notes_path),
            "mobile_dependency_review_sha256": _sha256(dependency_review_path),
            "mobile_device_smoke_template_summary_sha256": _sha256(
                smoke_template_summary_path
            ),
        }
    }
    handoff_path = tmp_path / "mobile-store-rollout-handoff.json"
    _write_json(handoff_path, handoff)

    handoff_summary = {
        "status": "pass",
        "rollout_status": "blocked_external",
        "blocked_channels": [
            "android:play_internal_testing",
            "ios:testflight_internal",
        ],
        "required_channels": [
            "android:play_internal_testing",
            "ios:testflight_internal",
        ],
    }
    handoff_summary_path = tmp_path / "mobile-store-rollout-handoff-summary.json"
    _write_json(handoff_summary_path, handoff_summary)

    return {
        "manifest": manifest_path,
        "readiness": readiness_path,
        "notes": notes_path,
        "dependency_review": dependency_review_path,
        "smoke_template_summary": smoke_template_summary_path,
        "handoff": handoff_path,
        "handoff_summary": handoff_summary_path,
    }


def _run_verifier(
    paths: dict[str, Path],
    *,
    check: bool = True,
    expect_git_sha: str | None = GIT_SHA,
    expect_run_id: str | None = RUN_ID,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(SCRIPT),
        "--manifest-json",
        str(paths["manifest"]),
        "--readiness-json",
        str(paths["readiness"]),
        "--release-notes",
        str(paths["notes"]),
        "--dependency-review-json",
        str(paths["dependency_review"]),
        "--smoke-template-summary-json",
        str(paths["smoke_template_summary"]),
        "--store-rollout-handoff-json",
        str(paths["handoff"]),
        "--store-rollout-summary-json",
        str(paths["handoff_summary"]),
        "--output",
        str(paths["manifest"].parent / "bundle-summary.json"),
    ]
    if expect_git_sha is not None:
        command.extend(["--expect-git-sha", expect_git_sha])
    if expect_run_id is not None:
        command.extend(["--expect-run-id", expect_run_id])
    return subprocess.run(command, check=check, text=True, capture_output=True)


def test_mobile_release_bundle_verifier_accepts_consistent_bundle(tmp_path: Path) -> None:
    paths = _valid_bundle(tmp_path)

    result = _run_verifier(paths)
    summary = json.loads(result.stdout)

    assert summary["status"] == "pass"
    assert summary["traceability"]["git_sha"] == GIT_SHA
    assert summary["local_check_counts"] == {"pass": 2}
    assert summary["store_rollout_status"] == "blocked_external"
    assert summary["store_rollout_blocked_channels"] == [
        "android:play_internal_testing",
        "ios:testflight_internal",
    ]
    assert "mobile_dependency_review" in summary["artifact_sha256"]
    assert "mobile_device_smoke_template_summary" in summary["artifact_sha256"]
    assert json.loads((tmp_path / "bundle-summary.json").read_text()) == summary


def test_mobile_release_bundle_verifier_rejects_handoff_digest_mismatch(
    tmp_path: Path,
) -> None:
    paths = _valid_bundle(tmp_path)
    handoff = json.loads(paths["handoff"].read_text(encoding="utf-8"))
    handoff["release"]["mobile_release_manifest_sha256"] = "0" * 64
    _write_json(paths["handoff"], handoff)

    result = _run_verifier(paths, check=False)
    summary = json.loads(result.stdout)

    assert result.returncode == 1
    assert summary["status"] == "fail"
    assert any("mobile_release_manifest_sha256 mismatch" in error for error in summary["errors"])


def test_mobile_release_bundle_verifier_rejects_readiness_count_mismatch(
    tmp_path: Path,
) -> None:
    paths = _valid_bundle(tmp_path)
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    manifest["readiness"]["local_check_counts"] = {"pass": 1}
    _write_json(paths["manifest"], manifest)

    result = _run_verifier(paths, check=False)
    summary = json.loads(result.stdout)

    assert result.returncode == 1
    assert summary["status"] == "fail"
    assert any("local_check_counts mismatch" in error for error in summary["errors"])


def test_mobile_release_bundle_verifier_rejects_smoke_template_digest_mismatch(
    tmp_path: Path,
) -> None:
    paths = _valid_bundle(tmp_path)
    handoff = json.loads(paths["handoff"].read_text(encoding="utf-8"))
    handoff["release"]["mobile_device_smoke_template_summary_sha256"] = "0" * 64
    _write_json(paths["handoff"], handoff)

    result = _run_verifier(paths, check=False)
    summary = json.loads(result.stdout)

    assert result.returncode == 1
    assert summary["status"] == "fail"
    assert any(
        "mobile_device_smoke_template_summary_sha256 mismatch" in error
        for error in summary["errors"]
    )


def test_mobile_release_bundle_verifier_rejects_dependency_review_digest_mismatch(
    tmp_path: Path,
) -> None:
    paths = _valid_bundle(tmp_path)
    handoff = json.loads(paths["handoff"].read_text(encoding="utf-8"))
    handoff["release"]["mobile_dependency_review_sha256"] = "0" * 64
    _write_json(paths["handoff"], handoff)

    result = _run_verifier(paths, check=False)
    summary = json.loads(result.stdout)

    assert result.returncode == 1
    assert summary["status"] == "fail"
    assert any(
        "mobile_dependency_review_sha256 mismatch" in error
        for error in summary["errors"]
    )


def test_mobile_release_bundle_verifier_rejects_failed_dependency_review(
    tmp_path: Path,
) -> None:
    paths = _valid_bundle(tmp_path)
    review_payload = json.loads(paths["dependency_review"].read_text(encoding="utf-8"))
    review_payload["status"] = "fail"
    review_payload["failed_checks"] = ["production_audit_no_known_vulnerabilities"]
    review_payload["audit"]["status"] = "fail"
    review_payload["audit"]["vulnerabilities"]["total"] = 1
    _write_json(paths["dependency_review"], review_payload)
    handoff = json.loads(paths["handoff"].read_text(encoding="utf-8"))
    handoff["release"]["mobile_dependency_review_sha256"] = _sha256(
        paths["dependency_review"]
    )
    _write_json(paths["handoff"], handoff)

    result = _run_verifier(paths, check=False)
    summary = json.loads(result.stdout)

    assert result.returncode == 1
    assert summary["status"] == "fail"
    assert "mobile_dependency_review.status must be 'pass'" in summary["errors"]
    assert "mobile_dependency_review.failed_checks must be empty" in summary["errors"]
    assert "mobile_dependency_review.audit.status must be 'pass'" in summary["errors"]
    assert (
        "mobile_dependency_review.audit.vulnerabilities.total must be 0"
        in summary["errors"]
    )


def test_mobile_release_bundle_verifier_rejects_missing_dependency_failed_checks(
    tmp_path: Path,
) -> None:
    paths = _valid_bundle(tmp_path)
    review_payload = json.loads(paths["dependency_review"].read_text(encoding="utf-8"))
    del review_payload["failed_checks"]
    _write_json(paths["dependency_review"], review_payload)
    handoff = json.loads(paths["handoff"].read_text(encoding="utf-8"))
    handoff["release"]["mobile_dependency_review_sha256"] = _sha256(
        paths["dependency_review"]
    )
    _write_json(paths["handoff"], handoff)

    result = _run_verifier(paths, check=False)
    summary = json.loads(result.stdout)

    assert result.returncode == 1
    assert summary["status"] == "fail"
    assert "mobile_dependency_review.failed_checks must be empty" in summary["errors"]


def test_mobile_release_bundle_verifier_rejects_failed_smoke_template_summary(
    tmp_path: Path,
) -> None:
    paths = _valid_bundle(tmp_path)
    summary_payload = json.loads(paths["smoke_template_summary"].read_text(encoding="utf-8"))
    summary_payload["status"] = "fail"
    summary_payload["errors"] = ["template failure"]
    _write_json(paths["smoke_template_summary"], summary_payload)
    handoff = json.loads(paths["handoff"].read_text(encoding="utf-8"))
    handoff["release"]["mobile_device_smoke_template_summary_sha256"] = _sha256(
        paths["smoke_template_summary"]
    )
    _write_json(paths["handoff"], handoff)

    result = _run_verifier(paths, check=False)
    summary = json.loads(result.stdout)

    assert result.returncode == 1
    assert summary["status"] == "fail"
    assert "mobile_device_smoke_template_summary.status must be 'pass'" in summary["errors"]
    assert "mobile_device_smoke_template_summary.errors must be empty" in summary["errors"]


def test_mobile_release_bundle_verifier_rejects_expected_git_sha_mismatch(
    tmp_path: Path,
) -> None:
    paths = _valid_bundle(tmp_path)

    result = _run_verifier(paths, check=False, expect_git_sha="bad-sha")
    summary = json.loads(result.stdout)

    assert result.returncode == 1
    assert summary["status"] == "fail"
    assert any("expected.git_sha mismatch" in error for error in summary["errors"])
