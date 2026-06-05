#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _asset_path(app_json: Path, raw_path: Any) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = app_json.parent / candidate
    return candidate


def _png_dimensions(path: Path | None) -> tuple[int, int] | None:
    if path is None or not path.is_file():
        return None
    header = path.read_bytes()[:24]
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        return None
    return int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")


def _is_six_digit_hex_color(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 7
        and value.startswith("#")
        and all(character in "0123456789abcdefABCDEF" for character in value[1:])
    )


def _read_ts_string_constant(source: str, name: str) -> str | None:
    pattern = re.compile(rf"export\s+const\s+{re.escape(name)}\s*=\s*[\"']([^\"']*)[\"']")
    match = pattern.search(source)
    return match.group(1) if match else None


def _load_release_metadata(app_json: Path) -> dict[str, str | None]:
    path = app_json.parent / "src" / "config" / "releaseMetadata.ts"
    if not path.is_file():
        return {
            "path": str(path),
            "app_version": None,
            "model_id": None,
            "capture_schema_version": None,
        }
    source = path.read_text(encoding="utf-8")
    return {
        "path": str(path),
        "app_version": _read_ts_string_constant(source, "APP_RELEASE_VERSION"),
        "model_id": _read_ts_string_constant(source, "APP_MODEL_ID"),
        "capture_schema_version": _read_ts_string_constant(
            source, "APP_CAPTURE_SCHEMA_VERSION"
        ),
    }


def _load_app_settings_defaults(app_json: Path) -> dict[str, str | None]:
    path = app_json.parent / "src" / "storage" / "appSettingsStorage.ts"
    if not path.is_file():
        return {"path": str(path), "default_api_base_url": None}
    source = path.read_text(encoding="utf-8")
    return {
        "path": str(path),
        "default_api_base_url": _read_ts_string_constant(source, "DEFAULT_API_BASE_URL"),
    }


def _is_localhost_url(value: str | None) -> bool:
    if value is None:
        return False
    return bool(re.match(r"^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0)([:/]|$)", value))


def _is_https_non_localhost_url(value: str | None) -> bool:
    if value is None:
        return False
    candidate = value.strip()
    is_https_url = bool(re.match(r"^https://[^/:\s]+(?::\d+)?(?:/|$)", candidate))
    return is_https_url and not _is_localhost_url(candidate)


def _read_file_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _has_plugin(plugins: list[Any], plugin_name: str) -> bool:
    for plugin in plugins:
        if plugin == plugin_name:
            return True
        if isinstance(plugin, list) and plugin and plugin[0] == plugin_name:
            return True
    return False


def _get_plugin_options(plugins: list[Any], plugin_name: str) -> dict[str, Any]:
    for plugin in plugins:
        if isinstance(plugin, list) and len(plugin) > 1 and plugin[0] == plugin_name:
            return plugin[1] if isinstance(plugin[1], dict) else {}
    return {}


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


def _build_traceability(env: dict[str, str]) -> dict[str, str]:
    return {
        "git_sha": env.get("GITHUB_SHA", "local"),
        "git_ref": env.get("GITHUB_REF", "local"),
        "git_run_id": env.get("GITHUB_RUN_ID", "local"),
        "workflow": env.get("GITHUB_WORKFLOW", "local"),
    }


