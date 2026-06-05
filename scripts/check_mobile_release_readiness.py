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


def _read_ts_boolean_constant(source: str, name: str) -> bool | None:
    pattern = re.compile(rf"export\s+const\s+{re.escape(name)}\s*=\s*(true|false)")
    match = pattern.search(source)
    if not match:
        return None
    return match.group(1) == "true"


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


def _load_app_runtime_config(app_json: Path) -> dict[str, str | bool | None]:
    path = app_json.parent / "src" / "config" / "appConfig.ts"
    if not path.is_file():
        return {
            "path": str(path),
            "runtime_mode": None,
            "endpoint_set": None,
            "default_capture_mode": None,
            "paired_measurements_endpoint_path": None,
            "capture_packages_endpoint_path": None,
            "store_raw_video": None,
            "store_raw_audio": None,
            "roi_only": None,
            "data_residency_region": None,
            "data_residency_boundary": None,
            "allow_cross_region_sync": None,
            "require_region_matched_clinical_hub": None,
            "allow_debug_controls": None,
            "allow_raw_response_details": None,
            "enable_verbose_logging": None,
        }
    source = path.read_text(encoding="utf-8")
    return {
        "path": str(path),
        "runtime_mode": _read_ts_string_constant(source, "APP_RUNTIME_MODE"),
        "endpoint_set": _read_ts_string_constant(source, "APP_ENDPOINT_SET"),
        "default_capture_mode": _read_ts_string_constant(source, "APP_DEFAULT_CAPTURE_MODE"),
        "paired_measurements_endpoint_path": _read_ts_string_constant(
            source, "APP_PAIRED_MEASUREMENTS_ENDPOINT_PATH"
        ),
        "capture_packages_endpoint_path": _read_ts_string_constant(
            source, "APP_CAPTURE_PACKAGES_ENDPOINT_PATH"
        ),
        "store_raw_video": _read_ts_boolean_constant(source, "APP_STORE_RAW_VIDEO"),
        "store_raw_audio": _read_ts_boolean_constant(source, "APP_STORE_RAW_AUDIO"),
        "roi_only": _read_ts_boolean_constant(source, "APP_ROI_ONLY"),
        "data_residency_region": _read_ts_string_constant(source, "APP_DATA_RESIDENCY_REGION"),
        "data_residency_boundary": _read_ts_string_constant(
            source, "APP_DATA_RESIDENCY_BOUNDARY"
        ),
        "allow_cross_region_sync": _read_ts_boolean_constant(
            source, "APP_ALLOW_CROSS_REGION_SYNC"
        ),
        "require_region_matched_clinical_hub": _read_ts_boolean_constant(
            source, "APP_REQUIRE_REGION_MATCHED_CLINICAL_HUB"
        ),
        "allow_debug_controls": _read_ts_boolean_constant(source, "APP_ALLOW_DEBUG_CONTROLS"),
        "allow_raw_response_details": _read_ts_boolean_constant(
            source, "APP_ALLOW_RAW_RESPONSE_DETAILS"
        ),
        "enable_verbose_logging": _read_ts_boolean_constant(
            source, "APP_ENABLE_VERBOSE_LOGGING"
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
                "Provision Apple Developer access, App Store Connect app record, signing "
                "certificates/profiles, and TestFlight distribution permissions."
            ),
            "verification": (
                "Trigger a signed iOS EAS build, then submit the latest production build and "
                "confirm TestFlight upload readiness."
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
                "Provision Google Play Console access, Android signing, Play API service account, "
                "EAS file secret GOOGLE_SERVICE_ACCOUNT, and internal testing track permissions."
            ),
            "verification": (
                "Trigger a signed Android EAS build, then submit the latest production build and "
                "confirm Play Internal Testing upload readiness."
            ),
            "secret_names": ["GOOGLE_SERVICE_ACCOUNT"],
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
    app_runtime_config = _load_app_runtime_config(app_json)
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
    eas_submit = eas_payload.get("submit", {})
    if not isinstance(eas_submit, dict):
        eas_submit = {}
    eas_submit_production = eas_submit.get("production", {})
    if not isinstance(eas_submit_production, dict):
        eas_submit_production = {}
    eas_submit_ios_is_object = isinstance(eas_submit_production.get("ios"), dict)
    eas_submit_android = eas_submit_production.get("android", {})
    if not isinstance(eas_submit_android, dict):
        eas_submit_android = {}
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
        "runtime_config_module",
        bool(app_runtime_config.get("runtime_mode"))
        and bool(app_runtime_config.get("endpoint_set"))
        and bool(app_runtime_config.get("default_capture_mode"))
        and bool(app_runtime_config.get("paired_measurements_endpoint_path"))
        and bool(app_runtime_config.get("capture_packages_endpoint_path"))
        and app_runtime_config.get("store_raw_video") is not None
        and app_runtime_config.get("store_raw_audio") is not None
        and app_runtime_config.get("roi_only") is not None
        and bool(app_runtime_config.get("data_residency_region"))
        and bool(app_runtime_config.get("data_residency_boundary"))
        and app_runtime_config.get("allow_cross_region_sync") is not None
        and app_runtime_config.get("require_region_matched_clinical_hub") is not None
        and app_runtime_config.get("allow_debug_controls") is not None
        and app_runtime_config.get("allow_raw_response_details") is not None
        and app_runtime_config.get("enable_verbose_logging") is not None,
        (
            f"path={app_runtime_config.get('path')}, "
            f"runtime_mode={app_runtime_config.get('runtime_mode')!r}, "
            f"endpoint_set={app_runtime_config.get('endpoint_set')!r}, "
            f"default_capture_mode={app_runtime_config.get('default_capture_mode')!r}, "
            "paired_measurements_endpoint_path="
            f"{app_runtime_config.get('paired_measurements_endpoint_path')!r}, "
            "capture_packages_endpoint_path="
            f"{app_runtime_config.get('capture_packages_endpoint_path')!r}, "
            f"store_raw_video={app_runtime_config.get('store_raw_video')!r}, "
            f"store_raw_audio={app_runtime_config.get('store_raw_audio')!r}, "
            f"roi_only={app_runtime_config.get('roi_only')!r}, "
            "data_residency_region="
            f"{app_runtime_config.get('data_residency_region')!r}, "
            "data_residency_boundary="
            f"{app_runtime_config.get('data_residency_boundary')!r}, "
            "allow_cross_region_sync="
            f"{app_runtime_config.get('allow_cross_region_sync')!r}, "
            "require_region_matched_clinical_hub="
            f"{app_runtime_config.get('require_region_matched_clinical_hub')!r}, "
            f"allow_debug_controls={app_runtime_config.get('allow_debug_controls')!r}, "
            "allow_raw_response_details="
            f"{app_runtime_config.get('allow_raw_response_details')!r}, "
            f"enable_verbose_logging={app_runtime_config.get('enable_verbose_logging')!r}"
        ),
    )
    _check(
        checks,
        "runtime_config_endpoint_set",
        app_runtime_config.get("endpoint_set") == "clinical_hub_v1"
        and app_runtime_config.get("paired_measurements_endpoint_path")
        == "/api/v1/paired-measurements"
        and app_runtime_config.get("capture_packages_endpoint_path")
        == "/api/v1/capture-packages",
        (
            f"endpoint_set={app_runtime_config.get('endpoint_set')!r}, "
            "paired_measurements_endpoint_path="
            f"{app_runtime_config.get('paired_measurements_endpoint_path')!r}, "
            "capture_packages_endpoint_path="
            f"{app_runtime_config.get('capture_packages_endpoint_path')!r}"
        ),
    )
    _check(
        checks,
        "runtime_config_default_capture_mode",
        app_runtime_config.get("default_capture_mode") == "water_impact",
        f"default_capture_mode={app_runtime_config.get('default_capture_mode')!r}",
    )
    _check(
        checks,
        "runtime_config_privacy_by_default",
        app_runtime_config.get("store_raw_video") is False
        and app_runtime_config.get("store_raw_audio") is False
        and app_runtime_config.get("roi_only") is True,
        (
            f"store_raw_video={app_runtime_config.get('store_raw_video')!r}, "
            f"store_raw_audio={app_runtime_config.get('store_raw_audio')!r}, "
            f"roi_only={app_runtime_config.get('roi_only')!r}"
        ),
    )
    _check(
        checks,
        "runtime_config_data_residency_policy",
        app_runtime_config.get("data_residency_region") == "us"
        and app_runtime_config.get("data_residency_boundary") == "single_region"
        and app_runtime_config.get("allow_cross_region_sync") is False
        and app_runtime_config.get("require_region_matched_clinical_hub") is True,
        (
            "data_residency_region="
            f"{app_runtime_config.get('data_residency_region')!r}, "
            "data_residency_boundary="
            f"{app_runtime_config.get('data_residency_boundary')!r}, "
            "allow_cross_region_sync="
            f"{app_runtime_config.get('allow_cross_region_sync')!r}, "
            "require_region_matched_clinical_hub="
            f"{app_runtime_config.get('require_region_matched_clinical_hub')!r}"
        ),
    )
    _check(
        checks,
        "runtime_config_debug_gates_disabled",
        app_runtime_config.get("allow_debug_controls") is False
        and app_runtime_config.get("allow_raw_response_details") is False
        and app_runtime_config.get("enable_verbose_logging") is False,
        (
            f"allow_debug_controls={app_runtime_config.get('allow_debug_controls')!r}, "
            "allow_raw_response_details="
            f"{app_runtime_config.get('allow_raw_response_details')!r}, "
            f"enable_verbose_logging={app_runtime_config.get('enable_verbose_logging')!r}"
        ),
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
        "file_system_dependency_locked",
        "expo-file-system" in package_dependencies
        and package_dependencies.get("expo-file-system")
        == lock_dependencies.get("expo-file-system"),
        (
            "expo-file-system dependency="
            f"{package_dependencies.get('expo-file-system')!r}, "
            f"lock={lock_dependencies.get('expo-file-system')!r}"
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
        "eas_submit_profile_production",
        (
            "production" in eas_submit
            and "ios" in eas_submit_production
            and "android" in eas_submit_production
            and eas_submit_ios_is_object
            and isinstance(eas_submit_production.get("android"), dict)
        ),
        (
            f"eas submit production keys={sorted(eas_submit_production)}, "
            f"ios_object={eas_submit_ios_is_object!r}, "
            f"android_object={isinstance(eas_submit_production.get('android'), dict)!r}"
        ),
    )
    android_service_account_key_path = eas_submit_android.get("serviceAccountKeyPath")
    _check(
        checks,
        "eas_submit_android_internal_track",
        isinstance(android_service_account_key_path, str)
        and android_service_account_key_path.startswith("@secret:")
        and eas_submit_android.get("track") == "internal"
        and eas_submit_android.get("releaseStatus") == "completed",
        (
            f"android.serviceAccountKeyPath={android_service_account_key_path!r}, "
            f"track={eas_submit_android.get('track')!r}, "
            f"releaseStatus={eas_submit_android.get('releaseStatus')!r}"
        ),
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
    app_config_tests_path = mobile_root / "tests" / "appConfig.test.js"
    app_helpers_path = mobile_root / "src" / "utils" / "appHelpers.ts"
    device_identity_source_path = mobile_root / "src" / "utils" / "deviceIdentity.ts"
    release_identity_source_path = mobile_root / "src" / "utils" / "releaseIdentity.ts"
    release_identity_component_path = (
        mobile_root / "src" / "components" / "ReleaseIdentitySection.tsx"
    )
    clinical_hub_source_path = mobile_root / "src" / "api" / "clinicalHub.ts"
    clinical_hub_preflight_source_path = (
        mobile_root / "src" / "api" / "clinicalHubPreflight.ts"
    )
    connection_check_source_path = mobile_root / "src" / "api" / "connectionCheck.ts"
    api_connection_section_path = (
        mobile_root / "src" / "components" / "ApiConnectionSection.tsx"
    )
    pending_sync_queue_source_path = mobile_root / "src" / "utils" / "pendingSyncQueue.ts"
    pending_sync_hook_source_path = mobile_root / "src" / "hooks" / "usePendingSyncQueue.ts"
    pending_storage_source_path = mobile_root / "src" / "storage" / "pendingSubmissionStorage.ts"
    submit_outcome_source_path = mobile_root / "src" / "utils" / "submitOutcome.ts"
    helper_tests_path = mobile_root / "tests" / "appHelpers.test.js"
    app_settings_storage_tests_path = mobile_root / "tests" / "appSettingsStorage.test.js"
    clinical_hub_api_tests_path = mobile_root / "tests" / "clinicalHub.test.js"
    clinical_hub_preflight_tests_path = (
        mobile_root / "tests" / "clinicalHubPreflight.test.js"
    )
    connection_check_tests_path = mobile_root / "tests" / "connectionCheck.test.js"
    capture_package_payload_tests_path = mobile_root / "tests" / "capturePackagePayload.test.js"
    capture_contract_source_path = mobile_root / "src" / "capture" / "buildCaptureContract.ts"
    runtime_capture_session_source_path = (
        mobile_root / "src" / "capture" / "runtimeCaptureSession.ts"
    )
    raw_media_retention_source_path = mobile_root / "src" / "capture" / "rawMediaRetention.ts"
    capture_tests_path = mobile_root / "tests" / "captureContract.test.js"
    repo_root = package_json.resolve().parent.parent.parent
    backend_capture_contract_path = repo_root / "src" / "uroflow_mobile" / "capture_contract.py"
    backend_capture_tests_path = repo_root / "tests" / "test_capture_contract.py"
    backend_session_path = repo_root / "src" / "uroflow_mobile" / "session.py"
    backend_session_tests_path = repo_root / "tests" / "test_session.py"
    mobile_device_smoke_template_path = (
        repo_root / "docs" / "mobile-device-smoke-log-template-v0.1.json"
    )
    mobile_device_smoke_validator_path = (
        repo_root / "scripts" / "validate_mobile_device_smoke_log.py"
    )
    mobile_device_smoke_validator_tests_path = (
        repo_root / "tests" / "test_mobile_device_smoke_log.py"
    )
    mobile_store_rollout_template_path = (
        repo_root / "docs" / "mobile-store-rollout-handoff-template-v0.1.json"
    )
    mobile_store_rollout_validator_path = (
        repo_root / "scripts" / "validate_mobile_store_rollout_handoff.py"
    )
    mobile_store_rollout_validator_tests_path = (
        repo_root / "tests" / "test_mobile_store_rollout_handoff.py"
    )
    mobile_release_bundle_verifier_path = (
        repo_root / "scripts" / "verify_mobile_release_bundle.py"
    )
    mobile_release_bundle_verifier_tests_path = (
        repo_root / "tests" / "test_mobile_release_bundle_verifier.py"
    )
    paired_payload_tests_path = mobile_root / "tests" / "pairedPayload.test.js"
    roi_signal_tests_path = mobile_root / "tests" / "roiSignalEstimator.test.js"
    runtime_metrics_source_path = mobile_root / "src" / "capture" / "runtimeMetrics.ts"
    runtime_metrics_tests_path = mobile_root / "tests" / "runtimeMetrics.test.js"
    raw_media_retention_tests_path = mobile_root / "tests" / "rawMediaRetention.test.js"
    pending_sync_queue_tests_path = mobile_root / "tests" / "pendingSyncQueue.test.js"
    pending_submission_storage_tests_path = (
        mobile_root / "tests" / "pendingSubmissionStorage.test.js"
    )
    summary_requests_tests_path = mobile_root / "tests" / "summaryRequests.test.js"
    submit_outcome_tests_path = mobile_root / "tests" / "submitOutcome.test.js"
    unit_runner_source = _read_file_text(unit_runner_path)
    app_ts_source = _read_file_text(app_ts_path)
    app_helpers_source = _read_file_text(app_helpers_path)
    device_identity_source = _read_file_text(device_identity_source_path)
    release_identity_source = _read_file_text(release_identity_source_path)
    release_identity_component_source = _read_file_text(release_identity_component_path)
    clinical_hub_source = _read_file_text(clinical_hub_source_path)
    clinical_hub_preflight_source = _read_file_text(clinical_hub_preflight_source_path)
    connection_check_source = _read_file_text(connection_check_source_path)
    api_connection_section_source = _read_file_text(api_connection_section_path)
    pending_sync_queue_source = _read_file_text(pending_sync_queue_source_path)
    pending_sync_hook_source = _read_file_text(pending_sync_hook_source_path)
    pending_storage_source = _read_file_text(pending_storage_source_path)
    submit_outcome_source = _read_file_text(submit_outcome_source_path)
    helper_tests_source = _read_file_text(helper_tests_path)
    device_identity_tests_path = mobile_root / "tests" / "deviceIdentity.test.js"
    device_identity_tests_source = _read_file_text(device_identity_tests_path)
    release_identity_tests_path = mobile_root / "tests" / "releaseIdentity.test.js"
    release_identity_tests_source = _read_file_text(release_identity_tests_path)
    clinical_hub_tests_source = _read_file_text(clinical_hub_api_tests_path)
    clinical_hub_preflight_tests_source = _read_file_text(
        clinical_hub_preflight_tests_path
    )
    connection_check_tests_source = _read_file_text(connection_check_tests_path)
    pending_sync_queue_tests_source = _read_file_text(pending_sync_queue_tests_path)
    pending_submission_storage_tests_source = _read_file_text(
        pending_submission_storage_tests_path
    )
    submit_outcome_tests_source = _read_file_text(submit_outcome_tests_path)
    capture_contract_source = _read_file_text(capture_contract_source_path)
    runtime_capture_session_source = _read_file_text(runtime_capture_session_source_path)
    raw_media_retention_source = _read_file_text(raw_media_retention_source_path)
    capture_tests_source = _read_file_text(capture_tests_path)
    backend_capture_contract_source = _read_file_text(backend_capture_contract_path)
    backend_capture_tests_source = _read_file_text(backend_capture_tests_path)
    backend_session_source = _read_file_text(backend_session_path)
    backend_session_tests_source = _read_file_text(backend_session_tests_path)
    runtime_metrics_source = _read_file_text(runtime_metrics_source_path)
    runtime_metrics_tests_source = _read_file_text(runtime_metrics_tests_path)
    raw_media_retention_tests_source = _read_file_text(raw_media_retention_tests_path)
    mobile_device_smoke_template_source = _read_file_text(mobile_device_smoke_template_path)
    mobile_device_smoke_validator_source = _read_file_text(mobile_device_smoke_validator_path)
    mobile_device_smoke_validator_tests_source = _read_file_text(
        mobile_device_smoke_validator_tests_path
    )
    mobile_store_rollout_template_source = _read_file_text(mobile_store_rollout_template_path)
    mobile_store_rollout_validator_source = _read_file_text(
        mobile_store_rollout_validator_path
    )
    mobile_store_rollout_validator_tests_source = _read_file_text(
        mobile_store_rollout_validator_tests_path
    )
    mobile_release_bundle_verifier_source = _read_file_text(
        mobile_release_bundle_verifier_path
    )
    mobile_release_bundle_verifier_tests_source = _read_file_text(
        mobile_release_bundle_verifier_tests_path
    )
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
    device_identity_source_requirements = {
        "helper_file": device_identity_source_path.is_file(),
        "expo_device_dependency": "expo-device" in package_dependencies,
        "model_label_helper": "buildDeviceModelLabel" in device_identity_source,
        "os_version_helper": "buildDeviceOsVersion" in device_identity_source,
        "app_imports_expo_device": 'import * as Device from "expo-device"'
        in app_ts_source,
        "app_default_device_model": "defaultDeviceModel" in app_ts_source
        and "buildDeviceModelLabel" in app_ts_source,
        "runtime_uses_model_helper": "buildDeviceModelLabel"
        in runtime_capture_session_source,
        "runtime_uses_os_helper": "buildDeviceOsVersion" in runtime_capture_session_source,
    }
    _check(
        checks,
        "mobile_device_identity_sources",
        all(device_identity_source_requirements.values()),
        f"requirements={device_identity_source_requirements!r}",
    )
    device_identity_test_requirements = {
        "unit_test_file": device_identity_tests_path.is_file(),
        "model_name_test": "prefers Expo Device model name" in device_identity_tests_source,
        "manufacturer_brand_fallback_test": "falls back to manufacturer and brand"
        in device_identity_tests_source,
        "platform_fallback_test": "platform fallback" in device_identity_tests_source,
        "os_version_test": "prefers Expo Device OS name and version"
        in device_identity_tests_source,
        "unit_runner_compiles_helper": "src/utils/deviceIdentity.ts" in unit_runner_source,
    }
    _check(
        checks,
        "mobile_device_identity_unit_tests_present",
        all(device_identity_test_requirements.values()),
        f"requirements={device_identity_test_requirements!r}",
    )
    release_identity_source_requirements = {
        "helper_file": release_identity_source_path.is_file(),
        "component_file": release_identity_component_path.is_file(),
        "app_renders_component": "ReleaseIdentitySection" in app_ts_source,
        "component_uses_helper": "buildReleaseIdentitySnapshot"
        in release_identity_component_source,
        "canonical_metadata": "APP_RELEASE_METADATA" in release_identity_source,
        "runtime_config": "APP_RUNTIME_CONFIG" in release_identity_source,
        "payload_alignment_status": "payloadStatus" in release_identity_source,
    }
    _check(
        checks,
        "mobile_release_identity_sources",
        all(release_identity_source_requirements.values()),
        f"requirements={release_identity_source_requirements!r}",
    )
    release_identity_test_requirements = {
        "unit_test_file": release_identity_tests_path.is_file(),
        "canonical_metadata_test": (
            "release identity snapshot exposes canonical runtime release metadata"
        )
        in release_identity_tests_source,
        "edited_payload_test": "warns when payload traceability is edited"
        in release_identity_tests_source,
        "unit_runner_compiles_helper": "src/utils/releaseIdentity.ts" in unit_runner_source,
    }
    _check(
        checks,
        "mobile_release_identity_unit_tests_present",
        all(release_identity_test_requirements.values()),
        f"requirements={release_identity_test_requirements!r}",
    )
    _check(
        checks,
        "app_config_unit_tests_present",
        app_config_tests_path.is_file(),
        f"path={app_config_tests_path}",
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
    runtime_trace_header_requirements = {
        "helper_function": "buildRuntimeTraceHeaders" in clinical_hub_source,
        "release_version_header": "x-uroflow-app-version" in clinical_hub_source
        and "APP_RELEASE_VERSION" in clinical_hub_source,
        "model_id_header": "x-uroflow-model-id" in clinical_hub_source
        and "APP_MODEL_ID" in clinical_hub_source,
        "capture_schema_header": "x-uroflow-capture-schema-version"
        in clinical_hub_source
        and "APP_CAPTURE_SCHEMA_VERSION" in clinical_hub_source,
        "runtime_mode_header": "x-uroflow-runtime-mode" in clinical_hub_source
        and "APP_RUNTIME_MODE" in clinical_hub_source,
        "endpoint_set_header": "x-uroflow-endpoint-set" in clinical_hub_source
        and "APP_ENDPOINT_SET" in clinical_hub_source,
        "data_residency_headers": (
            "x-uroflow-data-residency-region" in clinical_hub_source
            and "APP_DATA_RESIDENCY_REGION" in clinical_hub_source
            and "x-uroflow-data-residency-boundary" in clinical_hub_source
            and "APP_DATA_RESIDENCY_BOUNDARY" in clinical_hub_source
            and "x-uroflow-region-match-required" in clinical_hub_source
        ),
        "request_headers_include_trace": (
            "const headers: Record<string, string> = buildRuntimeTraceHeaders()"
            in clinical_hub_source
        ),
    }
    _check(
        checks,
        "clinical_hub_runtime_trace_headers_sources",
        all(runtime_trace_header_requirements.values()),
        f"requirements={runtime_trace_header_requirements!r}",
    )
    runtime_trace_header_test_requirements = {
        "runtime_trace_header_test": (
            "buildRuntimeTraceHeaders exposes release and residency metadata without secrets"
            in clinical_hub_tests_source
        ),
        "submit_header_test": "x-uroflow-data-residency-region"
        in clinical_hub_tests_source,
        "helper_header_test": "x-uroflow-runtime-mode" in helper_tests_source,
    }
    _check(
        checks,
        "clinical_hub_runtime_trace_headers_unit_tests_present",
        all(runtime_trace_header_test_requirements.values()),
        f"requirements={runtime_trace_header_test_requirements!r}",
    )
    clinical_hub_preflight_requirements = {
        "source_file": clinical_hub_preflight_source_path.is_file(),
        "uses_data_residency_policy": (
            "APP_DATA_RESIDENCY_REGION" in clinical_hub_preflight_source
            and "APP_REQUIRE_REGION_MATCHED_CLINICAL_HUB"
            in clinical_hub_preflight_source
            and "APP_ALLOW_CROSS_REGION_SYNC" in clinical_hub_preflight_source
        ),
        "blocked_status": '"blocked"' in clinical_hub_preflight_source,
        "region_mismatch_guard": "region_mismatch" in clinical_hub_preflight_source,
        "app_uses_preflight": (
            "buildClinicalHubPreflight" in app_ts_source
            and "isClinicalHubPreflightActionAllowed" in app_ts_source
        ),
        "hook_uses_preflight": (
            "buildClinicalHubPreflight" in pending_sync_hook_source
            and "isClinicalHubPreflightActionAllowed" in pending_sync_hook_source
        ),
        "ui_displays_preflight": "clinicalHubPreflightMessage"
        in api_connection_section_source,
        "unit_runner_compiles_preflight": "src/api/clinicalHubPreflight.ts"
        in unit_runner_source,
    }
    _check(
        checks,
        "clinical_hub_preflight_sources",
        all(clinical_hub_preflight_requirements.values()),
        f"requirements={clinical_hub_preflight_requirements!r}",
    )
    clinical_hub_preflight_test_requirements = {
        "unit_test_file": clinical_hub_preflight_tests_path.is_file(),
        "missing_url_test": "blocks missing Clinical Hub URL"
        in clinical_hub_preflight_tests_source,
        "local_smoke_warning_test": "allows local Clinical Hub smoke URLs with warning"
        in clinical_hub_preflight_tests_source,
        "cross_region_test": "blocks obvious cross-region Clinical Hub URLs"
        in clinical_hub_preflight_tests_source,
    }
    _check(
        checks,
        "clinical_hub_preflight_unit_tests_present",
        all(clinical_hub_preflight_test_requirements.values()),
        f"requirements={clinical_hub_preflight_test_requirements!r}",
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
        "runtime_motion_quality_gate_sources",
        "HIGH_MOTION_SAMPLE_THRESHOLD" in runtime_metrics_source
        and "highMotionRatio" in runtime_metrics_source
        and "high_motion_ratio" in capture_contract_source
        and "captureHighMotionRatio" in app_ts_source,
        (
            f"runtime_metrics={runtime_metrics_source_path}, "
            f"capture_contract={capture_contract_source_path}, "
            f"app={app_ts_path}"
        ),
    )
    _check(
        checks,
        "runtime_motion_quality_gate_unit_tests_present",
        "gates high-motion capture artifacts" in runtime_metrics_tests_source
        and "highMotionRatio" in runtime_metrics_tests_source
        and "high_motion_ratio" in capture_tests_source,
        f"paths={[str(runtime_metrics_tests_path), str(capture_tests_path)]}",
    )
    _check(
        checks,
        "runtime_capture_preflight_sources",
        "buildRuntimeCaptureReadiness" in runtime_metrics_source
        and "buildRuntimeCaptureReadiness" in app_ts_source
        and "Capture preflight blocked" in app_ts_source
        and "roiFrameCount" in app_ts_source
        and "roiFrameValid" in app_ts_source
        and "roiLocked" in app_ts_source,
        (
            f"runtime_metrics={runtime_metrics_source_path}, "
            f"app={app_ts_path}"
        ),
    )
    _check(
        checks,
        "runtime_capture_preflight_unit_tests_present",
        "buildRuntimeCaptureReadiness blocks unsafe capture starts" in runtime_metrics_tests_source
        and "buildRuntimeCaptureReadiness allows validated ROI capture starts"
        in runtime_metrics_tests_source,
        f"path={runtime_metrics_tests_path}",
    )
    _check(
        checks,
        "mobile_feature_media_manifest_sources",
        "feature_manifest" in capture_contract_source
        and "mobile_feature_manifest_v0.1" in capture_contract_source
        and "derivatives_only" in capture_contract_source
        and "raw_media" in capture_contract_source
        and "upload_raw_audio" in capture_contract_source
        and "feature_manifest" in backend_capture_contract_source
        and "FEATURE_MANIFEST_VERSION" in backend_capture_contract_source
        and "derivatives_only must be true" in backend_capture_contract_source
        and "upload_raw_audio" in backend_capture_contract_source
        and "raw_media.{flag} must be false" in backend_capture_contract_source,
        (
            f"mobile_capture_contract={capture_contract_source_path}, "
            f"backend_capture_contract={backend_capture_contract_path}"
        ),
    )
    _check(
        checks,
        "mobile_feature_media_manifest_unit_tests_present",
        "assertDerivativesOnlyFeatureManifest" in capture_tests_source
        and "runtime_quality.high_motion_ratio" in capture_tests_source
        and "allows_derivatives_only_feature_manifest" in backend_capture_tests_source
        and "rejects_feature_manifest_raw_media_upload" in backend_capture_tests_source,
        f"paths={[str(capture_tests_path), str(backend_capture_tests_path)]}",
    )
    raw_media_cleanup_requirements = {
        "cleanup_source_file": raw_media_retention_source_path.is_file(),
        "file_system_deleter": (
            'await import("expo-file-system")' in raw_media_retention_source
            and "new File(uri).delete()" in raw_media_retention_source
        ),
        "stop_and_delete_helper": "stopAndDeleteRuntimeRecording"
        in raw_media_retention_source,
        "runtime_session_uses_cleanup": "stopAndDeleteRuntimeRecording"
        in runtime_capture_session_source,
        "runtime_session_no_direct_stop_only": "await this.recording.stop()"
        not in runtime_capture_session_source,
    }
    _check(
        checks,
        "runtime_raw_media_temp_cleanup_sources",
        all(raw_media_cleanup_requirements.values()),
        f"requirements={raw_media_cleanup_requirements!r}",
    )
    raw_media_cleanup_test_requirements = {
        "test_file": raw_media_retention_tests_path.is_file(),
        "delete_after_stop": "deletes recorder uri after stop"
        in raw_media_retention_tests_source,
        "delete_after_stop_failure": "still deletes pre-stop uri when stop fails"
        in raw_media_retention_tests_source,
        "delete_failure_best_effort": "reports best-effort delete failure"
        in raw_media_retention_tests_source,
    }
    _check(
        checks,
        "runtime_raw_media_temp_cleanup_unit_tests_present",
        all(raw_media_cleanup_test_requirements.values()),
        f"requirements={raw_media_cleanup_test_requirements!r}",
    )
    _check(
        checks,
        "runtime_timeline_analysis_sources",
        "runtime_timeline" in capture_contract_source
        and "deriveRuntimeTimeline" in capture_contract_source
        and "elapsed_wall_clock_ms" in capture_contract_source
        and "max_sample_gap_ratio" in capture_contract_source
        and "runtime_timeline" in backend_capture_contract_source
        and "analysis.runtime_timeline.sample_count must match samples length"
        in backend_capture_contract_source,
        (
            f"mobile_capture_contract={capture_contract_source_path}, "
            f"backend_capture_contract={backend_capture_contract_path}"
        ),
    )
    _check(
        checks,
        "runtime_timeline_analysis_unit_tests_present",
        "adds runtime timeline analysis" in capture_tests_source
        and "rejects_invalid_runtime_timeline" in backend_capture_tests_source
        and "elapsed_wall_clock_ms" in backend_capture_tests_source,
        f"paths={[str(capture_tests_path), str(backend_capture_tests_path)]}",
    )
    _check(
        checks,
        "runtime_timeline_quality_gate_sources",
        "timingGapWarning" in runtime_metrics_source
        and "timing_gap_warning" in capture_contract_source
        and "timing_gap_warning" in app_ts_source
        and "runtime_timeline_gap_warning" in backend_session_source
        and "analysis.runtime_quality.timing_gap_warning must be boolean"
        in backend_capture_contract_source,
        (
            f"runtime_metrics={runtime_metrics_source_path}, "
            f"capture_contract={capture_contract_source_path}, "
            f"backend_session={backend_session_path}"
        ),
    )
    runtime_timeline_quality_test_paths = [
        str(runtime_metrics_tests_path),
        str(capture_tests_path),
        str(backend_capture_tests_path),
        str(backend_session_tests_path),
    ]
    _check(
        checks,
        "runtime_timeline_quality_gate_unit_tests_present",
        "repeats timing-gap captures" in runtime_metrics_tests_source
        and "runtime_quality.timing_gap_warning" in capture_tests_source
        and "rejects_invalid_runtime_quality_timing_gap" in backend_capture_tests_source
        and "marks_repeat_for_runtime_timeline_gap" in backend_session_tests_source,
        f"paths={runtime_timeline_quality_test_paths}",
    )
    _check(
        checks,
        "pending_sync_queue_unit_tests_present",
        pending_sync_queue_tests_path.is_file(),
        f"path={pending_sync_queue_tests_path}",
    )
    connectivity_restore_requirements = {
        "netinfo_dependency": "@react-native-community/netinfo" in package_dependencies,
        "netinfo_listener": "NetInfo.addEventListener" in pending_sync_hook_source,
        "network_reachable_helper": "isNetworkReachableForSync" in pending_sync_queue_source,
        "restore_gate_helper": "shouldAutoSyncOnConnectivityRestore"
        in pending_sync_queue_source,
        "restore_gate_used_by_hook": "shouldAutoSyncOnConnectivityRestore"
        in pending_sync_hook_source,
    }
    _check(
        checks,
        "pending_sync_connectivity_restore_sources",
        all(connectivity_restore_requirements.values()),
        f"requirements={connectivity_restore_requirements!r}",
    )
    connectivity_restore_test_requirements = {
        "reachability_helper_test": (
            "isNetworkReachableForSync treats connected unknown internet as usable"
        )
        in pending_sync_queue_tests_source,
        "restore_gate_test": "requires unreachable to reachable transition"
        in pending_sync_queue_tests_source,
    }
    _check(
        checks,
        "pending_sync_connectivity_restore_unit_tests_present",
        all(connectivity_restore_test_requirements.values()),
        f"requirements={connectivity_restore_test_requirements!r}",
    )
    auth_retry_policy_requirements = {
        "endpoint_policy_helper": "classifyEndpointRetryable" in app_helpers_source,
        "clinical_hub_uses_endpoint_policy": (
            "classifyEndpointRetryable(options.endpoint, response.status)"
        )
        in clinical_hub_source,
        "auth_statuses_recoverable": (
            "statusCode === 401 || statusCode === 403" in app_helpers_source
        ),
        "validation_statuses_still_non_retryable": (
            "classifyEndpointRetryable(\"capture_packages\", 422)" in helper_tests_source
        ),
    }
    _check(
        checks,
        "pending_sync_auth_retry_policy_sources",
        all(auth_retry_policy_requirements.values()),
        f"requirements={auth_retry_policy_requirements!r}",
    )
    auth_retry_policy_test_requirements = {
        "helper_policy_test": "keeps auth failures queued for clinical payloads"
        in helper_tests_source,
        "clinical_hub_auth_retry_test": (
            "keeps auth failures retryable for queued clinical payloads"
        )
        in clinical_hub_tests_source,
        "queue_auth_retry_test": "keeps auth failures queued for credential repair"
        in pending_sync_queue_tests_source,
        "auth_error_redacted": "auth_or_permission" in pending_sync_queue_tests_source,
    }
    _check(
        checks,
        "pending_sync_auth_retry_policy_unit_tests_present",
        all(auth_retry_policy_test_requirements.values()),
        f"requirements={auth_retry_policy_test_requirements!r}",
    )
    mobile_e2e_sync_smoke_requirements = {
        "batch_replay_helper": "runPendingSyncBatch" in pending_sync_queue_source,
        "submitter_injection": "submitEndpoint" in pending_sync_queue_source,
        "hook_uses_batch_replay_helper": "runPendingSyncBatch" in pending_sync_hook_source,
        "paired_and_capture_counts": (
            "syncedPaired" in pending_sync_queue_source
            and "syncedCapture" in pending_sync_queue_source
        ),
    }
    _check(
        checks,
        "mobile_e2e_sync_smoke_sources",
        all(mobile_e2e_sync_smoke_requirements.values()),
        f"requirements={mobile_e2e_sync_smoke_requirements!r}",
    )
    mobile_e2e_sync_smoke_test_requirements = {
        "restore_smoke_test": (
            "mobile E2E smoke replays queued paired and capture submissions "
            "after network restore"
        )
        in pending_sync_queue_tests_source,
        "paired_capture_queue": (
            '"paired_measurements:SESSION-001:SYNC-E2E-001"'
            in pending_sync_queue_tests_source
            and '"capture_packages:SESSION-001:SYNC-E2E-001"'
            in pending_sync_queue_tests_source
        ),
        "synced_outcomes": (
            '"synced_paired"' in pending_sync_queue_tests_source
            and '"synced_capture"' in pending_sync_queue_tests_source
        ),
    }
    _check(
        checks,
        "mobile_e2e_sync_smoke_unit_tests_present",
        all(mobile_e2e_sync_smoke_test_requirements.values()),
        f"requirements={mobile_e2e_sync_smoke_test_requirements!r}",
    )
    mobile_device_smoke_template_requirements = {
        "template_file": mobile_device_smoke_template_path.is_file(),
        "schema_version": "mobile_device_smoke_log_v0.1"
        in mobile_device_smoke_template_source,
        "ios_platform": '"platform": "ios"' in mobile_device_smoke_template_source,
        "android_platform": '"platform": "android"' in mobile_device_smoke_template_source,
        "restore_sync_check": "connectivity_restore_sync" in mobile_device_smoke_template_source,
        "log_phi_review_check": "device_logs_reviewed_no_phi"
        in mobile_device_smoke_template_source,
        "runtime_timeline_evidence": "runtime_timeline"
        in mobile_device_smoke_template_source
        and "runtime_timeline_integrity" in mobile_device_smoke_template_source
        and "capture_payload.analysis.runtime_timeline"
        in mobile_device_smoke_template_source,
    }
    _check(
        checks,
        "mobile_device_smoke_log_template_present",
        all(mobile_device_smoke_template_requirements.values()),
        f"requirements={mobile_device_smoke_template_requirements!r}",
    )
    mobile_device_smoke_validator_requirements = {
        "validator_file": mobile_device_smoke_validator_path.is_file(),
        "required_platforms": "REQUIRED_PLATFORMS" in mobile_device_smoke_validator_source,
        "required_checks": "REQUIRED_SMOKE_CHECK_IDS" in mobile_device_smoke_validator_source,
        "sha256_traceability": "mobile_release_manifest_sha256"
        in mobile_device_smoke_validator_source,
        "no_phi_log_review": "device_logs_reviewed_no_phi"
        in mobile_device_smoke_validator_source,
        "runtime_timeline_validation": "_validate_runtime_timeline"
        in mobile_device_smoke_validator_source
        and "runtime_timeline_integrity" in mobile_device_smoke_validator_source
        and "gap_warning must be false" in mobile_device_smoke_validator_source,
    }
    _check(
        checks,
        "mobile_device_smoke_log_validator_sources",
        all(mobile_device_smoke_validator_requirements.values()),
        f"requirements={mobile_device_smoke_validator_requirements!r}",
    )
    mobile_device_smoke_validator_test_requirements = {
        "valid_template_test": "test_mobile_device_smoke_log_template_validates"
        in mobile_device_smoke_validator_tests_source,
        "ios_android_matrix_test": "requires_ios_and_android"
        in mobile_device_smoke_validator_tests_source,
        "required_checks_test": "requires_passing_required_checks"
        in mobile_device_smoke_validator_tests_source,
        "runtime_timeline_required_test": "requires_runtime_timeline"
        in mobile_device_smoke_validator_tests_source,
        "runtime_timeline_gap_warning_test": "rejects_timeline_gap_warning"
        in mobile_device_smoke_validator_tests_source,
    }
    _check(
        checks,
        "mobile_device_smoke_log_validator_unit_tests_present",
        all(mobile_device_smoke_validator_test_requirements.values()),
        f"requirements={mobile_device_smoke_validator_test_requirements!r}",
    )
    mobile_store_rollout_template_requirements = {
        "template_file": mobile_store_rollout_template_path.is_file(),
        "schema_version": "mobile_store_rollout_handoff_v0.1"
        in mobile_store_rollout_template_source,
        "testflight_channel": '"distribution_channel": "testflight_internal"'
        in mobile_store_rollout_template_source,
        "play_internal_channel": '"distribution_channel": "play_internal_testing"'
        in mobile_store_rollout_template_source,
        "blocked_external_status": '"rollout_status": "blocked_external"'
        in mobile_store_rollout_template_source,
        "release_manifest_traceability": "mobile_release_manifest_sha256"
        in mobile_store_rollout_template_source,
    }
    _check(
        checks,
        "mobile_store_rollout_handoff_template_present",
        all(mobile_store_rollout_template_requirements.values()),
        f"requirements={mobile_store_rollout_template_requirements!r}",
    )
    mobile_store_rollout_validator_requirements = {
        "validator_file": mobile_store_rollout_validator_path.is_file(),
        "required_channels": "REQUIRED_CHANNELS" in mobile_store_rollout_validator_source,
        "testflight_internal": "testflight_internal" in mobile_store_rollout_validator_source,
        "play_internal_testing": "play_internal_testing" in mobile_store_rollout_validator_source,
        "sha256_traceability": "mobile_release_manifest_sha256"
        in mobile_store_rollout_validator_source,
        "blocked_external_support": "BLOCKED_STATUS" in mobile_store_rollout_validator_source,
    }
    _check(
        checks,
        "mobile_store_rollout_handoff_validator_sources",
        all(mobile_store_rollout_validator_requirements.values()),
        f"requirements={mobile_store_rollout_validator_requirements!r}",
    )
    mobile_store_rollout_validator_test_requirements = {
        "valid_template_test": "test_mobile_store_rollout_handoff_template_validates"
        in mobile_store_rollout_validator_tests_source,
        "ios_android_channels_test": "requires_ios_and_android"
        in mobile_store_rollout_validator_tests_source,
        "distribution_pass_checks_test": "requires_pass_checks_for_distribution"
        in mobile_store_rollout_validator_tests_source,
        "release_sha_test": "rejects_invalid_release_sha"
        in mobile_store_rollout_validator_tests_source,
    }
    _check(
        checks,
        "mobile_store_rollout_handoff_validator_unit_tests_present",
        all(mobile_store_rollout_validator_test_requirements.values()),
        f"requirements={mobile_store_rollout_validator_test_requirements!r}",
    )
    mobile_release_bundle_verifier_requirements = {
        "verifier_file": mobile_release_bundle_verifier_path.is_file(),
        "traceability_validation": "TRACEABILITY_FIELDS"
        in mobile_release_bundle_verifier_source,
        "readiness_count_validation": "local_check_counts"
        in mobile_release_bundle_verifier_source,
        "store_handoff_digest_validation": "mobile_release_manifest_sha256"
        in mobile_release_bundle_verifier_source,
        "expected_run_validation": "expect_run_id" in mobile_release_bundle_verifier_source,
    }
    _check(
        checks,
        "mobile_release_bundle_verifier_sources",
        all(mobile_release_bundle_verifier_requirements.values()),
        f"requirements={mobile_release_bundle_verifier_requirements!r}",
    )
    mobile_release_bundle_verifier_test_requirements = {
        "valid_bundle_test": "test_mobile_release_bundle_verifier_accepts_consistent_bundle"
        in mobile_release_bundle_verifier_tests_source,
        "handoff_digest_mismatch_test": "rejects_handoff_digest_mismatch"
        in mobile_release_bundle_verifier_tests_source,
        "readiness_count_mismatch_test": "rejects_readiness_count_mismatch"
        in mobile_release_bundle_verifier_tests_source,
        "expected_git_sha_mismatch_test": "rejects_expected_git_sha_mismatch"
        in mobile_release_bundle_verifier_tests_source,
    }
    _check(
        checks,
        "mobile_release_bundle_verifier_unit_tests_present",
        all(mobile_release_bundle_verifier_test_requirements.values()),
        f"requirements={mobile_release_bundle_verifier_test_requirements!r}",
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
        "submit_exception_body_redaction": "summarizeSafeExceptionCategory(error, "
        in clinical_hub_source,
        "submit_outcome": "formatSafeResponseProblem(result.statusCode, result.body"
        in submit_outcome_source,
        "pending_sync_attempt": "summarizePendingError(options.result.body)"
        in pending_sync_queue_source,
        "pending_enqueue": "summarizePendingError(lastError)" in pending_sync_hook_source,
        "pending_storage_migration": "summarizePendingError(rawLastError)"
        in pending_storage_source,
        "no_raw_submit_exception_body": "body: String(error)" not in clinical_hub_source,
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
        "submit_exception_body_test": "network failures retryable" in clinical_hub_tests_source
        and "secret-token" in clinical_hub_tests_source
        and '"network_or_timeout"' in clinical_hub_tests_source,
    }
    _check(
        checks,
        "mobile_api_response_redaction_unit_tests_present",
        all(redaction_test_requirements.values()),
        f"requirements={redaction_test_requirements!r}",
    )
    phi_exception_redaction_requirements = {
        "safe_exception_formatter": "formatSafeExceptionMessage" in app_helpers_source,
        "capture_start_status_safe": "Capture start failed: ${message}" in app_ts_source,
        "capture_start_alert_safe": 'Alert.alert("Capture start failed", message)'
        in app_ts_source,
        "capture_stop_status_safe": "Capture stop failed: ${message}" in app_ts_source,
        "capture_stop_alert_safe": 'Alert.alert("Capture stop failed", message)'
        in app_ts_source,
        "no_raw_capture_start_status": "Capture start failed: ${String(error)}"
        not in app_ts_source,
        "no_raw_capture_start_alert": 'Alert.alert("Capture start failed", String(error))'
        not in app_ts_source,
        "no_raw_capture_stop_status": "Capture stop failed: ${String(error)}"
        not in app_ts_source,
        "no_raw_capture_stop_alert": 'Alert.alert("Capture stop failed", String(error))'
        not in app_ts_source,
    }
    _check(
        checks,
        "mobile_phi_exception_redaction_sources",
        all(phi_exception_redaction_requirements.values()),
        f"requirements={phi_exception_redaction_requirements!r}",
    )
    _check(
        checks,
        "mobile_phi_exception_redaction_unit_tests_present",
        "formatSafeExceptionMessage redacts mobile PHI and secret-like details"
        in helper_tests_source
        and "formatSafeExceptionMessage preserves network category without raw exception text"
        in helper_tests_source,
        f"path={helper_tests_path}",
    )
    _check(
        checks,
        "build_scripts",
        "build:preview" in scripts and "build:production" in scripts,
        "package build scripts are present",
    )
    submit_script_requirements = {
        "ios_script": "submit:ios:production" in scripts,
        "ios_platform": "--platform ios" in scripts.get("submit:ios:production", ""),
        "android_script": "submit:android:production" in scripts,
        "android_platform": "--platform android" in scripts.get("submit:android:production", ""),
        "all_script": "submit:production" in scripts,
        "all_platform": "--platform all" in scripts.get("submit:production", ""),
        "production_profile": all(
            "--profile production" in scripts.get(script_name, "")
            for script_name in (
                "submit:ios:production",
                "submit:android:production",
                "submit:production",
            )
        ),
        "latest_build_source": all(
            "--latest" in scripts.get(script_name, "")
            for script_name in (
                "submit:ios:production",
                "submit:android:production",
                "submit:production",
            )
        ),
        "non_interactive": all(
            "--non-interactive" in scripts.get(script_name, "")
            for script_name in (
                "submit:ios:production",
                "submit:android:production",
                "submit:production",
            )
        ),
    }
    _check(
        checks,
        "eas_submit_scripts_present",
        all(submit_script_requirements.values()),
        f"requirements={submit_script_requirements!r}",
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
