# Mobile Install And Field Test Runbook (v0.1)

## Scope

This runbook defines how to install the mobile app on iPhone and Android and run paired tests against a reference uroflowmeter, with export-ready data for analysis.

## 1. Minimum Environment

- Backend host reachable from clinic Wi-Fi/LAN.
- Python 3.11+ with project dependencies.
- Expo/EAS account and app signing set up.
- At least one iPhone and one Android device.
- Reference uroflowmeter available for paired measurement.

## 2. Backend Start (Clinical Hub)

```bash
cd /Users/denecer/Documents/uroflow-mobile-concept
PYTHONPATH=src python -m uroflow_mobile.cli serve-clinical-hub \
  --db-path data/clinical_hub.db \
  --api-key-map-json config/clinical_hub_api_keys.json \
  --host 0.0.0.0 \
  --port 8000
```

Health checks:

```bash
curl -s http://<HUB_HOST>:8000/health
curl -s -H "x-api-key: <OPERATOR_KEY>" http://<HUB_HOST>:8000/api/v1/auth-context
```

## 3. Mobile Build And Install

Project path:

```bash
cd /Users/denecer/Documents/uroflow-mobile-concept/apps/field-mobile
```

For Expo Go smoke/install checks on macOS without `watchman`, start the app with:

```bash
npm ci
npm run start:device
```

This keeps Metro stable and publishes the laptop LAN IP into the Expo manifest for a physical phone on the same network.

iOS internal build:

```bash
eas build --platform ios --profile preview
```

Android internal build:

```bash
eas build --platform android --profile preview
```

Install:

- iOS: install via TestFlight/internal distribution link.
- Android: install `.apk`/`.aab` from EAS artifact link.

For release handoff, download the Mobile Build `mobile-store-rollout-handoff`
artifact and fill in TestFlight/Play Internal build links, tester group/track,
and distribution checks after external Apple/Google account setup is complete.
Validate the filled handoff before field use:

```bash
python3 scripts/validate_mobile_store_rollout_handoff.py \
  /tmp/mobile-store-rollout-handoff.json \
  --output /tmp/mobile-store-rollout-summary.json
```

## 4. First Launch Configuration

In app API section set:

- `API Base URL`: `http://<HUB_HOST>:8000`
- `API Key`: operator key
- `Actor Role`: `operator`
- `Site ID`: clinic/site code
- `Operator ID`: current operator code
- `Device Model`: auto-filled from Expo Device metadata; correct it manually only if the displayed physical model is wrong.

Verify with `Test API` button before first patient run.
Pending queue auto-sync stays paused until `API Base URL` is configured and starts with
`http://` or `https://`.

Before field use, verify the in-app `Release Identity` panel:
- App version, model ID, and capture schema match the Mobile Build manifest.
- Runtime mode is `pilot`, endpoint set is `clinical_hub_v1`, and default capture mode is `water_impact`.
- Privacy flags show raw video/audio off and ROI-only on.
- Data residency shows `us/single_region` with cross-region sync off.
- Device platform/model match the physical device that will be recorded in the smoke log.
- `Payload traceability` is `aligned`; if it shows `edited`, reset the App Version, Model ID, and Capture Mode fields before collecting pilot data.

## 5. Paired Test Workflow

Per subject/attempt:

1. Prepare reference uroflowmeter as per clinic SOP.
2. In app, lock ROI and wait until `ROI frames` is at least `1` and `valid: yes`.
3. Press `Start Capture`, then record voiding. If the app shows `Capture preflight blocked`,
   fix the listed camera/preview/ROI issue before retrying.
4. Press `Stop Capture`.
5. Check runtime block:
   - `quality score/status`
   - `roi_valid_ratio` and `low_confidence_ratio`
   - `Runtime Q(t) Preview`
   - after export, `capture_payload.analysis.runtime_timeline.gap_warning=false`
     or an operator note explaining the timing interruption
6. Enter reference metrics (`Qmax/Qavg/Vvoid` and optional time metrics).
7. Submit paired measurement.
8. If network failed, ensure queue item exists and run `Sync Queue` later.
9. For retry/audit troubleshooting, match the pending item `request_id` to Clinical Hub request logs.

