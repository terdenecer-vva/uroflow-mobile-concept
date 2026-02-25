#!/usr/bin/env python3
"""validate_privacy_guardrails_consistency.py

Cross-checks LIVE (on-device) privacy guardrails results against offline content-level checks
on ROI video (if stored).

Motivation:
- LIVE guardrails are supposed to prevent saving "unsafe" sessions.
- Offline content checks may reveal issues missed by LIVE logic (implementation bug, edge case).
- The consistency report is used as an auditable privacy control and as a record-level gate.

Inputs:
- dataset_root
- manifest (record_id)
- outputs/privacy_live_guardrails/privacy_live_guardrails.csv
- outputs/privacy_content_guardrails_v2/privacy_content_guardrails_v2.csv (optional)

Outputs:
- outputs/privacy_consistency/privacy_consistency.csv
- outputs/privacy_consistency/privacy_consistency_summary.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

import pandas as pd


def load_manifest(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)
    if "record_id" not in df.columns:
        raise ValueError("Manifest must contain record_id.")
    df["record_id"] = df["record_id"].astype(str)
    return df


def read_csv_if_exists(p: Path) -> pd.DataFrame | None:
    if p.exists():
        try:
            return pd.read_csv(p)
        except Exception:
            return None
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset_root", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out_dir", default=None)
    ap.add_argument("--allow_save_on_live_fail", action="store_true", help="If set, live FAIL + roi video saved becomes REVIEW (not FAIL)")
    args = ap.parse_args()

    dataset_root = Path(args.dataset_root)
    manifest = Path(args.manifest)

    out_dir = Path(args.out_dir) if args.out_dir else (dataset_root / "outputs/privacy_consistency")
    out_dir.mkdir(parents=True, exist_ok=True)

    dfm = load_manifest(manifest)

    live_csv = dataset_root / "outputs/privacy_live_guardrails/privacy_live_guardrails.csv"
    content_csv = dataset_root / "outputs/privacy_content_guardrails_v2/privacy_content_guardrails_v2.csv"

    live_df = read_csv_if_exists(live_csv)
    content_df = read_csv_if_exists(content_csv)

    # Normalize
    if live_df is not None:
        live_df["record_id"] = live_df["record_id"].astype(str)
    if content_df is not None:
        content_df["record_id"] = content_df["record_id"].astype(str)

    rows: List[Dict[str, Any]] = []
    fail_n = review_n = pass_n = 0

    for rid in dfm["record_id"].tolist():
        roi_video = dataset_root / "records" / rid / "roi_video.mp4"
        roi_exists = roi_video.exists()

        live_res = None
        live_reason = ""
        if live_df is not None and rid in set(live_df["record_id"].tolist()):
            r = live_df[live_df["record_id"] == rid].iloc[0]
            live_res = str(r.get("result", ""))
            live_reason = str(r.get("reason", ""))
        else:
            live_res = "MISSING"

        cont_res = "MISSING"
        cont_reason = ""
        if content_df is not None and rid in set(content_df["record_id"].tolist()):
            r = content_df[content_df["record_id"] == rid].iloc[0]
            cont_res = str(r.get("result", ""))
            cont_reason = str(r.get("reason", ""))
        else:
            cont_res = "MISSING"

        status = "PASS"
        reason = ""

        # Basic existence consistency
        if roi_exists and cont_res in ["NO_VIDEO", "MISSING", "nan", "None", ""]:
            status = "FAIL"
            reason = "ROI_VIDEO_PRESENT_BUT_NO_CONTENT_RESULT"
        if (not roi_exists) and cont_res not in ["NO_VIDEO", "MISSING", "nan", "None", ""]:
            # content check claims it saw a video, but video file not present
            status = "REVIEW"
            reason = "CONTENT_RESULT_BUT_NO_ROI_VIDEO"

        # Cross-check LIVE vs Content
        if live_res == "PASS" and roi_exists and cont_res == "FAIL":
            status = "FAIL"
            reason = "LIVE_PASS_CONTENT_FAIL"
        if live_res in ["FAIL", "MISSING"] and roi_exists and not args.allow_save_on_live_fail:
            # In production/pilot default: if LIVE would block, ROI video should not be stored
            # If you collected ROI video for investigation, run with --allow_save_on_live_fail
            status = "FAIL"
            reason = "LIVE_FAIL_OR_MISSING_BUT_VIDEO_SAVED"
        if live_res == "FAIL" and roi_exists and args.allow_save_on_live_fail:
            status = "REVIEW"
            reason = "LIVE_FAIL_VIDEO_SAVED_ALLOWED"

        # If content is FAIL regardless of LIVE, mark FAIL (privacy risk)
        if roi_exists and cont_res == "FAIL":
            status = "FAIL"
            if reason == "":
                reason = "CONTENT_FAIL"

        rows.append({
            "record_id": rid,
            "roi_video_exists": bool(roi_exists),
            "live_result": live_res,
            "live_reason": live_reason,
            "content_result": cont_res,
            "content_reason": cont_reason,
            "consistency_result": status,
            "consistency_reason": reason
        })

        if status == "PASS":
            pass_n += 1
        elif status == "FAIL":
            fail_n += 1
        else:
            review_n += 1

    out_df = pd.DataFrame(rows)
    out_csv = out_dir / "privacy_consistency.csv"
    out_df.to_csv(out_csv, index=False)

    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "records_total": int(len(out_df)),
        "pass": int(pass_n),
        "fail": int(fail_n),
        "review": int(review_n),
        "overall_pass": bool(fail_n == 0),
        "inputs": {
            "live_csv": str(live_csv),
            "content_csv": str(content_csv),
        }
    }
    (out_dir / "privacy_consistency_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"[OK] Wrote: {out_csv}")
    print(f"[OK] overall_pass={summary['overall_pass']} (fail={fail_n}, review={review_n})")


if __name__ == "__main__":
    main()
