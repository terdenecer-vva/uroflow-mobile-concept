from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(".github/workflows/mobile-build.yml")


def _workflow_triggers() -> dict:
    payload = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # PyYAML follows YAML 1.1 and may parse the GitHub Actions `on` key as True.
    return payload.get("on") or payload[True]


def test_mobile_build_workflow_runs_for_release_script_changes() -> None:
    triggers = _workflow_triggers()
    required_paths = {
        "apps/field-mobile/**",
        "scripts/build_mobile_release_manifest.py",
        "scripts/check_mobile_release_readiness.py",
        ".github/workflows/mobile-build.yml",
    }

    assert required_paths.issubset(set(triggers["push"]["paths"]))
    assert required_paths.issubset(set(triggers["pull_request"]["paths"]))