For release handoff, copy `docs/mobile-device-smoke-log-template-v0.1.json`, fill one
iPhone and one Android run, then validate it:

```bash
python3 scripts/validate_mobile_device_smoke_log.py \
  /tmp/mobile-device-smoke-log.json \
  --output /tmp/mobile-device-smoke-summary.json
```

The validator requires all mandatory smoke checks to pass on both platforms, including
offline queue retention, connectivity-restore sync, raw media disabled, and device-log
review for PHI/secret leakage.

## 6. Daily Export For Analysis

Paired records:

```bash
PYTHONPATH=src python -m uroflow_mobile.cli export-paired-measurements \
  --db-path data/clinical_hub.db \
  --output-csv data/paired_measurements_export.csv
```

Capture packages:

```bash
PYTHONPATH=src python -m uroflow_mobile.cli export-capture-packages \
  --db-path data/clinical_hub.db \
  --output-csv data/capture_packages_export.csv
```

Joined paired+capture (recommended for model/error analysis):

```bash
PYTHONPATH=src python -m uroflow_mobile.cli export-paired-with-capture \
  --db-path data/clinical_hub.db \
  --output-csv data/paired_with_capture_export.csv
```

Quick API coverage check (for QA dashboard):

```bash
curl -s \
  -H "x-api-key: <DATA_MANAGER_OR_SITE_KEY>" \
  "http://<HUB_HOST>:8000/api/v1/capture-coverage-summary?site_id=<SITE_ID>&quality_status=all"
```

Daily coverage summary export (CSV/PDF):

```bash
PYTHONPATH=src python -m uroflow_mobile.cli export-capture-coverage-summary \
  --db-path data/clinical_hub.db \
  --site-id <SITE_ID> \
  --sync-id <SYNC_ID> \
  --quality-status all \
  --output-csv data/capture_coverage_summary_<SYNC_ID>.csv \
  --output-pdf data/capture_coverage_summary_<SYNC_ID>.pdf
```

Coverage summary + pilot gate evaluation:

```bash
PYTHONPATH=src python -m uroflow_mobile.cli export-capture-coverage-summary \
  --db-path data/clinical_hub.db \
  --site-id <SITE_ID> \
  --quality-status all \
  --output-csv data/capture_coverage_summary_<SITE_ID>.csv \
  --targets-config config/coverage_targets_config.v1.json \
  --gates-output-json data/capture_coverage_gates_<SITE_ID>.json \
  --fail-on-hard-gates
```

GitHub Actions automation:

- Workflow: `/Users/denecer/Documents/uroflow-mobile-concept/.github/workflows/capture-coverage-report.yml`
- Schedule: daily at `02:30 UTC`.
- Recommended secrets/variables:
  - `CLINICAL_HUB_URL`
  - `CLINICAL_HUB_API_KEY`
  - `CLINICAL_HUB_SITE_ID` (repository variable)
  - `CLINICAL_HUB_COVERAGE_TARGETS_CONFIG` (default: `config/coverage_targets_config.v1.json`)
  - `CLINICAL_HUB_ENFORCE_COVERAGE_GATES` (`true`/`false`)
- Optional fallback:
  - `CLINICAL_HUB_DB_URL`

## 7. Data Quality Gates (Operational)

- Reject run if app cannot detect event or operator moved phone heavily.
- Repeat run if app `quality_status=repeat`.
- Flag run for review if:
  - `roi_valid_ratio < 0.80`
  - `low_confidence_ratio > 0.35`
  - `analysis.runtime_timeline.gap_warning=true`
  - capture package missing in joined export.

## 8. Security And Privacy Minimum

- Use operator/site scoped API keys only.
- Keep `store_raw_video=false` and `store_raw_audio=false` in capture contract.
- Export files to controlled clinic storage.
- For RF deployments, keep DB and processing in RF-hosted infrastructure.

## 9. Exit Criteria For v0.1 Pilot

- App installed and operating on iOS and Android.
- Validated store rollout handoff archived for TestFlight/Play Internal or EAS preview distribution.
- Validated iOS+Android smoke log summary archived.
- At least 100 paired attempts collected.
- At least 90% of paired rows have capture package linkage (`has_capture_package=1` in joined export).
- Method-comparison summary generated from production pilot DB.
