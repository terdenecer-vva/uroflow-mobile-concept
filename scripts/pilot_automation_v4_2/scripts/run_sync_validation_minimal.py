#!/usr/bin/env python3
"""run_sync_validation_minimal.py (v1.0)

Lightweight sync validation:
- Reads records/<record_id>/ref_alignment.json
- Extracts sync offset (seconds)
- Reports max absolute offset across records

Outputs:
- outputs/sync_validation/sync_validation_record_level.csv
- outputs/sync_validation/sync_validation_summary.json

This is intended as a minimal gate to prevent freezing a dataset with broken pairing.
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


def read_alignment(p: Path) -> dict | None:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return None


def extract_offset_s(d: dict) -> float | None:
    # common keys
    for k in ['sync_offset_s','sync_offset_seconds','sync_offset','offset_s','offset_seconds']:
        if k in d:
            try:
                return float(d[k])
            except Exception:
                pass
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset_root', required=True)
    ap.add_argument('--manifest', required=True)
    args = ap.parse_args()

    dataset_root = Path(args.dataset_root)
    manifest = Path(args.manifest)
    out_dir = dataset_root / 'outputs/sync_validation'
    out_dir.mkdir(parents=True, exist_ok=True)

    dfm = load_manifest(manifest)

    rows = []
    offsets = []
    for rid in dfm['record_id'].tolist():
        p = dataset_root / 'records' / str(rid) / 'ref_alignment.json'
        d = read_alignment(p)
        if d is None:
            rows.append({'record_id': rid, 'ref_alignment_found': False, 'sync_offset_s': None, 'result': 'MISSING'})
            continue
        off = extract_offset_s(d)
        if off is None:
            rows.append({'record_id': rid, 'ref_alignment_found': True, 'sync_offset_s': None, 'result': 'NO_OFFSET'})
            continue
        offsets.append(abs(off))
        rows.append({'record_id': rid, 'ref_alignment_found': True, 'sync_offset_s': float(off), 'result': 'OK'})

    rec = pd.DataFrame(rows)
    rec.to_csv(out_dir / 'sync_validation_record_level.csv', index=False)

    max_abs = float(max(offsets)) if offsets else None
    summary = {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'records_total': int(len(dfm)),
        'records_with_offset': int(len(offsets)),
        'max_abs_sync_offset_s': max_abs,
        'missing_alignment_count': int((rec['result'] == 'MISSING').sum()),
        'no_offset_count': int((rec['result'] == 'NO_OFFSET').sum()),
    }
    (out_dir / 'sync_validation_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')

    print(f"[OK] Wrote: {out_dir / 'sync_validation_summary.json'}")


if __name__ == '__main__':
    main()
