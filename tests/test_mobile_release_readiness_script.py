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
        "default_api_base_url_not_localhost",
        "eas_cli_version_declared",
        "eas_production_auto_increment",
        "eas_profile_channels",
        "ios_privacy_usage_descriptions",
        "app_config_unit_tests_present",
        "paired_payload_unit_tests_present",
        "package_lock_matches_root",
        "runtime_config_data_residency_policy",
        "runtime_config_default_capture_mode",
        "runtime_config_debug_gates_disabled",
        "runtime_config_endpoint_set",
        "runtime_config_module",
        "runtime_config_privacy_by_default",
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
        "mobile_api_response_redaction_sources",
        "mobile_api_response_redaction_unit_tests_present",
        "mobile_phi_exception_redaction_sources",
        "mobile_phi_exception_redaction_unit_tests_present",
        "mobile_feature_media_manifest_sources",
        "mobile_feature_media_manifest_unit_tests_present",
        "connection_check_unit_tests_present",
        "capture_contract_unit_tests_present",
        "pending_submission_storage_unit_tests_present",
        "pending_sync_connectivity_restore_sources",
        "pending_sync_connectivity_restore_unit_tests_present",
        "pending_sync_queue_unit_tests_present",
        "roi_signal_unit_tests_present",
        "runtime_metrics_unit_tests_present",
        "runtime_motion_quality_gate_sources",
        "runtime_motion_quality_gate_unit_tests_present",
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


def test_mobile_release_readiness_fails_localhost_default_api_url(tmp_path: Path) -> None:
    mutated_app_json = tmp_path / "app.json"
    app_settings_path = tmp_path / "src" / "storage" / "appSettingsStorage.ts"
    app_settings_path.parent.mkdir(parents=True)
    app_payload = json.loads(APP_JSON.read_text(encoding="utf-8"))
    mutated_app_json.write_text(json.dumps(app_payload), encoding="utf-8")
    app_settings_path.write_text(
        'export const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";\n',
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
        if item["id"] == "default_api_base_url_not_localhost"
    )
    assert payload["status"] == "not_ready"
    assert payload["local_checks_status"] == "fail"
    assert check["status"] == "fail"
    assert "http://127.0.0.1:8000" in check["evidence"]


