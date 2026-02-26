#!/usr/bin/env python3
"""
Validate manifest against expected columns, required fields and codelists.

Usage:
    python validate_manifest.py --manifest manifest.csv --config ../config/qa_config.json --out outputs
"""

from __future__ import annotations
import argparse
from pathlib import Path

from uroflow_qa_utils import load_json, save_json, load_manifest, validate_manifest_rows

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="outputs")
    args = ap.parse_args()

    manifest_path = Path(args.manifest).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    config = load_json(config_path)
    rows = load_manifest(manifest_path)
    _, issues = validate_manifest_rows(rows, config)
    save_json({"issue_count": len(issues)}, out_dir / "manifest_validation_summary.json")

    # write issues as CSV
    import csv
    if issues:
        with open(out_dir / "manifest_validation_issues.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(issues[0].keys()))
            w.writeheader()
            for r in issues:
                w.writerow(r)
    else:
        (out_dir / "manifest_validation_issues.csv").write_text("", encoding="utf-8")

    print(f"[OK] Issues: {len(issues)}. Output: {out_dir}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
