from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/validate_mobile_store_rollout_handoff.py")
TEMPLATE = Path("docs/mobile-store-rollout-handoff-template-v0.1.json")
SHA256_ZERO = "0" * 64


def _valid_payload() -> dict:
    return json.loads(TEMPLATE.read_text(encoding="utf-8"))


def _run_validator(
    tmp_path: Path,
    payload: dict,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    handoff = tmp_path / "store-rollout-handoff.json"
    output = tmp_path / "summary.json"
    handoff.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(handoff),
            "--output",
            str(output),
        ],
        check=check,
        text=True,
        capture_output=True,
    )


def test_mobile_store_rollout_handoff_template_validates(tmp_path: Path) -> None:
    result = _run_validator(tmp_path, _valid_payload())
    summary = json.loads(result.stdout)

    assert summary["status"] == "pass"
    assert summary["rollout_status"] == "blocked_external"
    assert summary["channels_seen"] == [
        "android:play_internal_testing",
        "ios:testflight_internal",
    ]
    assert summary["blocked_channels"] == [
        "android:play_internal_testing",
        "ios:testflight_internal",
    ]
    assert "mobile_release_manifest_archived" in summary["required_handoff_check_ids"]
    assert (
        "mobile_device_smoke_template_validation_archived"
        in summary["required_handoff_check_ids"]
    )
    assert "eas_ios_build_uploaded" in summary["required_channel_check_ids"][
        "ios:testflight_internal"
    ]
    assert json.loads((tmp_path / "summary.json").read_text(encoding="utf-8")) == summary


def test_mobile_store_rollout_handoff_requires_ios_and_android(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["channels"] = [
        channel for channel in payload["channels"] if channel["platform"] == "ios"
    ]

    result = _run_validator(tmp_path, payload, check=False)
    summary = json.loads(result.stdout)

    assert result.returncode == 1
    assert summary["status"] == "fail"
    assert "channels must include android play_internal_testing handoff" in summary["errors"]


def test_mobile_store_rollout_handoff_requires_pass_checks_for_distribution(
    tmp_path: Path,
) -> None:
    payload = copy.deepcopy(_valid_payload())
    payload["rollout_status"] = "distributed"
    payload["handoff_checks"] = [
        {**check, "status": "pass"} for check in payload["handoff_checks"]
    ]
    ios_channel = payload["channels"][0]
    ios_channel["status"] = "distributed"
    ios_channel["blockers"] = []
    ios_channel["build_artifact"] = {
        "eas_build_id": "eas-ios-001",
        "eas_build_url": "https://expo.dev/accounts/example/projects/uroflow/builds/ios",
        "store_build_number": "1",
        "artifact_sha256": SHA256_ZERO,
    }
    ios_channel["store_submission"] = {
        "store_console_url": "https://appstoreconnect.apple.com/apps/example/testflight",
        "submitted_at_utc": "2026-06-05T21:00:00Z",
        "submitted_by": "release_engineer",
        "tester_group_or_track": "Pilot internal testers",
    }

    result = _run_validator(tmp_path, payload, check=False)
    summary = json.loads(result.stdout)

    assert result.returncode == 1
    assert summary["status"] == "fail"
    assert "channels[0].checks[apple_developer_access].status must be 'pass'" in summary[
        "errors"
    ]


def test_mobile_store_rollout_handoff_rejects_invalid_release_sha(
    tmp_path: Path,
) -> None:
    payload = _valid_payload()
    payload["release"]["mobile_release_manifest_sha256"] = "A" * 64

    result = _run_validator(tmp_path, payload, check=False)
    summary = json.loads(result.stdout)

    assert result.returncode == 1
    assert summary["status"] == "fail"
    assert (
        "release.mobile_release_manifest_sha256 must be a lowercase SHA-256 hex digest"
        in summary["errors"]
    )


def test_mobile_store_rollout_handoff_rejects_invalid_smoke_template_sha(
    tmp_path: Path,
) -> None:
    payload = _valid_payload()
    payload["release"]["mobile_device_smoke_template_summary_sha256"] = "A" * 64

    result = _run_validator(tmp_path, payload, check=False)
    summary = json.loads(result.stdout)

    assert result.returncode == 1
    assert summary["status"] == "fail"
    assert (
        "release.mobile_device_smoke_template_summary_sha256 must be a lowercase "
        "SHA-256 hex digest"
    ) in summary["errors"]
