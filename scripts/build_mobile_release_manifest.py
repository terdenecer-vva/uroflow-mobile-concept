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
    pattern = re.compile(rf"export\s+const\s+{re.escape(name)}\s*=\s*[\"']([^\"']+)[\"']")
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build mobile release manifest for pilot traceability."
    )
    parser.add_argument("--app-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
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
