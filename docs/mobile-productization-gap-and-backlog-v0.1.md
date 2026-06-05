# Mobile Productization Gap & Backlog v0.1

Date: 2026-02-25
Scope: installable iOS/Android app for pilot `smartphone vs reference uroflowmeter`

## 1) Current state snapshot

Implemented now:
- Expo React Native field app for paired entry and sync.
- Clinical Hub API contract for `paired-measurements` and `capture-packages`.
- Pilot automation and release gates (`v4.2`) in repository.
- App-level runtime config for pilot mode, Clinical Hub v1 endpoint set, default capture mode, privacy-by-default switches, single-region data residency policy, and disabled debug gates.
- Runtime capture quality gates for ROI validity, low-confidence depth, and high-motion IMU artifacts.
- Derivatives-only feature/media manifest in mobile `ios_capture_v1` payloads, with backend validation that raw media storage/upload flags remain disabled.
- Release manifest traceability for app version, git SHA, model/schema, runtime config, capture contract feature-manifest evidence, and readiness gate summary.
- Mobile API response, submit exception outcome, and runtime exception redaction gates for raw body, PHI-like subject/site/operator IDs, and secret-like error details.
- Mobile release readiness gate for single-region data residency policy (`us`, no cross-region sync, region-matched Clinical Hub required).
- Pending queue auto-sync on connectivity restore via NetInfo, with interval/AppState fallback.
- Deterministic mobile sync smoke covering queued paired+capture replay after network restore.
- Mobile Build release notes artifact and manifest traceability for operator-facing build handoff.

Not yet implemented:
- Real sensor capture pipeline (camera/audio/IMU/depth).
- Native-grade timestamp sync and ROI extraction on device.
- Production mobile delivery chain (signing, TestFlight, Play Internal) executed end-to-end.

## 2) Gap analysis (what blocks real install-and-test)

### G1. Sensor capture gap
- Native sensor capture exists as a pilot runtime path, but still needs physical-device calibration against target iPhone/Android models.
- ROI-only processing pipeline is proxy-based and still needs native-grade ROI extraction on device.
- IMU motion gating is implemented in runtime quality scoring, but threshold calibration needs real device smoke evidence.

### G2. Data contract gap
- Capture contract can use live runtime samples, with scaffold fallback still available.
- `capture-packages` are queued for offline retry, with app-level connectivity-restore sync; device-level E2E replay evidence still needs to be archived.
- Mobile payloads include a derivatives-only feature/media manifest; native-grade feature bundles and device-level media-manifest replay evidence still need physical-device archival.

### G3. Security/privacy gap
- Secure storage introduced for API key, but no media encryption path yet.
- Mobile response/submit-exception/runtime-exception redaction tests are present; broader device log collection review still needs physical-device evidence.
- Mobile data residency policy controls are present; live Clinical Hub region mapping still needs deployment/account evidence.

### G4. Build/release gap
- EAS profiles are added but CI does not yet publish artifacts to testers automatically.
- TestFlight and Play Internal release SOPs are not codified in repo.
- Release manifest is generated with version -> git SHA -> model/schema -> gate summary traceability; signed store distribution remains externally blocked until Apple/Google/Expo credentials are configured.

### G5. Verification gap
- Mobile tests include TypeScript, unit, export, and deterministic sync replay coverage.
- Deterministic replay tests cover capture contract generation and queued paired+capture sync; physical-device evidence still needs archival.
- No device-matrix smoke checks (iPhone/Android model spread).

## 3) Backlog (implementation order)

## B0: Foundation (must finish first)
1. Split app architecture into modules: `api`, `capture`, `storage`, `sync`, `screens`.
2. Add app-level config object (`mode`, endpoint set, privacy switches, data residency policy, debug gates). Status: implemented for pilot mode, Clinical Hub v1 endpoint set, default capture mode, privacy switches, single-region data residency policy, and disabled debug gates.
3. Add release manifest JSON generation (`app_version`, `git_sha`, `model_id`, `schema_version`, readiness gate summary). Status: implemented in Mobile Build artifacts.

DoD:
- App builds locally for iOS and Android.
- Typecheck and lint pass.
- Config is environment-driven, no hardcoded pilot secrets.

## B1: Real capture MVP (water-impact only)
1. Implement capture start/stop session service.
2. Record audio envelope + ROI motion/texture + IMU jitter over unified timeline.
3. Build live `ios_capture_v1` payload from runtime samples.
4. Add quality pre-checks before submit (`roi_valid_ratio`, motion threshold, depth confidence ratio). Status: implemented in runtime payload scoring; needs physical-device threshold calibration.
5. Add feature/media manifest for derived mobile capture features. Status: implemented as derivatives-only manifest with raw media disabled in payload and backend validator.

DoD:
- Single-button record flow works on physical iPhone and Android.
- Generated payload validates against schema and uploads to `capture-packages`.
- Measurement marked `repeat/reject` when capture quality fails thresholds.

## B2: Sync and resilience
1. Extend offline queue to support both `paired-measurements` and `capture-packages` as independent jobs.
2. Add idempotent retry policies per endpoint and per status code.
3. Add background sync trigger on connectivity restore. Status: implemented for foreground app connectivity restore via NetInfo, plus interval and AppState fallback; OS background task scheduling remains out of scope until native/background execution policy is chosen.

DoD:
- Airplane-mode scenario retains both payload types.
- Sync replay recovers with no duplicates after network restore.

## B3: Release and tester delivery
1. Configure Expo project credentials and EAS secrets.
2. Wire CI dispatch for preview builds with release notes. Status: release notes input/artifact and manifest digest traceability implemented; authenticated EAS trigger still waits for Expo/EAS credentials.
3. Set distribution channels:
- iOS TestFlight (internal group)
- Android Internal Testing (Play)
4. Add install/runbook for clinic operators.

DoD:
- Testers receive installable builds via TestFlight/Internal Testing.
- Every build has linked commit SHA and changelog.

## B4: Quality and validation readiness
1. Add unit tests for capture payload generation and local validation. Status: implemented for paired payload, capture package payload, capture contract generation, ROI signal, runtime metrics, and backend capture contract validation.
2. Add E2E mobile smoke tests (session create -> submit -> queue -> sync). Status: implemented as deterministic repository-level paired+capture queue replay after network restore; physical-device/live Clinical Hub smoke evidence still required.
3. Export nightly comparison summary and gate snapshot to Clinical Hub.

DoD:
- Mobile regression suite blocks broken payload changes.
- Pilot gate report includes mobile build ID and schema version.

## 4) Immediate next PRs

- PR-1 (this branch): secure storage + capture scaffold upload + EAS profiles/workflow.
- PR-2 (implemented in current branch): queue refactor for multi-endpoint offline jobs + sync engine.
- PR-3 (partially implemented): runtime adapters for audio+IMU + camera preview/ROI lock gating + runtime contract generation + local proxy metrics/quality derivation.
- PR-4 (partially implemented): TestFlight/Play rollout runbook + release manifest generation in CI.

## 5) Exit criteria for pilot start

All of the following must be true:
1. Installable iOS and Android build distributed to pilot testers.
2. Real capture payloads (not scaffold) uploaded and validated in Clinical Hub.
3. Offline queue proves lossless retry for both payload types.
4. Pre-freeze gates pass with target valid-rate and privacy constraints.
5. Signed go/no-go record with release manifest and evidence links.
