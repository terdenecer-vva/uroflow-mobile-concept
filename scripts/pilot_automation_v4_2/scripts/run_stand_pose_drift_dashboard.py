#!/usr/bin/env python3
"""
run_stand_pose_drift_dashboard.py

Aggregates StandPose KPI by site/toilet/stand and flags drift.

Inputs:
- dataset_root
- manifest (CSV/XLSX), recommended columns: site_id, toilet_id, stand_id, iphone_model
- stand_pose_kpi.csv produced by compute_stand_pose_kpi.py (if absent, attempts to compute from per-record pose_timeseries.csv or meta.json)

Outputs:
- outputs/stand_pose_drift_dashboard/drift_dashboard.xlsx
- outputs/stand_pose_drift_dashboard/drift_summary.json
- outputs/stand_pose_drift_dashboard/drift_groups.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

import numpy as np
import pandas as pd


def load_manifest(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)
    if "record_id" not in df.columns:
        raise ValueError("Manifest must include record_id.")
    return df


def load_json(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


def compute_stand_pose_for_record(record_dir: Path) -> Optional[Dict[str, Any]]:
    """Fallback computation if stand_pose_kpi.csv not available."""
    meta_path = record_dir / "meta.json"
    if meta_path.exists():
        meta = load_json(meta_path)
        sp = meta.get("stand_pose_summary") or meta.get("stand_pose") or {}
        # Try common keys
        if sp:
            return {
                "distance_m_median": sp.get("distance_m_median"),
                "pitch_deg_median": sp.get("pitch_deg_median"),
                "yaw_deg_median": sp.get("yaw_deg_median"),
                "roll_deg_median": sp.get("roll_deg_median"),
                "jitter_deg": sp.get("jitter_deg"),
                "class": sp.get("class") or sp.get("stand_pose_class"),
            }

    ts_path = record_dir / "pose_timeseries.csv"
    if not ts_path.exists():
        return None

    try:
        ts = pd.read_csv(ts_path)
    except Exception:
        return None

    # Expect columns: distance_m, pitch_deg, yaw_deg, roll_deg
    needed = ["distance_m", "pitch_deg", "yaw_deg", "roll_deg"]
    if not all(c in ts.columns for c in needed):
        return None

    out = {
        "distance_m_median": float(ts["distance_m"].median()),
        "pitch_deg_median": float(ts["pitch_deg"].median()),
        "yaw_deg_median": float(ts["yaw_deg"].median()),
        "roll_deg_median": float(ts["roll_deg"].median()),
        "jitter_deg": float(np.sqrt(ts["pitch_deg"].var() + ts["yaw_deg"].var() + ts["roll_deg"].var())),
        "class": None,
    }
    return out


def classify(row: Dict[str, Any], cfg: Dict[str, Any]) -> str:
    dmin, dmax = cfg["distance_m_range"]
    pmin, pmax = cfg["pitch_deg_range"]
    yaw_max = cfg["yaw_deg_abs_max"]
    roll_max = cfg["roll_deg_abs_max"]
    jitter_max = cfg["jitter_deg_max"]

    d = row.get("distance_m_median")
    p = row.get("pitch_deg_median")
    y = row.get("yaw_deg_median")
    r = row.get("roll_deg_median")
    j = row.get("jitter_deg")

    # missing values -> borderline
    if any(v is None or (isinstance(v, float) and np.isnan(v)) for v in [d, p, y, r, j]):
        return "BORDERLINE"

    ok = (dmin <= d <= dmax) and (pmin <= p <= pmax) and (abs(y) <= yaw_max) and (abs(r) <= roll_max) and (j <= jitter_max)
    if ok:
        return "PASS"

    # borderline if slightly outside, else FAIL
    score = 0
    score += 1 if d < dmin or d > dmax else 0
    score += 1 if p < pmin or p > pmax else 0
    score += 1 if abs(y) > yaw_max else 0
    score += 1 if abs(r) > roll_max else 0
    score += 1 if j > jitter_max else 0
    return "FAIL" if score >= 2 else "BORDERLINE"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset_root", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--config", default="config/stand_pose_drift_config.json")
    ap.add_argument("--stand_pose_kpi", default=None, help="Optional path to stand_pose_kpi.csv. If omitted, will look in outputs/stand_pose_kpi/stand_pose_kpi.csv or compute fallback.")
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
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    out_dir = dataset_root / cfg.get("outputs_dirname", "outputs/stand_pose_drift_dashboard")
    out_dir.mkdir(parents=True, exist_ok=True)

    dfm = load_manifest(manifest)

    # Determine stand pose KPI source
    kpi_path = Path(args.stand_pose_kpi) if args.stand_pose_kpi else (dataset_root / "outputs/stand_pose_kpi/stand_pose_kpi.csv")
    kpi_df = None
    if kpi_path.exists():
        kpi_df = pd.read_csv(kpi_path)
        if "record_id" not in kpi_df.columns:
            kpi_df = None

    if kpi_df is None:
        # fallback compute
        rows: List[Dict[str, Any]] = []
        for _, r in dfm.iterrows():
            record_id = str(r["record_id"])
            rec_dir = dataset_root / "records" / record_id
            sp = compute_stand_pose_for_record(rec_dir)
            if sp is None:
                sp = {"distance_m_median": None, "pitch_deg_median": None, "yaw_deg_median": None, "roll_deg_median": None, "jitter_deg": None, "class": "BORDERLINE"}
            sp["record_id"] = record_id
            if sp.get("class") in [None, "", "nan"]:
                sp["class"] = classify(sp, cfg)
            rows.append(sp)
        kpi_df = pd.DataFrame(rows)
    else:
        # ensure class exists
        if "class" not in kpi_df.columns:
            kpi_df["class"] = kpi_df.apply(lambda rr: classify(rr.to_dict(), cfg), axis=1)

    # merge keys from manifest
    merge_cols = ["record_id"]
    merged = dfm.merge(kpi_df, on="record_id", how="left", suffixes=("", "_kpi"))

    # pick group keys if present
    group_keys = [k for k in ["site_id", "toilet_id", "stand_id", "iphone_model"] if k in merged.columns]
    if not group_keys:
        group_keys = ["toilet_id"] if "toilet_id" in merged.columns else ["record_id"]

    # group stats
    def pass_rate(s: pd.Series) -> float:
        return float((s == "PASS").mean())

    grouped = merged.groupby(group_keys).agg(
        n_records=("record_id", "count"),
        pass_rate=("class", pass_rate),
        borderline_rate=("class", lambda s: float((s == "BORDERLINE").mean())),
        fail_rate=("class", lambda s: float((s == "FAIL").mean())),
        distance_m_median=("distance_m_median", "median"),
        pitch_deg_median=("pitch_deg_median", "median"),
        yaw_deg_median=("yaw_deg_median", "median"),
        roll_deg_median=("roll_deg_median", "median"),
        jitter_deg_median=("jitter_deg", "median"),
    ).reset_index()

    # flags
    flags = []
    for _, row in grouped.iterrows():
        reasons = []
        if int(row["n_records"]) < int(cfg["min_records_per_group"]):
            reasons.append("LOW_N")
        if float(row["pass_rate"]) < float(cfg["min_pass_rate"]):
            reasons.append("LOW_PASS_RATE")
        dmin, dmax = cfg["distance_m_range"]
        if not (dmin <= float(row["distance_m_median"]) <= dmax):
            reasons.append("DIST_OUT_OF_RANGE")
        pmin, pmax = cfg["pitch_deg_range"]
        if not (pmin <= float(row["pitch_deg_median"]) <= pmax):
            reasons.append("PITCH_OUT_OF_RANGE")
        if abs(float(row["yaw_deg_median"])) > float(cfg["yaw_deg_abs_max"]):
            reasons.append("YAW_OUT_OF_RANGE")
        if abs(float(row["roll_deg_median"])) > float(cfg["roll_deg_abs_max"]):
            reasons.append("ROLL_OUT_OF_RANGE")
        if float(row["jitter_deg_median"]) > float(cfg["jitter_deg_max"]):
            reasons.append("JITTER_HIGH")
        flags.append(";".join(reasons))
    grouped["flags"] = flags
    grouped["is_red"] = grouped["flags"].apply(lambda x: 1 if ("LOW_PASS_RATE" in str(x) or "DIST_OUT_OF_RANGE" in str(x) or "JITTER_HIGH" in str(x)) else 0)

    drift_csv = out_dir / "drift_groups.csv"
    grouped.to_csv(drift_csv, index=False)

    red = grouped[grouped["is_red"] == 1].copy()
    red_csv = out_dir / "drift_red_groups.csv"
    red.to_csv(red_csv, index=False)

    # write excel dashboard
    xlsx = out_dir / "drift_dashboard.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        grouped.to_excel(xw, sheet_name="Groups", index=False)
        red.to_excel(xw, sheet_name="Red_Groups", index=False)
        merged[merge_cols + group_keys + ["class", "distance_m_median", "pitch_deg_median", "yaw_deg_median", "roll_deg_median", "jitter_deg"]].to_excel(xw, sheet_name="Record_Level", index=False)

    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "group_keys": group_keys,
        "groups_total": int(len(grouped)),
        "red_groups": int(len(red)),
        "overall_pass_rate": float((merged["class"] == "PASS").mean()),
        "config": cfg,
        "outputs": {
            "drift_groups_csv": str(drift_csv),
            "drift_dashboard_xlsx": str(xlsx),
            "drift_red_groups_csv": str(red_csv)
        }
    }
    out_json = out_dir / "drift_summary.json"
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"[OK] Wrote: {xlsx}")
    print(f"[OK] Wrote: {out_json}")


if __name__ == "__main__":
    main()
