from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/build_mobile_dependency_review.py")


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _valid_inputs(tmp_path: Path) -> dict[str, Path]:
    package = {
        "name": "uroflow-field-mobile",
        "version": "0.1.0",
        "engines": {"node": ">=22.13.0"},
        "dependencies": {
            "expo-camera": "~56.0.7",
            "react": "19.2.3",
        },
        "devDependencies": {
            "typescript": "~6.0.3",
        },
    }
    lock = {
        "lockfileVersion": 3,
        "packages": {
            "": {
                "name": "uroflow-field-mobile",
                "version": "0.1.0",
                "dependencies": package["dependencies"],
                "devDependencies": package["devDependencies"],
            },
            "node_modules/expo-camera": {
                "version": "56.0.7",
                "resolved": "https://registry.npmjs.org/expo-camera/-/expo-camera-56.0.7.tgz",
                "integrity": "sha512-camera",
            },
            "node_modules/react": {
                "version": "19.2.3",
                "resolved": "https://registry.npmjs.org/react/-/react-19.2.3.tgz",
                "integrity": "sha512-react",
            },
            "node_modules/typescript": {
                "version": "6.0.3",
                "resolved": "https://registry.npmjs.org/typescript/-/typescript-6.0.3.tgz",
                "integrity": "sha512-typescript",
            },
        },
    }
    audit = {
        "auditReportVersion": 2,
        "vulnerabilities": {},
        "metadata": {
            "vulnerabilities": {
                "info": 0,
                "low": 0,
                "moderate": 0,
                "high": 0,
                "critical": 0,
                "total": 0,
            },
            "dependencies": {"prod": 2, "dev": 1, "total": 3},
        },
    }
    paths = {
        "package": tmp_path / "package.json",
        "lock": tmp_path / "package-lock.json",
        "audit": tmp_path / "audit.json",
        "output": tmp_path / "mobile-dependency-review.json",
    }
    _write_json(paths["package"], package)
    _write_json(paths["lock"], lock)
    _write_json(paths["audit"], audit)
    return paths


def _run_review(paths: dict[str, Path], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--package-json",
            str(paths["package"]),
            "--package-lock",
            str(paths["lock"]),
            "--audit-json",
            str(paths["audit"]),
            "--output",
            str(paths["output"]),
        ],
        check=check,
        text=True,
        capture_output=True,
    )


def test_mobile_dependency_review_accepts_locked_zero_vulnerability_package(
    tmp_path: Path,
) -> None:
    paths = _valid_inputs(tmp_path)

    result = _run_review(paths)
    payload = json.loads(result.stdout)

    assert payload["schema_version"] == "mobile_dependency_review_v0.1"
    assert payload["status"] == "pass"
    assert payload["risk_traceability"]["risk_id"] == "SEC-003"
    assert payload["audit"]["vulnerabilities"]["total"] == 0
    assert {check["status"] for check in payload["checks"]} == {"pass"}
    assert payload["native_sensitive_dependency_surface"] == [
        {
            "name": "expo-camera",
            "surfaces": ["camera"],
            "release_controls": ["camera permission text", "ROI-only derived features"],
        }
    ]
    assert json.loads(paths["output"].read_text(encoding="utf-8")) == payload


def test_mobile_dependency_review_rejects_missing_direct_lock_entry(
    tmp_path: Path,
) -> None:
    paths = _valid_inputs(tmp_path)
    lock = json.loads(paths["lock"].read_text(encoding="utf-8"))
    del lock["packages"]["node_modules/expo-camera"]
    _write_json(paths["lock"], lock)

    result = _run_review(paths, check=False)
    payload = json.loads(result.stdout)

    assert result.returncode == 1
    assert payload["status"] == "fail"
    check = next(
        item for item in payload["checks"] if item["id"] == "direct_dependencies_locked"
    )
    assert check["status"] == "fail"
    assert "expo-camera:missing_node_modules_entry" in check["evidence"]


def test_mobile_dependency_review_rejects_production_audit_vulnerabilities(
    tmp_path: Path,
) -> None:
    paths = _valid_inputs(tmp_path)
    audit = json.loads(paths["audit"].read_text(encoding="utf-8"))
    audit["vulnerabilities"] = {"expo-camera": {"severity": "high"}}
    audit["metadata"]["vulnerabilities"]["high"] = 1
    audit["metadata"]["vulnerabilities"]["total"] = 1
    _write_json(paths["audit"], audit)

    result = _run_review(paths, check=False)
    payload = json.loads(result.stdout)

    assert result.returncode == 1
    assert payload["status"] == "fail"
    assert payload["audit"]["vulnerabilities"]["high"] == 1
    assert payload["audit"]["vulnerable_packages"] == ["expo-camera"]
    assert "remediate_mobile_prod_vulnerabilities" in {
        item["id"] for item in payload["remediation"]
    }


def test_mobile_dependency_review_rejects_unreviewed_native_dependency(
    tmp_path: Path,
) -> None:
    paths = _valid_inputs(tmp_path)
    package = json.loads(paths["package"].read_text(encoding="utf-8"))
    package["dependencies"]["expo-unknown-native"] = "1.0.0"
    _write_json(paths["package"], package)

    lock = json.loads(paths["lock"].read_text(encoding="utf-8"))
    lock["packages"][""]["dependencies"] = package["dependencies"]
    lock["packages"]["node_modules/expo-unknown-native"] = {
        "version": "1.0.0",
        "resolved": "https://registry.npmjs.org/expo-unknown-native/-/expo-unknown-native-1.0.0.tgz",
        "integrity": "sha512-unknown",
    }
    _write_json(paths["lock"], lock)

    result = _run_review(paths, check=False)
    payload = json.loads(result.stdout)

    assert result.returncode == 1
    assert payload["status"] == "fail"
    check = next(
        item
        for item in payload["checks"]
        if item["id"] == "native_sensitive_dependency_surface_reviewed"
    )
    assert check["status"] == "fail"
    assert "expo-unknown-native" in check["evidence"]
