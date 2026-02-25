#!/usr/bin/env python3
"""validate_ios_capture_contract.py

Validates that each record's meta.json complies with the iOS Capture Contract (JSON Schema).

Why this matters:
- It converts a *developer assumption* ("we store the right fields") into an auditable, testable rule.
- It enables repeatable dataset releases (dataset_id) without silent schema drift.

Inputs:
- --dataset_root : dataset root folder with records/<record_id>/
- --manifest     : CSV/XLSX with column record_id
- --schema       : optional path to JSON schema. Default:
                  <Submission_Build>/02_Algorithm_and_ML/ios_capture_contract_schema_v1.0.json

Behavior:
- Loads meta.json for each record.
- If privacy_live_guardrails is missing from meta.json but privacy_live_guardrails.json exists,
  injects it into the effective metadata before schema validation.
- Produces record-level results and a summary.

Outputs (under dataset_root):
- outputs/ios_capture_contract/ios_capture_contract_validation.csv
- outputs/ios_capture_contract/ios_capture_contract_summary.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

try:
    from jsonschema import Draft7Validator
except Exception:  # pragma: no cover
    Draft7Validator = None  # type: ignore


def load_manifest(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)
    if "record_id" not in df.columns:
        raise ValueError("Manifest must contain column 'record_id'.")
    df["record_id"] = df["record_id"].astype(str)
    return df


def read_json(p: Path) -> Optional[Dict[str, Any]]:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def effective_meta(record_dir: Path) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Returns (effective_meta, notes)."""
    notes: List[str] = []
    meta_path = record_dir / "meta.json"
    meta = read_json(meta_path)
    if meta is None or not isinstance(meta, dict):
        return None, ["META_MISSING_OR_INVALID"]
    # inject privacy_live_guardrails if separate file exists
    if "privacy_live_guardrails" not in meta:
        plg = read_json(record_dir / "privacy_live_guardrails.json")
        if isinstance(plg, dict):
            meta["privacy_live_guardrails"] = plg
            notes.append("INJECTED_PRIVACY_LIVE_GUARDRAILS")
    return meta, notes


def validate_one(meta: Dict[str, Any], validator: Draft7Validator) -> List[str]:
    errs = []
    for e in sorted(validator.iter_errors(meta), key=lambda x: list(x.path)):
        loc = ".".join([str(p) for p in e.path]) if e.path else "<root>"
        msg = f"{loc}: {e.message}"
        errs.append(msg)
    return errs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset_root", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--schema", default=None)
    ap.add_argument("--out_dir", default=None)
    args = ap.parse_args()

    if Draft7Validator is None:
        raise RuntimeError("jsonschema is not available. Install 'jsonschema' or use requirements_full.txt")

    dataset_root = Path(args.dataset_root)
    manifest = Path(args.manifest)

    build_root = Path(__file__).resolve().parents[2]
    automation_root = Path(__file__).resolve().parents[1]
    if args.schema:
        schema_path = Path(args.schema)
    else:
        bundled_schema = automation_root / "schemas" / "ios_capture_contract_schema_v1.0.json"
        submission_layout_schema = (
            build_root / "02_Algorithm_and_ML" / "ios_capture_contract_schema_v1.0.json"
        )
        schema_path = bundled_schema if bundled_schema.exists() else submission_layout_schema
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft7Validator(schema)

    out_dir = Path(args.out_dir) if args.out_dir else (dataset_root / "outputs/ios_capture_contract")
    out_dir.mkdir(parents=True, exist_ok=True)

    dfm = load_manifest(manifest)

    rows: List[Dict[str, Any]] = []
    for rid in dfm["record_id"].tolist():
        rdir = dataset_root / "records" / rid
        meta, notes = effective_meta(rdir)
        if meta is None:
            rows.append({
                "record_id": rid,
                "result": "MISSING",
                "error_count": 1,
                "errors": ";".join(notes)[:500],
                "notes": ""
            })
            continue
        errs = validate_one(meta, validator)
        rows.append({
            "record_id": rid,
            "result": "PASS" if len(errs) == 0 else "FAIL",
            "error_count": int(len(errs)),
            "errors": " | ".join(errs)[:1500],
            "notes": ";".join(notes)
        })

    out_df = pd.DataFrame(rows)
    out_csv = out_dir / "ios_capture_contract_validation.csv"
    out_df.to_csv(out_csv, index=False)

    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "schema_path": str(schema_path),
        "records_total": int(len(out_df)),
        "pass": int((out_df["result"] == "PASS").sum()),
        "fail": int((out_df["result"] == "FAIL").sum()),
        "missing": int((out_df["result"] == "MISSING").sum()),
        "overall_pass": bool((out_df["result"] != "PASS").sum() == 0),
    }
    (out_dir / "ios_capture_contract_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"[OK] Wrote: {out_csv}")
    print(f"[OK] overall_pass={summary['overall_pass']}") 


if __name__ == "__main__":
    main()
