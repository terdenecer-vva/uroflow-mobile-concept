from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


def _write_record(record_dir: Path) -> None:
    record_dir.mkdir(parents=True, exist_ok=True)
    (record_dir / "meta.json").write_text(
        json.dumps({"record_id": record_dir.name}),
        encoding="utf-8",
    )
    (record_dir / "app_result.json").write_text(
        json.dumps({"status": "ok"}),
        encoding="utf-8",
    )
    (record_dir / "quality.json").write_text(
        json.dumps({"quality_score": 85}),
        encoding="utf-8",
    )

    with (record_dir / "Q_pred.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["t_s", "Q_ml_s"])
        writer.writerow([0, 0.0])
        writer.writerow([1, 5.0])
        writer.writerow([2, 0.0])

    with (record_dir / "Q_ref.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["t_s", "Q_ml_s"])
        writer.writerow([0, 0.0])
        writer.writerow([1, 5.5])
        writer.writerow([2, 0.0])


def test_artifact_profile_validator_uses_default_profile_when_manifest_profile_missing(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = (
        repo_root
        / "scripts/pilot_automation_v2_8/scripts/validate_artifacts_by_profile.py"
    )
    config_path = (
        repo_root
        / "scripts/pilot_automation_v2_8/config/data_artifact_profile_config.json"
    )

    dataset_root = tmp_path / "dataset"
    records_root = dataset_root / "records"
    record_id = "REC-001"
    _write_record(records_root / record_id)

    # profile_id column is intentionally absent: validator must fallback to default_profile (P0).
    manifest_path = dataset_root / "manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["record_id"])
        writer.writeheader()
        writer.writerow({"record_id": record_id})

    out_dir = tmp_path / "validator_out"
    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--dataset_root",
            str(dataset_root),
            "--manifest",
            str(manifest_path),
            "--use_manifest_profile",
            "--config",
            str(config_path),
            "--out_dir",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    report = json.loads((out_dir / "artifact_profile_validation.json").read_text("utf-8"))
    assert report["summary"]["any_missing"] is False
    assert report["summary"]["any_forbidden"] is False
    assert report["results"][0]["profile_id"] == "P0"
    assert report["results"][0]["status"] == "PASS"


def test_artifact_profile_validator_fails_when_forbidden_artifact_present(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = (
        repo_root
        / "scripts/pilot_automation_v2_8/scripts/validate_artifacts_by_profile.py"
    )
    config_path = (
        repo_root
        / "scripts/pilot_automation_v2_8/config/data_artifact_profile_config.json"
    )

    dataset_root = tmp_path / "dataset"
    records_root = dataset_root / "records"
    record_id = "REC-002"
    record_dir = records_root / record_id
    _write_record(record_dir)
    (record_dir / "audio.wav").write_bytes(b"RIFF")

    manifest_path = dataset_root / "manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["record_id", "profile_id"])
        writer.writeheader()
        writer.writerow({"record_id": record_id, "profile_id": "P0"})

    out_dir = tmp_path / "validator_out"
    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--dataset_root",
            str(dataset_root),
            "--manifest",
            str(manifest_path),
            "--profile",
            "P0",
            "--config",
            str(config_path),
            "--out_dir",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    report = json.loads((out_dir / "artifact_profile_validation.json").read_text("utf-8"))
    assert report["summary"]["any_forbidden"] is True
    assert report["results"][0]["status"] in {"FAIL_FORBIDDEN", "FAIL_MISSING+FORBIDDEN"}

