# Mobile Release Runbook v0.1 (iOS + Android)

Date: 2026-02-25
Scope: pilot installable builds for Uroflow Field Mobile

## 1) Preconditions

1. App code merged to target branch.
2. `apps/field-mobile/eas.json` profiles updated.
3. GitHub secret `EXPO_TOKEN` configured.
4. `EAS_PROJECT_ID` configured as a GitHub repo variable or `expo.extra.eas.projectId` set in `app.json`.
5. Expo project credentials configured for iOS and Android signing.
6. App Store Connect app record exists for the iOS bundle ID before TestFlight submit.
7. Google Play Console app exists for the Android package and EAS file secret `GOOGLE_SERVICE_ACCOUNT` is configured for Play API submit.
8. Clinical Hub secrets configured when live API smoke/report push is part of the release:
   - `CLINICAL_HUB_URL` (`https://...`, non-localhost for live release readiness)
   - `CLINICAL_HUB_API_KEY`

## 2) Trigger preview build

From GitHub Actions:
1. Open workflow `Mobile Build`.
2. Run `workflow_dispatch` and set:
   - `build_profile` (`preview` for pilot by default),
   - `build_platform` (`all`/`ios`/`android`),
   - `wait_for_build` (`false` for fast trigger, `true` for full wait mode),
   - `submit_to_store` (`false` by default; set `true` only after a signed production build is ready),
   - `submit_platform` (`all`/`ios`/`android`),
   - `wait_for_submit` (`false` for fast trigger, `true` for full submit wait mode),
   - `what_to_test` for optional TestFlight notes when submitting iOS,
   - `release_notes` for operator-facing clinic handoff notes.
3. Verify `preflight` passes.
4. Open workflow summary (`Mobile Release Readiness`) and confirm:
   - `Local checks` is `pass`,
   - `Authenticated EAS readiness` is `pass` before attempting an EAS build trigger,
   - `Clinical Hub live API` is `present` before live API smoke/report push is expected,
   - missing or invalid external items are understood and either configured or accepted as blockers for this run.
   - `Next actions` maps the remaining external blockers to concrete setup tasks.
5. Verify `eas-build` starts when a build is requested. If `Authenticated EAS readiness` is `blocked`, authenticated EAS jobs are skipped by design and the readiness artifact is the handoff output.
6. Open workflow summary (`Mobile EAS Build`) and copy build links.
7. Download artifact `mobile-eas-build-result-<run_id>` for traceability JSON.
8. If `submit_to_store=true`, open workflow summary (`Mobile EAS Submit`) and download artifact `mobile-eas-submit-result-<run_id>` for the EAS submit log and exit code.

Local fallback:

```bash
cd apps/field-mobile
npm run build:preview
```

Production store-submit fallback after a signed production build is available:

```bash
cd apps/field-mobile
npm run submit:ios:production
npm run submit:android:production
# or submit both platforms from the production profile:
npm run submit:production
```

Do not commit Apple credentials or Google service-account JSON. Android submit is configured to read
the Google Play service account as EAS file secret `GOOGLE_SERVICE_ACCOUNT`; iOS submit still depends
on Apple Developer/App Store Connect credentials and the external app record. Submit commands use
`--latest` and therefore submit the latest completed production EAS build for the selected platform.

## 3) Release manifest and traceability

Workflow generates artifact `mobile-release-manifest` containing:
- app version and package IDs,
- release notes metadata (`present`, byte size, SHA-256, title) without embedding the full notes body,
- iOS build number and Android versionCode,
- icon/adaptive-icon paths, `expo-splash-screen` image path, SHA-256 fingerprints, byte sizes, PNG dimensions, and splash background/resize/width config,
- runtime release metadata from `apps/field-mobile/src/config/releaseMetadata.ts` for app version, model ID, and capture schema version,
- runtime app config from `apps/field-mobile/src/config/appConfig.ts` for pilot mode, Clinical Hub v1 endpoint set, default capture mode, privacy-by-default switches, single-region data residency policy, and disabled debug gates,
- EAS production submit config shape for iOS handoff and Android Play Internal Testing via `@secret:GOOGLE_SERVICE_ACCOUNT`,
- Clinical Hub preflight guard evidence proving the app blocks missing/unsupported URLs and obvious cross-region Hub targets before Test API, Submit, or Sync Queue,
- Clinical Hub request trace header evidence proving app/model/schema, runtime mode, endpoint set, and data-residency policy are sent as non-secret `x-uroflow-*` headers on API checks, submissions, summaries, and sync replay; backend audit stores these headers and rejects explicit region/runtime/endpoint mismatches,
- runtime quality evidence for ROI validity, low-confidence depth ratio, and high-motion IMU artifact ratio in `capture_payload.analysis.runtime_quality`,
- runtime timeline integrity evidence in `capture_payload.analysis.runtime_timeline`,
  including sample count, duration, median sample step, max sample gap, and gap warning,
