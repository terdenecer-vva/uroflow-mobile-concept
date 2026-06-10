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
        "docs/mobile-device-smoke-log-template-v0.1.json",
        "scripts/build_mobile_dependency_review.py",
        "scripts/build_mobile_external_readiness_packet.py",
        "scripts/build_mobile_release_manifest.py",
        "scripts/check_mobile_release_readiness.py",
        "scripts/validate_mobile_device_smoke_log.py",
        "tests/test_mobile_dependency_review.py",
        "tests/test_mobile_device_smoke_log.py",
        "tests/test_mobile_external_readiness_packet.py",
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


def test_mobile_build_workflow_uploads_external_readiness_packet_before_failure() -> None:
    payload = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = payload["jobs"]["preflight"]["steps"]
    step_names = [step.get("name") for step in steps]

    readiness_index = step_names.index("Build release readiness report")
    build_index = step_names.index("Build external readiness packet")
    summary_index = step_names.index("Publish external readiness packet summary")
    upload_index = step_names.index("Upload external readiness packet")
    fail_index = step_names.index("Fail on local release readiness errors")
    upload_step = steps[upload_index]

    assert readiness_index < build_index < summary_index < upload_index < fail_index
    assert "build_mobile_external_readiness_packet.py" in steps[build_index]["run"]
    assert "--readiness-json /tmp/mobile-release-readiness.json" in steps[build_index]["run"]
    assert "--output /tmp/mobile-external-readiness-packet.json" in steps[build_index]["run"]
    assert "mobile-external-readiness-packet.json" in steps[summary_index]["run"]
    assert upload_step["with"]["name"] == "mobile-external-readiness-packet"
    assert "/tmp/mobile-external-readiness-packet.json" in upload_step["with"]["path"]
    assert "/tmp/mobile-external-readiness-packet.md" in upload_step["with"]["path"]


def test_mobile_build_workflow_uploads_dependency_review_before_validation() -> None:
    payload = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = payload["jobs"]["preflight"]["steps"]
    step_names = [step.get("name") for step in steps]

    build_index = step_names.index("Build dependency review report")
    upload_index = step_names.index("Upload dependency review")
    fail_index = step_names.index("Fail on dependency review errors")
    validate_index = step_names.index("Validate Expo project")
    upload_step = steps[upload_index]

    assert build_index < upload_index < fail_index < validate_index
    assert "npm audit --omit=dev --json" in steps[build_index]["run"]
    assert "build_mobile_dependency_review.py" in steps[build_index]["run"]
    assert "mobile-dependency-review-exit-code" in steps[build_index]["run"]
    assert upload_step["with"]["name"] == "mobile-dependency-review"
    assert "/tmp/mobile-dependency-review.json" in upload_step["with"]["path"]
    assert "mobile-dependency-review artifact" in steps[fail_index]["run"]


def test_mobile_build_workflow_uploads_smoke_template_validation_before_failure() -> None:
    payload = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = payload["jobs"]["preflight"]["steps"]
    step_names = [step.get("name") for step in steps]

    build_index = step_names.index("Build smoke template validation artifact")
    summary_index = step_names.index("Publish smoke template validation summary")
    notes_index = step_names.index("Build release notes artifact")
    upload_index = step_names.index("Upload smoke template validation")
    smoke_fail_index = step_names.index("Fail on smoke template validation errors")
    readiness_fail_index = step_names.index("Fail on local release readiness errors")
    upload_step = steps[upload_index]

    assert build_index < summary_index < notes_index < upload_index
    assert upload_index < smoke_fail_index < readiness_fail_index
    assert "cp ../../docs/mobile-device-smoke-log-template-v0.1.json" in steps[build_index][
        "run"
    ]
    assert "validate_mobile_device_smoke_log.py" in steps[build_index]["run"]
    assert "/tmp/mobile-device-smoke-log-template-v0.1.json" in steps[build_index]["run"]
    assert "mobile-device-smoke-template-summary.json" in steps[build_index]["run"]
    assert "mobile-device-smoke-template-summary.json" in steps[summary_index]["run"]
    assert upload_step["with"]["name"] == "mobile-device-smoke-template-validation"
    assert "/tmp/mobile-device-smoke-log-template-v0.1.json" in upload_step["with"]["path"]
    assert "/tmp/mobile-device-smoke-template-summary.json" in upload_step["with"]["path"]
    assert "mobile-device-smoke-template-validation artifact" in steps[smoke_fail_index]["run"]


def test_mobile_build_workflow_embeds_readiness_summary_in_release_manifest() -> None:
    payload = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = payload["jobs"]["preflight"]["steps"]
    manifest_step = next(step for step in steps if step.get("name") == "Build release manifest")

    assert "--readiness-json /tmp/mobile-release-readiness.json" in manifest_step["run"]
    assert "--release-notes /tmp/mobile-release-notes.md" in manifest_step["run"]


def test_mobile_build_workflow_traces_smoke_template_summary_digest() -> None:
    payload = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = payload["jobs"]["preflight"]["steps"]
    handoff_step = next(
        step for step in steps if step.get("name") == "Build store rollout handoff artifact"
    )
    verifier_step = next(
        step for step in steps if step.get("name") == "Verify release artifact bundle"
    )

    assert "mobile_device_smoke_template_summary_sha256" in handoff_step["run"]
    assert "mobile_dependency_review_sha256" in handoff_step["run"]
    assert "/tmp/mobile-dependency-review.json" in handoff_step["run"]
    assert "/tmp/mobile-device-smoke-template-summary.json" in handoff_step["run"]
    assert "--dependency-review-json /tmp/mobile-dependency-review.json" in verifier_step["run"]
    assert (
        "--smoke-template-summary-json /tmp/mobile-device-smoke-template-summary.json"
        in verifier_step["run"]
    )


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
    assert "mobile-device-smoke-template-validation" in steps[notes_index]["run"]
    assert "mobile-external-readiness-packet" in steps[notes_index]["run"]


def test_mobile_build_workflow_summary_reports_invalid_external_items() -> None:
    payload = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = payload["jobs"]["preflight"]["steps"]
    summary_step = next(
        step for step in steps if step.get("name") == "Publish release readiness summary"
    )

    assert 'item.get("status") == "invalid"' in summary_step["run"]
    assert "Invalid external items" in summary_step["run"]
