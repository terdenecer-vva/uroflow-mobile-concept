# Uroflow Field Mobile (iOS + Android)

Cross-platform mobile client (Expo React Native) for collecting paired measurements:

- App measurement (Qmax/Qavg/Vvoid/...)
- Reference uroflowmeter measurement
- Session metadata (site/subject/operator/device)
- Traceability `sync_id` for linkage with capture artifacts and reference uroflow export
- Direct upload to Clinical Hub API
- In-app comparison dashboard (`GET /api/v1/comparison-summary`)
- In-app capture coverage dashboard (`GET /api/v1/capture-coverage-summary`)
- `Load Both Summaries` button refreshes comparison + coverage in one action
- Coverage ratio is color-coded against target 90% (`>=90%` green, `<90%` red)
- Offline pending queue with manual sync (`Sync Queue`)
- Offline pending queue stores both endpoint jobs: `paired-measurements` and `capture-packages`
- Retry policy: non-retryable API errors are not re-queued
- Pending items store request header context (`x-api-key`, `x-site-id`, `x-actor-role`, `x-operator-id`)
- Pending retries reuse a stable `x-request-id` per endpoint job to reduce duplicate risk after timeout/retry
- Sync reuses stored header context per item (prevents wrong-site replay after settings change)
- Pending queue preview shows error categories, not raw server response bodies
- Operator-facing API errors keep HTTP status but redact raw response bodies into safe categories
- Sync runs in bounded batches of 10 queued jobs to avoid long foreground stalls on large offline queues
- Auto-sync retries queued jobs every ~25s only after API Base URL is configured
- Queue controls: `Test API`, `Sync Queue`, `Clear Queue`
- Clinical Hub preflight is shown in the API block; missing/invalid URLs and obvious
  cross-region Hub targets are blocked before `Test API`, `Submit`, or `Sync Queue`.
- All Clinical Hub requests include non-secret `x-uroflow-*` trace headers for app version,
  model/schema, runtime mode, endpoint set, and data-residency policy.
- Persisted local settings (`API URL`, `site/operator`, timeout, summary filter)
- `API Key` stored in device secure storage (`expo-secure-store`) with AsyncStorage fallback
- `Device Model` defaults from Expo Device metadata with platform fallback and remains editable for field correction.
- On successful paired upload, app posts `capture_contract_json` to `POST /api/v1/capture-packages`
- Runtime capture mode collects live audio + IMU samples (camera permission used for ROI validity flag)
- `Start Capture` is blocked until camera permission, camera preview readiness, ROI lock,
  and at least one valid ROI frame are confirmed.
- In-app `Release Identity` panel shows canonical app version, model/schema, runtime config, privacy/data-residency flags, platform, and payload traceability alignment.
- If runtime capture was not started, app falls back to scaffold contract payload
- `Stop Capture` auto-fills app metrics (`Qmax/Qavg/Vvoid/FlowTime/TQmax`) and quality status/score from runtime-derived proxies
- Runtime block shows `roi_valid_ratio` and `low_confidence_ratio` quality flags
- Runtime block includes in-app `Q(t)` preview for operator review before submission
- Runtime capture contract analysis includes `runtime_timeline` timing integrity metadata
  (`duration_s`, sample count, median sample step, max gap, and gap warning).

## Run

1. Install dependencies:

```bash
cd apps/field-mobile
npm ci
```

2. Start Expo:

```bash
npm run start
```

If `npm run start` hits `EMFILE` on macOS without `watchman`, use the stable device-launch path:

```bash
npm run start:device
```

This mode keeps Metro up for Expo Go on a physical phone over LAN, publishes the laptop LAN IP into the Expo manifest, and disables live reload (`CI=1`) to avoid file-watcher exhaustion.

Optional local checks:

```bash
npm run typecheck
npm run validate:ci
```

`validate:ci` mirrors Mobile CI: TypeScript, Node unit tests for mobile helper/API,
capture-contract, ROI signal, and runtime metric/quality invariants, Expo Doctor,
production dependency audit, and Expo export bundle builds for both iOS and Android.

3. Open on iPhone/Android via Expo Go (QR code), or run native:

```bash
npm run ios
npm run android
```

Notes:
- `npm run start:device` is the recommended path for field smoke runs when the machine does not have `watchman`.
- `.watchmanconfig` is checked in so a future `watchman` install can scope watches to `apps/field-mobile` instead of the repository root.

## Runtime Capture Flow