- source-backed derivatives-only feature/media manifest evidence in `capture_contract.feature_manifest`, including manifest version, feature keys, `sample_count` source, `raw_media.*=false`, and `privacy.media_scope=roi_derivatives_only`,
- readiness gate summary in `readiness`, including local/external/EAS/Clinical Hub statuses, local check counts, failed check IDs, external blocker statuses, and next-action IDs without secret values or detailed evidence strings,
- runtime defaults such as `DEFAULT_API_BASE_URL` to prove release builds do not point field devices at localhost,
- git SHA/ref/run-id,
- model_id and capture schema version.
- selected build profile/channel.

Workflow also generates artifact `mobile-release-readiness` containing:
- git SHA/ref/run-id/workflow traceability,
- local mobile readiness checks (`app.json`, `eas.json`, EAS build/submit profile shape, runtime release metadata/config/defaults, endpoint set/data residency/debug gates, Expo Device identity defaults, Clinical Hub preflight guard, Clinical Hub runtime trace headers, in-app release identity evidence, pending sync connectivity restore, deterministic mobile E2E sync smoke, physical-device smoke log template/validator, store rollout handoff template/validator, release bundle verifier, runtime motion quality gates, runtime timeline integrity metadata, derivatives-only feature/media manifest gates, package scripts, lockfile, pinned tooling, API response + submit exception + runtime exception PHI redaction, unit-test coverage wiring),
- external credential state without secret values,
- authenticated EAS readiness status and specific EAS blockers,
- live Clinical Hub API readiness status (`present`, `missing`, or `invalid`),
- manual release requirements for Apple Developer and Google Play accounts,
- machine-readable `next_actions` for configuring missing GitHub secrets/variables and manual store-account handoff.

Workflow also generates artifact `mobile-release-notes` containing:
- git SHA/ref/run-id,
- selected build profile/platform,
- selected store-submit request/platform,
- operator-facing release notes from workflow input or an explicit placeholder when not supplied,
- required evidence reminders for manifest, readiness, EAS build links, and physical-device smoke logs.

Workflow also generates artifact `mobile-store-rollout-handoff` containing:
- per-run git SHA, app version, build profile/channel, and SHA-256 digests for `mobile-release-manifest`, `mobile-release-readiness`, and `mobile-release-notes`,
- iOS TestFlight internal handoff checklist and current external blockers,
- Android Play Internal Testing handoff checklist and current external blockers,
- validation summary from `scripts/validate_mobile_store_rollout_handoff.py`.

Workflow also generates artifact `mobile-release-bundle-verification` containing:
- git/run traceability shared by manifest, readiness, and store rollout handoff,
- SHA-256 fingerprints for manifest, readiness, release notes, store rollout handoff, and store rollout summary,
- consistency checks proving the manifest readiness summary matches raw readiness JSON,
- digest checks proving the store rollout handoff references the exact manifest/readiness/notes files from the same run.

Manifest script:

```bash
python3 scripts/build_mobile_release_manifest.py \
  --app-json apps/field-mobile/app.json \
  --output /tmp/mobile-release-manifest.json \
  --profile preview \
  --channel preview
```

Readiness script:

```bash
python3 scripts/check_mobile_release_readiness.py \
  --app-json apps/field-mobile/app.json \
  --eas-json apps/field-mobile/eas.json \
  --package-json apps/field-mobile/package.json \
  --package-lock apps/field-mobile/package-lock.json \
  --output /tmp/mobile-release-readiness.json
```

Physical-device smoke log validation:

```bash
cp docs/mobile-device-smoke-log-template-v0.1.json /tmp/mobile-device-smoke-log.json
# Fill in real iPhone + Android device evidence, manifest SHA, and per-check notes.
python3 scripts/validate_mobile_device_smoke_log.py \
  /tmp/mobile-device-smoke-log.json \
  --output /tmp/mobile-device-smoke-summary.json
```

Store rollout handoff validation:

```bash
cp docs/mobile-store-rollout-handoff-template-v0.1.json /tmp/mobile-store-rollout-handoff.json
# Fill in per-run manifest/readiness/notes SHA values and TestFlight/Play evidence.
python3 scripts/validate_mobile_store_rollout_handoff.py \
  /tmp/mobile-store-rollout-handoff.json \
  --output /tmp/mobile-store-rollout-summary.json
```

Release bundle verification:

```bash
python3 scripts/verify_mobile_release_bundle.py \
  --manifest-json /tmp/mobile-release-manifest.json \
  --readiness-json /tmp/mobile-release-readiness.json \
  --release-notes /tmp/mobile-release-notes.md \
  --store-rollout-handoff-json /tmp/mobile-store-rollout-handoff.json \
  --store-rollout-summary-json /tmp/mobile-store-rollout-summary.json \
  --output /tmp/mobile-release-bundle-verification.json
```

