#!/usr/bin/env python3
"""run_coverage_dashboard.py (v1.0)

Generates a coverage dashboard for the synchronous golden dataset.

Inputs:
- --dataset_root : dataset root containing records/ and outputs/
- --manifest     : CSV/XLSX manifest
- --targets      : JSON file with coverage targets

Outputs:
- outputs/coverage_dashboard/coverage_dashboard.xlsx
- outputs/coverage_dashboard/coverage_summary.json

Design notes:
- Targets are intentionally simple and auditable.
- The script normalizes common values (sex, posture) to reduce site-specific variation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

import pandas as pd


def load_manifest(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)
    if "record_id" not in df.columns:
        raise ValueError("Manifest must contain record_id")
    df["record_id"] = df["record_id"].astype(str)
    return df


def norm_sex(x: Any) -> str:
    if x is None:
        return "UNK"
    s = str(x).strip().lower()
    if s in ("m", "male", "man", "м", "муж", "мужчина"):
        return "M"
    if s in ("f", "female", "woman", "ж", "жен", "женщина"):
        return "F"
    return "UNK"


def norm_posture(x: Any) -> str:
    if x is None:
        return "UNK"
    s = str(x).strip().lower()
    if s in ("standing", "stand", "стоя", "сто", "st"):
        return "standing"
    if s in ("sitting", "sit", "сидя", "сид", "si"):
        return "sitting"
    return "UNK"


def compute_coverage(df: pd.DataFrame, targets: Dict[str, Any]) -> Dict[str, Any]:
    required_cols = targets.get("required_columns", [])
    missing_cols = [c for c in required_cols if c not in df.columns]

    df2 = df.copy()
    if "sex" in df2.columns:
        df2["sex_norm"] = df2["sex"].apply(norm_sex)
    else:
        df2["sex_norm"] = "UNK"

    if "posture" in df2.columns:
        df2["posture_norm"] = df2["posture"].apply(norm_posture)
    else:
        df2["posture_norm"] = "UNK"

    df2["sex_posture"] = df2["sex_norm"] + "|" + df2["posture_norm"]

    total_n = int(len(df2))

    by_sex = df2["sex_norm"].value_counts(dropna=False).to_dict()
    by_sex_posture = df2["sex_posture"].value_counts(dropna=False).to_dict()

    by_site = df2["site_id"].astype(str).value_counts(dropna=False).to_dict() if "site_id" in df2.columns else {}
    by_toilet = df2["toilet_id"].astype(str).value_counts(dropna=False).to_dict() if "toilet_id" in df2.columns else {}

    checks = []

    # total
    min_total = int(targets.get("min_total_records", 0))
    checks.append({
        "check": "min_total_records",
        "target": min_total,
        "actual": total_n,
        "pass": total_n >= min_total
    })

    # by sex
    for k, v in (targets.get("min_by_sex") or {}).items():
        actual = int(by_sex.get(k, 0))
        checks.append({
            "check": f"min_by_sex:{k}",
            "target": int(v),
            "actual": actual,
            "pass": actual >= int(v)
        })

    # by sex|posture
    for k, v in (targets.get("min_by_sex_posture") or {}).items():
        actual = int(by_sex_posture.get(k, 0))
        checks.append({
            "check": f"min_by_sex_posture:{k}",
            "target": int(v),
            "actual": actual,
            "pass": actual >= int(v)
        })

    # sites
    min_sites = int(targets.get("min_sites", 0))
    actual_sites = int(len([k for k in by_site.keys() if k and k != "nan"]))
    checks.append({
        "check": "min_sites",
        "target": min_sites,
        "actual": actual_sites,
        "pass": actual_sites >= min_sites
    })

    # per-site min
    min_per_site = int(targets.get("min_records_per_site", 0))
    if min_per_site > 0 and by_site:
        site_fails = {k: int(v) for k, v in by_site.items() if int(v) < min_per_site}
        checks.append({
            "check": "min_records_per_site",
            "target": min_per_site,
            "actual": {"min_site_n": int(min(by_site.values())) if by_site else 0, "fail_sites": site_fails},
            "pass": len(site_fails) == 0
        })

    # per-toilet min
    min_per_toilet = int(targets.get("min_records_per_toilet", 0))
    if min_per_toilet > 0 and by_toilet:
        toilet_fails = {k: int(v) for k, v in by_toilet.items() if int(v) < min_per_toilet}
        checks.append({
            "check": "min_records_per_toilet",
            "target": min_per_toilet,
            "actual": {"min_toilet_n": int(min(by_toilet.values())) if by_toilet else 0, "fail_toilets": toilet_fails},
            "pass": len(toilet_fails) == 0
        })

    overall_pass = (len(missing_cols) == 0) and all(bool(c["pass"]) for c in checks)

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "overall_pass": bool(overall_pass),
        "missing_required_columns": missing_cols,
        "total_records": total_n,
        "by_sex": by_sex,
        "by_sex_posture": by_sex_posture,
        "by_site": by_site,
        "by_toilet": by_toilet,
        "checks": checks,
        "targets": targets
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset_root", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--targets", default="config/coverage_targets_config.json")
    args = ap.parse_args()

    dataset_root = Path(args.dataset_root)
    manifest = Path(args.manifest)
    targets_path = Path(args.targets)
    if not targets_path.is_absolute():
        if not targets_path.exists():
            automation_root = Path(__file__).resolve().parents[1]
            local_candidate = automation_root / targets_path
            if local_candidate.exists():
                targets_path = local_candidate

    targets = json.loads(targets_path.read_text(encoding="utf-8"))
    df = load_manifest(manifest)

    out_dir = dataset_root / "outputs/coverage_dashboard"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = compute_coverage(df, targets)
    (out_dir / "coverage_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Build Excel dashboard
    xlsx_path = out_dir / "coverage_dashboard.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        pd.DataFrame([{k: summary.get(k) for k in ["generated_at","overall_pass","total_records"]}]).to_excel(writer, index=False, sheet_name="Overview")
        pd.DataFrame(summary.get("checks", [])).to_excel(writer, index=False, sheet_name="Checks")
        pd.DataFrame(list(summary.get("by_sex", {}).items()), columns=["sex","n"]).to_excel(writer, index=False, sheet_name="BySex")
        pd.DataFrame(list(summary.get("by_sex_posture", {}).items()), columns=["sex_posture","n"]).to_excel(writer, index=False, sheet_name="BySexPosture")
        pd.DataFrame(list(summary.get("by_site", {}).items()), columns=["site_id","n"]).to_excel(writer, index=False, sheet_name="BySite")
        pd.DataFrame(list(summary.get("by_toilet", {}).items()), columns=["toilet_id","n"]).to_excel(writer, index=False, sheet_name="ByToilet")

    print(f"[OK] Wrote: {xlsx_path}")
    print(f"[OK] Wrote: {out_dir / 'coverage_summary.json'}")
    print(f"[OK] OVERALL: {'PASS' if summary['overall_pass'] else 'FAIL'}")


if __name__ == "__main__":
    main()
