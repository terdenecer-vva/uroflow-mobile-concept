#!/usr/bin/env python3
"""Post pilot automation JSON reports to Clinical Hub API."""

from __future__ import annotations

import argparse
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib import error, request


@dataclass(frozen=True)
class ReportInput:
    report_type: str
    path: Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Clinical Hub base URL.")
    parser.add_argument("--api-key", required=True, help="Clinical Hub API key.")
    parser.add_argument("--site-id", required=True, help="Site ID for report records.")
    parser.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format.")
    parser.add_argument("--package-version", default="v2.8")
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--dataset-id", default=None)
    parser.add_argument("--notes", default=None)
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument("--qa-summary-json")
    parser.add_argument("--g1-eval-json")
    parser.add_argument("--tfl-summary-json")
    parser.add_argument("--drift-summary-json")
    parser.add_argument("--gate-summary-json")
    return parser.parse_args()


def _load_json_object(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _collect_reports(args: argparse.Namespace) -> list[ReportInput]:
    candidates = [
        ("qa_summary", args.qa_summary_json),
        ("g1_eval", args.g1_eval_json),
        ("tfl_summary", args.tfl_summary_json),
        ("drift_summary", args.drift_summary_json),
        ("gate_summary", args.gate_summary_json),
    ]
    reports: list[ReportInput] = []
    for report_type, raw_path in candidates:
        if not raw_path:
            continue
        path = Path(raw_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        reports.append(ReportInput(report_type=report_type, path=path))
    if not reports:
        raise ValueError("at least one report JSON must be provided")
    return reports


def _post_report(
    *,
    base_url: str,
    api_key: str,
    site_id: str,
    report_date: str,
    package_version: str | None,
    model_id: str | None,
    dataset_id: str | None,
    notes: str | None,
    report: ReportInput,
    timeout_s: float,
) -> int:
    payload = {
        "site_id": site_id,
        "report_date": report_date,
        "report_type": report.report_type,
        "package_version": package_version,
        "model_id": model_id,
        "dataset_id": dataset_id,
        "payload": _load_json_object(report.path),
        "notes": notes,
    }

    endpoint = base_url.rstrip("/") + "/api/v1/pilot-automation-reports"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        endpoint,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "x-site-id": site_id,
            "x-actor-role": "data_manager",
            "x-request-id": f"ci-{uuid.uuid4().hex[:12]}",
        },
    )
    try:
        with request.urlopen(req, timeout=timeout_s) as response:  # noqa: S310
            response_body = response.read().decode("utf-8")
            payload_response = json.loads(response_body)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            "POST "
            f"{endpoint} failed: status={exc.code}, "
            f"report_type={report.report_type}, body={body}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(
            f"POST {endpoint} failed: report_type={report.report_type}, reason={exc.reason}"
        ) from exc

    record_id = payload_response.get("id")
    if not isinstance(record_id, int):
        raise RuntimeError(
            f"unexpected response for report_type={report.report_type}: {payload_response}"
        )
    return record_id


def main() -> int:
    args = _parse_args()
    reports = _collect_reports(args)

    created_ids: list[int] = []
    for report in reports:
        record_id = _post_report(
            base_url=args.base_url,
            api_key=args.api_key,
            site_id=args.site_id,
            report_date=args.report_date,
            package_version=args.package_version,
            model_id=args.model_id,
            dataset_id=args.dataset_id,
            notes=args.notes,
            report=report,
            timeout_s=args.timeout_s,
        )
        created_ids.append(record_id)
        print(f"Uploaded {report.report_type}: id={record_id}, file={report.path}")

    print(f"Uploaded {len(created_ids)} report(s) to Clinical Hub")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
