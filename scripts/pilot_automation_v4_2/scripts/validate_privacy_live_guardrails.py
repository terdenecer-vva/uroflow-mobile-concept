#!/usr/bin/env python3
"""
validate_privacy_live_guardrails.py

Validates LIVE (on-device) privacy guardrails metadata for each record in a golden dataset.

Expected per-record inputs (either):
- records/<record_id>/privacy_live_guardrails.json
OR
- records/<record_id>/meta.json containing key privacy_live_guardrails

The validator produces:
- outputs/privacy_live_guardrails/privacy_live_guardrails.csv
- outputs/privacy_live_guardrails/privacy_live_summary.json

Policy (default):
- PASS: precheck.pass == True AND during.pass == True
- FAIL: any of them is False
- MISSING: no metadata found

This script is intentionally conservative: if required fields are missing, result becomes FAIL.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple, List

import pandas as pd


REQUIRED_FIELDS = [
    ("precheck", "pass"),
    ("during", "pass"),
]


def load_manifest(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)
    if "record_id" not in df.columns:
        raise ValueError("Manifest must contain record_id column.")
    return df


def read_json(p: Path) -> Dict[str, Any] | None:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def extract_live_guardrails(record_dir: Path) -> Dict[str, Any] | None:
    # 1) dedicated json
    j1 = record_dir / "privacy_live_guardrails.json"
    obj = read_json(j1)
    if obj is not None:
        return obj

    # 2) embedded into meta.json
    j2 = record_dir / "meta.json"
    meta = read_json(j2)
    if meta is not None and isinstance(meta, dict):
        if "privacy_live_guardrails" in meta and isinstance(meta["privacy_live_guardrails"], dict):
            return meta["privacy_live_guardrails"]
    return None


def validate_obj(obj: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[str, str]:
    # check required fields
    for parent, child in REQUIRED_FIELDS:
        if parent not in obj or not isinstance(obj[parent], dict) or child not in obj[parent]:
            return "FAIL", f"MISSING_FIELD:{parent}.{child}"

    pre_pass = bool(obj.get("precheck", {}).get("pass", False))
    dur_pass = bool(obj.get("during", {}).get("pass", False))

    if not pre_pass:
        return "FAIL", "PRECHECK_FAIL"
    if not dur_pass:
        return "FAIL", "DURING_FAIL"

    # optional threshold checks if numeric fields present
    thr = cfg.get("thresholds", {})
    # skin
    max_skin = obj.get("during", {}).get("max_skin_fraction_border", None)
    if max_skin is not None:
        try:
            if float(max_skin) > float(thr.get("skin_fraction_border_max", 1.0)):
                return "FAIL", "SKIN_THRESHOLD"
        except Exception:
            pass
    # reflection
    max_refl = obj.get("during", {}).get("max_reflection_risk", None)
    if max_refl is not None:
        try:
            if float(max_refl) > float(thr.get("reflection_risk_max", 1.0)):
                return "FAIL", "REFLECTION_THRESHOLD"
        except Exception:
            pass

    return "PASS", ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset_root", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--config", default="config/privacy_live_guardrails_config.json")
    args = ap.parse_args()

    dataset_root = Path(args.dataset_root)
    manifest = Path(args.manifest)
    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        if not cfg_path.exists():
            automation_root = Path(__file__).resolve().parents[1]
            local_candidate = automation_root / cfg_path
            if local_candidate.exists():
                cfg_path = local_candidate
    cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}

    out_dir = dataset_root / cfg.get("outputs_dirname", "outputs/privacy_live_guardrails")
    out_dir.mkdir(parents=True, exist_ok=True)

    dfm = load_manifest(manifest)
    rows: List[Dict[str, Any]] = []

    for rid in dfm["record_id"].astype(str).tolist():
        rdir = dataset_root / "records" / rid
        obj = extract_live_guardrails(rdir)
        if obj is None:
            rows.append({"record_id": rid, "result": "MISSING", "reason": "NO_PRIVACY_LIVE_METADATA"})
            continue
        res, reason = validate_obj(obj, cfg)
        rows.append({"record_id": rid, "result": res, "reason": reason})

    out_df = pd.DataFrame(rows)
    out_csv = out_dir / "privacy_live_guardrails.csv"
    out_df.to_csv(out_csv, index=False)

    fail_n = int((out_df["result"] == "FAIL").sum())
    missing_n = int((out_df["result"] == "MISSING").sum())
    pass_n = int((out_df["result"] == "PASS").sum())
    total = int(len(out_df))

    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_records": total,
        "pass_count": pass_n,
        "fail_count": fail_n,
        "missing_count": missing_n,
        "overall_pass": (fail_n == 0 and missing_n == 0),
        "config": cfg,
    }
    (out_dir / "privacy_live_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"[OK] Wrote: {out_csv}")
    print(f"[OK] overall_pass={summary['overall_pass']} (fail={fail_n}, missing={missing_n})")


if __name__ == "__main__":
    main()
