#!/usr/bin/env python3
"""run_daily_qa_minimal.py (v1.0)

Minimal daily QA for golden dataset readiness.
Checks per record:
- required files exist (meta.json, Q_ref.csv, ref_import_log.json, ref_alignment.json)
- Q_ref.csv is non-empty

Outputs:
- outputs/daily_qa/qa_record_level.csv
- outputs/daily_qa/qa_summary.json

This is intentionally lightweight and complements the record-level gates.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime

import pandas as pd


def load_manifest(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == '.csv':
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)
    if 'record_id' not in df.columns:
        raise ValueError('Manifest must contain record_id')
    df['record_id'] = df['record_id'].astype(str)
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset_root', required=True)
    ap.add_argument('--manifest', required=True)
    args = ap.parse_args()

    dataset_root = Path(args.dataset_root)
    manifest = Path(args.manifest)
    out_dir = dataset_root / 'outputs/daily_qa'
    out_dir.mkdir(parents=True, exist_ok=True)

    dfm = load_manifest(manifest)

    required_files = ['meta.json', 'Q_ref.csv', 'ref_import_log.json', 'ref_alignment.json']

    rows = []
    for rid in dfm['record_id'].tolist():
        rec_dir = dataset_root / 'records' / str(rid)
        missing = []
        for fn in required_files:
            if not (rec_dir / fn).exists():
                missing.append(fn)
        qref_nonempty = False
        qref_path = rec_dir / 'Q_ref.csv'
        if qref_path.exists():
            try:
                qdf = pd.read_csv(qref_path)
                qref_nonempty = len(qdf) > 0
            except Exception:
                qref_nonempty = False
        if not qref_nonempty and 'Q_ref.csv' not in missing:
            missing.append('Q_ref.csv(empty_or_unreadable)')

        result = 'PASS' if len(missing) == 0 else 'FAIL'
        rows.append({'record_id': rid, 'result': result, 'missing': ';'.join(missing)})

    rec = pd.DataFrame(rows)
    rec.to_csv(out_dir / 'qa_record_level.csv', index=False)

    summary = {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'records_total': int(len(dfm)),
        'fail_count': int((rec['result'] == 'FAIL').sum()),
        'overall_pass': bool(int((rec['result'] == 'FAIL').sum()) == 0)
    }
    (out_dir / 'qa_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')

    print(f"[OK] Wrote: {out_dir / 'qa_summary.json'}")
    print(f"[OK] OVERALL: {'PASS' if summary['overall_pass'] else 'FAIL'}")


if __name__ == '__main__':
    main()
