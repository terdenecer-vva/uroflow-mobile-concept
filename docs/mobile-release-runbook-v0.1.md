# Mobile Release Runbook v0.1 (iOS + Android)

Date: 2026-02-25
Scope: pilot installable builds for Uroflow Field Mobile

## 1) Preconditions

1. App code merged to target branch.
2. `apps/field-mobile/eas.json` profiles updated.
3. GitHub secret `EXPO_TOKEN` configured.
4. Expo project credentials configured for iOS and Android signing.

## 2) Trigger preview build

From GitHub Actions:
1. Open workflow `Mobile Build`.
2. Run `workflow_dispatch` and set:
   - `build_profile` (`preview` for pilot by default),
   - `build_platform` (`all`/`ios`/`android`),
   - `wait_for_build` (`false` for fast trigger, `true` for full wait mode).
3. Verify `preflight` passes.
4. Verify `eas-build` starts.
5. Open workflow summary (`Mobile EAS Build`) and copy build links.
6. Download artifact `mobile-eas-build-result-<run_id>` for traceability JSON.

Local fallback:

```bash
cd apps/field-mobile
npm run build:preview
```

## 3) Release manifest and traceability

Workflow generates artifact `mobile-release-manifest` containing:
- app version and package IDs,
- git SHA/ref/run-id,
- model_id and capture schema version.
- selected build profile/channel.

Manifest script:

```bash
python scripts/build_mobile_release_manifest.py \
  --app-json apps/field-mobile/app.json \
  --output /tmp/mobile-release-manifest.json \
  --profile preview \
  --channel preview
```

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
2. Build links (iOS + Android).
3. Smoke test log with device model and OS version.
4. Clinical Hub sample export (paired + capture package rows).
5. Go/No-Go note for pilot usage.
