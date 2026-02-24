#!/usr/bin/env python3
"""
Audio ↔ Q_ref sync/proxy check for a single record.

Usage:
    python sync_check_audio_qref.py --record_folder <PATH_TO_RECORD> --config ../config/qa_config.json
"""

from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np

from uroflow_qa_utils import (
    load_json,
    parse_qref_csv,
    integrate_flow,
    convert_audio_to_wav,
    detect_audio_onset,
    audio_proxy_q,
    resample_to_grid,
    pearson_corr,
)

DEFAULT_CONFIG_REL = "../config/qa_config.json"

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record_folder", required=True)
    ap.add_argument("--config", default="")
    args = ap.parse_args()

    record_folder = Path(args.record_folder).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve() if args.config else (Path(__file__).parent / DEFAULT_CONFIG_REL).resolve()
    config = load_json(config_path)

    qref_path = record_folder / "Q_ref.csv"
    t, q, v, issues = parse_qref_csv(qref_path, config)
    if issues or t.size == 0:
        print("[FAIL] Q_ref parse issues:", issues)
        return 2

    audio = None
    if (record_folder / "audio.wav").exists():
        audio = record_folder / "audio.wav"
    elif (record_folder / "audio.m4a").exists():
        audio = record_folder / "audio.m4a"

    if audio is None:
        print("[FAIL] audio missing")
        return 2

    wav = convert_audio_to_wav(audio)
    onset, debug, a_issues = detect_audio_onset(wav, config)
    if onset is None:
        print("[REVIEW] onset not detected:", a_issues)
        return 1

    ta, qa, ap_issues = audio_proxy_q(wav, onset, target_hz=10.0)
    if ta.size == 0:
        print("[REVIEW] proxy failed:", ap_issues)
        return 1

    qa_rs = resample_to_grid(ta, qa, t)
    qn = q / np.nanmax(q) if np.nanmax(q) > 0 else q
    corr = pearson_corr(qa_rs, qn)
    print(f"onset_s={onset:.2f}, corr_audio_qref={corr}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
