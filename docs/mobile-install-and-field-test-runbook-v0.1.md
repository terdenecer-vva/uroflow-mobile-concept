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

## 4. First Launch Configuration

In app API section set:

- `API Base URL`: `http://<HUB_HOST>:8000`
- `API Key`: operator key
- `Actor Role`: `operator`
- `Site ID`: clinic/site code
- `Operator ID`: current operator code

Verify with `Test API` button before first patient run.

## 5. Paired Test Workflow

Per subject/attempt:

1. Prepare reference uroflowmeter as per clinic SOP.
2. In app, lock ROI, press `Start Capture`, then record voiding.
3. Press `Stop Capture`.
4. Check runtime block:
   - `quality score/status`
   - `roi_valid_ratio` and `low_confidence_ratio`
   - `Runtime Q(t) Preview`
5. Enter reference metrics (`Qmax/Qavg/Vvoid` and optional time metrics).
6. Submit paired measurement.
7. If network failed, ensure queue item exists and run `Sync Queue` later.

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
  - capture package missing in joined export.

## 8. Security And Privacy Minimum

- Use operator/site scoped API keys only.
- Keep `store_raw_video=false` and `store_raw_audio=false` in capture contract.
- Export files to controlled clinic storage.
- For RF deployments, keep DB and processing in RF-hosted infrastructure.

## 9. Exit Criteria For v0.1 Pilot

- App installed and operating on iOS and Android.
- At least 100 paired attempts collected.
- At least 90% of paired rows have capture package linkage (`has_capture_package=1` in joined export).
- Method-comparison summary generated from production pilot DB.