External handoff commands, using placeholders only:

```bash
gh secret set EXPO_TOKEN --body "<expo_access_token>"
gh variable set EAS_PROJECT_ID --body "<eas_project_uuid>"
gh secret set CLINICAL_HUB_URL --body "https://<clinical-hub>"
gh secret set CLINICAL_HUB_API_KEY --body "<api_key>"
eas secret:create --name GOOGLE_SERVICE_ACCOUNT --value "$(cat /secure/path/google-service-account.json)" --type file
```

Manual store-account handoff remains outside GitHub secrets:
- `provision_apple_developer_account`: Apple Developer access, App Store Connect app record, signing certificates/profiles, and TestFlight permissions.
- `provision_google_play_account`: Google Play Console access, Android signing, Play API service account, and internal testing track permissions.

## 4) Distribution channels

iOS:
1. Download `mobile-store-rollout-handoff` from the Mobile Build run.
2. Configure Apple Developer/App Store Connect access, app record, signing credentials, and the internal TestFlight group.
3. Run `npm run submit:ios:production` from `apps/field-mobile`, or dispatch `Mobile Build` with `submit_to_store=true` and `submit_platform=ios`, to submit the latest production EAS build to TestFlight internal testers.
4. Update the iOS channel in `mobile-store-rollout-handoff.json` from `blocked_external` to the actual rollout state and fill in EAS/TestFlight evidence.
5. Verify build metadata, privacy strings, and permissions prompt behavior.

Android:
1. Download `mobile-store-rollout-handoff` from the Mobile Build run.
2. Configure Google Play Console access, Android signing, EAS file secret `GOOGLE_SERVICE_ACCOUNT`, and the internal testing track.
3. Run `npm run submit:android:production` from `apps/field-mobile`, or dispatch `Mobile Build` with `submit_to_store=true` and `submit_platform=android`, to submit the latest production EAS build to Play Internal Testing.
4. Update the Android channel in `mobile-store-rollout-handoff.json` from `blocked_external` to the actual rollout state and fill in EAS/Play evidence.
5. Verify package name, versionCode increment, and install/update path.

After either channel is updated, re-run:

```bash
python3 scripts/validate_mobile_store_rollout_handoff.py \
  /path/to/mobile-store-rollout-handoff.json \
  --output /path/to/mobile-store-rollout-summary.json
```

## 5) Smoke test checklist (mandatory)

1. App starts and opens settings screen.
2. `Release Identity` shows app version, model/schema, runtime mode, endpoint set, privacy/data-residency flags, and `Payload traceability: aligned`.
3. API block shows Clinical Hub preflight status; missing URL is blocked, local/LAN smoke URL is warning-only, and live URL is confirmed against the configured region policy.
4. Clinical Hub request logs include non-secret `x-uroflow-*` release/runtime/data-residency trace headers, and backend contract tests reject a deliberate mismatched region header.
5. `Device Model` is auto-filled from the physical device model or a platform fallback, and matches the smoke-log device entry after any field correction.
6. `Start Capture` and `Stop Capture` work on real device.
7. `Contract payload: ready` after stop, with `analysis.runtime_timeline.gap_warning=false`.
   Repeat or mark the run failed if foreground/device load creates a timing gap warning.
8. Submit produces `paired-measurements` and `capture-packages` records.
9. Offline mode queues both endpoint jobs.
10. Returning online triggers successful auto-sync through connectivity restore, interval, or AppState fallback.
11. Repository-level deterministic smoke confirms queued paired+capture replay drains after network restore.

## 6) Evidence to archive per build

1. Mobile release manifest JSON.
2. Mobile release readiness JSON.
3. Mobile release bundle verification JSON.
4. Mobile store rollout handoff JSON and validation summary.
5. Build links (iOS + Android).
6. Smoke test log with device model and OS version.
7. Validated smoke summary JSON from `scripts/validate_mobile_device_smoke_log.py`.
   - The smoke log must include per-device `runtime_timeline` evidence copied from
     `capture_payload.analysis.runtime_timeline`, with `gap_warning=false`.
8. Clinical Hub sample export (paired + capture package rows).
   - For `capture-packages`, archive `capture_payload.feature_manifest` and confirm `derivatives_only=true`, `raw_media.store_raw_video=false`, `raw_media.store_raw_audio=false`, `raw_media.upload_raw_video=false`, and `raw_media.upload_raw_audio=false`.
   - Archive `capture_payload.analysis.runtime_timeline` and investigate runs with
     `gap_warning=true` or unexpectedly large `max_sample_gap_s`.
9. Go/No-Go note for pilot usage.
