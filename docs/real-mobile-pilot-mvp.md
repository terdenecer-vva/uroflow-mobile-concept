# Real Mobile Pilot MVP (iPhone + Android)

This package enables real-world pilot collection for `app vs reference uroflowmeter`.

## Components

1. **Clinical Hub API (FastAPI + SQLite)**
2. **Field Mobile App (Expo React Native, iOS + Android)**
3. **CSV export for model/biostatistics pipelines**

## 1) Start Clinical Hub API

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[clinical-api,dev]"

PYTHONPATH=src python -m uroflow_mobile.cli serve-clinical-hub \
  --db-path data/clinical_hub.db \
  --api-key PILOT_SHARED_KEY \
  --host 0.0.0.0 \
  --port 8000
```

For multi-site role-bound keys:

```bash
PYTHONPATH=src python -m uroflow_mobile.cli serve-clinical-hub \
  --db-path data/clinical_hub.db \
  --api-key-map-json config/clinical_hub_api_keys.json \
  --host 0.0.0.0 \
  --port 8000
```

API endpoints:
- `GET /health`
- `GET /api/v1/auth-context`
- `POST /api/v1/paired-measurements`
- `GET /api/v1/paired-measurements`
- `GET /api/v1/paired-measurements/{id}`
- `GET /api/v1/paired-measurements.csv`
- `GET /api/v1/comparison-summary`
- `GET /api/v1/audit-events`

CI note:
- `.github/workflows/clinical-hub-contract.yml` runs targeted contract checks for Clinical Hub surfaces.

Idempotency notes:
- `POST /api/v1/paired-measurements`: identity replay returns `200`, conflict returns `409`.
- `POST /api/v1/capture-packages`: identity replay returns `200`, conflict returns `409`.
- `POST /api/v1/pilot-automation-reports`: identity replay returns `200`, conflict returns `409`.

Recommended headers for pilot traceability and access scope:
- `x-api-key`: shared pilot key
- `x-operator-id`: operator or nurse id
- `x-site-id`: clinic/site id (required for scoped operator workflows)
- `x-actor-role`: `operator`, `investigator`, `data_manager`, `admin`
- `x-request-id`: unique request id

Site scope behavior:
- `operator`/`investigator`: reads and writes are restricted to `x-site-id`;
- `operator`: actor `operator_id` is mandatory (`x-operator-id`, session payload, or mapped policy value), otherwise request is rejected with `403`;
- `operator`: list/read/summary/csv are auto-filtered by operator and cross-operator writes are rejected with `403`;
- `data_manager`/`admin`: cross-site access is allowed.
- if API key policy map is enabled, role/site are resolved from key policy first.

## 2) Run iPhone/Android app

```bash
cd apps/field-mobile
npm install
npm run start
```

In app set `API Base URL`:
- Simulator on same machine: `http://127.0.0.1:8000`
- Physical phone: `http://<LAN_IP_OF_LAPTOP>:8000`
- Set `API Key` if backend was started with `--api-key`.

## 3) Export paired dataset to CSV

```bash
PYTHONPATH=src python -m uroflow_mobile.cli export-paired-measurements \
  --db-path data/clinical_hub.db \
  --output-csv data/paired_measurements_export.csv
```

Optional integrity manifest:

```bash
PYTHONPATH=src python -m uroflow_mobile.cli export-paired-measurements \
  --db-path data/clinical_hub.db \
  --output-csv data/paired_measurements_export.csv \
  --sha256-file data/paired_measurements_export.csv.sha256
```

Generate method-comparison summary (`app vs reference`):

```bash
PYTHONPATH=src python -m uroflow_mobile.cli summarize-paired-measurements \
  --db-path data/clinical_hub.db \
  --quality-status valid \
  --output-json data/method_comparison_summary.json
```

Export audit trail:

```bash
PYTHONPATH=src python -m uroflow_mobile.cli export-audit-events \
  --db-path data/clinical_hub.db \
  --output-csv data/audit_events_export.csv
```

## Minimal pilot workflow

1. Operator runs app measurement.
2. Operator runs reference uroflowmeter measurement.
3. Operator enters both in mobile app and submits one paired record.
4. If network/API unavailable, app stores the record in local pending queue.
5. Pending item keeps its request header context (`x-api-key`, `x-site-id`, `x-actor-role`, `x-operator-id`).
6. Operator syncs pending queue after connectivity is restored.
7. Data manager exports CSV + summary JSON + audit CSV daily for QA/statistics.

## Next hardening targets

1. Stronger auth model (per-site/per-role API keys instead of shared key).
2. Immutable audit log and e-signature flow.
3. Encrypted media upload (if raw capture retained).
4. Site-level dashboards and discrepancy workflow.
