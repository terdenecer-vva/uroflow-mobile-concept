from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(".github/workflows/ci.yml")


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_pilot_automation_gate_summary_includes_mobile_traceability() -> None:
    payload = _workflow()
    steps = payload["jobs"]["pilot-automation-smoke"]["steps"]
    gate_step = next(
        step for step in steps if step.get("name") == "Build gate metrics from automation artifacts"
    )
    run_script = gate_step["run"]

    assert "--trace-git-sha \"$GITHUB_SHA\"" in run_script
    assert "--trace-workflow-run-id \"$GITHUB_RUN_ID\"" in run_script
    assert "--trace-mobile-build-id \"github_actions:${GITHUB_RUN_ID}\"" in run_script
    assert "--trace-app-json apps/field-mobile/app.json" in run_script
    assert (
        "--trace-release-metadata-ts apps/field-mobile/src/config/releaseMetadata.ts"
        in run_script
    )
