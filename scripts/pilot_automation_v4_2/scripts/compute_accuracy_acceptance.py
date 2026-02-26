#!/usr/bin/env python3
"""compute_accuracy_acceptance.py  (v4.1)

Computes agreement / accuracy metrics between reference Q_ref and app outputs.

Inputs:
- --dataset_root
- --manifest (csv/xlsx with record_id)
- --config (defaults to config/acceptance_metrics_config.json)

The script is best-effort:
- Reference: records/<record_id>/Q_ref.csv (required for evaluation)
- Predictions: tries, in order:
  1) records/<record_id>/Q_pred.csv  (time series)
  2) records/<record_id>/app_result.json (summary metrics)
  3) meta.json -> results_summary (summary metrics)

Quality gating:
- Uses meta.json -> quality_summary (quality_score, quality_class)
- Includes only records meeting allowed quality_class and min_quality_score in evaluation

Outputs:
- outputs/accuracy_acceptance/record_level_metrics.csv
- outputs/accuracy_acceptance/accuracy_summary.json
- outputs/accuracy_acceptance/acceptance_result.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List

import pandas as pd
import numpy as np


def load_manifest(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)
    if "record_id" not in df.columns:
        raise ValueError("Manifest must include record_id")
    df["record_id"] = df["record_id"].astype(str)
    return df


def read_json(p: Path) -> Optional[Dict[str, Any]]:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def detect_time_col(df: pd.DataFrame) -> Optional[str]:
    for c in ["t_s", "t", "time_s", "time", "seconds"]:
        if c in df.columns:
            return c
    return None


def detect_flow_col(df: pd.DataFrame) -> Optional[str]:
    # common candidates for flow in ml/s
    for c in ["Q_ml_s", "q_ml_s", "flow_ml_s", "flow", "Q", "q", "rate_ml_s", "rate"]:
        if c in df.columns:
            return c
    # fallback: first numeric column besides time
    for c in df.columns:
        if c.lower() in ("t_s", "t", "time_s", "time", "seconds"):
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            return c
    return None


def compute_metrics_from_timeseries(df: pd.DataFrame, flow_threshold: float = 0.2) -> Tuple[Optional[Dict[str, float]], str]:
    """Returns metrics dict or None + reason."""
    tcol = detect_time_col(df)
    qcol = detect_flow_col(df)
    if tcol is None or qcol is None:
        return None, "MISSING_COLUMNS"

    try:
        t = df[tcol].astype(float).to_numpy()
        q = df[qcol].astype(float).to_numpy()
    except Exception:
        return None, "PARSE_ERROR"

    if len(t) < 3:
        return None, "TOO_SHORT"

    # ensure sorted by time
    order = np.argsort(t)
    t = t[order]
    q = q[order]

    # flow mask
    mask = q > float(flow_threshold)
    if not np.any(mask):
        return None, "NO_FLOW_DETECTED"

    idx = np.where(mask)[0]
    i0, i1 = int(idx[0]), int(idx[-1])

    t_flow = t[i0:i1+1]
    q_flow = q[i0:i1+1]
    if len(t_flow) < 2:
        return None, "FLOW_TOO_SHORT"

    flow_time = float(t_flow[-1] - t_flow[0])
    if flow_time <= 0:
        return None, "FLOW_TIME_NONPOSITIVE"

    # volume via trapezoid integral
    vvoid = float(np.trapz(q_flow, t_flow))
    qmax = float(np.max(q_flow))
    qavg = float(vvoid / flow_time)

    return {
        "Qmax_ml_s": qmax,
        "Qavg_ml_s": qavg,
        "Vvoid_ml": vvoid,
        "FlowTime_s": flow_time
    }, ""


def parse_pred_summary(obj: Dict[str, Any]) -> Optional[Dict[str, float]]:
    # flexible key mapping
    key_map = {
        "Qmax_ml_s": ["Qmax_ml_s", "qmax_ml_s", "qmax", "Qmax"],
        "Qavg_ml_s": ["Qavg_ml_s", "qavg_ml_s", "qavg", "Qavg"],
        "Vvoid_ml": ["Vvoid_ml", "vvoid_ml", "vvoid", "Vvoid", "voided_volume_ml"],
        "FlowTime_s": ["FlowTime_s", "flow_time_s", "tflow_s", "flow_time"],
    }
    out = {}
    for out_k, candidates in key_map.items():
        val = None
        for ck in candidates:
            if ck in obj:
                val = obj.get(ck)
                break
        if val is None:
            continue
        try:
            out[out_k] = float(val)
        except Exception:
            continue
    return out if out else None


def get_quality(meta: Optional[Dict[str, Any]]) -> Tuple[Optional[float], Optional[str]]:
    if not isinstance(meta, dict):
        return None, None
    qsum = meta.get("quality_summary")
    if not isinstance(qsum, dict):
        return None, None
    qs = qsum.get("quality_score")
    qc = qsum.get("quality_class")
    try:
        qs_f = float(qs) if qs is not None else None
    except Exception:
        qs_f = None
    qc_s = str(qc) if qc is not None else None
    return qs_f, qc_s


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset_root", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--config", default="config/acceptance_metrics_config.json")
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
    out_dir = dataset_root / cfg.get("outputs_dirname", "outputs/accuracy_acceptance")
    out_dir.mkdir(parents=True, exist_ok=True)

    dfm = load_manifest(manifest)
    flow_threshold = float(cfg.get("flow_threshold_ml_s", 0.2))
    min_qs = float(cfg.get("min_quality_score", 70))
    allowed_qc = set([str(x) for x in cfg.get("allowed_quality_class", ["VALID"])])
    min_valid_rate = float(cfg.get("min_valid_rate", 0.80))
    thr = cfg.get("thresholds", {})

    rows: List[Dict[str, Any]] = []

    for rid in dfm["record_id"].tolist():
        rec_dir = dataset_root / "records" / str(rid)
        meta = read_json(rec_dir / "meta.json")
        qs, qc = get_quality(meta)

        # Reference metrics
        ref_df = None
        ref_metrics = None
        ref_reason = ""
        qref_path = rec_dir / "Q_ref.csv"
        if qref_path.exists():
            try:
                ref_df = pd.read_csv(qref_path)
                ref_metrics, ref_reason = compute_metrics_from_timeseries(ref_df, flow_threshold=flow_threshold)
            except Exception:
                ref_metrics, ref_reason = None, "QREF_PARSE_ERROR"
        else:
            ref_metrics, ref_reason = None, "QREF_MISSING"

        # Pred metrics
        pred_metrics = None
        pred_source = ""
        pred_reason = ""

        # 1) Q_pred.csv
        qpred_path = rec_dir / "Q_pred.csv"
        if qpred_path.exists():
            try:
                pred_df = pd.read_csv(qpred_path)
                pred_metrics, pred_reason = compute_metrics_from_timeseries(pred_df, flow_threshold=flow_threshold)
                pred_source = "Q_pred.csv"
            except Exception:
                pred_metrics, pred_reason = None, "QPRED_PARSE_ERROR"

        # 2) app_result.json
        if pred_metrics is None:
            app_res = read_json(rec_dir / "app_result.json")
            if isinstance(app_res, dict):
                pm = parse_pred_summary(app_res)
                if pm:
                    pred_metrics = pm
                    pred_source = "app_result.json"
                else:
                    pred_reason = "APP_RESULT_NO_KEYS"

        # 3) meta.json results_summary
        if pred_metrics is None and isinstance(meta, dict):
            rs = meta.get("results_summary") or meta.get("results") or meta.get("output_summary")
            if isinstance(rs, dict):
                pm = parse_pred_summary(rs)
                if pm:
                    pred_metrics = pm
                    pred_source = "meta.results_summary"
                else:
                    pred_reason = "META_RESULTS_NO_KEYS"

        # Quality include
        include_eval = True
        include_reasons = []
        if qc is None or qs is None:
            include_eval = False
            include_reasons.append("QUALITY_MISSING")
        else:
            if str(qc) not in allowed_qc:
                include_eval = False
                include_reasons.append(f"QUALITY_CLASS_{qc}")
            if float(qs) < min_qs:
                include_eval = False
                include_reasons.append("QUALITY_SCORE_BELOW_MIN")

        if ref_metrics is None:
            include_eval = False
            include_reasons.append(ref_reason or "REF_METRICS_MISSING")
        if pred_metrics is None:
            include_eval = False
            include_reasons.append(pred_reason or "PRED_METRICS_MISSING")

        # errors
        def err(a: Optional[float], b: Optional[float]) -> Optional[float]:
            if a is None or b is None:
                return None
            return float(b - a)

        qmax_ref = ref_metrics.get("Qmax_ml_s") if ref_metrics else None
        qavg_ref = ref_metrics.get("Qavg_ml_s") if ref_metrics else None
        vvoid_ref = ref_metrics.get("Vvoid_ml") if ref_metrics else None
        tflow_ref = ref_metrics.get("FlowTime_s") if ref_metrics else None

        qmax_pred = pred_metrics.get("Qmax_ml_s") if pred_metrics else None
        qavg_pred = pred_metrics.get("Qavg_ml_s") if pred_metrics else None
        vvoid_pred = pred_metrics.get("Vvoid_ml") if pred_metrics else None
        tflow_pred = pred_metrics.get("FlowTime_s") if pred_metrics else None

        rows.append({
            "record_id": str(rid),
            "quality_score": qs if qs is not None else "",
            "quality_class": qc if qc is not None else "",
            "ref_Qmax_ml_s": qmax_ref if qmax_ref is not None else "",
            "pred_Qmax_ml_s": qmax_pred if qmax_pred is not None else "",
            "err_Qmax_ml_s": err(qmax_ref, qmax_pred) if include_eval else "",
            "ref_Qavg_ml_s": qavg_ref if qavg_ref is not None else "",
            "pred_Qavg_ml_s": qavg_pred if qavg_pred is not None else "",
            "err_Qavg_ml_s": err(qavg_ref, qavg_pred) if include_eval else "",
            "ref_Vvoid_ml": vvoid_ref if vvoid_ref is not None else "",
            "pred_Vvoid_ml": vvoid_pred if vvoid_pred is not None else "",
            "err_Vvoid_ml": err(vvoid_ref, vvoid_pred) if include_eval else "",
            "ref_FlowTime_s": tflow_ref if tflow_ref is not None else "",
            "pred_FlowTime_s": tflow_pred if tflow_pred is not None else "",
            "err_FlowTime_s": err(tflow_ref, tflow_pred) if include_eval else "",
            "pred_source": pred_source,
            "include_in_eval": bool(include_eval),
            "include_reasons": ";".join(include_reasons),
        })

    out_df = pd.DataFrame(rows)
    out_df.to_csv(out_dir / "record_level_metrics.csv", index=False)

    # compute summary on included
    inc = out_df[out_df["include_in_eval"] == True]  # noqa: E712
    n_total = int(len(out_df))
    n_inc = int(len(inc))

    def mae(series: pd.Series) -> Optional[float]:
        vals = pd.to_numeric(series, errors="coerce").dropna().abs()
        if len(vals) == 0:
            return None
        return float(vals.mean())

    def bland_altman(err_series: pd.Series) -> Optional[Dict[str, float]]:
        vals = pd.to_numeric(err_series, errors="coerce").dropna()
        if len(vals) < 3:
            return None
        bias = float(vals.mean())
        sd = float(vals.std(ddof=1))
        loa_low = bias - 1.96 * sd
        loa_high = bias + 1.96 * sd
        return {
            "n": int(len(vals)),
            "bias": bias,
            "sd": sd,
            "loa_low": float(loa_low),
            "loa_high": float(loa_high),
            "loa_half_width": float((loa_high - loa_low) / 2.0),
        }

    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "records_total": n_total,
        "records_included_eval": n_inc,
        "valid_rate_eval": float(n_inc / max(1, n_total)),
        "min_valid_rate_required": min_valid_rate,
        "mae": {
            "Qmax_ml_s": mae(inc.get("err_Qmax_ml_s", pd.Series(dtype=float))),
            "Qavg_ml_s": mae(inc.get("err_Qavg_ml_s", pd.Series(dtype=float))),
            "Vvoid_ml": mae(inc.get("err_Vvoid_ml", pd.Series(dtype=float))),
            "FlowTime_s": mae(inc.get("err_FlowTime_s", pd.Series(dtype=float))),
        },
        "bland_altman": {
            "Qmax": bland_altman(inc.get("err_Qmax_ml_s", pd.Series(dtype=float)))
        },
        "thresholds": thr,
        "config": cfg
    }
    (out_dir / "accuracy_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # acceptance decision
    checks = []
    # valid rate
    checks.append({
        "check": "valid_rate_eval",
        "threshold": min_valid_rate,
        "actual": summary["valid_rate_eval"],
        "pass": bool(summary["valid_rate_eval"] >= min_valid_rate)
    })

    # MAE checks
    for k, thr_val in thr.items():
        if not k.endswith("_mae_ml_s") and not k.endswith("_mae_ml") and not k.endswith("_mae_s") and not k.endswith("_loa_halfwidth_ml_s"):
            continue
    # explicit mapping
    mae_map = {
        "Qmax_mae_ml_s": ("mae", "Qmax_ml_s"),
        "Qavg_mae_ml_s": ("mae", "Qavg_ml_s"),
        "Vvoid_mae_ml": ("mae", "Vvoid_ml"),
        "FlowTime_mae_s": ("mae", "FlowTime_s"),
    }
    for thr_key, (grp, key) in mae_map.items():
        if thr_key in thr:
            actual = summary.get(grp, {}).get(key)
            checks.append({
                "check": thr_key,
                "threshold": float(thr[thr_key]),
                "actual": actual,
                "pass": (actual is not None) and (float(actual) <= float(thr[thr_key]))
            })

    # BA check
    if "Qmax_loa_halfwidth_ml_s" in thr:
        ba = summary.get("bland_altman", {}).get("Qmax")
        actual = ba.get("loa_half_width") if isinstance(ba, dict) else None
        checks.append({
            "check": "Qmax_loa_halfwidth_ml_s",
            "threshold": float(thr["Qmax_loa_halfwidth_ml_s"]),
            "actual": actual,
            "pass": (actual is not None) and (float(actual) <= float(thr["Qmax_loa_halfwidth_ml_s"]))
        })

    overall_pass = all(bool(c.get("pass")) for c in checks)

    result = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "overall_pass": bool(overall_pass),
        "checks": checks,
        "summary_path": str(out_dir / "accuracy_summary.json")
    }
    (out_dir / "acceptance_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"[OK] Wrote: {out_dir}")
    print(f"[OK] OVERALL: {'PASS' if overall_pass else 'FAIL'}")


if __name__ == "__main__":
    main()
