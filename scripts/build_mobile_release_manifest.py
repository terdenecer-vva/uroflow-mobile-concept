#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _asset_path(app_json: Path, raw_path: Any) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = app_json.parent / candidate
    return candidate


def _png_dimensions(path: Path) -> list[int] | None:
    header = path.read_bytes()[:24]
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        return None
    return [int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")]


def _asset_metadata(app_json: Path, raw_path: Any) -> dict[str, Any] | None:
    path = _asset_path(app_json, raw_path)
    if path is None or not path.is_file():
        return None
    data = path.read_bytes()
    return {
        "path": raw_path,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "png_dimensions": _png_dimensions(path),
    }


def _get_plugin_options(plugins: list[Any], plugin_name: str) -> dict[str, Any]:
    for plugin in plugins:
        if isinstance(plugin, list) and len(plugin) > 1 and plugin[0] == plugin_name:
            return plugin[1] if isinstance(plugin[1], dict) else {}
    return {}


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


def _read_ts_string_assignment(source: str, name: str) -> str | None:
    pattern = re.compile(rf"{re.escape(name)}\s*=\s*[\"']([^\"']*)[\"']")
    match = pattern.search(source)
    return match.group(1) if match else None


def _release_metadata(app_json: Path) -> dict[str, str | None]:
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


def _app_runtime_config(app_json: Path) -> dict[str, str | bool | None]:
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
        "allow_debug_controls": _read_ts_boolean_constant(source, "APP_ALLOW_DEBUG_CONTROLS"),
        "allow_raw_response_details": _read_ts_boolean_constant(
            source, "APP_ALLOW_RAW_RESPONSE_DETAILS"
        ),
        "enable_verbose_logging": _read_ts_boolean_constant(
            source, "APP_ENABLE_VERBOSE_LOGGING"
        ),
    }


def _app_settings_defaults(app_json: Path) -> dict[str, str | None]:
    path = app_json.parent / "src" / "storage" / "appSettingsStorage.ts"
    if not path.is_file():
        return {"path": str(path), "default_api_base_url": None}
    source = path.read_text(encoding="utf-8")
    return {
        "path": str(path),
        "default_api_base_url": _read_ts_string_constant(source, "DEFAULT_API_BASE_URL"),
    }


def _capture_contract_evidence(
    app_json: Path,
    app_runtime_config: dict[str, str | bool | None],
) -> dict[str, Any]:
    path = app_json.parent / "src" / "capture" / "buildCaptureContract.ts"
    if not path.is_file():
        return {
            "path": str(path),
            "feature_manifest": {
                "version": None,
                "derivatives_only": None,
                "sample_count_source": None,
                "feature_keys": [],
                "raw_media": {
                    "store_raw_video": app_runtime_config.get("store_raw_video"),
                    "store_raw_audio": app_runtime_config.get("store_raw_audio"),
                    "upload_raw_video": None,
                    "upload_raw_audio": None,
                },
                "privacy": {
                    "roi_only": app_runtime_config.get("roi_only"),
                    "media_scope": None,
                },
            },
        }

    source = path.read_text(encoding="utf-8")
    feature_keys = [
        key
        for key in (
            "audio_rms_dbfs",
            "depth_confidence",
            "depth_level_mm",
            "motion_norm",
            "rgb_level_mm",
            "roi_valid",
            "runtime_flow_series.flow_ml_s",
            "runtime_quality.high_motion_ratio",
            "t_s",
        )
        if key in source
    ]
    if (
        "runtime_quality" in source
        and "high_motion_ratio" in source
        and "runtime_quality.high_motion_ratio" not in feature_keys
    ):
        feature_keys.append("runtime_quality.high_motion_ratio")
    return {
        "path": str(path),
        "feature_manifest": {
            "version": _read_ts_string_assignment(source, "FEATURE_MANIFEST_VERSION"),
            "derivatives_only": "derivatives_only: true" in source,
            "sample_count_source": (
                "samples.length" if "sample_count: samples.length" in source else None
            ),
            "feature_keys": feature_keys,
            "raw_media": {
                "store_raw_video": app_runtime_config.get("store_raw_video"),
                "store_raw_audio": app_runtime_config.get("store_raw_audio"),
                "upload_raw_video": False if "upload_raw_video: false" in source else None,
                "upload_raw_audio": False if "upload_raw_audio: false" in source else None,
            },
            "privacy": {
                "roi_only": app_runtime_config.get("roi_only"),
                "media_scope": (
                    "roi_derivatives_only"
                    if 'media_scope: "roi_derivatives_only"' in source
                    else None
                ),
            },
        },
    }


