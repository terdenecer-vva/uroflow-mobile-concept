#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "mobile_external_readiness_packet_v0.1"

SECRET_COMMANDS = {
    "EXPO_TOKEN": 'gh secret set EXPO_TOKEN --body "<expo_access_token>"',
    "CLINICAL_HUB_URL": 'gh secret set CLINICAL_HUB_URL --body "https://<clinical-hub>"',
    "CLINICAL_HUB_API_KEY": 'gh secret set CLINICAL_HUB_API_KEY --body "<api_key>"',
    "GOOGLE_SERVICE_ACCOUNT": (
        'eas secret:create --name GOOGLE_SERVICE_ACCOUNT '
        '--value "$(cat /secure/path/google-service-account.json)" --type file'
    ),
}
VARIABLE_COMMANDS = {
    "EAS_PROJECT_ID": 'gh variable set EAS_PROJECT_ID --body "<eas_project_uuid>"',
}
SECRET_LIKE_RE = re.compile(
    r"(?i)(token|api[_-]?key|secret|service[_-]?account|password)\s*[=:]\s*[^,\s]+"
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _redact_text(value: Any) -> str:
    text = "" if value is None else str(value)
    return SECRET_LIKE_RE.sub(lambda match: match.group(0).split("=", 1)[0] + "=<redacted>", text)


def _sanitize_item(item: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for field in fields:
        if field in item:
            sanitized[field] = _redact_text(item.get(field))
    return sanitized


def _string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if isinstance(value, str) and value.strip()]


def _action_commands(action: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    for secret_name in _string_list(action.get("secret_names")):
        command = SECRET_COMMANDS.get(secret_name)
        if command:
            commands.append(command)
    for variable_name in _string_list(action.get("variable_names")):
        command = VARIABLE_COMMANDS.get(variable_name)
        if command:
            commands.append(command)
    return commands


def _sanitize_action(action: dict[str, Any]) -> dict[str, Any]:
    sanitized = _sanitize_item(
        action,
        (
            "id",
            "blocked_item",
            "status",
            "owner",
            "action",
            "verification",
            "doc",
        ),
    )
    sanitized["secret_names"] = _string_list(action.get("secret_names"))
    sanitized["variable_names"] = _string_list(action.get("variable_names"))
    sanitized["file_paths"] = _string_list(action.get("file_paths"))
    sanitized["commands"] = _action_commands(action)
    return sanitized


def _dedupe_sorted(values: list[str]) -> list[str]:
    return sorted(set(values))


def _packet_status(readiness: dict[str, Any], required_actions: list[dict[str, Any]]) -> str:
    if readiness.get("local_checks_status") != "pass":
        return "not_ready"
    if required_actions:
        return "blocked_external"
    if readiness.get("external_readiness_status") == "pass":
        return "ready"
    return "blocked_external"


def build_external_readiness_packet(readiness: dict[str, Any]) -> dict[str, Any]:
    external_items = [
        _sanitize_item(item, ("id", "status", "required_for", "evidence"))
        for item in readiness.get("external_items", [])
        if isinstance(item, dict)
    ]
    manual_external_items = [
        _sanitize_item(item, ("id", "status", "required_for"))
        for item in readiness.get("manual_external_items", [])
        if isinstance(item, dict)
    ]
    required_actions = [
        _sanitize_action(action)
        for action in readiness.get("next_actions", [])
        if isinstance(action, dict)
        and action.get("status") in {"required", "manual_required"}
    ]

    secret_names = _dedupe_sorted(
        [
            name
            for action in required_actions
            for name in _string_list(action.get("secret_names"))
        ]
    )
    variable_names = _dedupe_sorted(
        [
            name
            for action in required_actions
            for name in _string_list(action.get("variable_names"))
        ]
    )
    file_paths = _dedupe_sorted(
        [
            path
            for action in required_actions
            for path in _string_list(action.get("file_paths"))
        ]
    )
    docs = _dedupe_sorted(
        [
            str(action.get("doc"))
            for action in required_actions
            if isinstance(action.get("doc"), str) and action.get("doc")
        ]
    )

    packet = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": _packet_status(readiness, required_actions),
        "traceability": readiness.get("traceability", {}),
        "readiness_status": readiness.get("status"),
        "local_checks_status": readiness.get("local_checks_status"),
        "external_readiness_status": readiness.get("external_readiness_status"),
        "authenticated_eas_status": readiness.get("authenticated_eas_status"),
        "authenticated_eas_blockers": _string_list(
            readiness.get("authenticated_eas_blockers")
        ),
        "clinical_hub_live_api_status": readiness.get("clinical_hub_live_api_status"),
        "summary": {
            "external_item_count": len(external_items),
            "manual_external_item_count": len(manual_external_items),
            "required_action_count": len(required_actions),
            "secret_names": secret_names,
            "variable_names": variable_names,
            "file_paths": file_paths,
            "docs": docs,
        },
        "external_items": external_items,
        "manual_external_items": manual_external_items,
        "required_actions": required_actions,
        "rerun_verification": {
            "workflow": "Mobile Build",
            "expected_ready_status": "ready",
            "expected_blocked_status": "blocked_external",
            "evidence_artifacts": [
                "mobile-release-readiness",
                "mobile-external-readiness-packet",
                "mobile-release-bundle-verification",
                "mobile-store-rollout-handoff",
            ],
        },
    }
    return packet


def render_markdown(packet: dict[str, Any]) -> str:
    summary = packet.get("summary", {})
    lines = [
        "# Mobile External Readiness Packet",
        "",
        f"- Status: `{packet.get('status')}`",
        f"- Readiness status: `{packet.get('readiness_status')}`",
        f"- External readiness: `{packet.get('external_readiness_status')}`",
        f"- Authenticated EAS: `{packet.get('authenticated_eas_status')}`",
        f"- Clinical Hub live API: `{packet.get('clinical_hub_live_api_status')}`",
        f"- Required actions: `{summary.get('required_action_count', 0)}`",
        "",
        "## Required Secrets And Variables",
        "",
        f"- Secrets: `{', '.join(summary.get('secret_names', [])) or 'none'}`",
        f"- Variables: `{', '.join(summary.get('variable_names', [])) or 'none'}`",
        f"- Files: `{', '.join(summary.get('file_paths', [])) or 'none'}`",
        "",
        "## Action Checklist",
        "",
    ]
    for action in packet.get("required_actions", []):
        lines.append(f"### {action.get('id')}")
        lines.append("")
        lines.append(f"- Owner: `{action.get('owner')}`")
        lines.append(f"- Blocked item: `{action.get('blocked_item')}`")
        lines.append(f"- Action: {action.get('action')}")
        lines.append(f"- Verification: {action.get('verification')}")
        commands = action.get("commands", [])
        if commands:
            lines.append("- Placeholder commands:")
            for command in commands:
                lines.append(f"  - `{command}`")
        lines.append("")
    lines.extend(
        [
            "## Verification",
            "",
            "- Re-run `Mobile Build` after provisioning.",
            (
                "- Confirm `mobile-release-readiness` no longer reports missing/invalid "
                "external items."
            ),
            "- Archive `mobile-external-readiness-packet` with the release handoff.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a sanitized mobile external readiness handoff packet."
    )
    parser.add_argument("--readiness-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    readiness = _load_json(args.readiness_json)
    packet = build_external_readiness_packet(readiness)
    args.output.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.write_text(render_markdown(packet), encoding="utf-8")
    print(json.dumps(packet, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
