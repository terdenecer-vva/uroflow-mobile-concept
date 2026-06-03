from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/check_mobile_release_readiness.py")
APP_JSON = Path("apps/field-mobile/app.json")
EAS_JSON = Path("apps/field-mobile/eas.json")
PACKAGE_JSON = Path("apps/field-mobile/package.json")
PACKAGE_LOCK = Path("apps/field-mobile/package-lock.json")


def _run_readiness(output: Path, env: dict[str, str]) -> dict:
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--app-json",
            str(APP_JSON),
            "--eas-json",
            str(EAS_JSON),
            "--package-json",
            str(PACKAGE_JSON),
            "--package-lock",
            str(PACKAGE_LOCK),
            "--output",
            str(output),
        ],
        check=True,
        env=env,
    )
    return json.loads(output.read_text(encoding="utf-8"))


def test_mobile_release_readiness_reports_external_blockers(tmp_path: Path) -> None:
    payload = _run_readiness(
        tmp_path / "readiness.json",
        env={"PATH": os.environ.get("PATH", "")},
    )

    assert payload["status"] == "ready_except_external_credentials"
    assert payload["local_checks_status"] == "pass"
    assert payload["external_readiness_status"] == "blocked"
    assert {item["id"] for item in payload["external_items"] if item["status"] == "missing"} == {
        "clinical_hub_live_api",
        "eas_project_identity",
        "expo_token",
    }
    assert all(item["status"] == "pass" for item in payload["local_checks"])


def test_mobile_release_readiness_passes_authenticated_preflight_env(tmp_path: Path) -> None:
    payload = _run_readiness(
        tmp_path / "readiness.json",
        env={
            "PATH": os.environ.get("PATH", ""),
            "CLINICAL_HUB_API_KEY": "test-key",
            "CLINICAL_HUB_URL": "https://clinical.example.test",
            "EAS_PROJECT_ID": "00000000-0000-0000-0000-000000000000",
            "EXPO_TOKEN": "test-token",
        },
    )

    assert payload["status"] == "ready_for_authenticated_eas_preflight"
    assert payload["local_checks_status"] == "pass"
    assert payload["external_readiness_status"] == "pass"
    assert all(item["status"] == "present" for item in payload["external_items"])
    assert {item["status"] for item in payload["manual_external_items"]} == {"manual_required"}
