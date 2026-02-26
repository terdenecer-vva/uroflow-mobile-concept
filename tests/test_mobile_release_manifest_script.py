from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_build_mobile_release_manifest_script(tmp_path: Path) -> None:
    app_json = tmp_path / "app.json"
    output = tmp_path / "manifest.json"

    app_json.write_text(
        json.dumps(
            {
                "expo": {
                    "name": "Uroflow Field",
                    "slug": "uroflow-field-mobile",
                    "version": "0.1.0",
                    "platforms": ["ios", "android"],
                    "ios": {"bundleIdentifier": "com.uroflow.field"},
                    "android": {"package": "com.uroflow.field"},
                }
            }
        ),
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
    assert payload["algorithm"]["model_id"] == "fusion-v0.1"
    assert payload["algorithm"]["capture_schema_version"] == "ios_capture_v1"
