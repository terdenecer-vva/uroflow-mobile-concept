from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/validate_mobile_device_smoke_log.py")
TEMPLATE = Path("docs/mobile-device-smoke-log-template-v0.1.json")


def _valid_payload() -> dict:
    return json.loads(TEMPLATE.read_text(encoding="utf-8"))


def _run_validator(
    tmp_path: Path,
    payload: dict,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    smoke_log = tmp_path / "smoke-log.json"
    output = tmp_path / "summary.json"
    smoke_log.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(smoke_log),
            "--output",
            str(output),
        ],
        check=check,
        text=True,
        capture_output=True,
    )


def test_mobile_device_smoke_log_template_validates(tmp_path: Path) -> None:
    result = _run_validator(tmp_path, _valid_payload())
    summary = json.loads(result.stdout)

    assert summary["status"] == "pass"
    assert summary["device_count"] == 2
    assert summary["platforms_seen"] == ["android", "ios"]
    assert "connectivity_restore_sync" in summary["required_check_ids"]
    assert "device_logs_reviewed_no_phi" in summary["required_check_ids"]
    assert "runtime_timeline_integrity" in summary["required_check_ids"]
    assert json.loads((tmp_path / "summary.json").read_text(encoding="utf-8")) == summary


def test_mobile_device_smoke_log_requires_ios_and_android(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["devices"] = [device for device in payload["devices"] if device["platform"] == "ios"]

    result = _run_validator(tmp_path, payload, check=False)
    summary = json.loads(result.stdout)

    assert result.returncode == 1
    assert summary["status"] == "fail"
    assert "devices must include at least one android smoke run" in summary["errors"]


def test_mobile_device_smoke_log_requires_passing_required_checks(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload = copy.deepcopy(payload)
    payload["devices"][0]["checks"][0] = {
        **payload["devices"][0]["checks"][0],
        "status": "fail",
        "evidence": "App crashed on launch.",
    }

    result = _run_validator(tmp_path, payload, check=False)
    summary = json.loads(result.stdout)

    assert result.returncode == 1
    assert summary["status"] == "fail"
    assert "devices[0].checks[app_launch].status must be 'pass'" in summary["errors"]


def test_mobile_device_smoke_log_requires_runtime_timeline(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload = copy.deepcopy(payload)
    del payload["devices"][0]["runtime_timeline"]

    result = _run_validator(tmp_path, payload, check=False)
    summary = json.loads(result.stdout)

    assert result.returncode == 1
    assert summary["status"] == "fail"
    assert "devices[0].runtime_timeline is required" in summary["errors"]


def test_mobile_device_smoke_log_rejects_timeline_gap_warning(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload = copy.deepcopy(payload)
    payload["devices"][0]["runtime_timeline"]["gap_warning"] = True

    result = _run_validator(tmp_path, payload, check=False)
    summary = json.loads(result.stdout)

    assert result.returncode == 1
    assert summary["status"] == "fail"
    assert (
        "devices[0].runtime_timeline.gap_warning must be false for release smoke evidence"
        in summary["errors"]
    )
