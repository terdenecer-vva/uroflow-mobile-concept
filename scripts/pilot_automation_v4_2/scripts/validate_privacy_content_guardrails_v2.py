#!/usr/bin/env python3
"""
validate_privacy_content_guardrails_v2.py

Content-level privacy guardrails (v2) for ROI video.

- Detects face/person/skin-area leaks in roi_video.mp4 (ROI-only video).
- Outputs record-level CSV + JSON summary.
- Optional: generate strongly de-identified evidence thumbnails for clinic-test only.

This script is intended to be run OFFLINE on a dataset root folder.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd
import cv2


def load_manifest(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    elif path.suffix.lower() in [".xlsx", ".xls"]:
        df = pd.read_excel(path)
    else:
        raise ValueError(f"Unsupported manifest format: {path}")
    if "record_id" not in df.columns:
        raise ValueError("Manifest must contain 'record_id' column.")
    return df


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def pixelate(img: np.ndarray, down: int, up: int) -> np.ndarray:
    h, w = img.shape[:2]
    small = cv2.resize(img, (down, down), interpolation=cv2.INTER_AREA)
    out = cv2.resize(small, (up, up), interpolation=cv2.INTER_NEAREST)
    return out


def make_evidence_thumbnail(frame_bgr: np.ndarray, mode: str, down: int, up: int) -> np.ndarray:
    # Strong de-identification
    if mode == "pixelate_edges":
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 60, 160)
        edges = cv2.GaussianBlur(edges, (7, 7), 0)
        out = pixelate(edges, down=down, up=up)
        return out
    elif mode == "pixelate_gray":
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (11, 11), 0)
        out = pixelate(gray, down=down, up=up)
        return out
    else:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        return pixelate(gray, down=down, up=up)


def compute_skin_frac(frame_bgr: np.ndarray) -> float:
    # YCrCb skin mask (simple heuristic)
    ycrcb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2YCrCb)
    lower = np.array([0, 133, 77], dtype=np.uint8)
    upper = np.array([255, 173, 127], dtype=np.uint8)
    mask = cv2.inRange(ycrcb, lower, upper)
    return float(mask.mean() / 255.0)


def border_leak_score(frame_bgr: np.ndarray, band_frac: float) -> float:
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 60, 160)
    h, w = edges.shape[:2]
    bw = int(max(1, min(h, w) * band_frac))
    border = np.zeros_like(edges, dtype=np.uint8)
    border[:bw, :] = 1
    border[-bw:, :] = 1
    border[:, :bw] = 1
    border[:, -bw:] = 1
    border_edges = edges[border == 1]
    score = float(border_edges.mean() / 255.0)  # fraction of edge pixels in border band
    return score


def init_detectors() -> Tuple[cv2.CascadeClassifier, cv2.HOGDescriptor]:
    face_cascade_path = str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
    face = cv2.CascadeClassifier(face_cascade_path)
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    return face, hog


def detect_on_video(
    video_path: Path,
    cfg: Dict[str, Any],
    face: cv2.CascadeClassifier,
    hog: cv2.HOGDescriptor,
) -> Dict[str, Any]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return {"result": "REVIEW", "reason": "VIDEO_DECODE_ERROR", "face_hits": 0, "person_hits": 0,
                "max_skin_frac": 0.0, "border_leak_max": 0.0, "evidence_frame": None}

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps is None or fps <= 0:
        fps = 30.0
    sample_fps = float(cfg.get("sample_fps", 3))
    step = int(max(1, round(fps / sample_fps)))
    max_frames = int(cfg.get("max_frames", 180))
    max_width = int(cfg.get("max_width", 640))

    face_hits = 0
    person_hits = 0
    max_skin = 0.0
    max_border = 0.0

    evidence_frame = None
    evidence_score = -1.0
    frame_idx = 0
    sampled = 0

    while sampled < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % step != 0:
            frame_idx += 1
            continue
        frame_idx += 1
        sampled += 1

        # resize for speed
        h, w = frame.shape[:2]
        if w > max_width:
            new_h = int(h * (max_width / w))
            frame = cv2.resize(frame, (max_width, new_h), interpolation=cv2.INTER_AREA)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Face
        faces = face.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(int(cfg.get("face_min_size_px", 40)), int(cfg.get("face_min_size_px", 40))))
        if len(faces) > 0:
            face_hits += len(faces)

        # Person
        rects, _weights = hog.detectMultiScale(frame, winStride=(8, 8), padding=(16, 16), scale=1.05)
        # count only large enough boxes
        ph_min = int(cfg.get("person_min_height_px", 80))
        rects_f = [r for r in rects if r[3] >= ph_min]
        if rects_f:
            person_hits += len(rects_f)

        # Skin
        skin = compute_skin_frac(frame)
        if skin > max_skin:
            max_skin = skin

        # Border leak
        bscore = border_leak_score(frame, float(cfg.get("border_band_frac", 0.12)))
        if bscore > max_border:
            max_border = bscore

        # choose evidence frame by "most suspicious"
        # prioritize faces/person, else max(skin,border)
        suspicious = 0.0
        if len(faces) > 0:
            suspicious = 10.0 + min(1.0, len(faces) / 3.0)
        elif rects_f:
            suspicious = 8.0 + min(1.0, len(rects_f) / 2.0)
        else:
            suspicious = max(skin * 5.0, bscore * 3.0)
        if suspicious > evidence_score:
            evidence_score = suspicious
            evidence_frame = frame.copy()

    cap.release()

    skin_fail = max_skin >= float(cfg.get("skin_frac_fail", 0.15))
    border_fail = max_border >= float(cfg.get("border_leak_fail", 0.85))
    border_review = max_border >= float(cfg.get("border_leak_review", 0.65))

    if face_hits > 0 or person_hits > 0 or skin_fail or border_fail:
        result = "FAIL"
        reason = "FACE" if face_hits > 0 else ("PERSON" if person_hits > 0 else ("SKIN" if skin_fail else "BORDER"))
    elif border_review:
        result = "REVIEW"
        reason = "BORDER_REVIEW"
    else:
        result = "PASS"
        reason = ""

    return {
        "result": result,
        "reason": reason,
        "face_hits": int(face_hits),
        "person_hits": int(person_hits),
        "max_skin_frac": float(max_skin),
        "border_leak_max": float(max_border),
        "evidence_frame": evidence_frame
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset_root", required=True, help="Path to dataset root (contains records/)")
    ap.add_argument("--manifest", required=True, help="Path to manifest CSV/XLSX (must include record_id)")
    ap.add_argument("--config", default="config/privacy_content_guardrails_v2_config.json", help="Config JSON path")
    ap.add_argument("--out_dir", default=None, help="Override outputs dir (default from config)")
    args = ap.parse_args()

    dataset_root = Path(args.dataset_root)
    manifest_path = Path(args.manifest)
    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        if not cfg_path.exists():
            automation_root = Path(__file__).resolve().parents[1]
            local_candidate = automation_root / cfg_path
            if local_candidate.exists():
                cfg_path = local_candidate

    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir) if args.out_dir else (dataset_root / cfg.get("outputs_dirname", "outputs/privacy_content_guardrails_v2"))
    ensure_dir(out_dir)
    evidence_dir = out_dir / "evidence"
    ensure_dir(evidence_dir)

    df = load_manifest(manifest_path)

    face, hog = init_detectors()

    rows: List[Dict[str, Any]] = []
    n_pass = n_fail = n_review = n_novideo = 0

    for _, r in df.iterrows():
        record_id = str(r["record_id"])
        # Allow explicit roi_video_path in manifest
        roi_path = None
        for col in ["roi_video_path", "roi_video", "roi_video_file"]:
            if col in df.columns and pd.notna(r.get(col)):
                roi_path = Path(str(r.get(col)))
                break
        if roi_path is None:
            rel = cfg.get("roi_video_default_relpath", "records/{record_id}/roi_video.mp4").format(record_id=record_id)
            roi_path = dataset_root / rel
        else:
            # if relative, resolve against dataset root
            if not roi_path.is_absolute():
                roi_path = dataset_root / roi_path

        if not roi_path.exists():
            rows.append({
                "record_id": record_id,
                "roi_video_path": str(roi_path),
                "result": "NO_VIDEO",
                "reason": "NO_VIDEO",
                "face_hits": 0,
                "person_hits": 0,
                "max_skin_frac": 0.0,
                "border_leak_max": 0.0,
                "evidence_file": ""
            })
            n_novideo += 1
            continue

        res = detect_on_video(roi_path, cfg, face, hog)
        evidence_file = ""
        if cfg.get("generate_evidence", False) and res.get("evidence_frame") is not None and res["result"] in ["FAIL", "REVIEW"]:
            mode = str(cfg.get("evidence_mode", "pixelate_edges"))
            down = int(cfg.get("evidence_downsample", 64))
            up = int(cfg.get("evidence_upscale", 256))
            thumb = make_evidence_thumbnail(res["evidence_frame"], mode=mode, down=down, up=up)
            # annotate minimally (non-identifying)
            canvas = thumb.copy()
            if canvas.ndim == 2:
                canvas = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)
            txt = f"{record_id} {res['result']} {res['reason']}"
            cv2.putText(canvas, txt[:40], (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
            evidence_file = str(evidence_dir / f"{record_id}_{res['result']}.png")
            cv2.imwrite(evidence_file, canvas)

        row = {
            "record_id": record_id,
            "roi_video_path": str(roi_path),
            "result": res["result"],
            "reason": res["reason"],
            "face_hits": res["face_hits"],
            "person_hits": res["person_hits"],
            "max_skin_frac": round(res["max_skin_frac"], 6),
            "border_leak_max": round(res["border_leak_max"], 6),
            "evidence_file": evidence_file
        }
        rows.append(row)

        if res["result"] == "PASS":
            n_pass += 1
        elif res["result"] == "FAIL":
            n_fail += 1
        else:
            n_review += 1

    out_csv = out_dir / "privacy_content_guardrails_v2.csv"
    out_json = out_dir / "privacy_content_guardrails_v2_summary.json"

    out_df = pd.DataFrame(rows)
    out_df.to_csv(out_csv, index=False)

    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "records_total": int(len(rows)),
        "pass": int(n_pass),
        "fail": int(n_fail),
        "review": int(n_review),
        "no_video": int(n_novideo),
        "fail_rate_excluding_no_video": float(n_fail / max(1, (len(rows) - n_novideo))),
        "config": cfg
    }
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"[OK] Wrote: {out_csv}")
    print(f"[OK] Wrote: {out_json}")


if __name__ == "__main__":
    main()
