#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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

    expo = app_payload.get("expo", {})
    plugins = expo.get("plugins", [])
    ios = expo.get("ios", {})
    android = expo.get("android", {})
    scripts = package_payload.get("scripts", {})
    root_lock = lock_payload.get("packages", {}).get("", {})
    eas_build = eas_payload.get("build", {})

    checks: list[dict[str, Any]] = []

    platforms = expo.get("platforms", [])
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

    for profile in ("development", "preview", "production"):
        _check(
            checks,
            f"eas_profile_{profile}",
            profile in eas_build,
            f"eas build profiles={list(eas_build)}",
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
    _check(
        checks,
        "build_scripts",
        "build:preview" in scripts and "build:production" in scripts,
        "package build scripts are present",
    )
    _check(
        checks,
        "package_lock_matches_root",
        root_lock.get("name") == package_payload.get("name"),
        f"lock root={root_lock.get('name')!r}, package={package_payload.get('name')!r}",
    )
    _check(
        checks,
        "expo_doctor_pinned",
        package_payload.get("devDependencies", {}).get("expo-doctor") == "1.19.8"
        and root_lock.get("devDependencies", {}).get("expo-doctor") == "1.19.8",
        "expo-doctor devDependency is pinned in package.json and package-lock.json",
    )

    extra = expo.get("extra", {})
    eas_project_id = (
        extra.get("eas", {}).get("projectId") if isinstance(extra.get("eas"), dict) else None
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
            "status": "present"
            if bool(env.get("CLINICAL_HUB_URL") and env.get("CLINICAL_HUB_API_KEY"))
            else "missing",
            "required_for": "Live Clinical Hub smoke tests and CI report push.",
            "evidence": "CLINICAL_HUB_URL and CLINICAL_HUB_API_KEY are set"
            if env.get("CLINICAL_HUB_URL") and env.get("CLINICAL_HUB_API_KEY")
            else "CLINICAL_HUB_URL and/or CLINICAL_HUB_API_KEY are not set",
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
    external_missing = [item for item in external_items if item["status"] == "missing"]
    if local_failures:
        status = "not_ready"
    elif external_missing:
        status = "ready_except_external_credentials"
    else:
        status = "ready_for_authenticated_eas_preflight"

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "local_checks_status": "pass" if not local_failures else "fail",
        "external_readiness_status": "pass" if not external_missing else "blocked",
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
