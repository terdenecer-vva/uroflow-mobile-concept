from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/check_mobile_release_readiness.py")
APP_JSON = Path("apps/field-mobile/app.json")
EAS_JSON = Path("apps/field-mobile/eas.json")
PACKAGE_JSON = Path("apps/field-mobile/package.json")
PACKAGE_LOCK = Path("apps/field-mobile/package-lock.json")


def _run_readiness(output: Path, env: dict[str, str]) -> dict:
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--app-json",
            str(APP_JSON),
            "--eas-json",
            str(EAS_JSON),
            "--package-json",
            str(PACKAGE_JSON),
            "--package-lock",
            str(PACKAGE_LOCK),
            "--output",
            str(output),
        ],
        check=True,
        env=env,
    )
    return json.loads(output.read_text(encoding="utf-8"))


def test_mobile_release_readiness_reports_external_blockers(tmp_path: Path) -> None:
    payload = _run_readiness(
        tmp_path / "readiness.json",
        env={"PATH": os.environ.get("PATH", "")},
    )

    assert payload["status"] == "ready_except_external_credentials"
    assert payload["local_checks_status"] == "pass"
    assert payload["external_readiness_status"] == "blocked"
    assert payload["authenticated_eas_status"] == "blocked"
    assert payload["authenticated_eas_blockers"] == ["expo_token", "eas_project_identity"]
    assert payload["clinical_hub_live_api_status"] == "missing"
    assert payload["traceability"] == {
        "git_ref": "local",
        "git_run_id": "local",
        "git_sha": "local",
        "workflow": "local",
    }
    assert {item["id"] for item in payload["external_items"] if item["status"] == "missing"} == {
        "clinical_hub_live_api",
        "eas_project_identity",
        "expo_token",
    }
    assert all(item["status"] == "pass" for item in payload["local_checks"])
    local_check_ids = {item["id"] for item in payload["local_checks"]}
    assert {
        "unit_test_script",
        "validate_ci_runs_unit_tests",
        "unit_test_runner_script",
        "mobile_helper_unit_tests_present",
        "capture_contract_unit_tests_present",
        "pending_submission_storage_unit_tests_present",
        "pending_sync_queue_unit_tests_present",
        "roi_signal_unit_tests_present",
        "runtime_metrics_unit_tests_present",
    }.issubset(local_check_ids)
    assert {item["id"] for item in payload["next_actions"]} == {
        "configure_clinical_hub_live_api",
        "configure_eas_project_identity",
        "configure_expo_token",
        "provision_apple_developer_account",
        "provision_google_play_account",
    }
    expo_action = next(
        item for item in payload["next_actions"] if item["id"] == "configure_expo_token"
    )
    assert expo_action["secret_names"] == ["EXPO_TOKEN"]
    assert expo_action["verification"]


def test_mobile_release_readiness_passes_authenticated_preflight_env(tmp_path: Path) -> None:
    payload = _run_readiness(
        tmp_path / "readiness.json",
        env={
            "PATH": os.environ.get("PATH", ""),
            "CLINICAL_HUB_API_KEY": "test-key",
            "CLINICAL_HUB_URL": "https://clinical.example.test",
            "EAS_PROJECT_ID": "00000000-0000-0000-0000-000000000000",
            "EXPO_TOKEN": "test-token",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_RUN_ID": "123456",
            "GITHUB_SHA": "abc123",
            "GITHUB_WORKFLOW": "Mobile Build",
        },
    )

    assert payload["status"] == "ready_for_authenticated_eas_preflight"
    assert payload["local_checks_status"] == "pass"
    assert payload["external_readiness_status"] == "pass"
    assert payload["authenticated_eas_status"] == "pass"
    assert payload["authenticated_eas_blockers"] == []
    assert payload["clinical_hub_live_api_status"] == "present"
    assert payload["traceability"] == {
        "git_ref": "refs/heads/main",
        "git_run_id": "123456",
        "git_sha": "abc123",
        "workflow": "Mobile Build",
    }
    assert all(item["status"] == "present" for item in payload["external_items"])
    assert {item["status"] for item in payload["manual_external_items"]} == {"manual_required"}
    assert {item["id"] for item in payload["next_actions"]} == {
        "provision_apple_developer_account",
        "provision_google_play_account",
    }


def test_mobile_release_readiness_separates_eas_from_clinical_hub(
    tmp_path: Path,
) -> None:
    payload = _run_readiness(
        tmp_path / "readiness.json",
        env={
            "PATH": os.environ.get("PATH", ""),
            "EAS_PROJECT_ID": "00000000-0000-0000-0000-000000000000",
            "EXPO_TOKEN": "test-token",
        },
    )

    assert payload["status"] == "ready_except_external_credentials"
    assert payload["external_readiness_status"] == "blocked"
    assert payload["authenticated_eas_status"] == "pass"
    assert payload["authenticated_eas_blockers"] == []
    assert payload["clinical_hub_live_api_status"] == "missing"
    assert {item["id"] for item in payload["next_actions"]} == {
        "configure_clinical_hub_live_api",
        "provision_apple_developer_account",
        "provision_google_play_account",
    }
