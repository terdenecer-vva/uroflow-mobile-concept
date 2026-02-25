from __future__ import annotations

import csv
import hashlib
import json
import math
import sqlite3
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

QUALITY_STATUS = Literal["valid", "repeat", "reject"]
CAPTURE_MODE = Literal["water_impact", "jet_in_air_assist", "fallback_non_water"]
PLATFORM = Literal["ios", "android"]
ACTOR_ROLE = Literal["operator", "investigator", "data_manager", "admin"]
PILOT_REPORT_TYPE = Literal[
    "qa_summary",
    "g1_eval",
    "tfl_summary",
    "drift_summary",
    "gate_summary",
]
_CROSS_SITE_ALLOWED_ROLES = {"data_manager", "admin"}


class FlowMetrics(BaseModel):
    qmax_ml_s: float = Field(ge=0)
    qavg_ml_s: float = Field(ge=0)
    vvoid_ml: float = Field(ge=0)
    flow_time_s: float | None = Field(default=None, ge=0)
    tqmax_s: float | None = Field(default=None, ge=0)


class SessionMeta(BaseModel):
    session_id: str = Field(min_length=1)
    site_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    operator_id: str = Field(min_length=1)
    attempt_number: int = Field(default=1, ge=1)
    measured_at: datetime
    platform: PLATFORM
    device_model: str | None = None
    app_version: str | None = None
    capture_mode: CAPTURE_MODE = "water_impact"


class AppMeasurement(BaseModel):
    metrics: FlowMetrics
    quality_status: QUALITY_STATUS
    quality_score: float | None = Field(default=None, ge=0, le=100)
    model_id: str | None = None


class ReferenceMeasurement(BaseModel):
    metrics: FlowMetrics
    device_model: str | None = None
    device_serial: str | None = None


class PairedMeasurementCreate(BaseModel):
    session: SessionMeta
    app: AppMeasurement
    reference: ReferenceMeasurement
    notes: str | None = None


class PairedMeasurementRecord(BaseModel):
    id: int
    created_at: datetime
    session: SessionMeta
    app: AppMeasurement
    reference: ReferenceMeasurement
    notes: str | None = None


class PairedMeasurementListItem(BaseModel):
    id: int
    created_at: datetime
    measured_at: datetime
    session_id: str
    site_id: str
    subject_id: str
    attempt_number: int
    platform: PLATFORM
    app_quality_status: QUALITY_STATUS
    app_qmax_ml_s: float
    ref_qmax_ml_s: float
    app_vvoid_ml: float
    ref_vvoid_ml: float


class MethodComparisonFilters(BaseModel):
    site_id: str | None = None
    subject_id: str | None = None
    platform: PLATFORM | None = None
    capture_mode: CAPTURE_MODE | None = None
    quality_status: QUALITY_STATUS | None = "valid"


class MetricComparisonSummary(BaseModel):
    metric: str
    paired_samples: int
    mean_app: float | None = None
    mean_reference: float | None = None
    mean_error: float | None = None
    mean_absolute_error: float | None = None
    rmse: float | None = None
    mape_pct: float | None = None
    pearson_r: float | None = None
    bland_altman_bias: float | None = None
    bland_altman_loa_lower: float | None = None
    bland_altman_loa_upper: float | None = None


class MethodComparisonSummary(BaseModel):
    generated_at: datetime
    filters: MethodComparisonFilters
    records_matched_filters: int
    records_considered: int
    quality_distribution: dict[str, int]
    metrics: list[MetricComparisonSummary]


class CapturePackageCreate(BaseModel):
    session: SessionMeta
    package_type: Literal["capture_contract_json", "feature_bundle", "media_manifest"] = (
        "capture_contract_json"
    )
    capture_payload: dict[str, object]
    paired_measurement_id: int | None = Field(default=None, ge=1)
    notes: str | None = None


class CapturePackageRecord(BaseModel):
    id: int
    created_at: datetime
    session: SessionMeta
    package_type: Literal["capture_contract_json", "feature_bundle", "media_manifest"]
    capture_payload: dict[str, object]
    paired_measurement_id: int | None = None
    notes: str | None = None


class CapturePackageListItem(BaseModel):
    id: int
    created_at: datetime
    measured_at: datetime
    session_id: str
    site_id: str
    subject_id: str
    operator_id: str
    attempt_number: int
    platform: PLATFORM
    package_type: Literal["capture_contract_json", "feature_bundle", "media_manifest"]
    paired_measurement_id: int | None = None


class PilotAutomationReportCreate(BaseModel):
    site_id: str = Field(min_length=1)
    report_date: date
    report_type: PILOT_REPORT_TYPE
    package_version: str | None = None
    model_id: str | None = None
    dataset_id: str | None = None
    payload: dict[str, object]
    notes: str | None = None


class PilotAutomationReportRecord(BaseModel):
    id: int
    created_at: datetime
    site_id: str
    report_date: date
    report_type: PILOT_REPORT_TYPE
    package_version: str | None = None
    model_id: str | None = None
    dataset_id: str | None = None
    payload: dict[str, object]
    notes: str | None = None


class PilotAutomationReportListItem(BaseModel):
    id: int
    created_at: datetime
    site_id: str
    report_date: date
    report_type: PILOT_REPORT_TYPE
    package_version: str | None = None
    model_id: str | None = None
    dataset_id: str | None = None


class AuditEventItem(BaseModel):
    id: int
    created_at: datetime
    method: str
    path: str
    status_code: int
    auth_result: str
    api_key_fingerprint: str | None = None
    actor_operator_id: str | None = None
    actor_role: str | None = None
    actor_site_id: str | None = None
    request_id: str | None = None
    session_id: str | None = None
    site_id: str | None = None
    subject_id: str | None = None
    operator_id: str | None = None
    remote_addr: str | None = None
    detail_json: str | None = None


class ApiKeyPolicy(BaseModel):
    role: ACTOR_ROLE
    site_id: str | None = None
    operator_id: str | None = None


METRIC_COLUMNS: dict[str, tuple[str, str]] = {
    "qmax_ml_s": ("app_qmax_ml_s", "ref_qmax_ml_s"),
    "qavg_ml_s": ("app_qavg_ml_s", "ref_qavg_ml_s"),
    "vvoid_ml": ("app_vvoid_ml", "ref_vvoid_ml"),
    "flow_time_s": ("app_flow_time_s", "ref_flow_time_s"),
    "tqmax_s": ("app_tqmax_s", "ref_tqmax_s"),
}


def _normalize_site_id(site_id: str | None) -> str | None:
    if site_id is None:
        return None
    stripped = site_id.strip()
    if not stripped:
        return None
    return stripped


def _normalize_operator_id(operator_id: str | None) -> str | None:
    if operator_id is None:
        return None
    stripped = operator_id.strip()
    if not stripped:
        return None
    return stripped


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    cursor = connection.execute(f"PRAGMA table_info({table})")
    rows = cursor.fetchall()
    return {str(row["name"]) for row in rows}


def _ensure_table_columns(
    connection: sqlite3.Connection,
    table: str,
    columns_sql: dict[str, str],
) -> None:
    existing = _table_columns(connection, table)
    for column_name, column_sql in columns_sql.items():
        if column_name in existing:
            continue
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column_name} {column_sql}")


