# Uroflow Field Mobile (iOS + Android)

Cross-platform mobile client (Expo React Native) for collecting paired measurements:

- App measurement (Qmax/Qavg/Vvoid/...)
- Reference uroflowmeter measurement
- Session metadata (site/subject/operator/device)
- Direct upload to Clinical Hub API
- In-app comparison dashboard (`GET /api/v1/comparison-summary`)
- Offline pending queue with manual sync (`Sync Queue`)
- Retry policy: non-retryable API errors are not re-queued
- Pending items store request header context (`x-api-key`, `x-site-id`, `x-actor-role`, `x-operator-id`)
- Sync reuses stored header context per item (prevents wrong-site replay after settings change)
- Queue controls: `Test API`, `Sync Queue`, `Clear Queue`
- Persisted local settings (`API URL`, `API Key`, `site/operator`, timeout, summary filter)

## Run

1. Install dependencies:

```bash
cd apps/field-mobile
npm install
```

2. Start Expo:

```bash
npm run start
```

Optional local check:

```bash
npm run typecheck
```

3. Open on iPhone/Android via Expo Go (QR code), or run native:

```bash
npm run ios
npm run android
```

## API URL

Set `API Base URL` in the app screen.
If backend API-key protection is enabled, set `API Key` too (sent as `x-api-key` header).

Examples:

- local dev server from same machine: `http://127.0.0.1:8000`
- physical phone to local machine: `http://<LAN_IP_OF_LAPTOP>:8000`

## Clinical Hub payload

App sends `POST /api/v1/paired-measurements` payload aligned to backend schema.
The `Comparison Summary` block loads `GET /api/v1/comparison-summary` with filters.

When backend is configured with API key policy map (`--api-key-map-json`), set in app:
- `API Key` to the site/role key (e.g. operator key)
- `Site ID` to the same site as key policy
- `Actor Role` to policy role (`operator`, `investigator`, `data_manager`, `admin`)
- `Test API` calls `/api/v1/auth-context` to show effective auth/role/site resolution.

CI:
- `.github/workflows/mobile-ci.yml` runs TypeScript typecheck for `apps/field-mobile/**` changes.
