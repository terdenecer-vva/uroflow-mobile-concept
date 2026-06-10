from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/build_mobile_external_readiness_packet.py")


def _blocked_readiness() -> dict:
    return {
        "status": "ready_except_external_credentials",
        "local_checks_status": "pass",
        "external_readiness_status": "blocked",
        "authenticated_eas_status": "blocked",
        "authenticated_eas_blockers": ["expo_token", "eas_project_identity"],
        "clinical_hub_live_api_status": "missing",
        "traceability": {
            "git_sha": "abc123",
            "git_ref": "refs/heads/main",
            "git_run_id": "42",
            "workflow": "Mobile Build",
        },
        "external_items": [
            {
                "id": "expo_token",
                "status": "missing",
                "required_for": "Authenticated EAS build trigger.",
                "evidence": "EXPO_TOKEN environment variable is not set",
            },
            {
                "id": "clinical_hub_live_api",
                "status": "missing",
                "required_for": "Live Clinical Hub smoke tests.",
                "evidence": "CLINICAL_HUB_API_KEY=super-secret-value",
            },
        ],
        "manual_external_items": [
            {
                "id": "apple_developer_account",
                "status": "manual_required",
                "required_for": "Signed iOS build and TestFlight distribution.",
            },
        ],
        "next_actions": [
            {
                "id": "configure_expo_token",
                "blocked_item": "expo_token",
                "status": "required",
                "owner": "release_engineer",
                "action": "Create an Expo access token.",
                "verification": "Re-run Mobile Build.",
                "secret_names": ["EXPO_TOKEN"],
                "variable_names": [],
                "file_paths": [],
                "doc": "docs/mobile-release-runbook-v0.1.md",
            },
            {
                "id": "configure_clinical_hub_live_api",
                "blocked_item": "clinical_hub_live_api",
                "status": "required",
                "owner": "clinical_hub_admin",
                "action": "Add Clinical Hub URL and API key.",
                "verification": "Re-run Mobile Build.",
                "secret_names": ["CLINICAL_HUB_URL", "CLINICAL_HUB_API_KEY"],
                "variable_names": [],
                "file_paths": [],
                "doc": "docs/mobile-release-runbook-v0.1.md",
            },
            {
                "id": "configure_eas_project_identity",
                "blocked_item": "eas_project_identity",
                "status": "required",
                "owner": "release_engineer",
                "action": "Set the EAS project identity.",
                "verification": "Re-run Mobile Build.",
                "secret_names": [],
                "variable_names": ["EAS_PROJECT_ID"],
                "file_paths": ["apps/field-mobile/app.json"],
                "doc": "docs/mobile-release-runbook-v0.1.md",
            },
            {
                "id": "provision_apple_developer_account",
                "blocked_item": "apple_developer_account",
                "status": "manual_required",
                "owner": "account_admin",
                "action": "Provision Apple Developer access.",
                "verification": "Trigger a signed iOS EAS build.",
                "secret_names": [],
                "variable_names": [],
                "file_paths": [],
                "doc": "docs/mobile-release-runbook-v0.1.md",
            },
        ],
    }


def _run_packet(tmp_path: Path, readiness: dict) -> dict:
    readiness_path = tmp_path / "readiness.json"
    output_path = tmp_path / "packet.json"
    markdown_path = tmp_path / "packet.md"
    readiness_path.write_text(json.dumps(readiness), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--readiness-json",
            str(readiness_path),
            "--output",
            str(output_path),
            "--markdown-output",
            str(markdown_path),
        ],
        check=True,
    )
    packet = json.loads(output_path.read_text(encoding="utf-8"))
    packet["_markdown"] = markdown_path.read_text(encoding="utf-8")
    return packet


def test_mobile_external_readiness_packet_sanitizes_blockers(tmp_path: Path) -> None:
    packet = _run_packet(tmp_path, _blocked_readiness())
    serialized = json.dumps(packet)

    assert packet["schema_version"] == "mobile_external_readiness_packet_v0.1"
    assert packet["status"] == "blocked_external"
    assert packet["traceability"]["git_sha"] == "abc123"
    assert packet["summary"]["required_action_count"] == 4
    assert packet["summary"]["secret_names"] == [
        "CLINICAL_HUB_API_KEY",
        "CLINICAL_HUB_URL",
        "EXPO_TOKEN",
    ]
    assert packet["summary"]["variable_names"] == ["EAS_PROJECT_ID"]
    assert packet["summary"]["file_paths"] == ["apps/field-mobile/app.json"]
    assert "super-secret-value" not in serialized
    assert "<expo_access_token>" in packet["_markdown"]
    assert "gh variable set EAS_PROJECT_ID" in packet["_markdown"]


def test_mobile_external_readiness_packet_marks_ready_without_actions(tmp_path: Path) -> None:
    readiness = _blocked_readiness()
    readiness["status"] = "ready"
    readiness["external_readiness_status"] = "pass"
    readiness["authenticated_eas_status"] = "pass"
    readiness["authenticated_eas_blockers"] = []
    readiness["clinical_hub_live_api_status"] = "present"
    readiness["external_items"] = [
        {"id": "expo_token", "status": "present", "required_for": "EAS"},
        {"id": "clinical_hub_live_api", "status": "present", "required_for": "Clinical Hub"},
    ]
    readiness["manual_external_items"] = []
    readiness["next_actions"] = []

    packet = _run_packet(tmp_path, readiness)

    assert packet["status"] == "ready"
    assert packet["summary"]["required_action_count"] == 0
    assert packet["summary"]["secret_names"] == []
    assert "Required actions: `0`" in packet["_markdown"]
