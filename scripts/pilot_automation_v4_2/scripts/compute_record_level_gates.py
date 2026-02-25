#!/usr/bin/env python3
"""compute_record_level_gates.py

Computes per-record gate status and a final include/exclude decision.

This is the *record-level* companion to run_pre_freeze_gates.py (dataset-level).
It is intended to be used in:
- DatasetRelease guarded builder (v3.9+)
- Site daily QA dashboards
- Audit-ready evidence generation

Inputs:
- dataset_root
- manifest (record_id)
- config/record_level_gates_config.json (from the Submission_Build package)

Outputs (under dataset_root):
- outputs/record_level_gates/record_level_gates.csv
- outputs/record_level_gates/record_level_gates_summary.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

import pandas as pd
import numpy as np


def load_manifest(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)
    if "record_id" not in df.columns:
        raise ValueError("Manifest must include record_id.")
    df["record_id"] = df["record_id"].astype(str)
    return df


def read_json(p: Path) -> Optional[Dict[str, Any]]:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def safe_read_csv(p: Path) -> Optional[pd.DataFrame]:
    if not p.exists():
        return None
    try:
        return pd.read_csv(p)
    except Exception:
        return None


def lookup_result(df: Optional[pd.DataFrame], rid: str, col_result: str = "result", col_reason: str = "reason") -> Tuple[str, str]:
    if df is None or "record_id" not in df.columns:
        return "MISSING", ""
    try:
        sub = df[df["record_id"].astype(str) == str(rid)]
        if len(sub) == 0:
            return "MISSING", ""
        r = sub.iloc[0]
        return str(r.get(col_result, "MISSING")), str(r.get(col_reason, ""))
    except Exception:
        return "MISSING", ""


def get_standpose_class(dataset_root: Path, rid: str) -> str:
    # 1) prefer drift dashboard record-level sheet
    dash = dataset_root / "outputs/stand_pose_drift_dashboard/drift_dashboard.xlsx"
    if dash.exists():
        try:
            df = pd.read_excel(dash, sheet_name="Record_Level")
            if "record_id" in df.columns:
                df["record_id"] = df["record_id"].astype(str)
                sub = df[df["record_id"] == str(rid)]
                if len(sub) > 0:
                    # column can be 'class' or 'class_kpi'
                    for c in ["class", "class_kpi", "stand_pose_class"]:
                        if c in sub.columns:
                            v = str(sub.iloc[0][c])
                            if v and v != "nan":
                                return v
        except Exception:
            pass
    # 2) fallback to meta.json
    meta = read_json(dataset_root / "records" / rid / "meta.json")
    if isinstance(meta, dict):
        sp = meta.get("stand_pose_summary") or meta.get("stand_pose") or meta.get("stand_pose_summary_v1")
        if isinstance(sp, dict):
            v = sp.get("class") or sp.get("stand_pose_class")
            if v is not None:
                return str(v)
    return "MISSING"


def qref_pass(record_dir: Path) -> Tuple[bool, str]:
    qref = record_dir / "Q_ref.csv"
    if not qref.exists():
        return False, "QREF_MISSING"
    try:
        df = pd.read_csv(qref)
    except Exception:
        return False, "QREF_PARSE_ERROR"
    # try to detect time column
    tcol = None
    for c in ["t_s", "t", "time_s", "time", "seconds"]:
        if c in df.columns:
            tcol = c
            break
    if tcol is None:
        return False, "QREF_NO_TIME_COL"
    t = df[tcol].values
    if len(t) < 3:
        return False, "QREF_TOO_SHORT"
    # monotonic non-decreasing
    if np.any(np.diff(t) < -1e-9):
        return False, "QREF_TIME_NOT_MONOTONIC"
    return True, ""


def sync_pass(record_dir: Path, max_abs: float, require_ref_alignment: bool) -> Tuple[bool, float | None, str]:
    ra = record_dir / "ref_alignment.json"
    if not ra.exists():
        return (False, None, "SYNC_MISSING") if require_ref_alignment else (True, None, "SYNC_NOT_REQUIRED")
    obj = read_json(ra)
    if not isinstance(obj, dict):
        return False, None, "SYNC_PARSE_ERROR"
    off = obj.get("sync_offset_s")
    try:
        off_f = float(off)
    except Exception:
        return False, None, "SYNC_OFFSET_NOT_NUM"
    if abs(off_f) > float(max_abs):
        return False, off_f, "SYNC_OFFSET_EXCEEDED"
    return True, off_f, ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset_root", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--config", default="config/record_level_gates_config.json")
    args = ap.parse_args()

    dataset_root = Path(args.dataset_root)
    manifest = Path(args.manifest)

    # Config path: support both submission-build layout and repo-local automation layout.
    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        if not cfg_path.exists():
            automation_root = Path(__file__).resolve().parents[1]
            local_candidate = automation_root / cfg_path
            submission_candidate = Path(__file__).resolve().parents[2] / "10_Pilot_Automation" / cfg_path
            if local_candidate.exists():
                cfg_path = local_candidate
            elif submission_candidate.exists():
                cfg_path = submission_candidate
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    out_dir = dataset_root / cfg.get("outputs_dirname", "outputs/record_level_gates")
    out_dir.mkdir(parents=True, exist_ok=True)

    dfm = load_manifest(manifest)

    # inputs
    live_df = safe_read_csv(dataset_root / "outputs/privacy_live_guardrails/privacy_live_guardrails.csv")
    if live_df is not None:
        live_df["record_id"] = live_df["record_id"].astype(str)
    cont_df = safe_read_csv(dataset_root / "outputs/privacy_content_guardrails_v2/privacy_content_guardrails_v2.csv")
    if cont_df is not None:
        cont_df["record_id"] = cont_df["record_id"].astype(str)

    ios_df = safe_read_csv(dataset_root / "outputs/ios_capture_contract/ios_capture_contract_validation.csv")
    if ios_df is not None:
        ios_df["record_id"] = ios_df["record_id"].astype(str)

    cons_df = safe_read_csv(dataset_root / "outputs/privacy_consistency/privacy_consistency.csv")
    if cons_df is not None:
        cons_df["record_id"] = cons_df["record_id"].astype(str)

    rows: List[Dict[str, Any]] = []

    for rid in dfm["record_id"].tolist():
        record_dir = dataset_root / "records" / rid

        # gates
        ios_res, _ = lookup_result(ios_df, rid, col_result="result", col_reason="errors")
        live_res, live_reason = lookup_result(live_df, rid, col_result="result", col_reason="reason")
        cont_res, cont_reason = lookup_result(cont_df, rid, col_result="result", col_reason="reason")
        cons_res, cons_reason = lookup_result(cons_df, rid, col_result="consistency_result", col_reason="consistency_reason")
        stand_class = get_standpose_class(dataset_root, rid)

        # quality summary (QS) from meta.json
        meta_obj = read_json(record_dir / "meta.json")
        quality_score = None
        quality_class = None
        if isinstance(meta_obj, dict):
            qsum_key = cfg.get("quality_summary_path", "quality_summary")
            qsum = meta_obj.get(qsum_key) if qsum_key else None
            if isinstance(qsum, dict):
                qs_key = cfg.get("quality_score_field", "quality_score")
                qc_key = cfg.get("quality_class_field", "quality_class")
                quality_score = qsum.get(qs_key)
                quality_class = qsum.get(qc_key)


        roi_exists = (record_dir / "roi_video.mp4").exists()
        priv_content_required = bool(cfg.get("priv_content_required_if_video_present", True) and roi_exists)

        # Evaluate each gate
        reasons: List[str] = []

        ios_ok = True
        if cfg.get("require_ios_contract", True):
            ios_ok = (ios_res == "PASS")
            if not ios_ok:
                reasons.append("IOS_CONTRACT_FAIL" if ios_res == "FAIL" else "IOS_CONTRACT_MISSING")

        live_ok = (live_res == "PASS")
        if not live_ok:
            reasons.append("PRIV_LIVE_" + str(live_res))

        content_ok = True
        if priv_content_required:
            content_ok = (cont_res in cfg.get("priv_content_pass_values", ["PASS", "REVIEW"]))
            if not content_ok:
                reasons.append("PRIV_CONTENT_" + str(cont_res))

        cons_ok = True
        if cfg.get("require_privacy_consistency", True):
            cons_ok = (cons_res == "PASS")
            if not cons_ok:
                reasons.append("PRIV_CONSISTENCY_" + str(cons_res))

        stand_ok = stand_class in cfg.get("standpose_allowed_classes", ["PASS", "BORDERLINE"])

        quality_ok = True
        if cfg.get("require_quality_summary", False):
            if quality_class is None or str(quality_class) == "nan":
                quality_ok = False
                reasons.append("QUALITY_CLASS_MISSING")
            else:
                qc = str(quality_class)
                allowed = cfg.get("allowed_quality_classes", ["VALID", "BORDERLINE"])
                if qc not in allowed:
                    quality_ok = False
                    reasons.append("QUALITY_CLASS_" + qc)
            try:
                qs_f = float(quality_score) if quality_score is not None else None
            except Exception:
                qs_f = None
            if qs_f is None:
                if cfg.get("require_quality_summary", False):
                    quality_ok = False
                    reasons.append("QUALITY_SCORE_MISSING")
            else:
                if qs_f < float(cfg.get("min_quality_score", 0)):
                    quality_ok = False
                    reasons.append("QUALITY_SCORE_BELOW_MIN")

        if not stand_ok:
            reasons.append("STANDPOSE_" + str(stand_class))

        sync_ok, sync_off, sync_reason = sync_pass(record_dir, float(cfg.get("sync_offset_max_s", 1.0)), bool(cfg.get("require_ref_alignment", True)))
        if not sync_ok:
            reasons.append(sync_reason)

        q_ok, q_reason = qref_pass(record_dir) if cfg.get("require_q_ref", True) else (True, "")
        if not q_ok:
            reasons.append(q_reason)

        include = ios_ok and live_ok and content_ok and cons_ok and stand_ok and quality_ok and sync_ok and q_ok

        rows.append({
            "record_id": rid,
            "include_in_release": bool(include),
            "reasons": ";".join(reasons),
            "ios_contract": ios_res,
            "priv_live": live_res,
            "priv_live_reason": live_reason,
            "priv_content": cont_res,
            "priv_content_reason": cont_reason,
            "priv_consistency": cons_res,
            "priv_consistency_reason": cons_reason,
            "roi_video_exists": bool(roi_exists),
            "standpose_class": stand_class,
            "quality_score": quality_score if quality_score is not None else "",
            "quality_class": quality_class if quality_class is not None else "",
            "sync_offset_s": sync_off if sync_off is not None else "",
            "sync_pass": bool(sync_ok),
            "qref_pass": bool(q_ok),
        })

    out_df = pd.DataFrame(rows)
    out_csv = out_dir / "record_level_gates.csv"
    out_df.to_csv(out_csv, index=False)

    included = int(out_df["include_in_release"].sum())
    excluded = int(len(out_df) - included)

    # reason counts (split)
    reason_counts: Dict[str, int] = {}
    for rr in out_df["reasons"].fillna("").astype(str).tolist():
        for part in [p for p in rr.split(";") if p.strip()]:
            reason_counts[part] = reason_counts.get(part, 0) + 1

    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "records_total": int(len(out_df)),
        "included": included,
        "excluded": excluded,
        "include_rate": float(included / max(1, len(out_df))),
        "reason_counts": dict(sorted(reason_counts.items(), key=lambda x: (-x[1], x[0]))),
        "config": cfg,
    }
    (out_dir / "record_level_gates_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"[OK] Wrote: {out_csv}")
    print(f"[OK] included={included} excluded={excluded}")


if __name__ == "__main__":
    main()
