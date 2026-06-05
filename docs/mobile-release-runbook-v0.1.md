# Mobile Release Runbook v0.1 (iOS + Android)

Date: 2026-02-25
Scope: pilot installable builds for Uroflow Field Mobile

## 1) Preconditions

1. App code merged to target branch.
2. `apps/field-mobile/eas.json` profiles updated.
3. GitHub secret `EXPO_TOKEN` configured.
4. `EAS_PROJECT_ID` configured as a GitHub repo variable or `expo.extra.eas.projectId` set in `app.json`.
5. Expo project credentials configured for iOS and Android signing.
6. Clinical Hub secrets configured when live API smoke/report push is part of the release:
   - `CLINICAL_HUB_URL` (`https://...`, non-localhost for live release readiness)
   - `CLINICAL_HUB_API_KEY`

## 2) Trigger preview build

From GitHub Actions:
1. Open workflow `Mobile Build`.
2. Run `workflow_dispatch` and set:
   - `build_profile` (`preview` for pilot by default),
   - `build_platform` (`all`/`ios`/`android`),
   - `wait_for_build` (`false` for fast trigger, `true` for full wait mode).
3. Verify `preflight` passes.
4. Open workflow summary (`Mobile Release Readiness`) and confirm:
   - `Local checks` is `pass`,
   - `Authenticated EAS readiness` is `pass` before attempting an EAS build trigger,
   - `Clinical Hub live API` is `present` before live API smoke/report push is expected,
   - missing or invalid external items are understood and either configured or accepted as blockers for this run.
   - `Next actions` maps the remaining external blockers to concrete setup tasks.
5. Verify `eas-build` starts. If `Authenticated EAS readiness` is `blocked`, `eas-build` is skipped by design and the readiness artifact is the handoff output.
6. Open workflow summary (`Mobile EAS Build`) and copy build links.
7. Download artifact `mobile-eas-build-result-<run_id>` for traceability JSON.

Local fallback:

```bash
cd apps/field-mobile
npm run build:preview
```

## 3) Release manifest and traceability

Workflow generates artifact `mobile-release-manifest` containing:
- app version and package IDs,
- iOS build number and Android versionCode,
- icon/adaptive-icon paths, `expo-splash-screen` image path, SHA-256 fingerprints, byte sizes, PNG dimensions, and splash background/resize/width config,
- runtime release metadata from `apps/field-mobile/src/config/releaseMetadata.ts` for app version, model ID, and capture schema version,
- runtime defaults such as `DEFAULT_API_BASE_URL` to prove release builds do not point field devices at localhost,
- git SHA/ref/run-id,
- model_id and capture schema version.
- selected build profile/channel.

Workflow also generates artifact `mobile-release-readiness` containing:
- git SHA/ref/run-id/workflow traceability,
- local mobile readiness checks (`app.json`, `eas.json`, runtime release metadata/defaults, package scripts, lockfile, pinned tooling, API response redaction, unit-test coverage wiring),
- external credential state without secret values,
- authenticated EAS readiness status and specific EAS blockers,
- live Clinical Hub API readiness status (`present`, `missing`, or `invalid`),
- manual release requirements for Apple Developer and Google Play accounts,
- machine-readable `next_actions` for configuring missing GitHub secrets/variables and manual store-account handoff.

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

External handoff commands, using placeholders only:

```bash
gh secret set EXPO_TOKEN --body "<expo_access_token>"
gh variable set EAS_PROJECT_ID --body "<eas_project_uuid>"
gh secret set CLINICAL_HUB_URL --body "https://<clinical-hub>"
gh secret set CLINICAL_HUB_API_KEY --body "<api_key>"
```

Manual store-account handoff remains outside GitHub secrets:
- `provision_apple_developer_account`: Apple Developer access, signing certificates/profiles, and TestFlight permissions.
- `provision_google_play_account`: Google Play Console access, Android signing, and internal testing track permissions.

## 4) Distribution channels

iOS:
1. Use EAS output for TestFlight upload (internal testers).
2. Verify build metadata, privacy strings, and permissions prompt behavior.

Android:
1. Use EAS output for Play Internal Testing.
2. Verify package name, versionCode increment, and install/update path.

## 5) Smoke test checklist (mandatory)

1. App starts and opens settings screen.
2. `Start Capture` and `Stop Capture` work on real device.
3. `Contract payload: ready` after stop.
4. Submit produces `paired-measurements` and `capture-packages` records.
5. Offline mode queues both endpoint jobs.
6. Returning online triggers successful auto-sync.

## 6) Evidence to archive per build

1. Mobile release manifest JSON.
2. Mobile release readiness JSON.
3. Build links (iOS + Android).
4. Smoke test log with device model and OS version.
5. Clinical Hub sample export (paired + capture package rows).
6. Go/No-Go note for pilot usage.
