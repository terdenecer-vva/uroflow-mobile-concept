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
        if item["status"] == "missing" and item["id"] in external_action_map:
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

    expo = app_payload.get("expo", {})
    plugins = expo.get("plugins", [])
    ios = expo.get("ios", {})
    android = expo.get("android", {})
    scripts = package_payload.get("scripts", {})
    root_lock = lock_payload.get("packages", {}).get("", {})
    eas_build = eas_payload.get("build", {})
    mobile_root = package_json.parent

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
    validate_ci_script = scripts.get("validate:ci", "")
    test_unit_script = scripts.get("test:unit", "")
    unit_runner_path = mobile_root / "scripts" / "run-unit-tests.sh"
    helper_tests_path = mobile_root / "tests" / "appHelpers.test.js"
    app_settings_storage_tests_path = mobile_root / "tests" / "appSettingsStorage.test.js"
    clinical_hub_api_tests_path = mobile_root / "tests" / "clinicalHub.test.js"
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
    authenticated_eas_item_ids = {"expo_token", "eas_project_identity"}
    authenticated_eas_blockers = [
        item["id"] for item in external_items if item["id"] in authenticated_eas_item_ids
        and item["status"] == "missing"
    ]
    clinical_hub_live_api_status = next(
        (
            item["status"]
            for item in external_items
            if item["id"] == "clinical_hub_live_api"
        ),
        "missing",
    )
    if local_failures:
        status = "not_ready"
    elif external_missing:
        status = "ready_except_external_credentials"
    else:
        status = "ready_for_authenticated_eas_preflight"

    next_actions = _build_next_actions(external_items, manual_external_items)

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "traceability": _build_traceability(env),
        "status": status,
        "local_checks_status": "pass" if not local_failures else "fail",
        "external_readiness_status": "pass" if not external_missing else "blocked",
        "authenticated_eas_status": "pass" if not authenticated_eas_blockers else "blocked",
        "authenticated_eas_blockers": authenticated_eas_blockers,
        "clinical_hub_live_api_status": clinical_hub_live_api_status,
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