1. In app, tap `Start Capture` before the test.
2. Complete voiding and tap `Stop Capture`.
3. Verify `Contract payload: ready`.
4. Submit paired measurement as usual.

Notes:
- Runtime capture currently logs sampled audio metering + motion, and derives proxy level traces.
- Camera preview + ROI lock state are included in runtime quality gating.
- Runtime quality scoring includes `roi_valid_ratio`, `low_confidence_ratio`, and `high_motion_ratio`.
- Runtime contract analysis includes `runtime_timeline` so Clinical Hub evidence can flag
  timing gaps caused by foreground stalls or device load.
- Raw media is not stored by default (privacy-by-default behavior).
- Capture contract payloads include a derivatives-only `feature_manifest` with sample count,
  derived feature keys, and raw media storage/upload flags pinned to `false`.

## API URL

Set `API Base URL` in the app screen.
If backend API-key protection is enabled, set `API Key` too (sent as `x-api-key` header).
The API block shows a preflight result. Missing/unsupported URLs block field actions.
Local/LAN URLs are allowed with a warning for smoke tests. HTTPS URLs with an obvious
non-US region token are blocked because the pilot runtime policy requires the configured
single-region Clinical Hub.
Requests add `x-uroflow-app-version`, `x-uroflow-model-id`,
`x-uroflow-capture-schema-version`, `x-uroflow-runtime-mode`,
`x-uroflow-endpoint-set`, and data-residency headers so Clinical Hub logs can be
matched to the release manifest without exposing API keys or PHI.

Examples:

- local dev server from same machine: `http://127.0.0.1:8000`
- physical phone to local machine: `http://<LAN_IP_OF_LAPTOP>:8000`

## Clinical Hub payload

App sends `POST /api/v1/paired-measurements` payload aligned to backend schema.
The `Comparison Summary` block loads `GET /api/v1/comparison-summary` with filters.
The `Capture Coverage Summary` block loads `GET /api/v1/capture-coverage-summary` with the same filters.
`Sync ID` can be entered manually (or auto-generated) and used as `sync_id` filter in summary view.
`Platform` defaults to current OS (`ios`/`android`) and can be overridden for troubleshooting.

When backend is configured with API key policy map (`--api-key-map-json`), set in app:
- `API Key` to the site/role key (e.g. operator key)
- `Site ID` to the same site as key policy
- `Actor Role` to policy role (`operator`, `investigator`, `data_manager`, `admin`)
- `Test API` calls `/api/v1/auth-context` to show effective auth/role/site resolution.

CI:
- `.github/workflows/mobile-ci.yml` runs `npm run validate:ci` for `apps/field-mobile/**` changes.
- `validate:ci` covers TypeScript, Clinical Hub API client/connection check/summary requests + mobile helper/API + runtime config + submit outcome + paired/capture-package payload + capture-contract + ROI signal + runtime metric + pending queue + deterministic sync smoke + storage unit tests, Expo Doctor, production dependency audit, and iOS/Android Expo exports.
- `.github/workflows/mobile-build.yml` runs release preflight for mobile app/release-script changes and provides manual EAS build/submit triggers (`workflow_dispatch`) with inputs:
  - `build_profile` (`preview` / `development` / `production`)
  - `build_platform` (`all` / `ios` / `android`)
  - `wait_for_build` (`true` / `false`)
  - `submit_to_store` (`true` / `false`; submits the latest production build only when authenticated EAS readiness is `pass`)
  - `submit_platform` (`all` / `ios` / `android`)
  - `wait_for_submit` (`true` / `false`)
  - `what_to_test` (optional TestFlight text for iOS submit)
  - `release_notes` (operator-facing handoff notes archived as `mobile-release-notes`)
- `mobile-build` uploads:
  - `mobile-release-manifest` (version + runtime release metadata/config + release notes digest + capture contract feature-manifest evidence + readiness gate summary + git SHA + model/schema traceability)
  - `mobile-release-readiness` (git traceability + local readiness checks + explicit external credential blockers)
  - `mobile-release-notes` (operator-facing release notes and required evidence reminders)
  - `mobile-release-bundle-verification` (manifest/readiness/notes/store-handoff digest and traceability consistency summary)
  - `mobile-store-rollout-handoff` (per-run TestFlight/Play Internal handoff template + validation summary with current external blockers)
  - `mobile-eas-build-result-<run_id>` (raw EAS JSON response for build IDs/URLs)
  - `mobile-eas-submit-result-<run_id>` (raw EAS submit log + exit code when `submit_to_store=true`)
