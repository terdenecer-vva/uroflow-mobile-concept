from __future__ import annotations

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
    assets = tmp_path / "assets"
    metadata_path = tmp_path / "src" / "config" / "releaseMetadata.ts"
    app_config_path = tmp_path / "src" / "config" / "appConfig.ts"
    app_settings_path = tmp_path / "src" / "storage" / "appSettingsStorage.ts"
    assets.mkdir()
    metadata_path.parent.mkdir(parents=True)
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

    script_path = Path("scripts/build_mobile_release_manifest.py")
    subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--app-json",
            str(app_json),
            "--output",
            str(output),
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
    assert payload["runtime_config"]["allow_debug_controls"] is False
    assert payload["runtime_config"]["allow_raw_response_details"] is False
    assert payload["runtime_config"]["enable_verbose_logging"] is False
    assert payload["runtime_defaults"]["default_api_base_url"] == ""
    assert payload["algorithm"]["model_id"] == "fusion-v0.1"
    assert payload["algorithm"]["capture_schema_version"] == "ios_capture_v1"
