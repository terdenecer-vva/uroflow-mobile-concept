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
    assert "release_notes" in triggers["workflow_dispatch"]["inputs"]


def test_mobile_build_workflow_uploads_readiness_before_local_failure() -> None:
    payload = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = payload["jobs"]["preflight"]["steps"]
    step_names = [step.get("name") for step in steps]

    build_index = step_names.index("Build release readiness report")
    upload_index = step_names.index("Upload release readiness report")
    fail_index = step_names.index("Fail on local release readiness errors")

    assert build_index < upload_index < fail_index
    assert "mobile-release-readiness-exit-code" in steps[build_index]["run"]
    assert "mobile-release-readiness artifact" in steps[fail_index]["run"]


def test_mobile_build_workflow_embeds_readiness_summary_in_release_manifest() -> None:
    payload = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = payload["jobs"]["preflight"]["steps"]
    manifest_step = next(step for step in steps if step.get("name") == "Build release manifest")

    assert "--readiness-json /tmp/mobile-release-readiness.json" in manifest_step["run"]
    assert "--release-notes /tmp/mobile-release-notes.md" in manifest_step["run"]


def test_mobile_build_workflow_uploads_release_notes_artifact() -> None:
    payload = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = payload["jobs"]["preflight"]["steps"]
    step_names = [step.get("name") for step in steps]

    notes_index = step_names.index("Build release notes artifact")
    manifest_index = step_names.index("Build release manifest")
    upload_index = step_names.index("Upload release notes")
    notes_upload_step = steps[upload_index]

    assert notes_index < manifest_index < upload_index
    assert "WORKFLOW_RELEASE_NOTES" in steps[notes_index]["env"]
    assert notes_upload_step["with"]["name"] == "mobile-release-notes"
    assert notes_upload_step["with"]["path"] == "/tmp/mobile-release-notes.md"


def test_mobile_build_workflow_summary_reports_invalid_external_items() -> None:
    payload = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = payload["jobs"]["preflight"]["steps"]
    summary_step = next(
        step for step in steps if step.get("name") == "Publish release readiness summary"
    )

    assert 'item.get("status") == "invalid"' in summary_step["run"]
    assert "Invalid external items" in summary_step["run"]
