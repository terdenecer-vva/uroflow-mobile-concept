#!/usr/bin/env python3
"""
run_pre_freeze_gates.py  (v3.8)

Creates a single pre-freeze gate report to decide whether DatasetRelease/ModelRelease can be frozen.

This script is designed to be compatible with a larger Uroflow automation stack.
It can run in a "best-effort" mode:
- Reads existing outputs if present (privacy LIVE, privacy content guardrails, standpose drift dashboard, sync validation, daily QA).
- Always runs a minimal storage-level privacy scan (forbidden artifact patterns).

Outputs:
- outputs/pre_freeze_gates/pre_freeze_gates_report.json
- outputs/pre_freeze_gates/pre_freeze_gates_report.csv
- outputs/pre_freeze_gates/pre_freeze_gates_summary.txt
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
    return df


def latest_file(folder: Path, pattern: str) -> Path | None:
    files = sorted(folder.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def scan_forbidden_artifacts(dataset_root: Path, patterns: List[str]) -> List[str]:
    hits = []
    for pat in patterns:
        for fp in dataset_root.glob(pat):
            hits.append(str(fp))
    return sorted(list(set(hits)))




def norm_sex(x: Any) -> str:
    if x is None:
        return 'UNK'
    s = str(x).strip().lower()
    if s in ('m','male','man','м','муж','мужчина'):
        return 'M'
    if s in ('f','female','woman','ж','жен','женщина'):
        return 'F'
    return 'UNK'


def norm_posture(x: Any) -> str:
    if x is None:
        return 'UNK'
    s = str(x).strip().lower()
    if s in ('standing','stand','стоя','сто','st'):
        return 'standing'
    if s in ('sitting','sit','сидя','сид','si'):
        return 'sitting'
    return 'UNK'


def compute_coverage_from_manifest(dfm: pd.DataFrame, targets: Dict[str, Any]) -> Dict[str, Any]:
    required_cols = targets.get('required_columns', [])
    missing_cols = [c for c in required_cols if c not in dfm.columns]

    df = dfm.copy()
    df['sex_norm'] = df['sex'].apply(norm_sex) if 'sex' in df.columns else 'UNK'
    df['posture_norm'] = df['posture'].apply(norm_posture) if 'posture' in df.columns else 'UNK'
    df['sex_posture'] = df['sex_norm'] + '|' + df['posture_norm']

    total_n = int(len(df))
    by_sex = df['sex_norm'].value_counts(dropna=False).to_dict()
    by_sex_posture = df['sex_posture'].value_counts(dropna=False).to_dict()
    by_site = df['site_id'].astype(str).value_counts(dropna=False).to_dict() if 'site_id' in df.columns else {}
    by_toilet = df['toilet_id'].astype(str).value_counts(dropna=False).to_dict() if 'toilet_id' in df.columns else {}

    checks = []
    min_total = int(targets.get('min_total_records', 0))
    checks.append({'check':'min_total_records','target':min_total,'actual':total_n,'pass': total_n >= min_total})

    for k, v in (targets.get('min_by_sex') or {}).items():
        actual = int(by_sex.get(k, 0))
        checks.append({'check':f"min_by_sex:{k}", 'target':int(v), 'actual':actual, 'pass': actual >= int(v)})

    for k, v in (targets.get('min_by_sex_posture') or {}).items():
        actual = int(by_sex_posture.get(k, 0))
        checks.append({'check':f"min_by_sex_posture:{k}", 'target':int(v), 'actual':actual, 'pass': actual >= int(v)})

    min_sites = int(targets.get('min_sites', 0))
    actual_sites = int(len([k for k in by_site.keys() if k and k != 'nan']))
    checks.append({'check':'min_sites','target':min_sites,'actual':actual_sites,'pass': actual_sites >= min_sites})

    min_per_site = int(targets.get('min_records_per_site', 0))
    if min_per_site > 0 and by_site:
        site_fails = {k:int(v) for k,v in by_site.items() if int(v) < min_per_site}
        checks.append({'check':'min_records_per_site','target':min_per_site,'actual':{'fail_sites':site_fails},'pass': len(site_fails)==0})

    min_per_toilet = int(targets.get('min_records_per_toilet', 0))
    if min_per_toilet > 0 and by_toilet:
        toilet_fails = {k:int(v) for k,v in by_toilet.items() if int(v) < min_per_toilet}
        checks.append({'check':'min_records_per_toilet','target':min_per_toilet,'actual':{'fail_toilets':toilet_fails},'pass': len(toilet_fails)==0})

    overall_pass = (len(missing_cols)==0) and all(bool(c['pass']) for c in checks)

    return {
        'overall_pass': bool(overall_pass),
        'missing_required_columns': missing_cols,
        'total_records': total_n,
        'by_sex': by_sex,
        'by_sex_posture': by_sex_posture,
        'by_site': by_site,
        'by_toilet': by_toilet,
        'checks': checks,
        'targets': targets
    }


def extract_sync_offset_s(d: Dict[str, Any]) -> float | None:
    for k in ['sync_offset_s','sync_offset_seconds','sync_offset','offset_s','offset_seconds']:
        if k in d:
            try:
                return float(d[k])
            except Exception:
                return None
    return None


def compute_sync_summary(dataset_root: Path, record_ids: List[str]) -> Dict[str, Any] | None:
    offsets = []
    missing = 0
    no_offset = 0
    for rid in record_ids:
        p = dataset_root / 'records' / str(rid) / 'ref_alignment.json'
        if not p.exists():
            missing += 1
            continue
        try:
            d = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            no_offset += 1
            continue
        off = extract_sync_offset_s(d)
        if off is None:
            no_offset += 1
            continue
        offsets.append(abs(off))

    if not offsets and (missing > 0 or no_offset > 0):
        return {
            'generated_at': datetime.utcnow().isoformat() + 'Z',
            'records_total': int(len(record_ids)),
            'records_with_offset': 0,
            'max_abs_sync_offset_s': None,
            'missing_alignment_count': int(missing),
            'no_offset_count': int(no_offset)
        }

    if not offsets:
        return None

    return {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'records_total': int(len(record_ids)),
        'records_with_offset': int(len(offsets)),
        'max_abs_sync_offset_s': float(max(offsets)),
        'missing_alignment_count': int(missing),
        'no_offset_count': int(no_offset)
    }


def compute_daily_qa_summary(dataset_root: Path, record_ids: List[str]) -> Dict[str, Any]:
    required_files = ['meta.json', 'Q_ref.csv', 'ref_import_log.json', 'ref_alignment.json']
    fail = 0
    for rid in record_ids:
        rec_dir = dataset_root / 'records' / str(rid)
        missing = 0
        for fn in required_files:
            if not (rec_dir / fn).exists():
                missing += 1
        # basic Q_ref non-empty check
        qref = rec_dir / 'Q_ref.csv'
        if qref.exists():
            try:
                qdf = pd.read_csv(qref)
                if len(qdf) == 0:
                    missing += 1
            except Exception:
                missing += 1
        if missing > 0:
            fail += 1

    return {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'records_total': int(len(record_ids)),
        'fail_count': int(fail),
        'overall_pass': bool(fail == 0)
    }

def compute_valid_rate_from_meta(dataset_root: Path, record_ids: List[str], min_quality_score: float = 70.0) -> Dict[str, Any]:
    """Best-effort valid-rate computation based on meta.json quality_summary.
    Valid = quality_class == 'VALID' and quality_score >= min_quality_score.
    """
    valid = 0
    missing_meta = 0
    missing_quality = 0
    for rid in record_ids:
        meta_p = dataset_root / 'records' / str(rid) / 'meta.json'
        if not meta_p.exists():
            missing_meta += 1
            continue
        try:
            meta = json.loads(meta_p.read_text(encoding='utf-8'))
        except Exception:
            missing_meta += 1
            continue
        qsum = meta.get('quality_summary') if isinstance(meta, dict) else None
        if not isinstance(qsum, dict):
            missing_quality += 1
            continue
        qc = qsum.get('quality_class')
        qs = qsum.get('quality_score')
        try:
            qs_f = float(qs)
        except Exception:
            qs_f = None
        if str(qc) == 'VALID' and qs_f is not None and qs_f >= float(min_quality_score):
            valid += 1
    total = max(1, len(record_ids))
    return {
        'records_total': int(len(record_ids)),
        'valid_count': int(valid),
        'valid_rate': float(valid / total),
        'missing_meta_count': int(missing_meta),
        'missing_quality_count': int(missing_quality),
        'min_quality_score': float(min_quality_score),
    }

def read_json_if_exists(p: Path) -> Dict[str, Any] | None:
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset_root", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--config", default="config/pre_freeze_gates_config.json")

    ap.add_argument("--privacy_live_csv", default=None, help="Optional override path to privacy_live_guardrails.csv")
    ap.add_argument("--privacy_content_csv", default=None, help="Optional override path to privacy_content_guardrails_v2.csv")
    ap.add_argument("--standpose_drift_json", default=None, help="Optional override path to drift_summary.json")
    ap.add_argument("--daily_qa_json", default=None, help="Optional override path to qa_summary.json")
    ap.add_argument("--sync_json", default=None, help="Optional override path to sync validation summary json")
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

    out_dir = dataset_root / cfg.get("outputs_dirname", "outputs/pre_freeze_gates")
    out_dir.mkdir(parents=True, exist_ok=True)

    dfm = load_manifest(manifest)
    record_ids = dfm["record_id"].astype(str).tolist()

    # Gate: PRIV_LIVE (on-device privacy guardrails metadata)
    live_csv = Path(args.privacy_live_csv) if args.privacy_live_csv else (dataset_root / "outputs/privacy_live_guardrails/privacy_live_guardrails.csv")
    if not live_csv.exists():
        folder = dataset_root / "outputs/privacy_live_guardrails"
        lf = latest_file(folder, "*.csv") if folder.exists() else None
        if lf:
            live_csv = lf

    live_used = False
    live_df = None
    live_pass = True
    live_fail_n = 0
    live_missing_n = 0
    if live_csv.exists():
        live_used = True
        try:
            live_df = pd.read_csv(live_csv)
            if "result" in live_df.columns:
                live_fail_n = int((live_df["result"] == "FAIL").sum())
                live_missing_n = int((live_df["result"] == "MISSING").sum())
                live_pass = (live_fail_n == 0 and live_missing_n == 0)
            else:
                live_pass = False
        except Exception:
            live_pass = False
    else:
        # If required and missing -> fail
        live_pass = False

    gate_priv_live = {
        "name": "PRIV_LIVE",
        "required": "PRIV_LIVE" in cfg.get("required_gates", []),
        "pass": bool(live_pass) if ("PRIV_LIVE" in cfg.get("required_gates", [])) else True,
        "details": {
            "live_csv_found": bool(live_used),
            "live_csv_path": str(live_csv) if live_used else "",
            "fail_count": int(live_fail_n),
            "missing_count": int(live_missing_n),
        }
    }

    # Gate: PRIV_STORAGE (forbidden artifact patterns)
    forbidden = scan_forbidden_artifacts(dataset_root, cfg.get("forbidden_artifact_patterns", []))
    gate_priv_store = {
        "name": "PRIV_STORAGE",
        "required": "PRIV_STORAGE" in cfg.get("required_gates", []),
        "pass": len(forbidden) == 0,
        "details": {
            "forbidden_hits": forbidden[:50],
            "forbidden_hits_count": len(forbidden)
        }
    }

    # Gate: PRIV_CONTENT (conditional on ROI video presence)
    priv_content_csv = Path(args.privacy_content_csv) if args.privacy_content_csv else (dataset_root / "outputs/privacy_content_guardrails_v2/privacy_content_guardrails_v2.csv")
    if not priv_content_csv.exists():
        folder = dataset_root / "outputs/privacy_content_guardrails_v2"
        lf = latest_file(folder, "*.csv") if folder.exists() else None
        if lf:
            priv_content_csv = lf

    roi_video_present = any((dataset_root / "records" / str(rid) / "roi_video.mp4").exists() for rid in record_ids)

    priv_content_pass = True
    priv_content_fail_n = 0
    priv_content_no_video_n = 0
    priv_content_used = False
    priv_content_df = None
    if priv_content_csv.exists():
        priv_content_used = True
        try:
            priv_content_df = pd.read_csv(priv_content_csv)
            if "result" in priv_content_df.columns:
                priv_content_fail_n = int((priv_content_df["result"] == "FAIL").sum())
                priv_content_no_video_n = int((priv_content_df["result"] == "NO_VIDEO").sum())
                priv_content_pass = (priv_content_fail_n == 0)
            else:
                priv_content_pass = False
        except Exception:
            priv_content_pass = False
    else:
        priv_content_pass = not (cfg.get("priv_content_required_if_video_present", True) and roi_video_present)

    gate_priv_content = {
        "name": "PRIV_CONTENT",
        "required": bool(cfg.get("priv_content_required_if_video_present", True) and roi_video_present),
        "pass": bool(priv_content_pass),
        "details": {
            "roi_video_present": bool(roi_video_present),
            "content_csv_found": bool(priv_content_used),
            "content_csv_path": str(priv_content_csv) if priv_content_used else "",
            "fail_count": int(priv_content_fail_n),
            "no_video_count": int(priv_content_no_video_n),
        }
    }

    # Gate: STANDPOSE
    drift_json = Path(args.standpose_drift_json) if args.standpose_drift_json else (dataset_root / "outputs/stand_pose_drift_dashboard/drift_summary.json")
    drift = read_json_if_exists(drift_json)
    standpose_pass = True
    if drift is not None:
        red_groups = int(drift.get("red_groups", 0))
        overall_pass_rate = float(drift.get("overall_pass_rate", 0.0))
        standpose_pass = (red_groups == 0) and (overall_pass_rate >= float(cfg.get("min_standpose_pass_rate", cfg.get("min_overall_valid_rate", 0.85))))
    else:
        standpose_pass = False
    gate_standpose = {
        "name": "STANDPOSE",
        "required": "STANDPOSE" in cfg.get("required_gates", []),
        "pass": bool(standpose_pass),
        "details": {
            "drift_summary_path": str(drift_json),
            "drift_summary_found": drift is not None,
            "red_groups": int(drift.get("red_groups", -1)) if drift else -1,
            "overall_pass_rate": float(drift.get("overall_pass_rate", -1.0)) if drift else -1.0,
        }
    }

    # Gate: SYNC
    sync_json = Path(args.sync_json) if args.sync_json else (dataset_root / "outputs/sync_validation/sync_validation_summary.json")
    sync = read_json_if_exists(sync_json)
    sync_pass = True
    if sync is not None:
        max_off = float(sync.get("max_abs_sync_offset_s", 0.0))
        sync_pass = max_off <= float(cfg.get("sync_offset_max_s", 1.0))
    else:
        # compute minimal sync summary from ref_alignment.json
        try:
            sync = compute_sync_summary(dataset_root, record_ids)
            if sync is not None:
                sync_json.parent.mkdir(parents=True, exist_ok=True)
                sync_json.write_text(json.dumps(sync, indent=2), encoding='utf-8')
                max_off = float(sync.get('max_abs_sync_offset_s', 0.0) or 0.0)
                sync_pass = max_off <= float(cfg.get('sync_offset_max_s', 1.0))
            else:
                sync_pass = False
        except Exception:
            sync_pass = False
    gate_sync = {
        "name": "SYNC",
        "required": "SYNC" in cfg.get("required_gates", []),
        "pass": bool(sync_pass),
        "details": {"sync_summary_path": str(sync_json), "sync_summary_found": sync is not None}
    }

    # Gate: DAILY_QA
    daily_json = Path(args.daily_qa_json) if args.daily_qa_json else (dataset_root / "outputs/daily_qa/qa_summary.json")
    qa = read_json_if_exists(daily_json)
    qa_pass = True
    if qa is not None:
        qa_pass = bool(qa.get("overall_pass", False))
    else:
        # compute minimal daily QA summary (file presence + Q_ref non-empty)
        try:
            qa = compute_daily_qa_summary(dataset_root, record_ids)
            daily_json.parent.mkdir(parents=True, exist_ok=True)
            daily_json.write_text(json.dumps(qa, indent=2), encoding='utf-8')
            qa_pass = bool(qa.get('overall_pass', False))
        except Exception:
            qa_pass = False
    gate_qa = {
        "name": "DAILY_QA",
        "required": "DAILY_QA" in cfg.get("required_gates", []),
        "pass": bool(qa_pass),
        "details": {"qa_summary_path": str(daily_json), "qa_summary_found": qa is not None}
    }

    # Gate: COVERAGE (dataset-level coverage targets)
    cov_summary_path = dataset_root / cfg.get('coverage_summary_path_default', 'outputs/coverage_dashboard/coverage_summary.json')
    cov = read_json_if_exists(cov_summary_path)
    cov_pass = True
    cov_details = {}
    if cov is None:
        # compute from manifest and targets
        try:
            targets_path = Path(cfg.get('coverage_targets_config', 'config/coverage_targets_config.json'))
            targets = json.loads(targets_path.read_text(encoding='utf-8')) if targets_path.exists() else {}
            cov = compute_coverage_from_manifest(dfm, targets)
            cov_summary_path.parent.mkdir(parents=True, exist_ok=True)
            cov_summary_path.write_text(json.dumps(cov, indent=2), encoding='utf-8')
        except Exception as e:
            cov = None
            cov_details = {'error': str(e)}

    if cov is not None:
        cov_pass = bool(cov.get('overall_pass', False))
        cov_details.update({
            'coverage_summary_path': str(cov_summary_path),
            'missing_required_columns': cov.get('missing_required_columns', []),
            'total_records': cov.get('total_records', -1),
            'checks': cov.get('checks', [])
        })
    else:
        cov_pass = False
        cov_details.update({'coverage_summary_path': str(cov_summary_path), 'coverage_summary_found': False})

    gate_coverage = {
        'name': 'COVERAGE',
        'required': 'COVERAGE' in cfg.get('required_gates', []),
        'pass': bool(cov_pass),
        'details': cov_details
    }



    # Gate: VALID_RATE (dataset-level valid measurement rate)
    valid_rate_details = {}
    valid_rate = None
    # Prefer record-level gates summary if available
    rlg_summary_path = dataset_root / 'outputs/record_level_gates/record_level_gates_summary.json'
    rlg = read_json_if_exists(rlg_summary_path)
    if rlg is not None and 'include_rate' in rlg:
        try:
            valid_rate = float(rlg.get('include_rate'))
        except Exception:
            valid_rate = None
        valid_rate_details = {
            'source': 'record_level_gates',
            'record_level_gates_summary_path': str(rlg_summary_path),
            'included': int(rlg.get('included', -1)),
            'records_total': int(rlg.get('records_total', -1)),
            'include_rate': valid_rate,
        }
    else:
        # Best-effort: compute from meta.json quality_summary
        vr = compute_valid_rate_from_meta(dataset_root, record_ids, float(cfg.get('min_quality_score_for_valid_rate', 70)))
        valid_rate = float(vr.get('valid_rate', 0.0))
        valid_rate_details = {'source': 'meta_quality_summary', **vr}

    min_valid_rate = float(cfg.get('min_valid_measurement_rate', 0.0))
    valid_rate_pass = (valid_rate is not None) and (valid_rate >= min_valid_rate)
    gate_valid_rate = {
        'name': 'VALID_RATE',
        'required': 'VALID_RATE' in cfg.get('required_gates', []),
        'pass': bool(valid_rate_pass),
        'details': {
            **valid_rate_details,
            'min_valid_measurement_rate': min_valid_rate,
        }
    }

    gates = [gate_priv_live, gate_priv_store, gate_priv_content, gate_standpose, gate_sync, gate_qa, gate_coverage, gate_valid_rate]

    required_failed = [g for g in gates if g["required"] and not g["pass"]]
    overall_pass = len(required_failed) == 0

    # record-level report (merge privacy live + privacy content results if available)
    out_df = dfm[["record_id"]].copy()
    out_df["record_id"] = out_df["record_id"].astype(str)

    if live_df is not None and "record_id" in live_df.columns and "result" in live_df.columns:
        tmp = live_df[["record_id", "result"]].copy()
        tmp["record_id"] = tmp["record_id"].astype(str)
        tmp = tmp.rename(columns={"result": "priv_live_result"})
        if "reason" in live_df.columns:
            tmp["priv_live_reason"] = live_df["reason"]
        out_df = out_df.merge(tmp, on="record_id", how="left")

    if priv_content_df is not None and "record_id" in priv_content_df.columns and "result" in priv_content_df.columns:
        tmp = priv_content_df[["record_id", "result"]].copy()
        tmp["record_id"] = tmp["record_id"].astype(str)
        tmp = tmp.rename(columns={"result": "priv_content_result"})
        if "reason" in priv_content_df.columns:
            tmp["priv_content_reason"] = priv_content_df["reason"]
        out_df = out_df.merge(tmp, on="record_id", how="left")

    out_df.to_csv(out_dir / "pre_freeze_gates_report.csv", index=False)

    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "overall_pass": bool(overall_pass),
        "required_failed": [g["name"] for g in required_failed],
        "gates": gates,
        "config": cfg
    }
    (out_dir / "pre_freeze_gates_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    summary_lines = [
        f"Pre-Freeze Gates Report - {report['generated_at']}",
        f"OVERALL: {'PASS' if overall_pass else 'FAIL'}",
        "",
        "Gate results:"
    ]
    for g in gates:
        summary_lines.append(f"- {g['name']}: {'PASS' if g['pass'] else 'FAIL'} (required={g['required']})")
    if required_failed:
        summary_lines.append("")
        summary_lines.append("Required failed:")
        for g in required_failed:
            summary_lines.append(f"  * {g['name']}")
    (out_dir / "pre_freeze_gates_summary.txt").write_text("\n".join(summary_lines), encoding="utf-8")

    print(f"[OK] Wrote: {out_dir / 'pre_freeze_gates_report.json'}")
    print(f"[OK] OVERALL: {'PASS' if overall_pass else 'FAIL'}")


if __name__ == "__main__":
    main()
