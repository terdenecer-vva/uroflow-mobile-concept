#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


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
            "ios_bundle_identifier": expo.get("ios", {}).get("bundleIdentifier"),
            "android_package": expo.get("android", {}).get("package"),
        },
        "traceability": {
            "git_sha": os.environ.get("GITHUB_SHA", "local"),
            "git_ref": os.environ.get("GITHUB_REF", "local"),
            "git_run_id": os.environ.get("GITHUB_RUN_ID", "local"),
            "workflow": os.environ.get("GITHUB_WORKFLOW", "local"),
        },
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