def _readiness_summary(readiness_json: Path | None) -> dict[str, Any]:
    if readiness_json is None:
        return {
            "source_path": None,
            "status": "not_provided",
            "local_checks_status": None,
            "external_readiness_status": None,
            "authenticated_eas_status": None,
            "authenticated_eas_blockers": [],
            "clinical_hub_live_api_status": None,
            "local_check_counts": {},
            "failed_local_checks": [],
            "warning_local_checks": [],
            "external_items": [],
            "manual_external_items": [],
            "next_action_ids": [],
        }
    if not readiness_json.is_file():
        return {
            "source_path": str(readiness_json),
            "status": "missing",
            "local_checks_status": None,
            "external_readiness_status": None,
            "authenticated_eas_status": None,
            "authenticated_eas_blockers": [],
            "clinical_hub_live_api_status": None,
            "local_check_counts": {},
            "failed_local_checks": [],
            "warning_local_checks": [],
            "external_items": [],
            "manual_external_items": [],
            "next_action_ids": [],
        }

    payload = json.loads(readiness_json.read_text(encoding="utf-8"))
    local_checks = payload.get("local_checks", [])
    local_check_counts: dict[str, int] = {}
    failed_local_checks: list[str] = []
    warning_local_checks: list[str] = []
    for check in local_checks:
        if not isinstance(check, dict):
            continue
        status = str(check.get("status", "unknown"))
        local_check_counts[status] = local_check_counts.get(status, 0) + 1
        check_id = check.get("id")
        if isinstance(check_id, str) and status != "pass":
            failed_local_checks.append(check_id)
        if isinstance(check_id, str) and check.get("severity") == "warning":
            warning_local_checks.append(check_id)

    def item_statuses(items: Any) -> list[dict[str, str]]:
        if not isinstance(items, list):
            return []
        result: list[dict[str, str]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            status = item.get("status")
            if isinstance(item_id, str) and isinstance(status, str):
                result.append({"id": item_id, "status": status})
        return result

    next_action_ids = [
        item["id"]
        for item in payload.get("next_actions", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]

    return {
        "source_path": str(readiness_json),
        "status": payload.get("status"),
        "local_checks_status": payload.get("local_checks_status"),
        "external_readiness_status": payload.get("external_readiness_status"),
        "authenticated_eas_status": payload.get("authenticated_eas_status"),
        "authenticated_eas_blockers": payload.get("authenticated_eas_blockers", []),
        "clinical_hub_live_api_status": payload.get("clinical_hub_live_api_status"),
        "local_check_counts": local_check_counts,
        "failed_local_checks": failed_local_checks,
        "warning_local_checks": warning_local_checks,
        "external_items": item_statuses(payload.get("external_items")),
        "manual_external_items": item_statuses(payload.get("manual_external_items")),
        "next_action_ids": next_action_ids,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build mobile release manifest for pilot traceability."
    )
    parser.add_argument("--app-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--readiness-json", type=Path)
    parser.add_argument("--profile", default="preview")
    parser.add_argument("--channel", default="preview")
    parser.add_argument("--model-id", default="fusion-v0.1")
    parser.add_argument("--schema-version", default="ios_capture_v1")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app_payload = json.loads(args.app_json.read_text(encoding="utf-8"))
    expo = app_payload.get("expo", {})
    plugins = expo.get("plugins", [])
    ios = expo.get("ios", {})
    android = expo.get("android", {})
    splash = _get_plugin_options(plugins, "expo-splash-screen")
    release_metadata = _release_metadata(args.app_json)
    app_runtime_config = _app_runtime_config(args.app_json)
    app_settings_defaults = _app_settings_defaults(args.app_json)
    android_adaptive_icon = android.get("adaptiveIcon", {})

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "release": {
            "profile": args.profile,
            "channel": args.channel,
            "platforms": expo.get("platforms", ["ios", "android"]),
        },
        "app": {
            "name": expo.get("name"),
            "slug": expo.get("slug"),
            "version": expo.get("version"),
            "ios_bundle_identifier": ios.get("bundleIdentifier"),
            "ios_build_number": ios.get("buildNumber"),
            "android_package": android.get("package"),
            "android_version_code": android.get("versionCode"),
        },
        "assets": {
            "icon": _asset_metadata(args.app_json, expo.get("icon")),
            "splash": {
                "image": _asset_metadata(args.app_json, splash.get("image")),
                "resize_mode": splash.get("resizeMode"),
                "background_color": splash.get("backgroundColor"),
                "image_width": splash.get("imageWidth"),
            },
            "android_adaptive_icon": {
                "foreground": _asset_metadata(
                    args.app_json, android_adaptive_icon.get("foregroundImage")
                ),
                "background_color": android_adaptive_icon.get("backgroundColor"),
            },
        },
        "traceability": {
            "git_sha": os.environ.get("GITHUB_SHA", "local"),
            "git_ref": os.environ.get("GITHUB_REF", "local"),
            "git_run_id": os.environ.get("GITHUB_RUN_ID", "local"),
            "workflow": os.environ.get("GITHUB_WORKFLOW", "local"),
        },
        "runtime_release_metadata": release_metadata,
        "runtime_config": app_runtime_config,
        "runtime_defaults": app_settings_defaults,
        "capture_contract": _capture_contract_evidence(args.app_json, app_runtime_config),
        "readiness": _readiness_summary(args.readiness_json),
        "algorithm": {
            "model_id": args.model_id,
            "capture_schema_version": args.schema_version,
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"written {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
