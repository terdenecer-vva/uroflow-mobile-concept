#!/usr/bin/env python3
"""
Freeze Bundle Generator (offline)

Creates an immutable evidence bundle for a frozen dataset/model/QS configuration.
This is intended to prevent "evidence drift" across CER/CSR/V&V and regulatory submissions.

Usage:
    python freeze_bundle_generator.py --dataset_root <PATH> --manifest <MANIFEST> \
        --freeze_config config/freeze_config_template.json --out outputs

Outputs:
    outputs/freeze_bundle_<dataset_id>_<model_id>_<timestamp>.zip
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import time
from pathlib import Path
from typing import List

from uroflow_qa_utils import load_manifest, load_json, save_json, sha256_file, now_ymd, find_record_folder


def copy_if_exists(src: Path, dst: Path, missing_ok: bool = True) -> bool:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return True
    if not missing_ok:
        raise FileNotFoundError(str(src))
    return False


def dataset_card_auto(manifest_rows: List[dict]) -> str:
    n = len(manifest_rows)
    by_sex = {}
    by_posture = {}
    by_site = {}
    by_toilet = {}
    valid = 0
    for r in manifest_rows:
        sex = (r.get("sex") or "").strip()
        posture = (r.get("posture") or "").strip()
        site = (r.get("site_id") or "").strip()
        toilet = (r.get("toilet_id") or "").strip()
        by_sex[sex] = by_sex.get(sex, 0) + 1
        by_posture[posture] = by_posture.get(posture, 0) + 1
        by_site[site] = by_site.get(site, 0) + 1
        by_toilet[toilet] = by_toilet.get(toilet, 0) + 1
        if (r.get("overall_record_valid") or "").strip().lower() == "yes":
            valid += 1

    lines = []
    lines.append("# Uroflow Golden Dataset — Auto Dataset Card")
    lines.append("")
    lines.append(f"- Records in manifest: **{n}**")
    lines.append(f"- Marked overall_record_valid=yes: **{valid}**")
    lines.append("")
    lines.append("## Distribution (counts)")
    lines.append("")
    lines.append("### Sex")
    for k, v in sorted(by_sex.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- {k or '(empty)'}: {v}")
    lines.append("")
    lines.append("### Posture")
    for k, v in sorted(by_posture.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- {k or '(empty)'}: {v}")
    lines.append("")
    lines.append("### Site")
    for k, v in sorted(by_site.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- {k or '(empty)'}: {v}")
    lines.append("")
    lines.append("### Toilet")
    for k, v in sorted(by_toilet.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- {k or '(empty)'}: {v}")
    lines.append("")
    lines.append("## Notes")
    lines.append("- This file is auto-generated and should be reviewed by QA/Clinical before submission use.")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset_root", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--freeze_config", required=True)
    ap.add_argument("--out", default="outputs")
    ap.add_argument("--include_media", action="store_true", help="Include audio/video files in freeze bundle (NOT recommended unless required and consented)")
    args = ap.parse_args()

    dataset_root = Path(args.dataset_root).expanduser().resolve()
    manifest_path = Path(args.manifest).expanduser().resolve()
    out_root = Path(args.out).expanduser().resolve()
    freeze_config_path = Path(args.freeze_config).expanduser().resolve()

    freeze_cfg = load_json(freeze_config_path)
    dataset_id = freeze_cfg.get("dataset_id", "DATASET")
    model_id = freeze_cfg.get("model_id", "MODEL")
    ts = time.strftime("%Y%m%d_%H%M%S")

    build_root = Path(__file__).resolve().parents[3]  # .../Submission_Build_v2.4
    bundle_dir = out_root / f"freeze_bundle_{dataset_id}_{model_id}_{ts}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    # Copy manifest and freeze config
    copy_if_exists(manifest_path, bundle_dir / "manifest" / manifest_path.name, missing_ok=False)
    copy_if_exists(freeze_config_path, bundle_dir / "freeze_config" / freeze_config_path.name, missing_ok=False)

    # Auto dataset card
    manifest_rows = load_manifest(manifest_path)
    (bundle_dir / "dataset_card").mkdir(exist_ok=True)
    (bundle_dir / "dataset_card" / "dataset_card_auto.md").write_text(dataset_card_auto(manifest_rows), encoding="utf-8")

    # Optional: copy dataset card provided by team (if any)
    # We look for 'dataset_card.docx' or 'dataset_card.md' in dataset root
    for name in ["dataset_card.docx", "dataset_card.md", "dataset_card.pdf"]:
        if (dataset_root / name).exists():
            copy_if_exists(dataset_root / name, bundle_dir / "dataset_card" / name)

    # Include selected build artifacts (claims lock, acceptance lock, evidence manifest, etc.)
    inc = freeze_cfg.get("include_paths_relative_to_build", [])
    copied = []
    for rel in inc:
        src = build_root / rel
        dst = bundle_dir / "submission_build_artifacts" / rel
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(rel)

    # Checksums for manifest + (optionally) record files
    checksums = []
    checksums.append({"file": f"manifest/{manifest_path.name}", "sha256": sha256_file(manifest_path)})
    # Copy checksums.sha256 if exists
    for cand in ["checksums.sha256", "outputs/checksums.sha256"]:
        p = dataset_root / cand
        if p.exists():
            copy_if_exists(p, bundle_dir / "checksums" / p.name)
            checksums.append({"file": f"checksums/{p.name}", "sha256": sha256_file(p)})

    # Optionally include media (dangerous for privacy)
    if args.include_media:
        media_dir = bundle_dir / "media"
        media_dir.mkdir(exist_ok=True)
        for r in manifest_rows:
            record_id = (r.get("record_id") or "").strip()
            if not record_id:
                continue
            rf = find_record_folder(dataset_root, record_id, freeze_cfg) or find_record_folder(dataset_root, record_id, {"record_folder_candidates": ["records/{record_id}", "{record_id}"]})
            if rf is None:
                continue
            for fn in ["audio.wav", "audio.m4a", "roi_video.mp4"]:
                if (rf / fn).exists():
                    dst = media_dir / record_id / fn
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(rf / fn, dst)

    freeze_manifest = {
        "created_at": ts,
        "dataset_id": dataset_id,
        "model_id": model_id,
        "qs_thresholds": freeze_cfg.get("qs_thresholds", {}),
        "claims_set_id": freeze_cfg.get("claims_set_id", ""),
        "region": freeze_cfg.get("region", ""),
        "build_version": freeze_cfg.get("build_version", ""),
        "dataset_root": str(dataset_root),
        "manifest": str(manifest_path),
        "included_build_artifacts": copied,
        "checksums": checksums,
        "notes": freeze_cfg.get("notes", ""),
    }
    save_json(freeze_manifest, bundle_dir / "freeze_manifest.json")

    # Zip
    zip_path = out_root / f"FreezeBundle_{dataset_id}_{model_id}_{ts}.zip"
    import zipfile
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in bundle_dir.rglob("*"):
            if p.is_file():
                z.write(p, arcname=p.relative_to(bundle_dir))
    print(f"[OK] Freeze bundle created: {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
