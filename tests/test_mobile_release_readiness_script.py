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


def _run_readiness_with_paths(
    output: Path,
    env: dict[str, str],
    *,
    app_json: Path = APP_JSON,
    eas_json: Path = EAS_JSON,
    package_json: Path = PACKAGE_JSON,
    package_lock: Path = PACKAGE_LOCK,
    check: bool = True,
) -> dict:
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--app-json",
            str(app_json),
            "--eas-json",
            str(eas_json),
            "--package-json",
            str(package_json),
            "--package-lock",
            str(package_lock),
            "--output",
            str(output),
        ],
        check=check,
        env=env,
    )
    return json.loads(output.read_text(encoding="utf-8"))


def _run_readiness(output: Path, env: dict[str, str]) -> dict:
    return _run_readiness_with_paths(output, env)


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
        "android_adaptive_icon_background_color",
        "android_adaptive_icon_png_asset",
        "android_runtime_permissions_minimal",
        "app_icon_png_asset",
        "app_version_matches_package_version",
        "app_settings_storage_unit_tests_present",
        "audio_microphone_permission",
        "clinical_hub_api_unit_tests_present",
        "capture_package_payload_unit_tests_present",
        "eas_cli_version_declared",
        "eas_production_auto_increment",
        "eas_profile_channels",
        "ios_privacy_usage_descriptions",
        "paired_payload_unit_tests_present",
        "package_lock_matches_root",
        "secure_store_dependency_locked",
        "secure_store_plugin",
        "splash_background_color",
        "splash_image_width",
        "splash_png_asset",
        "splash_resize_mode",
        "splash_screen_dependency_locked",
        "splash_screen_plugin",
        "unit_test_script",
        "validate_ci_runs_unit_tests",
        "unit_test_runner_script",
        "mobile_helper_unit_tests_present",
        "connection_check_unit_tests_present",
        "capture_contract_unit_tests_present",
        "pending_submission_storage_unit_tests_present",
        "pending_sync_queue_unit_tests_present",
        "roi_signal_unit_tests_present",
        "runtime_metrics_unit_tests_present",
        "release_metadata_capture_schema_version",
        "release_metadata_model_id",
        "release_metadata_module",
        "release_metadata_version_matches_expo",
        "summary_requests_unit_tests_present",
        "submit_outcome_unit_tests_present",
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


def test_mobile_release_readiness_fails_missing_app_icon(tmp_path: Path) -> None:
    mutated_app_json = tmp_path / "app.json"
    app_payload = json.loads(APP_JSON.read_text(encoding="utf-8"))
    app_payload["expo"]["icon"] = "./assets/missing-icon.png"
    mutated_app_json.write_text(json.dumps(app_payload), encoding="utf-8")

    payload = _run_readiness_with_paths(
        tmp_path / "readiness.json",
        env={"PATH": os.environ.get("PATH", "")},
        app_json=mutated_app_json,
        check=False,
    )

    check = next(item for item in payload["local_checks"] if item["id"] == "app_icon_png_asset")
    assert payload["status"] == "not_ready"
    assert payload["local_checks_status"] == "fail"
    assert check["status"] == "fail"
    assert "missing-icon.png" in check["evidence"]


def test_mobile_release_readiness_fails_missing_splash_asset(tmp_path: Path) -> None:
    mutated_app_json = tmp_path / "app.json"
    app_payload = json.loads(APP_JSON.read_text(encoding="utf-8"))
    splash_plugin = next(
        plugin
        for plugin in app_payload["expo"]["plugins"]
        if isinstance(plugin, list) and plugin[0] == "expo-splash-screen"
    )
    splash_plugin[1]["image"] = "./assets/missing-splash.png"
    mutated_app_json.write_text(json.dumps(app_payload), encoding="utf-8")

    payload = _run_readiness_with_paths(
        tmp_path / "readiness.json",
        env={"PATH": os.environ.get("PATH", "")},
        app_json=mutated_app_json,
        check=False,
    )

    check = next(item for item in payload["local_checks"] if item["id"] == "splash_png_asset")
    assert payload["status"] == "not_ready"
    assert payload["local_checks_status"] == "fail"
    assert check["status"] == "fail"
    assert "missing-splash.png" in check["evidence"]


def test_mobile_release_readiness_fails_local_version_mismatch(tmp_path: Path) -> None:
    mutated_app_json = tmp_path / "app.json"
    app_payload = json.loads(APP_JSON.read_text(encoding="utf-8"))
    app_payload["expo"]["version"] = "9.9.9"
    mutated_app_json.write_text(json.dumps(app_payload), encoding="utf-8")

    payload = _run_readiness_with_paths(
        tmp_path / "readiness.json",
        env={"PATH": os.environ.get("PATH", "")},
        app_json=mutated_app_json,
        check=False,
    )

    check = next(
        item
        for item in payload["local_checks"]
        if item["id"] == "app_version_matches_package_version"
    )
    assert payload["status"] == "not_ready"
    assert payload["local_checks_status"] == "fail"
    assert check["status"] == "fail"
    assert "expo.version='9.9.9'" in check["evidence"]


def test_mobile_release_readiness_fails_release_metadata_version_mismatch(
    tmp_path: Path,
) -> None:
    mutated_app_json = tmp_path / "app.json"
    metadata_path = tmp_path / "src" / "config" / "releaseMetadata.ts"
    metadata_path.parent.mkdir(parents=True)
    app_payload = json.loads(APP_JSON.read_text(encoding="utf-8"))
    mutated_app_json.write_text(json.dumps(app_payload), encoding="utf-8")
    metadata_path.write_text(
        "\n".join(
            [
                'export const APP_RELEASE_VERSION = "9.9.9";',
                'export const APP_MODEL_ID = "fusion-v0.1";',
                'export const APP_CAPTURE_SCHEMA_VERSION = "ios_capture_v1";',
            ]
        ),
        encoding="utf-8",
    )

    payload = _run_readiness_with_paths(
        tmp_path / "readiness.json",
        env={"PATH": os.environ.get("PATH", "")},
        app_json=mutated_app_json,
        check=False,
    )

    check = next(
        item
        for item in payload["local_checks"]
        if item["id"] == "release_metadata_version_matches_expo"
    )
    assert payload["status"] == "not_ready"
    assert payload["local_checks_status"] == "fail"
    assert check["status"] == "fail"
    assert "release_metadata.app_version='9.9.9'" in check["evidence"]


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