def _build_next_actions(
    external_items: list[dict[str, Any]],
    manual_external_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    external_action_map = {
        "expo_token": {
            "id": "configure_expo_token",
            "blocked_item": "expo_token",
            "status": "required",
            "owner": "release_engineer",
            "action": "Create an Expo access token and add it as GitHub Actions secret EXPO_TOKEN.",
            "verification": (
                "Re-run Mobile Build; external_items.expo_token status should become present."
            ),
            "secret_names": ["EXPO_TOKEN"],
            "variable_names": [],
            "file_paths": [],
            "doc": "docs/mobile-release-runbook-v0.1.md",
        },
        "eas_project_identity": {
            "id": "configure_eas_project_identity",
            "blocked_item": "eas_project_identity",
            "status": "required",
            "owner": "release_engineer",
            "action": (
                "Set GitHub repository variable EAS_PROJECT_ID or commit expo.extra.eas.projectId "
                "in apps/field-mobile/app.json."
            ),
            "verification": (
                "Re-run Mobile Build; external_items.eas_project_identity status should become "
                "present."
            ),
            "secret_names": [],
            "variable_names": ["EAS_PROJECT_ID"],
            "file_paths": ["apps/field-mobile/app.json"],
            "doc": "docs/mobile-release-runbook-v0.1.md",
        },
        "clinical_hub_live_api": {
            "id": "configure_clinical_hub_live_api",
            "blocked_item": "clinical_hub_live_api",
            "status": "required",
            "owner": "clinical_hub_admin",
            "action": (
                "Add GitHub Actions secrets CLINICAL_HUB_URL and CLINICAL_HUB_API_KEY for live "
                "Clinical Hub smoke tests and report push."
            ),
            "verification": (
                "Re-run Mobile Build; external_items.clinical_hub_live_api status should become "
                "present."
            ),
            "secret_names": ["CLINICAL_HUB_URL", "CLINICAL_HUB_API_KEY"],
            "variable_names": [],
            "file_paths": [],
            "doc": "docs/mobile-release-runbook-v0.1.md",
        },
    }
    manual_action_map = {
        "apple_developer_account": {
            "id": "provision_apple_developer_account",
            "blocked_item": "apple_developer_account",
            "status": "manual_required",
            "owner": "account_admin",
            "action": (
                "Provision Apple Developer access, signing certificates/profiles, and TestFlight "
                "distribution permissions."
            ),
            "verification": (
                "Trigger a signed iOS EAS build and confirm TestFlight upload readiness."
            ),
            "secret_names": [],
            "variable_names": [],
            "file_paths": [],
            "doc": "docs/mobile-release-runbook-v0.1.md",
        },
        "google_play_account": {
            "id": "provision_google_play_account",
            "blocked_item": "google_play_account",
            "status": "manual_required",
            "owner": "account_admin",
            "action": (
                "Provision Google Play Console access, Android signing, and internal testing track "
                "permissions."
            ),
            "verification": (
                "Trigger a signed Android EAS build and confirm Play Internal Testing upload "
                "readiness."
            ),
            "secret_names": [],
            "variable_names": [],
            "file_paths": [],
            "doc": "docs/mobile-release-runbook-v0.1.md",
        },
    }

    next_actions: list[dict[str, Any]] = []
    for item in external_items:
        if item["status"] in {"missing", "invalid"} and item["id"] in external_action_map:
            next_actions.append(external_action_map[item["id"]])
    for item in manual_external_items:
        if item["status"] == "manual_required" and item["id"] in manual_action_map:
            next_actions.append(manual_action_map[item["id"]])
    return next_actions


def build_readiness_report(
    *,
    app_json: Path,
    eas_json: Path,
    package_json: Path,
    package_lock: Path,
    env: dict[str, str],
) -> dict[str, Any]:
    app_payload = _load_json(app_json)
    eas_payload = _load_json(eas_json)
    package_payload = _load_json(package_json)
    lock_payload = _load_json(package_lock)
    release_metadata = _load_release_metadata(app_json)
    app_settings_defaults = _load_app_settings_defaults(app_json)

    expo = app_payload.get("expo", {})
    plugins = expo.get("plugins", [])
    ios = expo.get("ios", {})
    android = expo.get("android", {})
    splash = _get_plugin_options(plugins, "expo-splash-screen")
    android_adaptive_icon = android.get("adaptiveIcon", {})
    scripts = package_payload.get("scripts", {})
    root_lock = lock_payload.get("packages", {}).get("", {})
    eas_build = eas_payload.get("build", {})
    mobile_root = package_json.parent

    checks: list[dict[str, Any]] = []

    platforms = expo.get("platforms", [])
    package_dependencies = package_payload.get("dependencies", {})
    lock_dependencies = root_lock.get("dependencies", {})
    lock_dev_dependencies = root_lock.get("devDependencies", {})
    _check(
        checks,
        "platforms_ios_android",
        "ios" in platforms and "android" in platforms,
        f"platforms={platforms!r}",
    )
    _check(checks, "expo_name", bool(expo.get("name")), f"name={expo.get('name')!r}")
    _check(checks, "expo_slug", bool(expo.get("slug")), f"slug={expo.get('slug')!r}")
    _check(checks, "expo_version", bool(expo.get("version")), f"version={expo.get('version')!r}")
    _check(
        checks,
        "release_metadata_module",
        bool(release_metadata.get("app_version"))
        and bool(release_metadata.get("model_id"))
        and bool(release_metadata.get("capture_schema_version")),
        (
            f"path={release_metadata.get('path')}, "
            f"app_version={release_metadata.get('app_version')!r}, "
            f"model_id={release_metadata.get('model_id')!r}, "
            f"capture_schema_version={release_metadata.get('capture_schema_version')!r}"
        ),
    )
    _check(
        checks,
        "release_metadata_version_matches_expo",
        release_metadata.get("app_version") == expo.get("version"),
        (
            f"release_metadata.app_version={release_metadata.get('app_version')!r}, "
            f"expo.version={expo.get('version')!r}"
        ),
    )
    _check(
        checks,
        "release_metadata_model_id",
        isinstance(release_metadata.get("model_id"), str)
        and bool(str(release_metadata.get("model_id")).strip()),
        f"model_id={release_metadata.get('model_id')!r}",
    )
    _check(
        checks,
        "release_metadata_capture_schema_version",
        release_metadata.get("capture_schema_version") == "ios_capture_v1",
        f"capture_schema_version={release_metadata.get('capture_schema_version')!r}",
    )
    _check(
        checks,
        "default_api_base_url_not_localhost",
        app_settings_defaults.get("default_api_base_url") is not None
        and not _is_localhost_url(app_settings_defaults.get("default_api_base_url")),
        (
            f"path={app_settings_defaults.get('path')}, "
            f"default_api_base_url={app_settings_defaults.get('default_api_base_url')!r}"
        ),
    )
    app_icon_path = _asset_path(app_json, expo.get("icon"))
    app_icon_dimensions = _png_dimensions(app_icon_path)
    _check(
        checks,
        "app_icon_png_asset",
        app_icon_dimensions is not None
        and app_icon_dimensions[0] == app_icon_dimensions[1]
        and app_icon_dimensions[0] >= 1024,
        f"icon={expo.get('icon')!r}, dimensions={app_icon_dimensions!r}",
    )
    splash_image_path = _asset_path(app_json, splash.get("image"))
    splash_dimensions = _png_dimensions(splash_image_path)
    _check(
        checks,
        "splash_png_asset",
        splash_dimensions is not None
        and splash_dimensions[0] == splash_dimensions[1]
        and splash_dimensions[0] >= 1024,
        f"image={splash.get('image')!r}, dimensions={splash_dimensions!r}",
    )
    _check(
        checks,
        "splash_screen_plugin",
        _has_plugin(plugins, "expo-splash-screen"),
        "expo-splash-screen plugin configured",
    )
    _check(
        checks,
        "splash_resize_mode",
        splash.get("resizeMode") in {"contain", "cover", "native"},
        f"resizeMode={splash.get('resizeMode')!r}",
    )
    _check(
        checks,
        "splash_image_width",
        isinstance(splash.get("imageWidth"), int) and 0 < splash.get("imageWidth", 0) <= 512,
        f"imageWidth={splash.get('imageWidth')!r}",
    )
    _check(
        checks,
        "splash_background_color",
        _is_six_digit_hex_color(splash.get("backgroundColor")),
        f"backgroundColor={splash.get('backgroundColor')!r}",
    )
    _check(
        checks,
        "app_version_matches_package_version",
        expo.get("version") == package_payload.get("version") == root_lock.get("version"),
        (
            f"expo.version={expo.get('version')!r}, "
            f"package.version={package_payload.get('version')!r}, "
            f"lock.version={root_lock.get('version')!r}"
        ),
    )
    _check(
        checks,
        "ios_bundle_identifier",
        bool(ios.get("bundleIdentifier")),
        f"bundleIdentifier={ios.get('bundleIdentifier')!r}",
    )
    _check(
        checks,
        "ios_build_number",
        bool(ios.get("buildNumber")),
        f"buildNumber={ios.get('buildNumber')!r}",
    )
    ios_info_plist = ios.get("infoPlist", {})
    required_ios_privacy_strings = {
        "NSCameraUsageDescription",
        "NSMicrophoneUsageDescription",
        "NSMotionUsageDescription",
    }
    _check(
        checks,
        "ios_privacy_usage_descriptions",
        required_ios_privacy_strings.issubset(set(ios_info_plist))
        and all(
            isinstance(ios_info_plist.get(key), str) and bool(ios_info_plist.get(key, "").strip())
            for key in required_ios_privacy_strings
        ),
        f"infoPlist keys={sorted(ios_info_plist)}",
    )
    _check(
        checks,
        "android_package",
        bool(android.get("package")),
        f"package={android.get('package')!r}",
    )
    _check(
        checks,
        "android_version_code",
        isinstance(android.get("versionCode"), int) and android.get("versionCode", 0) > 0,
        f"versionCode={android.get('versionCode')!r}",
    )
    _check(
        checks,
        "camera_plugin",
        _has_plugin(plugins, "expo-camera"),
        "expo-camera plugin configured",
    )
    _check(
        checks,
        "audio_plugin",
        _has_plugin(plugins, "expo-audio"),
        "expo-audio plugin configured",
    )

    audio_options = _get_plugin_options(plugins, "expo-audio")
    _check(
        checks,
        "foreground_audio_disabled",
        audio_options.get("enableBackgroundPlayback") is False
        and audio_options.get("enableBackgroundRecording") is False,
        f"expo-audio options={audio_options!r}",
    )
    _check(
        checks,
        "android_runtime_permissions_declared",
        {"CAMERA", "RECORD_AUDIO"}.issubset(set(android.get("permissions", []))),
        f"permissions={android.get('permissions', [])!r}",
    )
    _check(
        checks,
        "android_runtime_permissions_minimal",
        set(android.get("permissions", [])) == {"CAMERA", "RECORD_AUDIO"},
        f"permissions={android.get('permissions', [])!r}",
        severity="warning",
    )
    android_adaptive_icon_path = _asset_path(
        app_json, android_adaptive_icon.get("foregroundImage")
    )
    android_adaptive_icon_dimensions = _png_dimensions(android_adaptive_icon_path)
    _check(
        checks,
        "android_adaptive_icon_png_asset",
        android_adaptive_icon_dimensions is not None
        and android_adaptive_icon_dimensions[0] == android_adaptive_icon_dimensions[1]
        and android_adaptive_icon_dimensions[0] >= 1024,
        (
            f"foregroundImage={android_adaptive_icon.get('foregroundImage')!r}, "
            f"dimensions={android_adaptive_icon_dimensions!r}"
        ),
    )
    _check(
        checks,
        "android_adaptive_icon_background_color",
        _is_six_digit_hex_color(android_adaptive_icon.get("backgroundColor")),
        f"backgroundColor={android_adaptive_icon.get('backgroundColor')!r}",
    )
    _check(
        checks,
        "secure_store_plugin",
        _has_plugin(plugins, "expo-secure-store"),
        "expo-secure-store plugin configured",
    )
    _check(
        checks,
        "secure_store_dependency_locked",
        "expo-secure-store" in package_dependencies
        and package_dependencies.get("expo-secure-store")
        == lock_dependencies.get("expo-secure-store"),
        (
            "expo-secure-store dependency="
            f"{package_dependencies.get('expo-secure-store')!r}, "
            f"lock={lock_dependencies.get('expo-secure-store')!r}"
        ),
    )
    _check(
        checks,
        "splash_screen_dependency_locked",
        "expo-splash-screen" in package_dependencies
        and package_dependencies.get("expo-splash-screen")
        == lock_dependencies.get("expo-splash-screen"),
        (
            "expo-splash-screen dependency="
            f"{package_dependencies.get('expo-splash-screen')!r}, "
            f"lock={lock_dependencies.get('expo-splash-screen')!r}"
        ),
    )
    _check(
        checks,
        "audio_microphone_permission",
        isinstance(audio_options.get("microphonePermission"), str)
        and bool(audio_options.get("microphonePermission", "").strip()),
        f"microphonePermission={audio_options.get('microphonePermission')!r}",
    )

    for profile in ("development", "preview", "production"):
        _check(
            checks,
            f"eas_profile_{profile}",
            profile in eas_build,
            f"eas build profiles={list(eas_build)}",
        )
    _check(
        checks,
        "eas_cli_version_declared",
        bool(eas_payload.get("cli", {}).get("version")),
        f"eas.cli.version={eas_payload.get('cli', {}).get('version')!r}",
    )
    _check(
        checks,
        "eas_profile_channels",
        eas_build.get("development", {}).get("channel") == "development"
        and eas_build.get("preview", {}).get("channel") == "preview"
        and eas_build.get("production", {}).get("channel") == "production",
        (
            f"development={eas_build.get('development', {}).get('channel')!r}, "
            f"preview={eas_build.get('preview', {}).get('channel')!r}, "
            f"production={eas_build.get('production', {}).get('channel')!r}"
        ),
    )
    _check(
        checks,
        "eas_production_auto_increment",
        eas_build.get("production", {}).get("autoIncrement") is True,
        f"production.autoIncrement={eas_build.get('production', {}).get('autoIncrement')!r}",
    )
    _check(
        checks,
        "preview_android_apk",
        eas_build.get("preview", {}).get("android", {}).get("buildType") == "apk",
        f"preview.android={eas_build.get('preview', {}).get('android')!r}",
        severity="warning",
    )
    _check(
        checks,
        "validate_ci_script",
        "validate:ci" in scripts,
        "package script validate:ci is present",
    )
    validate_ci_script = scripts.get("validate:ci", "")
    test_unit_script = scripts.get("test:unit", "")
    unit_runner_path = mobile_root / "scripts" / "run-unit-tests.sh"
    app_ts_path = mobile_root / "App.tsx"
    app_helpers_path = mobile_root / "src" / "utils" / "appHelpers.ts"
    connection_check_source_path = mobile_root / "src" / "api" / "connectionCheck.ts"
    pending_sync_queue_source_path = mobile_root / "src" / "utils" / "pendingSyncQueue.ts"
    pending_sync_hook_source_path = mobile_root / "src" / "hooks" / "usePendingSyncQueue.ts"
    pending_storage_source_path = mobile_root / "src" / "storage" / "pendingSubmissionStorage.ts"
    submit_outcome_source_path = mobile_root / "src" / "utils" / "submitOutcome.ts"
    helper_tests_path = mobile_root / "tests" / "appHelpers.test.js"
    app_settings_storage_tests_path = mobile_root / "tests" / "appSettingsStorage.test.js"
    clinical_hub_api_tests_path = mobile_root / "tests" / "clinicalHub.test.js"
    connection_check_tests_path = mobile_root / "tests" / "connectionCheck.test.js"
    capture_package_payload_tests_path = mobile_root / "tests" / "capturePackagePayload.test.js"
    capture_tests_path = mobile_root / "tests" / "captureContract.test.js"
    paired_payload_tests_path = mobile_root / "tests" / "pairedPayload.test.js"
    roi_signal_tests_path = mobile_root / "tests" / "roiSignalEstimator.test.js"
    runtime_metrics_tests_path = mobile_root / "tests" / "runtimeMetrics.test.js"
    pending_sync_queue_tests_path = mobile_root / "tests" / "pendingSyncQueue.test.js"
    pending_submission_storage_tests_path = (
        mobile_root / "tests" / "pendingSubmissionStorage.test.js"
    )
    summary_requests_tests_path = mobile_root / "tests" / "summaryRequests.test.js"
    submit_outcome_tests_path = mobile_root / "tests" / "submitOutcome.test.js"
    app_ts_source = _read_file_text(app_ts_path)
    app_helpers_source = _read_file_text(app_helpers_path)
    connection_check_source = _read_file_text(connection_check_source_path)
    pending_sync_queue_source = _read_file_text(pending_sync_queue_source_path)
    pending_sync_hook_source = _read_file_text(pending_sync_hook_source_path)
    pending_storage_source = _read_file_text(pending_storage_source_path)
    submit_outcome_source = _read_file_text(submit_outcome_source_path)
    helper_tests_source = _read_file_text(helper_tests_path)
    connection_check_tests_source = _read_file_text(connection_check_tests_path)
    pending_sync_queue_tests_source = _read_file_text(pending_sync_queue_tests_path)
    pending_submission_storage_tests_source = _read_file_text(
        pending_submission_storage_tests_path
    )
    submit_outcome_tests_source = _read_file_text(submit_outcome_tests_path)
    _check(
        checks,
        "unit_test_script",
        bool(test_unit_script),
        "package script test:unit is present",
    )
    _check(
        checks,
        "validate_ci_runs_unit_tests",
        "npm run test:unit" in validate_ci_script,
        f"validate:ci={validate_ci_script!r}",
    )
    _check(
        checks,
        "unit_test_runner_script",
        unit_runner_path.is_file(),
        f"path={unit_runner_path}",
    )
    _check(
        checks,
        "mobile_helper_unit_tests_present",
        helper_tests_path.is_file(),
        f"path={helper_tests_path}",
    )
    _check(
        checks,
        "app_settings_storage_unit_tests_present",
        app_settings_storage_tests_path.is_file(),
        f"path={app_settings_storage_tests_path}",
    )
    _check(
        checks,
        "clinical_hub_api_unit_tests_present",
        clinical_hub_api_tests_path.is_file(),
        f"path={clinical_hub_api_tests_path}",
    )
    _check(
        checks,
        "connection_check_unit_tests_present",
        connection_check_tests_path.is_file(),
        f"path={connection_check_tests_path}",
    )
    _check(
        checks,
        "capture_contract_unit_tests_present",
        capture_tests_path.is_file(),
        f"path={capture_tests_path}",
    )
    _check(
        checks,
        "capture_package_payload_unit_tests_present",
        capture_package_payload_tests_path.is_file(),
        f"path={capture_package_payload_tests_path}",
    )
    _check(
        checks,
        "paired_payload_unit_tests_present",
        paired_payload_tests_path.is_file(),
        f"path={paired_payload_tests_path}",
    )
    _check(
        checks,
        "roi_signal_unit_tests_present",
        roi_signal_tests_path.is_file(),
        f"path={roi_signal_tests_path}",
    )
    _check(
        checks,
        "runtime_metrics_unit_tests_present",
        runtime_metrics_tests_path.is_file(),
        f"path={runtime_metrics_tests_path}",
    )
    _check(
        checks,
        "pending_sync_queue_unit_tests_present",
        pending_sync_queue_tests_path.is_file(),
        f"path={pending_sync_queue_tests_path}",
    )
    _check(
        checks,
        "pending_submission_storage_unit_tests_present",
        pending_submission_storage_tests_path.is_file(),
        f"path={pending_submission_storage_tests_path}",
    )
    _check(
        checks,
        "summary_requests_unit_tests_present",
        summary_requests_tests_path.is_file(),
        f"path={summary_requests_tests_path}",
    )
    _check(
        checks,
        "submit_outcome_unit_tests_present",
        submit_outcome_tests_path.is_file(),
        f"path={submit_outcome_tests_path}",
    )
    redaction_source_requirements = {
        "app_helpers_formatter": "formatSafeResponseProblem" in app_helpers_source,
        "app_summary_errors": "formatSafeResponseProblem(response.status, body)" in app_ts_source,
        "app_network_errors": 'formatSafeResponseProblem(null, String(error), "NETWORK")'
        in app_ts_source,
        "connection_check": "formatSafeResponseProblem(status, body)" in connection_check_source,
        "submit_outcome": "formatSafeResponseProblem(result.statusCode, result.body"
        in submit_outcome_source,
        "pending_sync_attempt": "summarizePendingError(options.result.body)"
        in pending_sync_queue_source,
        "pending_enqueue": "summarizePendingError(lastError)" in pending_sync_hook_source,
        "pending_storage_migration": "summarizePendingError(rawLastError)"
        in pending_storage_source,
        "no_raw_summary_body": "HTTP ${response.status}: ${body}" not in app_ts_source,
        "no_raw_summary_catch": "setSummaryError(String(error))" not in app_ts_source,
        "no_raw_coverage_catch": "setCoverageError(String(error))" not in app_ts_source,
    }
    _check(
        checks,
        "mobile_api_response_redaction_sources",
        all(redaction_source_requirements.values()),
        f"requirements={redaction_source_requirements!r}",
    )
    redaction_test_requirements = {
        "safe_formatter_test": "without leaking raw response bodies" in helper_tests_source,
        "connection_check_test": "without raw body" in connection_check_tests_source,
        "pending_sync_test": "server_or_client_response" in pending_sync_queue_tests_source
        and "validation" in pending_sync_queue_tests_source,
        "pending_storage_migration_test": "redacts migrated raw last errors"
        in pending_submission_storage_tests_source,
        "submit_outcome_test": "without raw body" in submit_outcome_tests_source,
    }
    _check(
        checks,
        "mobile_api_response_redaction_unit_tests_present",
        all(redaction_test_requirements.values()),
        f"requirements={redaction_test_requirements!r}",
    )
    _check(
        checks,
        "build_scripts",
        "build:preview" in scripts and "build:production" in scripts,
        "package build scripts are present",
    )
    _check(
        checks,
        "package_lock_matches_root",
        root_lock.get("name") == package_payload.get("name")
        and root_lock.get("version") == package_payload.get("version"),
        (
            f"lock root={root_lock.get('name')!r}/{root_lock.get('version')!r}, "
            f"package={package_payload.get('name')!r}/{package_payload.get('version')!r}"
        ),
    )
    _check(
        checks,
        "expo_doctor_pinned",
        package_payload.get("devDependencies", {}).get("expo-doctor") == "1.19.8"
        and lock_dev_dependencies.get("expo-doctor") == "1.19.8",
        "expo-doctor devDependency is pinned in package.json and package-lock.json",
    )

    extra = expo.get("extra", {})
    eas_project_id = (
        extra.get("eas", {}).get("projectId") if isinstance(extra.get("eas"), dict) else None
    )
    clinical_hub_url = env.get("CLINICAL_HUB_URL", "").strip()
    clinical_hub_api_key_present = bool(env.get("CLINICAL_HUB_API_KEY"))
    clinical_hub_live_api_present = bool(clinical_hub_url and clinical_hub_api_key_present)
    clinical_hub_live_api_valid = (
        clinical_hub_live_api_present and _is_https_non_localhost_url(clinical_hub_url)
    )
    if clinical_hub_live_api_valid:
        clinical_hub_live_api_status = "present"
        clinical_hub_live_api_evidence = (
            "CLINICAL_HUB_URL uses https with a non-localhost host and CLINICAL_HUB_API_KEY is set"
        )
    elif clinical_hub_live_api_present:
        clinical_hub_live_api_status = "invalid"
        clinical_hub_live_api_evidence = (
            "CLINICAL_HUB_URL is set but must use https with a non-localhost host for live "
            "release readiness"
        )
    else:
        clinical_hub_live_api_status = "missing"
        clinical_hub_live_api_evidence = (
            "CLINICAL_HUB_URL and/or CLINICAL_HUB_API_KEY are not set"
        )
    external_items = [
        {
            "id": "expo_token",
            "status": "present" if bool(env.get("EXPO_TOKEN")) else "missing",
            "required_for": "Authenticated EAS build trigger from GitHub Actions.",
            "evidence": "EXPO_TOKEN environment variable is set"
            if env.get("EXPO_TOKEN")
            else "EXPO_TOKEN environment variable is not set",
        },
        {
            "id": "eas_project_identity",
            "status": "present" if bool(eas_project_id or env.get("EAS_PROJECT_ID")) else "missing",
            "required_for": "Deterministic non-interactive EAS project identity.",
            "evidence": "expo.extra.eas.projectId or EAS_PROJECT_ID is set"
            if eas_project_id or env.get("EAS_PROJECT_ID")
            else "Neither expo.extra.eas.projectId nor EAS_PROJECT_ID is set",
        },
        {
            "id": "clinical_hub_live_api",
            "status": clinical_hub_live_api_status,
            "required_for": "Live Clinical Hub smoke tests and CI report push.",
            "evidence": clinical_hub_live_api_evidence,
        },
    ]
    manual_external_items = [
        {
            "id": "apple_developer_account",
            "status": "manual_required",
            "required_for": (
                "Signed iOS build, TestFlight/App Store distribution, "
                "and certificate/profile management."
            ),
        },
        {
            "id": "google_play_account",
            "status": "manual_required",
            "required_for": (
                "Android production signing, Play Console upload, and store distribution."
            ),
        },
    ]

    local_failures = [
        item for item in checks if item["status"] == "fail" and item["severity"] == "error"
    ]
    external_blocked = [item for item in external_items if item["status"] != "present"]
    authenticated_eas_item_ids = {"expo_token", "eas_project_identity"}
    authenticated_eas_blockers = [
        item["id"] for item in external_items if item["id"] in authenticated_eas_item_ids
        and item["status"] != "present"
    ]
    clinical_hub_live_api_status_for_report = next(
        (
            item["status"]
            for item in external_items
            if item["id"] == "clinical_hub_live_api"
        ),
        "missing",
    )
    if local_failures:
        status = "not_ready"
    elif external_blocked:
        status = "ready_except_external_credentials"
    else:
        status = "ready_for_authenticated_eas_preflight"

    next_actions = _build_next_actions(external_items, manual_external_items)

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "traceability": _build_traceability(env),
        "status": status,
        "local_checks_status": "pass" if not local_failures else "fail",
        "external_readiness_status": "pass" if not external_blocked else "blocked",
        "authenticated_eas_status": "pass" if not authenticated_eas_blockers else "blocked",
        "authenticated_eas_blockers": authenticated_eas_blockers,
        "clinical_hub_live_api_status": clinical_hub_live_api_status_for_report,
        "app": {
            "name": expo.get("name"),
            "slug": expo.get("slug"),
            "version": expo.get("version"),
            "ios_bundle_identifier": ios.get("bundleIdentifier"),
            "android_package": android.get("package"),
        },
        "local_checks": checks,
        "external_items": external_items,
        "manual_external_items": manual_external_items,
        "next_actions": next_actions,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a mobile release readiness report with explicit external blockers."
    )
    parser.add_argument("--app-json", type=Path, required=True)
    parser.add_argument("--eas-json", type=Path, required=True)
    parser.add_argument("--package-json", type=Path, required=True)
    parser.add_argument("--package-lock", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--strict-external",
        action="store_true",
        help="Return a non-zero exit code when external credentials are missing.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_readiness_report(
        app_json=args.app_json,
        eas_json=args.eas_json,
        package_json=args.package_json,
        package_lock=args.package_lock,
        env=dict(os.environ),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"written {args.output}")
    print(f"status: {report['status']}")

    if report["local_checks_status"] != "pass":
        return 1
    if args.strict_external and report["external_readiness_status"] != "pass":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