- Workflow summary includes release readiness status and direct EAS build links for operator/release use.

## Release Readiness Handoff

`mobile-release-readiness` intentionally separates local readiness from external account and
secret blockers. The artifact has separate machine-readable gates:

- `local_checks_status`: local app metadata, runtime release metadata, EAS profile shape,
  EAS production submit shape for TestFlight / Play Internal Testing handoff,
  runtime config/defaults such as Clinical Hub v1 endpoint set, disabled debug gates,
  privacy-by-default switches, single-region data residency policy, Expo Device identity defaults,
  Clinical Hub preflight guard,
  Clinical Hub runtime trace headers,
  in-app release identity evidence,
  runtime capture preflight guard, runtime motion quality gates, derivatives-only feature/media
  manifest gates, pending sync connectivity-restore trigger, device-smoke evidence template/validator,
  store rollout handoff template/validator, release bundle verifier,
  API response + submit exception + runtime exception PHI redaction, and non-localhost API URL defaults,
  store privacy declarations,
  launch/icon assets, dependency lock alignment, and unit-test evidence that can be verified
  without external credentials.
- `authenticated_eas_status`: whether `EXPO_TOKEN` and deterministic EAS project identity are ready for an authenticated EAS build trigger.
- `clinical_hub_live_api_status`: whether live Clinical Hub API smoke/report-push credentials are configured with an `https` non-localhost URL.
- `external_readiness_status`: aggregate external status across Expo/EAS + Clinical Hub.

When status is `ready_except_external_credentials`, use `next_actions` in the artifact as the
release handoff checklist:

| next action | Required setup | Verification |
| --- | --- | --- |
| `configure_expo_token` | `gh secret set EXPO_TOKEN --body "<expo_access_token>"` | Re-run `Mobile Build`; `external_items.expo_token` becomes `present`. |
| `configure_eas_project_identity` | `gh variable set EAS_PROJECT_ID --body "<eas_project_uuid>"` or commit `expo.extra.eas.projectId` in `app.json` | Re-run `Mobile Build`; `external_items.eas_project_identity` becomes `present`. |
| `configure_clinical_hub_live_api` | `gh secret set CLINICAL_HUB_URL --body "https://<clinical-hub>"` and `gh secret set CLINICAL_HUB_API_KEY --body "<api_key>"` | Re-run `Mobile Build`; `external_items.clinical_hub_live_api` becomes `present` rather than `missing`/`invalid`. |
| `provision_apple_developer_account` | Apple Developer access, App Store Connect app record, signing certificates/profiles, and TestFlight permissions | Trigger signed iOS EAS build and confirm TestFlight upload readiness. |
| `provision_google_play_account` | Google Play Console access, Android signing, internal testing track permissions, and EAS file secret `GOOGLE_SERVICE_ACCOUNT` | Trigger signed Android EAS build and confirm Play Internal Testing upload readiness. |

Do not commit secret values. Keep live Clinical Hub keys in GitHub Actions secrets and device-local
app settings only.

On manual `Mobile Build` dispatch, the `eas-build` job runs only when `authenticated_eas_status`
is `pass`. If it is `blocked`, the run still uploads readiness/manifest artifacts and skips the EAS
trigger by design.

## Installable Build (EAS)

EAS profiles are configured in `apps/field-mobile/eas.json`:
- `development` (internal dev client)
- `preview` (internal distribution; Android APK)
- `production`

Local trigger (requires Expo auth):

```bash
cd apps/field-mobile
npx eas build --platform all --profile preview
```

or via npm script:

```bash
npm run build:preview
```

Production store submit commands are also wired for authenticated release handoff:

```bash
npm run submit:ios:production
npm run submit:android:production
npm run submit:production
```

iOS submit still requires the external App Store Connect app record and Apple credentials.
Android submit uses `submit.production.android.serviceAccountKeyPath=@secret:GOOGLE_SERVICE_ACCOUNT`
and targets the Play Internal Testing track. All submit scripts use `--latest` so non-interactive
handoff submits the latest completed EAS production build rather than prompting for build selection.

Detailed release SOP:
- `docs/mobile-release-runbook-v0.1.md`
- `docs/mobile-install-and-field-test-runbook-v0.1.md`
- `docs/mobile-store-rollout-handoff-template-v0.1.json`
- `scripts/verify_mobile_release_bundle.py`
