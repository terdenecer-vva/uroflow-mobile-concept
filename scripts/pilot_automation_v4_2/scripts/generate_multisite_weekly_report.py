#!/usr/bin/env python3
"""generate_multisite_weekly_report.py (v1.0)

Builds an auditable weekly (or ad-hoc) operational report for multi-site golden dataset collection.

It is intentionally lightweight: it reads existing validator outputs if present.

Inputs:
- --dataset_root : dataset root
- --manifest     : manifest CSV/XLSX

Outputs:
- outputs/multisite_weekly_report/weekly_report.xlsx
- outputs/multisite_weekly_report/weekly_report_summary.json

"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict

import pandas as pd


def load_df(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == '.csv':
        return pd.read_csv(path)
    return pd.read_excel(path)


def read_json(p: Path) -> Dict[str, Any] | None:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset_root', required=True)
    ap.add_argument('--manifest', required=True)
    args = ap.parse_args()

    dataset_root = Path(args.dataset_root)
    manifest = Path(args.manifest)

    out_dir = dataset_root / 'outputs/multisite_weekly_report'
    out_dir.mkdir(parents=True, exist_ok=True)

    mdf = load_df(manifest)
    total_records = int(len(mdf))

    # coverage
    cov = read_json(dataset_root / 'outputs/coverage_dashboard/coverage_summary.json')

    # stand pose
    drift = read_json(dataset_root / 'outputs/stand_pose_drift_dashboard/drift_summary.json')

    # privacy live
    live_csv = dataset_root / 'outputs/privacy_live_guardrails/privacy_live_guardrails.csv'
    live = None
    if live_csv.exists():
        live = pd.read_csv(live_csv)

    # privacy content v2
    pc_csv = dataset_root / 'outputs/privacy_content_guardrails_v2/privacy_content_guardrails_v2.csv'
    pc = None
    if pc_csv.exists():
        pc = pd.read_csv(pc_csv)

    # record-level gates
    gates_csv = dataset_root / 'outputs/record_level_gates/record_level_gates.csv'
    gates = None
    if gates_csv.exists():
        gates = pd.read_csv(gates_csv)

    summary: Dict[str, Any] = {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'total_records': total_records,
        'coverage_overall_pass': bool(cov.get('overall_pass', False)) if cov else None,
        'standpose_overall_pass_rate': float(drift.get('overall_pass_rate', -1.0)) if drift else None,
        'standpose_red_groups': int(drift.get('red_groups', -1)) if drift else None,
    }

    if live is not None and 'result' in live.columns:
        summary.update({
            'privacy_live_fail': int((live['result'] == 'FAIL').sum()),
            'privacy_live_missing': int((live['result'] == 'MISSING').sum()),
        })
    else:
        summary.update({'privacy_live_fail': None, 'privacy_live_missing': None})

    if pc is not None and 'result' in pc.columns:
        summary.update({
            'privacy_content_fail': int((pc['result'] == 'FAIL').sum()),
            'privacy_content_no_video': int((pc['result'] == 'NO_VIDEO').sum()),
        })
    else:
        summary.update({'privacy_content_fail': None, 'privacy_content_no_video': None})

    if gates is not None and 'include_in_release' in gates.columns:
        included = int((gates['include_in_release'] == True).sum())  # noqa: E712
        excluded = int(len(gates) - included)
        summary.update({'valid_records': included, 'invalid_records': excluded})
        # top reasons
        reason_cols = [c for c in gates.columns if c.endswith('_reason')]
        top_reasons = []
        if reason_cols:
            reasons = pd.Series(dtype=str)
            for c in reason_cols:
                reasons = pd.concat([reasons, gates.loc[gates['include_in_release'] != True, c].dropna().astype(str)])
            if len(reasons) > 0:
                top_reasons = reasons.value_counts().head(10).to_dict()
        summary['top_invalid_reasons'] = top_reasons
    else:
        summary.update({'valid_records': None, 'invalid_records': None, 'top_invalid_reasons': {}})

    (out_dir / 'weekly_report_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')

    # Excel report
    xlsx = out_dir / 'weekly_report.xlsx'
    with pd.ExcelWriter(xlsx, engine='openpyxl') as writer:
        pd.DataFrame([summary]).to_excel(writer, index=False, sheet_name='Summary')
        # optional sheets
        if cov:
            pd.DataFrame(cov.get('checks', [])).to_excel(writer, index=False, sheet_name='CoverageChecks')
            pd.DataFrame(list((cov.get('by_site') or {}).items()), columns=['site_id','n']).to_excel(writer, index=False, sheet_name='CoverageBySite')
        if drift:
            pd.DataFrame([drift]).to_excel(writer, index=False, sheet_name='StandPoseDrift')
        if live is not None:
            live.to_excel(writer, index=False, sheet_name='PrivacyLive')
        if pc is not None:
            pc.to_excel(writer, index=False, sheet_name='PrivacyContent')
        if gates is not None:
            gates.to_excel(writer, index=False, sheet_name='RecordGates')

    print(f"[OK] Wrote: {xlsx}")
    print(f"[OK] Wrote: {out_dir / 'weekly_report_summary.json'}")


if __name__ == '__main__':
    main()