def test_mobile_release_readiness_fails_raw_media_runtime_config(tmp_path: Path) -> None:
    mutated_app_json = tmp_path / "app.json"
    app_config_path = tmp_path / "src" / "config" / "appConfig.ts"
    app_config_path.parent.mkdir(parents=True)
    app_payload = json.loads(APP_JSON.read_text(encoding="utf-8"))
    mutated_app_json.write_text(json.dumps(app_payload), encoding="utf-8")
    app_config_path.write_text(
        "\n".join(
            [
                'export const APP_RUNTIME_MODE = "pilot";',
                'export const APP_ENDPOINT_SET = "clinical_hub_v1";',
                'export const APP_DEFAULT_CAPTURE_MODE = "water_impact";',
                (
                    'export const APP_PAIRED_MEASUREMENTS_ENDPOINT_PATH = '
                    '"/api/v1/paired-measurements";'
                ),
                (
                    'export const APP_CAPTURE_PACKAGES_ENDPOINT_PATH = '
                    '"/api/v1/capture-packages";'
                ),
                "export const APP_STORE_RAW_VIDEO = true;",
                "export const APP_STORE_RAW_AUDIO = false;",
                "export const APP_ROI_ONLY = true;",
                'export const APP_DATA_RESIDENCY_REGION = "us";',
                'export const APP_DATA_RESIDENCY_BOUNDARY = "single_region";',
                "export const APP_ALLOW_CROSS_REGION_SYNC = false;",
                "export const APP_REQUIRE_REGION_MATCHED_CLINICAL_HUB = true;",
                "export const APP_ALLOW_DEBUG_CONTROLS = false;",
                "export const APP_ALLOW_RAW_RESPONSE_DETAILS = false;",
                "export const APP_ENABLE_VERBOSE_LOGGING = false;",
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
        if item["id"] == "runtime_config_privacy_by_default"
    )
    assert payload["status"] == "not_ready"
    assert payload["local_checks_status"] == "fail"
    assert check["status"] == "fail"
    assert "store_raw_video=True" in check["evidence"]


def test_mobile_release_readiness_fails_cross_region_runtime_config(tmp_path: Path) -> None:
    mutated_app_json = tmp_path / "app.json"
    app_config_path = tmp_path / "src" / "config" / "appConfig.ts"
    app_config_path.parent.mkdir(parents=True)
    app_payload = json.loads(APP_JSON.read_text(encoding="utf-8"))
    mutated_app_json.write_text(json.dumps(app_payload), encoding="utf-8")
    app_config_path.write_text(
        "\n".join(
            [
                'export const APP_RUNTIME_MODE = "pilot";',
                'export const APP_ENDPOINT_SET = "clinical_hub_v1";',
                'export const APP_DEFAULT_CAPTURE_MODE = "water_impact";',
                (
                    'export const APP_PAIRED_MEASUREMENTS_ENDPOINT_PATH = '
                    '"/api/v1/paired-measurements";'
                ),
                (
                    'export const APP_CAPTURE_PACKAGES_ENDPOINT_PATH = '
                    '"/api/v1/capture-packages";'
                ),
                "export const APP_STORE_RAW_VIDEO = false;",
                "export const APP_STORE_RAW_AUDIO = false;",
                "export const APP_ROI_ONLY = true;",
                'export const APP_DATA_RESIDENCY_REGION = "us";',
                'export const APP_DATA_RESIDENCY_BOUNDARY = "multi_region";',
                "export const APP_ALLOW_CROSS_REGION_SYNC = true;",
                "export const APP_REQUIRE_REGION_MATCHED_CLINICAL_HUB = false;",
                "export const APP_ALLOW_DEBUG_CONTROLS = false;",
                "export const APP_ALLOW_RAW_RESPONSE_DETAILS = false;",
                "export const APP_ENABLE_VERBOSE_LOGGING = false;",
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
        if item["id"] == "runtime_config_data_residency_policy"
    )
    assert payload["status"] == "not_ready"
    assert payload["local_checks_status"] == "fail"
    assert check["status"] == "fail"
    assert "allow_cross_region_sync=True" in check["evidence"]


def test_mobile_release_readiness_fails_debug_runtime_config(tmp_path: Path) -> None:
    mutated_app_json = tmp_path / "app.json"
    app_config_path = tmp_path / "src" / "config" / "appConfig.ts"
    app_config_path.parent.mkdir(parents=True)
    app_payload = json.loads(APP_JSON.read_text(encoding="utf-8"))
    mutated_app_json.write_text(json.dumps(app_payload), encoding="utf-8")
    app_config_path.write_text(
        "\n".join(
            [
                'export const APP_RUNTIME_MODE = "pilot";',
                'export const APP_ENDPOINT_SET = "clinical_hub_v1";',
                'export const APP_DEFAULT_CAPTURE_MODE = "water_impact";',
                (
                    'export const APP_PAIRED_MEASUREMENTS_ENDPOINT_PATH = '
                    '"/api/v1/paired-measurements";'
                ),
                (
                    'export const APP_CAPTURE_PACKAGES_ENDPOINT_PATH = '
                    '"/api/v1/capture-packages";'
                ),
                "export const APP_STORE_RAW_VIDEO = false;",
                "export const APP_STORE_RAW_AUDIO = false;",
                "export const APP_ROI_ONLY = true;",
                'export const APP_DATA_RESIDENCY_REGION = "us";',
                'export const APP_DATA_RESIDENCY_BOUNDARY = "single_region";',
                "export const APP_ALLOW_CROSS_REGION_SYNC = false;",
                "export const APP_REQUIRE_REGION_MATCHED_CLINICAL_HUB = true;",
                "export const APP_ALLOW_DEBUG_CONTROLS = true;",
                "export const APP_ALLOW_RAW_RESPONSE_DETAILS = false;",
                "export const APP_ENABLE_VERBOSE_LOGGING = false;",
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
        if item["id"] == "runtime_config_debug_gates_disabled"
    )
    assert payload["status"] == "not_ready"
    assert payload["local_checks_status"] == "fail"
    assert check["status"] == "fail"
    assert "allow_debug_controls=True" in check["evidence"]


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


def test_mobile_release_readiness_rejects_insecure_live_clinical_hub_url(
    tmp_path: Path,
) -> None:
    payload = _run_readiness(
        tmp_path / "readiness.json",
        env={
            "PATH": os.environ.get("PATH", ""),
            "CLINICAL_HUB_API_KEY": "test-key",
            "CLINICAL_HUB_URL": "http://127.0.0.1:8000",
            "EAS_PROJECT_ID": "00000000-0000-0000-0000-000000000000",
            "EXPO_TOKEN": "test-token",
        },
    )

    clinical_hub_item = next(
        item for item in payload["external_items"] if item["id"] == "clinical_hub_live_api"
    )
    assert payload["status"] == "ready_except_external_credentials"
    assert payload["external_readiness_status"] == "blocked"
    assert payload["authenticated_eas_status"] == "pass"
    assert payload["clinical_hub_live_api_status"] == "invalid"
    assert clinical_hub_item["status"] == "invalid"
    assert "https" in clinical_hub_item["evidence"]
    assert {item["id"] for item in payload["next_actions"]} == {
        "configure_clinical_hub_live_api",
        "provision_apple_developer_account",
        "provision_google_play_account",
    }
