from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from uroflow_mobile.clinical_hub import create_clinical_hub_app


def _payload(
    session_id: str,
    site_id: str,
    subject_id: str,
    *,
    sync_id: str | None = None,
    platform: str = "ios",
    device_model: str = "iPhone15,3",
) -> dict[str, object]:
    return {
        "session": {
            "session_id": session_id,
            "sync_id": sync_id,
            "site_id": site_id,
            "subject_id": subject_id,
            "operator_id": "OP-01",
            "attempt_number": 1,
            "measured_at": "2026-02-25T08:00:00Z",
            "platform": platform,
            "device_model": device_model,
            "app_version": "0.3.0",
            "capture_mode": "water_impact",
        },
        "app": {
            "metrics": {
                "qmax_ml_s": 18.4,
                "qavg_ml_s": 9.7,
                "vvoid_ml": 305.0,
                "flow_time_s": 22.0,
                "tqmax_s": 5.1,
            },
            "quality_status": "valid",
            "quality_score": 90.0,
            "model_id": "fusion-v0.3",
        },
        "reference": {
            "metrics": {
                "qmax_ml_s": 18.9,
                "qavg_ml_s": 10.0,
                "vvoid_ml": 312.0,
                "flow_time_s": 21.7,
                "tqmax_s": 4.9,
            },
            "device_model": "Uroflow Classic",
            "device_serial": "UF-998877",
        },
        "notes": "mobile e2e",
    }


def _is_retryable(status_code: int | None) -> bool:
    if status_code is None:
        return True
    if status_code >= 500:
        return True
    return status_code in {408, 425, 429}


def test_mobile_queue_sync_e2e_with_policy_key_and_idempotency(tmp_path: Path) -> None:
    db_path = tmp_path / "clinical_hub_mobile_sync.db"
    app = create_clinical_hub_app(
        db_path,
        api_key_policy_map={
            "op-site-1-key": {
                "role": "operator",
                "site_id": "SITE-001",
                "operator_id": "OP-01",
            },
        },
    )

    # Queue includes:
    # 1) valid record
    # 2) replay of same record (should return 200 and remain idempotent)
    # 3) cross-site payload (403, non-retryable, must be dropped)
    queue: list[dict[str, object]] = [
        {
            "id": "PENDING-1",
            "payload": _payload(
                "session-mobile-001",
                "SITE-001",
                "SUBJ-001",
                sync_id="sync-mobile-001",
            ),
            "headers": {"x-api-key": "op-site-1-key"},
        },
        {
            "id": "PENDING-2",
            "payload": _payload(
                "session-mobile-001",
                "SITE-001",
                "SUBJ-001",
                sync_id="sync-mobile-001",
            ),
            "headers": {"x-api-key": "op-site-1-key"},
        },
        {
            "id": "PENDING-3",
            "payload": _payload(
                "session-mobile-002",
                "SITE-002",
                "SUBJ-002",
                sync_id="sync-mobile-002",
            ),
            "headers": {"x-api-key": "op-site-1-key"},
        },
    ]

    synced = 0
    dropped_non_retryable = 0
    remaining_retryable: list[dict[str, object]] = []

    with TestClient(app) as client:
        for item in queue:
            response = client.post(
                "/api/v1/paired-measurements",
                json=item["payload"],
                headers=item["headers"],
            )
            if 200 <= response.status_code < 300:
                synced += 1
                continue
            if _is_retryable(response.status_code):
                remaining_retryable.append(item)
                continue
            dropped_non_retryable += 1

        assert synced == 2
        assert dropped_non_retryable == 1
        assert remaining_retryable == []

        listing = client.get("/api/v1/paired-measurements", headers={"x-api-key": "op-site-1-key"})
        assert listing.status_code == 200
        listed_rows = listing.json()
        assert len(listed_rows) == 1
        assert listed_rows[0]["site_id"] == "SITE-001"
        assert listed_rows[0]["sync_id"] == "sync-mobile-001"

        summary = client.get(
            "/api/v1/comparison-summary",
            params={"quality_status": "all", "sync_id": "sync-mobile-001"},
            headers={"x-api-key": "op-site-1-key"},
        )
        assert summary.status_code == 200
        summary_payload = summary.json()
        assert summary_payload["records_considered"] == 1
        assert summary_payload["filters"]["sync_id"] == "sync-mobile-001"


def test_mobile_queue_sync_e2e_android_ios_and_platform_filter(tmp_path: Path) -> None:
    db_path = tmp_path / "clinical_hub_mobile_sync_platform.db"
    app = create_clinical_hub_app(
        db_path,
        api_key_policy_map={
            "op-site-1-key": {
                "role": "operator",
                "site_id": "SITE-001",
                "operator_id": "OP-01",
            },
        },
    )

    queue: list[dict[str, object]] = [
        {
            "id": "PENDING-A1",
            "payload": _payload(
                "session-mobile-android-001",
                "SITE-001",
                "SUBJ-101",
                sync_id="sync-android-001",
                platform="android",
                device_model="Pixel 8",
            ),
            "headers": {"x-api-key": "op-site-1-key"},
        },
        {
            "id": "PENDING-A2",
            "payload": _payload(
                "session-mobile-android-001",
                "SITE-001",
                "SUBJ-101",
                sync_id="sync-android-001",
                platform="android",
                device_model="Pixel 8",
            ),
            "headers": {"x-api-key": "op-site-1-key"},
        },
        {
            "id": "PENDING-I1",
            "payload": _payload(
                "session-mobile-ios-001",
                "SITE-001",
                "SUBJ-102",
                sync_id="sync-ios-001",
                platform="ios",
                device_model="iPhone15,3",
            ),
            "headers": {"x-api-key": "op-site-1-key"},
        },
    ]

    with TestClient(app) as client:
        success_codes = 0
        for item in queue:
            response = client.post(
                "/api/v1/paired-measurements",
                json=item["payload"],
                headers=item["headers"],
            )
            if 200 <= response.status_code < 300:
                success_codes += 1
            else:
                raise AssertionError(f"unexpected status={response.status_code}")

        assert success_codes == 3

        listing = client.get("/api/v1/paired-measurements", headers={"x-api-key": "op-site-1-key"})
        assert listing.status_code == 200
        rows = listing.json()
        assert len(rows) == 2
        assert {row["platform"] for row in rows} == {"android", "ios"}

        android_summary = client.get(
            "/api/v1/comparison-summary",
            params={
                "quality_status": "all",
                "platform": "android",
                "sync_id": "sync-android-001",
            },
            headers={"x-api-key": "op-site-1-key"},
        )
        assert android_summary.status_code == 200
        android_summary_payload = android_summary.json()
        assert android_summary_payload["records_considered"] == 1
        assert android_summary_payload["filters"]["platform"] == "android"
        assert android_summary_payload["filters"]["sync_id"] == "sync-android-001"