def ensure_clinical_hub_schema(db_path: Path) -> None:
    with _connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS paired_measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                measured_at TEXT NOT NULL,
                session_id TEXT NOT NULL,
                site_id TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                operator_id TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                platform TEXT NOT NULL,
                device_model TEXT,
                app_version TEXT,
                capture_mode TEXT NOT NULL,
                app_quality_status TEXT NOT NULL,
                app_quality_score REAL,
                app_model_id TEXT,
                app_qmax_ml_s REAL NOT NULL,
                app_qavg_ml_s REAL NOT NULL,
                app_vvoid_ml REAL NOT NULL,
                app_flow_time_s REAL,
                app_tqmax_s REAL,
                ref_qmax_ml_s REAL NOT NULL,
                ref_qavg_ml_s REAL NOT NULL,
                ref_vvoid_ml REAL NOT NULL,
                ref_flow_time_s REAL,
                ref_tqmax_s REAL,
                ref_device_model TEXT,
                ref_device_serial TEXT,
                notes TEXT,
                payload_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_paired_measurements_session
            ON paired_measurements(session_id, attempt_number)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_paired_measurements_subject
            ON paired_measurements(site_id, subject_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_paired_measurements_measured_at
            ON paired_measurements(measured_at)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                method TEXT NOT NULL,
                path TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                auth_result TEXT NOT NULL,
                api_key_fingerprint TEXT,
                actor_operator_id TEXT,
                actor_role TEXT,
                actor_site_id TEXT,
                request_id TEXT,
                session_id TEXT,
                site_id TEXT,
                subject_id TEXT,
                operator_id TEXT,
                remote_addr TEXT,
                detail_json TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_events_created_at
            ON audit_events(created_at)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_events_path
            ON audit_events(path)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS capture_packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                measured_at TEXT NOT NULL,
                session_id TEXT NOT NULL,
                site_id TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                operator_id TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                platform TEXT NOT NULL,
                device_model TEXT,
                app_version TEXT,
                capture_mode TEXT NOT NULL,
                package_type TEXT NOT NULL,
                paired_measurement_id INTEGER,
                notes TEXT,
                capture_payload_json TEXT NOT NULL,
                FOREIGN KEY(paired_measurement_id) REFERENCES paired_measurements(id)
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_capture_packages_session
            ON capture_packages(session_id, attempt_number)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_capture_packages_subject
            ON capture_packages(site_id, subject_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_capture_packages_measured_at
            ON capture_packages(measured_at)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_capture_packages_paired_measurement
            ON capture_packages(paired_measurement_id)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS pilot_automation_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                site_id TEXT NOT NULL,
                report_date TEXT NOT NULL,
                report_type TEXT NOT NULL,
                package_version TEXT,
                model_id TEXT,
                dataset_id TEXT,
                payload_json TEXT NOT NULL,
                notes TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_pilot_reports_site_type_date
            ON pilot_automation_reports(site_id, report_type, report_date)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_pilot_reports_report_date
            ON pilot_automation_reports(report_date)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_pilot_reports_created_at
            ON pilot_automation_reports(created_at)
            """
        )

        _ensure_table_columns(
            connection,
            "audit_events",
            {
                "actor_operator_id": "TEXT",
                "actor_role": "TEXT",
                "actor_site_id": "TEXT",
                "request_id": "TEXT",
            },
        )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _dt_to_iso(value: datetime) -> str:
    normalized = value.astimezone(UTC).replace(microsecond=0)
    return normalized.isoformat().replace("+00:00", "Z")


def _dt_from_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _insert_paired_measurement(
    connection: sqlite3.Connection, payload: PairedMeasurementCreate
) -> int:
    created_at = _utc_now()
    measured_at = payload.session.measured_at.astimezone(UTC)
    payload_json = json.dumps(payload.model_dump(mode="json"), ensure_ascii=False)

    cursor = connection.execute(
        """
        INSERT INTO paired_measurements (
            created_at,
            measured_at,
            session_id,
            site_id,
            subject_id,
            operator_id,
            attempt_number,
            platform,
            device_model,
            app_version,
            capture_mode,
            app_quality_status,
            app_quality_score,
            app_model_id,
            app_qmax_ml_s,
            app_qavg_ml_s,
            app_vvoid_ml,
            app_flow_time_s,
            app_tqmax_s,
            ref_qmax_ml_s,
            ref_qavg_ml_s,
            ref_vvoid_ml,
            ref_flow_time_s,
            ref_tqmax_s,
            ref_device_model,
            ref_device_serial,
            notes,
            payload_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _dt_to_iso(created_at),
            _dt_to_iso(measured_at),
            payload.session.session_id,
            payload.session.site_id,
            payload.session.subject_id,
            payload.session.operator_id,
            payload.session.attempt_number,
            payload.session.platform,
            payload.session.device_model,
            payload.session.app_version,
            payload.session.capture_mode,
            payload.app.quality_status,
            payload.app.quality_score,
            payload.app.model_id,
            payload.app.metrics.qmax_ml_s,
            payload.app.metrics.qavg_ml_s,
            payload.app.metrics.vvoid_ml,
            payload.app.metrics.flow_time_s,
            payload.app.metrics.tqmax_s,
            payload.reference.metrics.qmax_ml_s,
            payload.reference.metrics.qavg_ml_s,
            payload.reference.metrics.vvoid_ml,
            payload.reference.metrics.flow_time_s,
            payload.reference.metrics.tqmax_s,
            payload.reference.device_model,
            payload.reference.device_serial,
            payload.notes,
            payload_json,
        ),
    )
    return int(cursor.lastrowid)


def _insert_capture_package(
    connection: sqlite3.Connection,
    payload: CapturePackageCreate,
) -> int:
    created_at = _utc_now()
    measured_at = payload.session.measured_at.astimezone(UTC)
    capture_payload_json = json.dumps(payload.capture_payload, ensure_ascii=False)
    cursor = connection.execute(
        """
        INSERT INTO capture_packages (
            created_at,
            measured_at,
            session_id,
            site_id,
            subject_id,
            operator_id,
            attempt_number,
            platform,
            device_model,
            app_version,
            capture_mode,
            package_type,
            paired_measurement_id,
            notes,
            capture_payload_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _dt_to_iso(created_at),
            _dt_to_iso(measured_at),
            payload.session.session_id,
            payload.session.site_id,
            payload.session.subject_id,
            payload.session.operator_id,
            payload.session.attempt_number,
            payload.session.platform,
            payload.session.device_model,
            payload.session.app_version,
            payload.session.capture_mode,
            payload.package_type,
            payload.paired_measurement_id,
            payload.notes,
            capture_payload_json,
        ),
    )
    return int(cursor.lastrowid)


def _insert_pilot_automation_report(
    connection: sqlite3.Connection,
    payload: PilotAutomationReportCreate,
) -> int:
    created_at = _utc_now()
    cursor = connection.execute(
        """
        INSERT INTO pilot_automation_reports (
            created_at,
            site_id,
            report_date,
            report_type,
            package_version,
            model_id,
            dataset_id,
            payload_json,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _dt_to_iso(created_at),
            payload.site_id,
            payload.report_date.isoformat(),
            payload.report_type,
            payload.package_version,
            payload.model_id,
            payload.dataset_id,
            json.dumps(payload.payload, ensure_ascii=False),
            payload.notes,
        ),
    )
    return int(cursor.lastrowid)


def _fetch_record_by_id(connection: sqlite3.Connection, record_id: int) -> sqlite3.Row | None:
    cursor = connection.execute(
        "SELECT * FROM paired_measurements WHERE id = ?",
        (record_id,),
    )
    return cursor.fetchone()


def _fetch_paired_measurement_by_identity(
    connection: sqlite3.Connection,
    *,
    site_id: str,
    subject_id: str,
    session_id: str,
    attempt_number: int,
) -> sqlite3.Row | None:
    cursor = connection.execute(
        """
        SELECT *
        FROM paired_measurements
        WHERE site_id = ?
          AND subject_id = ?
          AND session_id = ?
          AND attempt_number = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (site_id, subject_id, session_id, attempt_number),
    )
    return cursor.fetchone()


def _fetch_capture_package_by_id(
    connection: sqlite3.Connection,
    record_id: int,
) -> sqlite3.Row | None:
    cursor = connection.execute(
        "SELECT * FROM capture_packages WHERE id = ?",
        (record_id,),
    )
    return cursor.fetchone()


def _fetch_pilot_automation_report_by_id(
    connection: sqlite3.Connection,
    record_id: int,
) -> sqlite3.Row | None:
    cursor = connection.execute(
        "SELECT * FROM pilot_automation_reports WHERE id = ?",
        (record_id,),
    )
    return cursor.fetchone()


def _row_to_record(row: sqlite3.Row) -> PairedMeasurementRecord:
    payload = json.loads(str(row["payload_json"]))
    source = PairedMeasurementCreate.model_validate(payload)
    return PairedMeasurementRecord(
        id=int(row["id"]),
        created_at=_dt_from_iso(str(row["created_at"])),
        session=source.session,
        app=source.app,
        reference=source.reference,
        notes=source.notes,
    )


def _row_to_capture_package_record(row: sqlite3.Row) -> CapturePackageRecord:
    session = SessionMeta(
        session_id=str(row["session_id"]),
        site_id=str(row["site_id"]),
        subject_id=str(row["subject_id"]),
        operator_id=str(row["operator_id"]),
        attempt_number=int(row["attempt_number"]),
        measured_at=_dt_from_iso(str(row["measured_at"])),
        platform=str(row["platform"]),  # type: ignore[arg-type]
        device_model=str(row["device_model"]) if row["device_model"] is not None else None,
        app_version=str(row["app_version"]) if row["app_version"] is not None else None,
        capture_mode=str(row["capture_mode"]),  # type: ignore[arg-type]
    )
    return CapturePackageRecord(
        id=int(row["id"]),
        created_at=_dt_from_iso(str(row["created_at"])),
        session=session,
        package_type=str(row["package_type"]),  # type: ignore[arg-type]
        capture_payload=json.loads(str(row["capture_payload_json"])),
        paired_measurement_id=int(row["paired_measurement_id"])
        if row["paired_measurement_id"] is not None
        else None,
        notes=str(row["notes"]) if row["notes"] is not None else None,
    )


def _row_to_list_item(row: sqlite3.Row) -> PairedMeasurementListItem:
    return PairedMeasurementListItem(
        id=int(row["id"]),
        created_at=_dt_from_iso(str(row["created_at"])),
        measured_at=_dt_from_iso(str(row["measured_at"])),
        session_id=str(row["session_id"]),
        site_id=str(row["site_id"]),
        subject_id=str(row["subject_id"]),
        attempt_number=int(row["attempt_number"]),
        platform=str(row["platform"]),  # type: ignore[arg-type]
        app_quality_status=str(row["app_quality_status"]),  # type: ignore[arg-type]
        app_qmax_ml_s=float(row["app_qmax_ml_s"]),
        ref_qmax_ml_s=float(row["ref_qmax_ml_s"]),
        app_vvoid_ml=float(row["app_vvoid_ml"]),
        ref_vvoid_ml=float(row["ref_vvoid_ml"]),
    )


def _row_to_capture_package_list_item(row: sqlite3.Row) -> CapturePackageListItem:
    return CapturePackageListItem(
        id=int(row["id"]),
        created_at=_dt_from_iso(str(row["created_at"])),
        measured_at=_dt_from_iso(str(row["measured_at"])),
        session_id=str(row["session_id"]),
        site_id=str(row["site_id"]),
        subject_id=str(row["subject_id"]),
        operator_id=str(row["operator_id"]),
        attempt_number=int(row["attempt_number"]),
        platform=str(row["platform"]),  # type: ignore[arg-type]
        package_type=str(row["package_type"]),  # type: ignore[arg-type]
        paired_measurement_id=int(row["paired_measurement_id"])
        if row["paired_measurement_id"] is not None
        else None,
    )


def _row_to_pilot_automation_report_record(row: sqlite3.Row) -> PilotAutomationReportRecord:
    return PilotAutomationReportRecord(
        id=int(row["id"]),
        created_at=_dt_from_iso(str(row["created_at"])),
        site_id=str(row["site_id"]),
        report_date=date.fromisoformat(str(row["report_date"])),
        report_type=str(row["report_type"]),  # type: ignore[arg-type]
        package_version=str(row["package_version"]) if row["package_version"] is not None else None,
        model_id=str(row["model_id"]) if row["model_id"] is not None else None,
        dataset_id=str(row["dataset_id"]) if row["dataset_id"] is not None else None,
        payload=json.loads(str(row["payload_json"])),
        notes=str(row["notes"]) if row["notes"] is not None else None,
    )


def _row_to_pilot_automation_report_list_item(
    row: sqlite3.Row,
) -> PilotAutomationReportListItem:
    return PilotAutomationReportListItem(
        id=int(row["id"]),
        created_at=_dt_from_iso(str(row["created_at"])),
        site_id=str(row["site_id"]),
        report_date=date.fromisoformat(str(row["report_date"])),
        report_type=str(row["report_type"]),  # type: ignore[arg-type]
        package_version=str(row["package_version"]) if row["package_version"] is not None else None,
        model_id=str(row["model_id"]) if row["model_id"] is not None else None,
        dataset_id=str(row["dataset_id"]) if row["dataset_id"] is not None else None,
    )


def _build_where_clause(filters: list[tuple[str, object]]) -> tuple[str, list[object]]:
    where = ""
    values: list[object] = []
    if filters:
        where = "WHERE " + " AND ".join(f"{name} = ?" for name, _ in filters)
        values = [value for _, value in filters]
    return where, values


def _safe_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


def _safe_pearson(x_values: list[float], y_values: list[float]) -> float | None:
    if len(x_values) < 2 or len(x_values) != len(y_values):
        return None

    mean_x = _safe_mean(x_values)
    mean_y = _safe_mean(y_values)
    if mean_x is None or mean_y is None:
        return None

    centered_x = [value - mean_x for value in x_values]
    centered_y = [value - mean_y for value in y_values]
    sum_x2 = sum(value * value for value in centered_x)
    sum_y2 = sum(value * value for value in centered_y)
    if sum_x2 <= 0 or sum_y2 <= 0:
        return None

    covariance = sum(x * y for x, y in zip(centered_x, centered_y, strict=True))
    return float(covariance / math.sqrt(sum_x2 * sum_y2))


def _normalize_actor_role(actor_role: str | None) -> ACTOR_ROLE | None:
    if actor_role is None:
        return None
    normalized = actor_role.strip().lower()
    if normalized in {"operator", "investigator", "data_manager", "admin"}:
        return normalized
    return None


def _validate_api_key_policy_map(
    api_key_policy_map: dict[str, dict[str, str | None]] | None,
) -> dict[str, ApiKeyPolicy]:
    if api_key_policy_map is None:
        return {}
    validated: dict[str, ApiKeyPolicy] = {}
    for api_key, raw_policy in api_key_policy_map.items():
        normalized_api_key = api_key.strip()
        if not normalized_api_key:
            raise ValueError("api key policy map contains an empty key")
        policy = ApiKeyPolicy.model_validate(raw_policy)
        policy.site_id = _normalize_site_id(policy.site_id)
        policy.operator_id = _normalize_operator_id(policy.operator_id)
        if policy.role in {"operator", "investigator"} and policy.site_id is None:
            raise ValueError(
                f"api key policy for role '{policy.role}' must include site_id "
                f"(key fingerprint={_hash_api_key(normalized_api_key)})"
            )
        validated[normalized_api_key] = policy
    return validated


def _is_cross_site_allowed(actor_role: ACTOR_ROLE | None) -> bool:
    if actor_role is None:
        return False
    return actor_role in _CROSS_SITE_ALLOWED_ROLES


def _resolve_site_scope(request: Request, requested_site_id: str | None) -> str | None:
    actor_site_id = request.state.actor_site_id
    actor_role = request.state.actor_role
    if actor_site_id is None or _is_cross_site_allowed(actor_role):
        return requested_site_id
    if requested_site_id is not None and requested_site_id != actor_site_id:
        raise HTTPException(
            status_code=403,
            detail="site scope violation: access to requested site is not allowed",
        )
    return actor_site_id


def _enforce_payload_site_scope(request: Request, payload_site_id: str) -> None:
    actor_site_id = request.state.actor_site_id
    actor_role = request.state.actor_role
    if actor_site_id is None or _is_cross_site_allowed(actor_role):
        return
    if payload_site_id != actor_site_id:
        raise HTTPException(
            status_code=403,
            detail="site scope violation: payload site_id does not match actor site",
        )


def _enforce_row_site_scope(request: Request, row_site_id: str) -> None:
    actor_site_id = request.state.actor_site_id
    actor_role = request.state.actor_role
    if actor_site_id is None or _is_cross_site_allowed(actor_role):
        return
    if row_site_id != actor_site_id:
        raise HTTPException(
            status_code=403,
            detail="site scope violation: record site_id does not match actor site",
        )


def _metric_summary(
    metric: str,
    app_values: list[float],
    ref_values: list[float],
) -> MetricComparisonSummary:
    paired_samples = len(app_values)
    if paired_samples == 0:
        return MetricComparisonSummary(metric=metric, paired_samples=0)

    errors = [
        app_value - ref_value
        for app_value, ref_value in zip(app_values, ref_values, strict=True)
    ]
    abs_errors = [abs(error) for error in errors]
    sq_errors = [error * error for error in errors]
    mape_terms = [
        abs((app_value - ref_value) / ref_value) * 100.0
        for app_value, ref_value in zip(app_values, ref_values, strict=True)
        if ref_value != 0
    ]

    bias = _safe_mean(errors)
    if paired_samples > 1 and bias is not None:
        variance = sum((error - bias) ** 2 for error in errors) / (paired_samples - 1)
        std = math.sqrt(variance)
        loa_lower = bias - 1.96 * std
        loa_upper = bias + 1.96 * std
    else:
        loa_lower = None
        loa_upper = None

    return MetricComparisonSummary(
        metric=metric,
        paired_samples=paired_samples,
        mean_app=_safe_mean(app_values),
        mean_reference=_safe_mean(ref_values),
        mean_error=bias,
        mean_absolute_error=_safe_mean(abs_errors),
        rmse=math.sqrt(sum(sq_errors) / paired_samples),
        mape_pct=_safe_mean(mape_terms),
        pearson_r=_safe_pearson(app_values, ref_values),
        bland_altman_bias=bias,
        bland_altman_loa_lower=loa_lower,
        bland_altman_loa_upper=loa_upper,
    )


def _hash_api_key(api_key: str | None) -> str | None:
    if not api_key:
        return None
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]


def _extract_session_metadata_from_body(body: bytes) -> dict[str, str | None]:
    def _session_value(session: dict[str, object], key: str) -> str | None:
        value = session.get(key)
        if isinstance(value, str):
            return value
        return None

    def _payload_value(payload: dict[str, object], key: str) -> str | None:
        value = payload.get(key)
        if isinstance(value, str):
            return value
        return None

    if not body:
        return {
            "session_id": None,
            "site_id": None,
            "subject_id": None,
            "operator_id": None,
        }
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {
            "session_id": None,
            "site_id": None,
            "subject_id": None,
            "operator_id": None,
        }

    if not isinstance(payload, dict):
        return {
            "session_id": None,
            "site_id": None,
            "subject_id": None,
            "operator_id": None,
        }
    session = payload.get("session")
    if not isinstance(session, dict):
        return {
            "session_id": _payload_value(payload, "session_id"),
            "site_id": _payload_value(payload, "site_id"),
            "subject_id": _payload_value(payload, "subject_id"),
            "operator_id": _payload_value(payload, "operator_id"),
        }

    return {
        "session_id": _session_value(session, "session_id"),
        "site_id": _session_value(session, "site_id"),
        "subject_id": _session_value(session, "subject_id"),
        "operator_id": _session_value(session, "operator_id"),
    }


def _insert_audit_event(
    connection: sqlite3.Connection,
    *,
    method: str,
    path: str,
    status_code: int,
    auth_result: str,
    api_key_fingerprint: str | None,
    actor_operator_id: str | None,
    actor_role: str | None,
    actor_site_id: str | None,
    request_id: str | None,
    session_id: str | None,
    site_id: str | None,
    subject_id: str | None,
    operator_id: str | None,
    remote_addr: str | None,
    detail_json: str | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO audit_events (
            created_at,
            method,
            path,
            status_code,
            auth_result,
            api_key_fingerprint,
            actor_operator_id,
            actor_role,
            actor_site_id,
            request_id,
            session_id,
            site_id,
            subject_id,
            operator_id,
            remote_addr,
            detail_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _dt_to_iso(_utc_now()),
            method,
            path,
            status_code,
            auth_result,
            api_key_fingerprint,
            actor_operator_id,
            actor_role,
            actor_site_id,
            request_id,
            session_id,
            site_id,
            subject_id,
            operator_id,
            remote_addr,
            detail_json,
        ),
    )


def _build_method_comparison_summary_from_rows(
    rows: list[sqlite3.Row],
    filters: MethodComparisonFilters,
) -> MethodComparisonSummary:
    quality_distribution: dict[str, int] = {"valid": 0, "repeat": 0, "reject": 0}
    for row in rows:
        status = str(row["app_quality_status"])
        quality_distribution[status] = quality_distribution.get(status, 0) + 1

    considered_rows = rows
    if filters.quality_status is not None:
        considered_rows = [
            row for row in rows if str(row["app_quality_status"]) == filters.quality_status
        ]

    metrics: list[MetricComparisonSummary] = []
    for metric, (app_column, ref_column) in METRIC_COLUMNS.items():
        app_values: list[float] = []
        ref_values: list[float] = []
        for row in considered_rows:
            app_value = row[app_column]
            ref_value = row[ref_column]
            if app_value is None or ref_value is None:
                continue
            app_values.append(float(app_value))
            ref_values.append(float(ref_value))
        metrics.append(_metric_summary(metric=metric, app_values=app_values, ref_values=ref_values))

    return MethodComparisonSummary(
        generated_at=_utc_now(),
        filters=filters,
        records_matched_filters=len(rows),
        records_considered=len(considered_rows),
        quality_distribution=quality_distribution,
        metrics=metrics,
    )


def _fetch_method_comparison_rows(
    connection: sqlite3.Connection,
    *,
    site_id: str | None = None,
    subject_id: str | None = None,
    platform: PLATFORM | None = None,
    capture_mode: CAPTURE_MODE | None = None,
) -> list[sqlite3.Row]:
    filter_pairs: list[tuple[str, object]] = []
    if site_id:
        filter_pairs.append(("site_id", site_id))
    if subject_id:
        filter_pairs.append(("subject_id", subject_id))
    if platform:
        filter_pairs.append(("platform", platform))
    if capture_mode:
        filter_pairs.append(("capture_mode", capture_mode))
    where_sql, where_values = _build_where_clause(filter_pairs)
    cursor = connection.execute(
        f"""
        SELECT
            app_quality_status,
            app_qmax_ml_s,
            app_qavg_ml_s,
            app_vvoid_ml,
            app_flow_time_s,
            app_tqmax_s,
            ref_qmax_ml_s,
            ref_qavg_ml_s,
            ref_vvoid_ml,
            ref_flow_time_s,
            ref_tqmax_s
        FROM paired_measurements
        {where_sql}
        ORDER BY measured_at ASC, id ASC
        """,
        tuple(where_values),
    )
    return cursor.fetchall()


def _row_to_audit_item(row: sqlite3.Row) -> AuditEventItem:
    return AuditEventItem(
        id=int(row["id"]),
        created_at=_dt_from_iso(str(row["created_at"])),
        method=str(row["method"]),
        path=str(row["path"]),
        status_code=int(row["status_code"]),
        auth_result=str(row["auth_result"]),
        api_key_fingerprint=str(row["api_key_fingerprint"])
        if row["api_key_fingerprint"] is not None
        else None,
        actor_operator_id=str(row["actor_operator_id"])
        if row["actor_operator_id"] is not None
        else None,
        actor_role=str(row["actor_role"]) if row["actor_role"] is not None else None,
        actor_site_id=str(row["actor_site_id"]) if row["actor_site_id"] is not None else None,
        request_id=str(row["request_id"]) if row["request_id"] is not None else None,
        session_id=str(row["session_id"]) if row["session_id"] is not None else None,
        site_id=str(row["site_id"]) if row["site_id"] is not None else None,
        subject_id=str(row["subject_id"]) if row["subject_id"] is not None else None,
        operator_id=str(row["operator_id"]) if row["operator_id"] is not None else None,
        remote_addr=str(row["remote_addr"]) if row["remote_addr"] is not None else None,
        detail_json=str(row["detail_json"]) if row["detail_json"] is not None else None,
    )


def export_paired_measurements_to_csv(db_path: Path, output_csv: Path) -> int:
    ensure_clinical_hub_schema(db_path)
    with _connect(db_path) as connection:
        cursor = connection.execute(
            """
            SELECT
                id,
                created_at,
                measured_at,
                session_id,
                site_id,
                subject_id,
                operator_id,
                attempt_number,
                platform,
                device_model,
                app_version,
                capture_mode,
                app_quality_status,
                app_quality_score,
                app_model_id,
                app_qmax_ml_s,
                app_qavg_ml_s,
                app_vvoid_ml,
                app_flow_time_s,
                app_tqmax_s,
                ref_qmax_ml_s,
                ref_qavg_ml_s,
                ref_vvoid_ml,
                ref_flow_time_s,
                ref_tqmax_s,
                ref_device_model,
                ref_device_serial,
                notes
            FROM paired_measurements
            ORDER BY measured_at DESC, id DESC
            """
        )
        rows = cursor.fetchall()

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "id",
                "created_at",
                "measured_at",
                "session_id",
                "site_id",
                "subject_id",
                "operator_id",
                "attempt_number",
                "platform",
                "device_model",
                "app_version",
                "capture_mode",
                "app_quality_status",
                "app_quality_score",
                "app_model_id",
                "app_qmax_ml_s",
                "app_qavg_ml_s",
                "app_vvoid_ml",
                "app_flow_time_s",
                "app_tqmax_s",
                "ref_qmax_ml_s",
                "ref_qavg_ml_s",
                "ref_vvoid_ml",
                "ref_flow_time_s",
                "ref_tqmax_s",
                "ref_device_model",
                "ref_device_serial",
                "notes",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["id"],
                    row["created_at"],
                    row["measured_at"],
                    row["session_id"],
                    row["site_id"],
                    row["subject_id"],
                    row["operator_id"],
                    row["attempt_number"],
                    row["platform"],
                    row["device_model"],
                    row["app_version"],
                    row["capture_mode"],
                    row["app_quality_status"],
                    row["app_quality_score"],
                    row["app_model_id"],
                    row["app_qmax_ml_s"],
                    row["app_qavg_ml_s"],
                    row["app_vvoid_ml"],
                    row["app_flow_time_s"],
                    row["app_tqmax_s"],
                    row["ref_qmax_ml_s"],
                    row["ref_qavg_ml_s"],
                    row["ref_vvoid_ml"],
                    row["ref_flow_time_s"],
                    row["ref_tqmax_s"],
                    row["ref_device_model"],
                    row["ref_device_serial"],
                    row["notes"],
                ]
            )
    return len(rows)


def export_audit_events_to_csv(db_path: Path, output_csv: Path) -> int:
    ensure_clinical_hub_schema(db_path)
    with _connect(db_path) as connection:
        cursor = connection.execute(
            """
            SELECT
                id,
                created_at,
                method,
                path,
                status_code,
                auth_result,
                api_key_fingerprint,
                actor_operator_id,
                actor_role,
                actor_site_id,
                request_id,
                session_id,
                site_id,
                subject_id,
                operator_id,
                remote_addr,
                detail_json
            FROM audit_events
            ORDER BY id DESC
            """
        )
        rows = cursor.fetchall()

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "id",
                "created_at",
                "method",
                "path",
                "status_code",
                "auth_result",
                "api_key_fingerprint",
                "actor_operator_id",
                "actor_role",
                "actor_site_id",
                "request_id",
                "session_id",
                "site_id",
                "subject_id",
                "operator_id",
                "remote_addr",
                "detail_json",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["id"],
                    row["created_at"],
                    row["method"],
                    row["path"],
                    row["status_code"],
                    row["auth_result"],
                    row["api_key_fingerprint"],
                    row["actor_operator_id"],
                    row["actor_role"],
                    row["actor_site_id"],
                    row["request_id"],
                    row["session_id"],
                    row["site_id"],
                    row["subject_id"],
                    row["operator_id"],
                    row["remote_addr"],
                    row["detail_json"],
                ]
            )
    return len(rows)


def export_capture_packages_to_csv(db_path: Path, output_csv: Path) -> int:
    ensure_clinical_hub_schema(db_path)
    with _connect(db_path) as connection:
        cursor = connection.execute(
            """
            SELECT
                id,
                created_at,
                measured_at,
                session_id,
                site_id,
                subject_id,
                operator_id,
                attempt_number,
                platform,
                device_model,
                app_version,
                capture_mode,
                package_type,
                paired_measurement_id,
                notes,
                capture_payload_json
            FROM capture_packages
            ORDER BY measured_at DESC, id DESC
            """
        )
        rows = cursor.fetchall()

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "id",
                "created_at",
                "measured_at",
                "session_id",
                "site_id",
                "subject_id",
                "operator_id",
                "attempt_number",
                "platform",
                "device_model",
                "app_version",
                "capture_mode",
                "package_type",
                "paired_measurement_id",
                "notes",
                "capture_payload_json",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["id"],
                    row["created_at"],
                    row["measured_at"],
                    row["session_id"],
                    row["site_id"],
                    row["subject_id"],
                    row["operator_id"],
                    row["attempt_number"],
                    row["platform"],
                    row["device_model"],
                    row["app_version"],
                    row["capture_mode"],
                    row["package_type"],
                    row["paired_measurement_id"],
                    row["notes"],
                    row["capture_payload_json"],
                ]
            )
    return len(rows)


def export_pilot_automation_reports_to_csv(db_path: Path, output_csv: Path) -> int:
    ensure_clinical_hub_schema(db_path)
    with _connect(db_path) as connection:
        cursor = connection.execute(
            """
            SELECT
                id,
                created_at,
                site_id,
                report_date,
                report_type,
                package_version,
                model_id,
                dataset_id,
                notes,
                payload_json
            FROM pilot_automation_reports
            ORDER BY report_date DESC, id DESC
            """
        )
        rows = cursor.fetchall()

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "id",
                "created_at",
                "site_id",
                "report_date",
                "report_type",
                "package_version",
                "model_id",
                "dataset_id",
                "notes",
                "payload_json",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["id"],
                    row["created_at"],
                    row["site_id"],
                    row["report_date"],
                    row["report_type"],
                    row["package_version"],
                    row["model_id"],
                    row["dataset_id"],
                    row["notes"],
                    row["payload_json"],
                ]
            )
    return len(rows)


def build_method_comparison_summary(
    db_path: Path,
    *,
    site_id: str | None = None,
    subject_id: str | None = None,
    platform: PLATFORM | None = None,
    capture_mode: CAPTURE_MODE | None = None,
    quality_status: QUALITY_STATUS | None = "valid",
) -> MethodComparisonSummary:
    ensure_clinical_hub_schema(db_path)
    filters = MethodComparisonFilters(
        site_id=site_id,
        subject_id=subject_id,
        platform=platform,
        capture_mode=capture_mode,
        quality_status=quality_status,
    )
    with _connect(db_path) as connection:
        rows = _fetch_method_comparison_rows(
            connection,
            site_id=site_id,
            subject_id=subject_id,
            platform=platform,
            capture_mode=capture_mode,
        )
    return _build_method_comparison_summary_from_rows(rows=rows, filters=filters)


def create_clinical_hub_app(
    db_path: Path,
    api_key: str | None = None,
    api_key_policy_map: dict[str, dict[str, str | None]] | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
        ensure_clinical_hub_schema(db_path)
        yield

    app = FastAPI(
        title="Uroflow Clinical Hub API",
        version="0.1.0",
        description="API for paired app vs reference uroflow measurements.",
        lifespan=_lifespan,
    )
    app.state.db_path = db_path
    app.state.api_key = api_key
    app.state.api_key_policy_map = _validate_api_key_policy_map(api_key_policy_map)

    @app.middleware("http")
    async def _audit_and_auth_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path
        if not path.startswith("/api/v1/"):
            return await call_next(request)

        body_bytes = await request.body()
        session_meta = _extract_session_metadata_from_body(body_bytes)
        request_api_key = request.headers.get("x-api-key")
        actor_operator_id = _normalize_operator_id(request.headers.get("x-operator-id"))
        if actor_operator_id is None:
            actor_operator_id = _normalize_operator_id(session_meta["operator_id"])
        actor_site_id = _normalize_site_id(request.headers.get("x-site-id"))
        if actor_site_id is None:
            actor_site_id = _normalize_site_id(session_meta["site_id"])
        actor_role = _normalize_actor_role(request.headers.get("x-actor-role"))
        request_id = request.headers.get("x-request-id")
        required_api_key: str | None = app.state.api_key
        api_key_policy_map: dict[str, ApiKeyPolicy] = app.state.api_key_policy_map
        api_key_policy = api_key_policy_map.get(request_api_key) if request_api_key else None
        if api_key_policy is not None:
            actor_role = api_key_policy.role
            actor_site_id = api_key_policy.site_id or actor_site_id
            actor_operator_id = api_key_policy.operator_id or actor_operator_id

        request.state.actor_site_id = actor_site_id
        request.state.actor_role = actor_role
        auth_result = "not_configured"
        if api_key_policy_map:
            if api_key_policy is not None:
                auth_result = "valid_policy"
            elif required_api_key is not None and request_api_key == required_api_key:
                auth_result = "valid_legacy"
            else:
                auth_result = "invalid"
        elif required_api_key:
            auth_result = "valid" if request_api_key == required_api_key else "invalid"

        if auth_result == "invalid":
            response = JSONResponse(status_code=401, content={"detail": "invalid API key"})
            with _connect(app.state.db_path) as audit_connection:
                _insert_audit_event(
                    audit_connection,
                    method=request.method,
                    path=path,
                    status_code=401,
                    auth_result=auth_result,
                    api_key_fingerprint=_hash_api_key(request_api_key),
                    actor_operator_id=actor_operator_id,
                    actor_role=actor_role,
                    actor_site_id=actor_site_id,
                    request_id=request_id,
                    session_id=session_meta["session_id"],
                    site_id=session_meta["site_id"],
                    subject_id=session_meta["subject_id"],
                    operator_id=session_meta["operator_id"],
                    remote_addr=request.client.host if request.client else None,
                    detail_json=json.dumps(
                        {
                            "query": str(request.url.query),
                            "reason": "missing_or_invalid_api_key",
                        },
                        ensure_ascii=False,
                    ),
                )
                audit_connection.commit()
            return response

        async def receive() -> dict[str, object]:
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        replayed_request = Request(request.scope, receive)
        response = await call_next(replayed_request)

        with _connect(app.state.db_path) as audit_connection:
            _insert_audit_event(
                audit_connection,
                method=request.method,
                path=path,
                status_code=response.status_code,
                auth_result=auth_result,
                api_key_fingerprint=_hash_api_key(request_api_key),
                actor_operator_id=actor_operator_id,
                actor_role=actor_role,
                actor_site_id=actor_site_id,
                request_id=request_id,
                session_id=session_meta["session_id"],
                site_id=session_meta["site_id"],
                subject_id=session_meta["subject_id"],
                operator_id=session_meta["operator_id"],
                remote_addr=request.client.host if request.client else None,
                detail_json=json.dumps({"query": str(request.url.query)}, ensure_ascii=False),
            )
            audit_connection.commit()
        return response

    def _connection() -> sqlite3.Connection:
        return _connect(app.state.db_path)

    def get_connection() -> sqlite3.Connection:
        connection = _connection()
        try:
            yield connection
        finally:
            connection.close()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/api/v1/paired-measurements",
        response_model=PairedMeasurementRecord,
        status_code=201,
    )
    def create_paired_measurement(
        payload: PairedMeasurementCreate,
        request: Request,
        response: Response,
        connection: sqlite3.Connection = Depends(get_connection),  # noqa: B008
    ) -> PairedMeasurementRecord:
        _enforce_payload_site_scope(request, payload.session.site_id)
        existing_row = _fetch_paired_measurement_by_identity(
            connection,
            site_id=payload.session.site_id,
            subject_id=payload.session.subject_id,
            session_id=payload.session.session_id,
            attempt_number=payload.session.attempt_number,
        )
        if existing_row is not None:
            existing_payload = json.loads(str(existing_row["payload_json"]))
            incoming_payload = payload.model_dump(mode="json")
            if existing_payload != incoming_payload:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "paired measurement already exists with the same "
                        "site/subject/session/attempt but different payload"
                    ),
                )
            response.status_code = 200
            return _row_to_record(existing_row)

        record_id = _insert_paired_measurement(connection, payload=payload)
        connection.commit()
        row = _fetch_record_by_id(connection, record_id)
        if row is None:
            raise HTTPException(status_code=500, detail="record was not persisted")
        return _row_to_record(row)

    @app.get("/api/v1/paired-measurements", response_model=list[PairedMeasurementListItem])
    def list_paired_measurements(
        request: Request,
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
        site_id: str | None = None,
        subject_id: str | None = None,
        connection: sqlite3.Connection = Depends(get_connection),  # noqa: B008
    ) -> list[PairedMeasurementListItem]:
        effective_site_id = _resolve_site_scope(request, site_id)
        filters: list[str] = []
        values: list[object] = []
        if effective_site_id:
            filters.append("site_id = ?")
            values.append(effective_site_id)
        if subject_id:
            filters.append("subject_id = ?")
            values.append(subject_id)

        where_sql = ""
        if filters:
            where_sql = "WHERE " + " AND ".join(filters)

        cursor = connection.execute(
            f"""
            SELECT
                id,
                created_at,
                measured_at,
                session_id,
                site_id,
                subject_id,
                attempt_number,
                platform,
                app_quality_status,
                app_qmax_ml_s,
                ref_qmax_ml_s,
                app_vvoid_ml,
                ref_vvoid_ml
            FROM paired_measurements
            {where_sql}
            ORDER BY measured_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (*values, limit, offset),
        )
        rows = cursor.fetchall()
        return [_row_to_list_item(row) for row in rows]

    @app.get("/api/v1/paired-measurements/{record_id}", response_model=PairedMeasurementRecord)
    def get_paired_measurement(
        request: Request,
        record_id: int,
        connection: sqlite3.Connection = Depends(get_connection),  # noqa: B008
    ) -> PairedMeasurementRecord:
        row = _fetch_record_by_id(connection, record_id)
        if row is None:
            raise HTTPException(status_code=404, detail="paired measurement not found")
        _enforce_row_site_scope(request, str(row["site_id"]))
        return _row_to_record(row)

    @app.post("/api/v1/capture-packages", response_model=CapturePackageRecord, status_code=201)
    def create_capture_package(
        payload: CapturePackageCreate,
        request: Request,
        connection: sqlite3.Connection = Depends(get_connection),  # noqa: B008
    ) -> CapturePackageRecord:
        _enforce_payload_site_scope(request, payload.session.site_id)
        if payload.paired_measurement_id is not None:
            paired_row = _fetch_record_by_id(connection, payload.paired_measurement_id)
            if paired_row is None:
                raise HTTPException(
                    status_code=400,
                    detail="paired_measurement_id does not exist",
                )
        record_id = _insert_capture_package(connection, payload)
        connection.commit()
        row = _fetch_capture_package_by_id(connection, record_id)
        if row is None:
            raise HTTPException(status_code=500, detail="capture package was not persisted")
        return _row_to_capture_package_record(row)

    @app.get("/api/v1/capture-packages", response_model=list[CapturePackageListItem])
    def list_capture_packages(
        request: Request,
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
        site_id: str | None = None,
        subject_id: str | None = None,
        session_id: str | None = None,
        package_type: (
            Literal["capture_contract_json", "feature_bundle", "media_manifest"] | None
        ) = None,
        connection: sqlite3.Connection = Depends(get_connection),  # noqa: B008
    ) -> list[CapturePackageListItem]:
        effective_site_id = _resolve_site_scope(request, site_id)
        filters: list[str] = []
        values: list[object] = []
        if effective_site_id:
            filters.append("site_id = ?")
            values.append(effective_site_id)
        if subject_id:
            filters.append("subject_id = ?")
            values.append(subject_id)
        if session_id:
            filters.append("session_id = ?")
            values.append(session_id)
        if package_type:
            filters.append("package_type = ?")
            values.append(package_type)

        where_sql = ""
        if filters:
            where_sql = "WHERE " + " AND ".join(filters)

        cursor = connection.execute(
            f"""
            SELECT
                id,
                created_at,
                measured_at,
                session_id,
                site_id,
                subject_id,
                operator_id,
                attempt_number,
                platform,
                package_type,
                paired_measurement_id
            FROM capture_packages
            {where_sql}
            ORDER BY measured_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (*values, limit, offset),
        )
        rows = cursor.fetchall()
        return [_row_to_capture_package_list_item(row) for row in rows]

    @app.get("/api/v1/capture-packages/{record_id}", response_model=CapturePackageRecord)
    def get_capture_package(
        request: Request,
        record_id: int,
        connection: sqlite3.Connection = Depends(get_connection),  # noqa: B008
    ) -> CapturePackageRecord:
        row = _fetch_capture_package_by_id(connection, record_id)
        if row is None:
            raise HTTPException(status_code=404, detail="capture package not found")
        _enforce_row_site_scope(request, str(row["site_id"]))
        return _row_to_capture_package_record(row)

    @app.post(
        "/api/v1/pilot-automation-reports",
        response_model=PilotAutomationReportRecord,
        status_code=201,
    )
    def create_pilot_automation_report(
        payload: PilotAutomationReportCreate,
        request: Request,
        connection: sqlite3.Connection = Depends(get_connection),  # noqa: B008
    ) -> PilotAutomationReportRecord:
        _enforce_payload_site_scope(request, payload.site_id)
        record_id = _insert_pilot_automation_report(connection, payload)
        connection.commit()
        row = _fetch_pilot_automation_report_by_id(connection, record_id)
        if row is None:
            raise HTTPException(status_code=500, detail="pilot automation report was not persisted")
        return _row_to_pilot_automation_report_record(row)

    @app.get(
        "/api/v1/pilot-automation-reports",
        response_model=list[PilotAutomationReportListItem],
    )
    def list_pilot_automation_reports(
        request: Request,
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
        site_id: str | None = None,
        report_type: PILOT_REPORT_TYPE | None = None,
        report_date_from: date | None = None,
        report_date_to: date | None = None,
        connection: sqlite3.Connection = Depends(get_connection),  # noqa: B008
    ) -> list[PilotAutomationReportListItem]:
        effective_site_id = _resolve_site_scope(request, site_id)
        filters: list[str] = []
        values: list[object] = []
        if effective_site_id:
            filters.append("site_id = ?")
            values.append(effective_site_id)
        if report_type:
            filters.append("report_type = ?")
            values.append(report_type)
        if report_date_from is not None:
            filters.append("report_date >= ?")
            values.append(report_date_from.isoformat())
        if report_date_to is not None:
            filters.append("report_date <= ?")
            values.append(report_date_to.isoformat())

        where_sql = ""
        if filters:
            where_sql = "WHERE " + " AND ".join(filters)

        cursor = connection.execute(
            f"""
            SELECT
                id,
                created_at,
                site_id,
                report_date,
                report_type,
                package_version,
                model_id,
                dataset_id
            FROM pilot_automation_reports
            {where_sql}
            ORDER BY report_date DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (*values, limit, offset),
        )
        rows = cursor.fetchall()
        return [_row_to_pilot_automation_report_list_item(row) for row in rows]

    @app.get(
        "/api/v1/pilot-automation-reports/{record_id}",
        response_model=PilotAutomationReportRecord,
    )
    def get_pilot_automation_report(
        request: Request,
        record_id: int,
        connection: sqlite3.Connection = Depends(get_connection),  # noqa: B008
    ) -> PilotAutomationReportRecord:
        row = _fetch_pilot_automation_report_by_id(connection, record_id)
        if row is None:
            raise HTTPException(status_code=404, detail="pilot automation report not found")
        _enforce_row_site_scope(request, str(row["site_id"]))
        return _row_to_pilot_automation_report_record(row)

    @app.get("/api/v1/comparison-summary", response_model=MethodComparisonSummary)
    def get_method_comparison_summary(
        request: Request,
        site_id: str | None = None,
        subject_id: str | None = None,
        platform: PLATFORM | None = None,
        capture_mode: CAPTURE_MODE | None = None,
        quality_status: Literal["valid", "repeat", "reject", "all"] = Query(default="valid"),
        connection: sqlite3.Connection = Depends(get_connection),  # noqa: B008
    ) -> MethodComparisonSummary:
        effective_site_id = _resolve_site_scope(request, site_id)
        normalized_quality: QUALITY_STATUS | None = (
            None if quality_status == "all" else quality_status
        )

        rows = _fetch_method_comparison_rows(
            connection,
            site_id=effective_site_id,
            subject_id=subject_id,
            platform=platform,
            capture_mode=capture_mode,
        )
        filters = MethodComparisonFilters(
            site_id=effective_site_id,
            subject_id=subject_id,
            platform=platform,
            capture_mode=capture_mode,
            quality_status=normalized_quality,
        )
        return _build_method_comparison_summary_from_rows(rows=rows, filters=filters)

    @app.get("/api/v1/audit-events", response_model=list[AuditEventItem])
    def list_audit_events(
        request: Request,
        limit: int = Query(default=200, ge=1, le=5000),
        offset: int = Query(default=0, ge=0),
        path: str | None = None,
        site_id: str | None = None,
        status_code: int | None = Query(default=None, ge=100, le=599),
        connection: sqlite3.Connection = Depends(get_connection),  # noqa: B008
    ) -> list[AuditEventItem]:
        effective_site_id = _resolve_site_scope(request, site_id)
        filters: list[str] = []
        values: list[object] = []
        if path:
            filters.append("path = ?")
            values.append(path)
        if effective_site_id:
            filters.append("(site_id = ? OR actor_site_id = ?)")
            values.extend((effective_site_id, effective_site_id))
        if status_code is not None:
            filters.append("status_code = ?")
            values.append(status_code)

        where_sql = ""
        if filters:
            where_sql = "WHERE " + " AND ".join(filters)

        cursor = connection.execute(
            f"""
            SELECT
                id,
                created_at,
                method,
                path,
                status_code,
                auth_result,
                api_key_fingerprint,
                actor_operator_id,
                actor_role,
                actor_site_id,
                request_id,
                session_id,
                site_id,
                subject_id,
                operator_id,
                remote_addr,
                detail_json
            FROM audit_events
            {where_sql}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (*values, limit, offset),
        )
        rows = cursor.fetchall()
        return [_row_to_audit_item(row) for row in rows]

    @app.get("/api/v1/pilot-automation-reports.csv")
    def export_pilot_automation_reports_csv(
        request: Request,
        site_id: str | None = None,
        connection: sqlite3.Connection = Depends(get_connection),  # noqa: B008
    ) -> Response:
        effective_site_id = _resolve_site_scope(request, site_id)
        where_sql, where_values = _build_where_clause(
            [("site_id", effective_site_id)] if effective_site_id else []
        )
        cursor = connection.execute(
            """
            SELECT
                id,
                created_at,
                site_id,
                report_date,
                report_type,
                package_version,
                model_id,
                dataset_id,
                notes,
                payload_json
            FROM pilot_automation_reports
            """
            + f"""
            {where_sql}
            ORDER BY report_date DESC, id DESC
            """,
            tuple(where_values),
        )
        rows = cursor.fetchall()

        from io import StringIO

        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "id",
                "created_at",
                "site_id",
                "report_date",
                "report_type",
                "package_version",
                "model_id",
                "dataset_id",
                "notes",
                "payload_json",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["id"],
                    row["created_at"],
                    row["site_id"],
                    row["report_date"],
                    row["report_type"],
                    row["package_version"],
                    row["model_id"],
                    row["dataset_id"],
                    row["notes"],
                    row["payload_json"],
                ]
            )
        return Response(
            content=buffer.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=pilot_automation_reports.csv"},
        )

    @app.get("/api/v1/capture-packages.csv")
    def export_capture_packages_csv(
        request: Request,
        site_id: str | None = None,
        connection: sqlite3.Connection = Depends(get_connection),  # noqa: B008
    ) -> Response:
        effective_site_id = _resolve_site_scope(request, site_id)
        where_sql, where_values = _build_where_clause(
            [("site_id", effective_site_id)] if effective_site_id else []
        )
        cursor = connection.execute(
            """
            SELECT
                id,
                created_at,
                measured_at,
                session_id,
                site_id,
                subject_id,
                operator_id,
                attempt_number,
                platform,
                device_model,
                app_version,
                capture_mode,
                package_type,
                paired_measurement_id,
                notes,
                capture_payload_json
            FROM capture_packages
            """
            + f"""
            {where_sql}
            ORDER BY measured_at DESC, id DESC
            """,
            tuple(where_values),
        )
        rows = cursor.fetchall()

        from io import StringIO

        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "id",
                "created_at",
                "measured_at",
                "session_id",
                "site_id",
                "subject_id",
                "operator_id",
                "attempt_number",
                "platform",
                "device_model",
                "app_version",
                "capture_mode",
                "package_type",
                "paired_measurement_id",
                "notes",
                "capture_payload_json",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["id"],
                    row["created_at"],
                    row["measured_at"],
                    row["session_id"],
                    row["site_id"],
                    row["subject_id"],
                    row["operator_id"],
                    row["attempt_number"],
                    row["platform"],
                    row["device_model"],
                    row["app_version"],
                    row["capture_mode"],
                    row["package_type"],
                    row["paired_measurement_id"],
                    row["notes"],
                    row["capture_payload_json"],
                ]
            )
        return Response(
            content=buffer.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=capture_packages.csv"},
        )

    @app.get("/api/v1/paired-measurements.csv")
    def export_csv(
        request: Request,
        site_id: str | None = None,
        connection: sqlite3.Connection = Depends(get_connection),  # noqa: B008
    ) -> Response:
        effective_site_id = _resolve_site_scope(request, site_id)
        where_sql, where_values = _build_where_clause(
            [("site_id", effective_site_id)] if effective_site_id else []
        )
        cursor = connection.execute(
            """
            SELECT
                id,
                created_at,
                measured_at,
                session_id,
                site_id,
                subject_id,
                operator_id,
                attempt_number,
                platform,
                device_model,
                app_version,
                capture_mode,
                app_quality_status,
                app_quality_score,
                app_model_id,
                app_qmax_ml_s,
                app_qavg_ml_s,
                app_vvoid_ml,
                app_flow_time_s,
                app_tqmax_s,
                ref_qmax_ml_s,
                ref_qavg_ml_s,
                ref_vvoid_ml,
                ref_flow_time_s,
                ref_tqmax_s,
                ref_device_model,
                ref_device_serial,
                notes
            FROM paired_measurements
            """
            + f"""
            {where_sql}
            ORDER BY measured_at DESC, id DESC
            """,
            tuple(where_values),
        )
        rows = cursor.fetchall()

        from io import StringIO

        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "id",
                "created_at",
                "measured_at",
                "session_id",
                "site_id",
                "subject_id",
                "operator_id",
                "attempt_number",
                "platform",
                "device_model",
                "app_version",
                "capture_mode",
                "app_quality_status",
                "app_quality_score",
                "app_model_id",
                "app_qmax_ml_s",
                "app_qavg_ml_s",
                "app_vvoid_ml",
                "app_flow_time_s",
                "app_tqmax_s",
                "ref_qmax_ml_s",
                "ref_qavg_ml_s",
                "ref_vvoid_ml",
                "ref_flow_time_s",
                "ref_tqmax_s",
                "ref_device_model",
                "ref_device_serial",
                "notes",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["id"],
                    row["created_at"],
                    row["measured_at"],
                    row["session_id"],
                    row["site_id"],
                    row["subject_id"],
                    row["operator_id"],
                    row["attempt_number"],
                    row["platform"],
                    row["device_model"],
                    row["app_version"],
                    row["capture_mode"],
                    row["app_quality_status"],
                    row["app_quality_score"],
                    row["app_model_id"],
                    row["app_qmax_ml_s"],
                    row["app_qavg_ml_s"],
                    row["app_vvoid_ml"],
                    row["app_flow_time_s"],
                    row["app_tqmax_s"],
                    row["ref_qmax_ml_s"],
                    row["ref_qavg_ml_s"],
                    row["ref_vvoid_ml"],
                    row["ref_flow_time_s"],
                    row["ref_tqmax_s"],
                    row["ref_device_model"],
                    row["ref_device_serial"],
                    row["notes"],
                ]
            )

        return Response(
            content=buffer.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=paired_measurements.csv"},
        )

    return app
