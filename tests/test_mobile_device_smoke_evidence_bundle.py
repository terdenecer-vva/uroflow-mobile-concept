from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/verify_mobile_device_smoke_evidence_bundle.py")
SMOKE_VALIDATOR = Path("scripts/validate_mobile_device_smoke_log.py")
HANDOFF_VALIDATOR = Path("scripts/validate_mobile_store_rollout_handoff.py")
SMOKE_TEMPLATE = Path("docs/mobile-device-smoke-log-template-v0.1.json")
HANDOFF_TEMPLATE = Path("docs/mobile-store-rollout-handoff-template-v0.1.json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _set_handoff_check_status(payload: dict, check_id: str, status: str) -> None:
    for check in payload["handoff_checks"]:
        if check["id"] == check_id:
            check["status"] = status
            return
    raise AssertionError(f"missing handoff check {check_id!r}")


def _build_valid_bundle(tmp_path: Path) -> dict[str, Path]:
    smoke_log = tmp_path / "mobile-device-smoke-log.json"
    smoke_summary = tmp_path / "mobile-device-smoke-summary.json"
    smoke_payload = json.loads(SMOKE_TEMPLATE.read_text(encoding="utf-8"))
    _write_json(smoke_log, smoke_payload)
    subprocess.run(
        [
            sys.executable,
            str(SMOKE_VALIDATOR),
            str(smoke_log),
            "--output",
            str(smoke_summary),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    smoke_summary_payload = json.loads(smoke_summary.read_text(encoding="utf-8"))

    handoff_payload = json.loads(HANDOFF_TEMPLATE.read_text(encoding="utf-8"))
    _set_handoff_check_status(handoff_payload, "device_smoke_evidence_linked", "pass")
    handoff_payload["device_smoke_evidence"] = {
        "status": "pass",
        "mobile_device_smoke_log_sha256": smoke_summary_payload["smoke_log_sha256"],
        "mobile_device_smoke_summary_sha256": _sha256(smoke_summary),
        "summary_url": "https://github.com/example/run/artifacts/mobile-device-smoke-summary",
        "validated_at_utc": "2026-06-05T21:30:00Z",
        "validator_summary_status": smoke_summary_payload["status"],
        "platforms_seen": smoke_summary_payload["platforms_seen"],
        "blockers": [],
    }
    handoff = tmp_path / "mobile-store-rollout-handoff.json"
    handoff_summary = tmp_path / "mobile-store-rollout-handoff-summary.json"
    _write_json(handoff, handoff_payload)
    subprocess.run(
        [
            sys.executable,
            str(HANDOFF_VALIDATOR),
            str(handoff),
            "--output",
            str(handoff_summary),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    return {
        "smoke_log": smoke_log,
        "smoke_summary": smoke_summary,
        "handoff": handoff,
        "handoff_summary": handoff_summary,
    }


def _run_verifier(
    paths: dict[str, Path],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--device-smoke-log-json",
            str(paths["smoke_log"]),
            "--device-smoke-summary-json",
            str(paths["smoke_summary"]),
            "--store-rollout-handoff-json",
            str(paths["handoff"]),
            "--store-rollout-summary-json",
            str(paths["handoff_summary"]),
            "--output",
            str(paths["smoke_log"].parent / "device-smoke-evidence-bundle.json"),
        ],
        check=check,
        text=True,
        capture_output=True,
    )


def test_mobile_device_smoke_evidence_bundle_accepts_linked_evidence(
    tmp_path: Path,
) -> None:
    paths = _build_valid_bundle(tmp_path)

    result = _run_verifier(paths)
    summary = json.loads(result.stdout)

    assert summary["status"] == "pass"
    assert summary["smoke_log_sha256"] == _sha256(paths["smoke_log"])
    assert summary["smoke_summary_sha256"] == _sha256(paths["smoke_summary"])
    assert summary["smoke_summary_status"] == "pass"
    assert summary["platforms_seen"] == ["android", "ios"]
    assert summary["device_smoke_evidence_status"] == "pass"
    assert summary["device_smoke_evidence_validator_summary_status"] == "pass"
    assert summary["device_smoke_evidence_platforms_seen"] == ["android", "ios"]
    assert json.loads(
        (tmp_path / "device-smoke-evidence-bundle.json").read_text(encoding="utf-8")
    ) == summary


def test_mobile_device_smoke_evidence_bundle_rejects_stale_log_digest(
    tmp_path: Path,
) -> None:
    paths = _build_valid_bundle(tmp_path)
    handoff = json.loads(paths["handoff"].read_text(encoding="utf-8"))
    handoff["device_smoke_evidence"]["mobile_device_smoke_log_sha256"] = "0" * 64
    _write_json(paths["handoff"], handoff)

    result = _run_verifier(paths, check=False)
    summary = json.loads(result.stdout)

    assert result.returncode == 1
    assert summary["status"] == "fail"
    assert any(
        "store_rollout_handoff.device_smoke_evidence.mobile_device_smoke_log_sha256 mismatch"
        in error
        for error in summary["errors"]
    )


def test_mobile_device_smoke_evidence_bundle_rejects_stale_handoff_summary(
    tmp_path: Path,
) -> None:
    paths = _build_valid_bundle(tmp_path)
    handoff_summary = json.loads(paths["handoff_summary"].read_text(encoding="utf-8"))
    handoff_summary["device_smoke_evidence_platforms_seen"] = ["ios"]
    handoff_summary["device_smoke_evidence_summary_sha256"] = "1" * 64
    _write_json(paths["handoff_summary"], handoff_summary)

    result = _run_verifier(paths, check=False)
    summary = json.loads(result.stdout)

    assert result.returncode == 1
    assert summary["status"] == "fail"
    assert any(
        "store_rollout_handoff.summary.device_smoke_evidence_platforms_seen mismatch"
        in error
        for error in summary["errors"]
    )
    assert any(
        "store_rollout_handoff.summary.device_smoke_evidence_summary_sha256 mismatch"
        in error
        for error in summary["errors"]
    )


def test_mobile_device_smoke_evidence_bundle_rejects_failed_smoke_summary(
    tmp_path: Path,
) -> None:
    paths = _build_valid_bundle(tmp_path)
    smoke_summary = json.loads(paths["smoke_summary"].read_text(encoding="utf-8"))
    smoke_summary = copy.deepcopy(smoke_summary)
    smoke_summary["status"] = "fail"
    smoke_summary["errors"] = ["devices must include at least one android smoke run"]
    _write_json(paths["smoke_summary"], smoke_summary)
    handoff = json.loads(paths["handoff"].read_text(encoding="utf-8"))
    handoff["device_smoke_evidence"]["mobile_device_smoke_summary_sha256"] = _sha256(
        paths["smoke_summary"]
    )
    _write_json(paths["handoff"], handoff)

    result = _run_verifier(paths, check=False)
    summary = json.loads(result.stdout)

    assert result.returncode == 1
    assert summary["status"] == "fail"
    assert "mobile_device_smoke_summary.status must be 'pass'" in summary["errors"]
    assert "mobile_device_smoke_summary.errors must be empty" in summary["errors"]
