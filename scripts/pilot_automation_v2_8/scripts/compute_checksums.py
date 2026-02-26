#!/usr/bin/env python3
"""
Compute SHA256 checksums for record folders.

Usage:
    python compute_checksums.py --dataset_root /data/golden --manifest manifest.csv --out outputs/checksums.sha256
"""

from __future__ import annotations
import argparse
from pathlib import Path

from uroflow_qa_utils import load_json, load_manifest, find_record_folder, sha256_file

DEFAULT_CONFIG_REL = "../config/qa_config.json"

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset_root", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--config", default="")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    dataset_root = Path(args.dataset_root).expanduser().resolve()
    manifest = Path(args.manifest).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve() if args.config else (Path(__file__).parent / DEFAULT_CONFIG_REL).resolve()

    config = load_json(config_path)
    rows = load_manifest(manifest)

    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    for r in rows:
        record_id = (r.get("record_id") or "").strip()
        if not record_id:
            continue
        rf = find_record_folder(dataset_root, record_id, config)
        if rf is None:
            continue
        for p in sorted(rf.rglob("*")):
            if p.is_file():
                h = sha256_file(p)
                rel = p.relative_to(dataset_root)
                lines.append(f"{h}  {rel.as_posix()}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] checksums written: {out_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
