from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zlib
from pathlib import Path


def _write_png(path: Path, width: int, height: int) -> None:
    import struct

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    row = b"\x00" + (b"\x00\x00\x00\xff" * width)
    raw = row * height
    payload = b"\x89PNG\r\n\x1a\n"
    payload += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    payload += chunk(b"IDAT", zlib.compress(raw, 9))
    payload += chunk(b"IEND", b"")
    path.write_bytes(payload)


def test_build_mobile_release_manifest_script(tmp_path: Path) -> None:
    app_json = tmp_path / "app.json"
    output = tmp_path / "manifest.json"
    readiness_json = tmp_path / "readiness.json"
    release_notes = tmp_path / "mobile-release-notes.md"
    assets = tmp_path / "assets"
    metadata_path = tmp_path / "src" / "config" / "releaseMetadata.ts"
    app_config_path = tmp_path / "src" / "config" / "appConfig.ts"
    capture_contract_path = tmp_path / "src" / "capture" / "buildCaptureContract.ts"
    app_settings_path = tmp_path / "src" / "storage" / "appSettingsStorage.ts"
    assets.mkdir()
    metadata_path.parent.mkdir(parents=True)
    capture_contract_path.parent.mkdir(parents=True)
    app_settings_path.parent.mkdir(parents=True)
    _write_png(assets / "icon.png", 1024, 1024)
    _write_png(assets / "adaptive-icon.png", 1024, 1024)
    _write_png(assets / "splash.png", 1024, 1024)

    app_json.write_text(
        json.dumps(
            {
                "expo": {
                    "name": "Uroflow Field",
                    "slug": "uroflow-field-mobile",
                    "version": "0.1.0",
                    "icon": "./assets/icon.png",
                    "platforms": ["ios", "android"],
                    "plugins": [
                        [
                            "expo-splash-screen",
                            {
                                "image": "./assets/splash.png",
                                "resizeMode": "contain",
                                "backgroundColor": "#F5F2EA",
                                "imageWidth": 220,
                            },
                        ]
                    ],
                    "ios": {
                        "bundleIdentifier": "com.uroflow.field",
                        "buildNumber": "1",
                    },
                    "android": {
                        "package": "com.uroflow.field",
                        "versionCode": 1,
                        "adaptiveIcon": {
                            "foregroundImage": "./assets/adaptive-icon.png",
                            "backgroundColor": "#0B1F2A",
                        },
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    metadata_path.write_text(
        "\n".join(
            [
                'export const APP_RELEASE_VERSION = "0.1.0";',
                'export const APP_MODEL_ID = "fusion-v0.1";',
                'export const APP_CAPTURE_SCHEMA_VERSION = "ios_capture_v1";',
            ]
        ),
        encoding="utf-8",
    )
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
                "export const APP_ALLOW_DEBUG_CONTROLS = false;",
                "export const APP_ALLOW_RAW_RESPONSE_DETAILS = false;",
                "export const APP_ENABLE_VERBOSE_LOGGING = false;",
            ]
        ),
        encoding="utf-8",
    )
    app_settings_path.write_text(
        'export const DEFAULT_API_BASE_URL = "";\n',
        encoding="utf-8",
    )
    capture_contract_path.write_text(
        "\n".join(
            [
                'const FEATURE_MANIFEST_VERSION = "mobile_feature_manifest_v0.1";',
                'const BASE_FEATURE_KEYS = ["t_s", "depth_level_mm", "rgb_level_mm",',
                '  "depth_confidence", "audio_rms_dbfs", "motion_norm", "roi_valid"];',
                'featureKeys.add("runtime_flow_series.flow_ml_s");',
                'featureKeys.add("runtime_alignment.max_stream_drift_ms");',
                'featureKeys.add("runtime_alignment.drift_warning");',
                'featureKeys.add("runtime_quality.high_motion_ratio");',
                'featureKeys.add("runtime_quality.alignment_drift_warning");',
                'featureKeys.add("runtime_quality.timing_gap_warning");',
                'featureKeys.add("runtime_timeline.max_sample_gap_s");',
                'featureKeys.add("runtime_timeline.gap_warning");',
                "const featureManifest = {",
                "  derivatives_only: true,",
                "  sample_count: samples.length,",
                "  upload_raw_video: false,",
                "  upload_raw_audio: false,",
                '  media_scope: "roi_derivatives_only",',
                "};",
            ]
        ),
        encoding="utf-8",
    )
    readiness_json.write_text(
        json.dumps(
            {
                "status": "ready_except_external_credentials",
                "local_checks_status": "pass",
                "external_readiness_status": "blocked",
                "authenticated_eas_status": "blocked",
                "authenticated_eas_blockers": ["expo_token", "eas_project_identity"],
                "clinical_hub_live_api_status": "missing",
                "local_checks": [
                    {
                        "id": "runtime_config_privacy_by_default",
                        "status": "pass",
                        "severity": "error",
                        "evidence": "secret-free evidence",
                    },
                    {
                        "id": "preview_android_apk",
                        "status": "pass",
                        "severity": "warning",
                        "evidence": "warning evidence",
                    },
                ],
                "external_items": [
                    {
                        "id": "expo_token",
                        "status": "missing",
                        "evidence": "EXPO_TOKEN environment variable is not set",
                    },
                    {
                        "id": "eas_project_identity",
                        "status": "missing",
                        "evidence": "EAS_PROJECT_ID is not set",
                    },
                    {
                        "id": "clinical_hub_live_api",
                        "status": "missing",
                        "evidence": "CLINICAL_HUB_URL and/or CLINICAL_HUB_API_KEY are not set",
                    },
                ],
                "manual_external_items": [
                    {
                        "id": "apple_developer_account",
                        "status": "manual_required",
                    },
                    {
                        "id": "google_play_account",
                        "status": "manual_required",
                    },
                ],
                "next_actions": [
                    {"id": "configure_expo_token"},
                    {"id": "configure_eas_project_identity"},
                    {"id": "configure_clinical_hub_live_api"},
                ],
            }
        ),
        encoding="utf-8",
    )
    release_notes.write_text(
        "\n".join(
            [
                "# Uroflow Field Mobile Release Notes",
                "",
                "Pilot operator note: verify offline queue before first subject.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    script_path = Path("scripts/build_mobile_release_manifest.py")
    subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--app-json",
            str(app_json),
            "--output",
            str(output),
            "--readiness-json",
            str(readiness_json),
            "--release-notes",
            str(release_notes),
            "--profile",
            "preview",
            "--channel",
            "preview",
            "--model-id",
            "fusion-v0.1",
            "--schema-version",
            "ios_capture_v1",
        ],
        check=True,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["release"]["profile"] == "preview"
    assert payload["release"]["channel"] == "preview"
    assert payload["app"]["name"] == "Uroflow Field"
    assert payload["app"]["ios_build_number"] == "1"
    assert payload["app"]["android_version_code"] == 1
    assert payload["assets"]["icon"]["path"] == "./assets/icon.png"
    assert payload["assets"]["icon"]["bytes"] > 0
    assert len(payload["assets"]["icon"]["sha256"]) == 64
    assert payload["assets"]["icon"]["png_dimensions"] == [1024, 1024]
    assert payload["assets"]["splash"]["image"]["path"] == "./assets/splash.png"
    assert payload["assets"]["splash"]["image"]["png_dimensions"] == [1024, 1024]
    assert payload["assets"]["splash"]["resize_mode"] == "contain"
    assert payload["assets"]["splash"]["background_color"] == "#F5F2EA"
    assert payload["assets"]["splash"]["image_width"] == 220
    assert payload["assets"]["android_adaptive_icon"]["foreground"]["path"] == (
        "./assets/adaptive-icon.png"
    )
    assert payload["assets"]["android_adaptive_icon"]["foreground"]["png_dimensions"] == [
        1024,
        1024,
    ]
    assert payload["assets"]["android_adaptive_icon"]["background_color"] == "#0B1F2A"
    assert payload["runtime_release_metadata"]["app_version"] == "0.1.0"
    assert payload["runtime_release_metadata"]["model_id"] == "fusion-v0.1"
    assert payload["runtime_release_metadata"]["capture_schema_version"] == "ios_capture_v1"
    assert payload["runtime_config"]["runtime_mode"] == "pilot"
    assert payload["runtime_config"]["endpoint_set"] == "clinical_hub_v1"
    assert payload["runtime_config"]["default_capture_mode"] == "water_impact"
    assert payload["runtime_config"]["paired_measurements_endpoint_path"] == (
        "/api/v1/paired-measurements"
    )
    assert payload["runtime_config"]["capture_packages_endpoint_path"] == (
        "/api/v1/capture-packages"
    )
    assert payload["runtime_config"]["store_raw_video"] is False
    assert payload["runtime_config"]["store_raw_audio"] is False
    assert payload["runtime_config"]["roi_only"] is True
    assert payload["runtime_config"]["data_residency_region"] == "us"
    assert payload["runtime_config"]["data_residency_boundary"] == "single_region"
    assert payload["runtime_config"]["allow_cross_region_sync"] is False
    assert payload["runtime_config"]["require_region_matched_clinical_hub"] is True
    assert payload["runtime_config"]["allow_debug_controls"] is False
    assert payload["runtime_config"]["allow_raw_response_details"] is False
    assert payload["runtime_config"]["enable_verbose_logging"] is False
    assert payload["runtime_defaults"]["default_api_base_url"] == ""
    assert payload["capture_contract"]["path"] == str(capture_contract_path)
    feature_manifest = payload["capture_contract"]["feature_manifest"]
    assert feature_manifest["version"] == "mobile_feature_manifest_v0.1"
    assert feature_manifest["derivatives_only"] is True
    assert feature_manifest["sample_count_source"] == "samples.length"
    assert feature_manifest["raw_media"] == {
        "store_raw_video": False,
        "store_raw_audio": False,
        "upload_raw_video": False,
        "upload_raw_audio": False,
    }
    assert feature_manifest["privacy"] == {
        "roi_only": True,
        "media_scope": "roi_derivatives_only",
    }
    assert "audio_rms_dbfs" in feature_manifest["feature_keys"]
    assert "runtime_alignment.max_stream_drift_ms" in feature_manifest["feature_keys"]
    assert "runtime_alignment.drift_warning" in feature_manifest["feature_keys"]
    assert "runtime_quality.high_motion_ratio" in feature_manifest["feature_keys"]
    assert "runtime_quality.alignment_drift_warning" in feature_manifest["feature_keys"]
    assert "runtime_quality.timing_gap_warning" in feature_manifest["feature_keys"]
    assert "runtime_timeline.max_sample_gap_s" in feature_manifest["feature_keys"]
    assert "runtime_timeline.gap_warning" in feature_manifest["feature_keys"]
    assert payload["readiness"] == {
        "source_path": str(readiness_json),
        "status": "ready_except_external_credentials",
        "local_checks_status": "pass",
        "external_readiness_status": "blocked",
        "authenticated_eas_status": "blocked",
        "authenticated_eas_blockers": ["expo_token", "eas_project_identity"],
        "clinical_hub_live_api_status": "missing",
        "local_check_counts": {"pass": 2},
        "failed_local_checks": [],
        "warning_local_checks": ["preview_android_apk"],
        "external_items": [
            {"id": "expo_token", "status": "missing"},
            {"id": "eas_project_identity", "status": "missing"},
            {"id": "clinical_hub_live_api", "status": "missing"},
        ],
        "manual_external_items": [
            {"id": "apple_developer_account", "status": "manual_required"},
            {"id": "google_play_account", "status": "manual_required"},
        ],
        "next_action_ids": [
            "configure_expo_token",
            "configure_eas_project_identity",
            "configure_clinical_hub_live_api",
        ],
    }
    release_notes_bytes = release_notes.read_bytes()
    assert payload["release_notes"] == {
        "source_path": str(release_notes),
        "present": True,
        "bytes": len(release_notes_bytes),
        "sha256": hashlib.sha256(release_notes_bytes).hexdigest(),
        "title": "Uroflow Field Mobile Release Notes",
    }
    serialized_manifest = json.dumps(payload)
    assert "secret-free evidence" not in serialized_manifest
    assert "EXPO_TOKEN environment variable is not set" not in serialized_manifest
    assert payload["algorithm"]["model_id"] == "fusion-v0.1"
    assert payload["algorithm"]["capture_schema_version"] == "ios_capture_v1"
