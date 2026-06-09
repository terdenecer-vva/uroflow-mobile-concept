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
- Runtime capture preflight blocks start until camera permission, camera preview readiness,
  ROI lock, and a valid ROI frame are confirmed on device.
- In-app operator SOP checklist blocks capture start until reference readiness, phone
  stability, water-impact workflow, and metadata/privacy confirmations are checked.
- Runtime capture contracts include `analysis.runtime_timeline` timing integrity metadata
  for duration, sample count, median sample step, max gap, and gap warnings.
- Runtime capture contracts include `analysis.runtime_alignment` stream-alignment metadata
  with a 50 ms drift limit; mobile and backend quality gates reject drift failures.
- Runtime quality scoring gates timing gaps with `runtime_quality.timing_gap_warning`,
  forcing at least `repeat` when capture sampling stalls.
- Mobile submission blocks operator edits that would mark a runtime `repeat/reject`
  capture as `valid`, and shows a low-quality warning for `repeat/reject` uploads.
- Mobile submission blocks unsupported pilot `capture_mode` values, keeping the
  field workflow constrained to validated `water_impact` submissions.
- Mobile paired submission validates Clinical Hub/eCRF contract fields before upload:
  ISO timestamp, `ios/android` platform, integer attempt number, finite non-negative
  required metrics, `qmax >= qavg`, and `quality_score` in `0..100`.
- Derivatives-only feature/media manifest in mobile `ios_capture_v1` payloads, with backend validation that raw media storage/upload flags remain disabled.
- Runtime audio recorder temp files are deleted best-effort after stop/reset; payloads retain
  derived metering/flow features only.
- Release manifest traceability for app version, git SHA, model/schema, runtime config, capture contract feature-manifest evidence, and readiness gate summary.
- Mobile API response, submit exception outcome, and runtime exception redaction gates for raw body, PHI-like subject/site/operator IDs, and secret-like error details.
- Mobile release readiness gate for single-region data residency policy (`us`, no cross-region sync, region-matched Clinical Hub required).
- Clinical Hub API key policy map plus site/operator scope enforcement is covered by
  release readiness checks and backend unit tests.
- In-app pilot claims notice states comparison-only, non-diagnostic, non-treatment
  limitations, with mobile release readiness checks and unit tests.
- Pending queue auto-sync on connectivity restore via NetInfo, with interval/AppState fallback.
- Pending sync retry policy keeps network/transient and Clinical Hub auth/permission failures
  queued for credential repair while dropping validation/conflict errors.
- Deterministic mobile sync smoke covering queued paired+capture replay after network restore.
- Clinical Hub capture package records include canonical `capture_payload_sha256` in
  detail/list/CSV exports, with migration backfill for existing SQLite rows.
- Mobile Build release notes artifact and manifest traceability for operator-facing build handoff.
- Physical-device smoke evidence JSON template and validator for iOS+Android release handoff.
- Physical-device smoke evidence requires per-device runtime timeline integrity metadata
  with `gap_warning=false`.
- Store rollout handoff JSON template, validator, and Mobile Build artifact for TestFlight/Play Internal traceability.
- Mobile release bundle verifier for manifest/readiness/notes/store-handoff artifact consistency.
- Mobile dependency review artifact for direct dependency lockfile integrity, production
  `npm audit` summary, native sensitive dependency surface review, and SEC-003 remediation hints.
- In-app Release Identity panel for app/model/schema/runtime/privacy/data-residency evidence on device.
- Runtime release guard blocks capture/API/submit/sync actions when app/model/schema/runtime
  config, endpoint set, privacy, data-residency, or debug gates are incompatible.
- Expo Device-based device model/OS identity defaults for paired payload and capture package traceability.

Not yet implemented:
- Real sensor capture pipeline (camera/audio/IMU/depth).
- Native-grade timestamp sync and ROI extraction on device.
- Production mobile delivery chain (signing, TestFlight, Play Internal) executed end-to-end.

## 2) Gap analysis (what blocks real install-and-test)

### G1. Sensor capture gap
- Native sensor capture exists as a pilot runtime path, but still needs physical-device calibration against target iPhone/Android models.
- Runtime sample timing and stream alignment are summarized in payload metadata and gated in
  quality scoring, but native-grade timestamp synchronization still needs device calibration
  against target iPhone/Android models.
- ROI-only processing pipeline is proxy-based with pre-capture ROI frame validation, and still
  needs native-grade ROI extraction on device.
- IMU motion gating is implemented in runtime quality scoring, but threshold calibration needs real device smoke evidence.

### G2. Data contract gap
- Capture contract can use live runtime samples, with scaffold fallback still available.
- `capture-packages` are queued for offline retry, with app-level connectivity-restore sync; device-level E2E replay evidence now has a validated archive format but still needs real-device logs.
- Mobile payloads include a derivatives-only feature/media manifest; native-grade feature bundles and device-level media-manifest replay evidence still need physical-device archival.

### G3. Security/privacy gap
- Secure storage introduced for API key; raw media is not retained by default and runtime audio
  temp files are deleted after stop/reset, but physical-device storage audit evidence is still required.
- Clinical Hub RBAC/site/operator scope is implemented and release-gated locally; live
  deployment still needs access-review evidence and production key provisioning.
- Mobile response/submit-exception/runtime-exception redaction tests are present; device log PHI review is now required in the physical-device smoke log format, but real logs still need archival.
- Mobile data residency policy controls are present; live Clinical Hub region mapping still needs deployment/account evidence.
- Mobile dependency review is generated in Mobile Build; formal vulnerability-management
  review cadence and release sign-off remain part of external security governance.

### G4. Build/release gap
- EAS profiles are added but CI does not yet publish artifacts to testers automatically.
- TestFlight and Play Internal release SOPs are codified as a store rollout handoff template/validator and Mobile Build artifact.
- Release manifest is generated with version -> git SHA -> model/schema -> gate summary traceability; signed store distribution remains externally blocked until Apple/Google/Expo credentials are configured.

### G5. Verification gap
- Mobile tests include TypeScript, unit, export, and deterministic sync replay coverage.
- Claims notice text is unit-tested and release-gated locally; formal RA/QA claim-signoff
  remains part of the external release governance package.
- Runtime quality submission guard is unit-tested and release-gated locally; physical-device
  usability evidence still needs real operator execution.
- Capture mode submission guard is unit-tested and release-gated locally; operator SOP
  drill evidence still needs real site execution.
- Operator SOP checklist is unit-tested and release-gated locally; site monitoring and
  training evidence still need real operator execution.
- Paired submission contract guard is unit-tested and release-gated locally; formal
  data-management QC remains part of pilot operations.
- Deterministic replay tests cover capture contract generation and queued paired+capture sync; physical-device evidence now has a validator/template but still needs real-device execution.
- Device-matrix smoke evidence requires at least one iPhone and one Android run in
  `mobile_device_smoke_log_v0.1`, including runtime timeline evidence from
  `capture_payload.analysis.runtime_timeline`.

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
2. Record audio envelope + ROI motion/texture + IMU jitter over unified timeline. Status: implemented with runtime timeline integrity metadata and timing-gap quality gating; native-grade timestamp synchronization still needs device calibration.
3. Build live `ios_capture_v1` payload from runtime samples.
4. Add quality pre-checks before submit (`roi_valid_ratio`, motion threshold, depth confidence ratio). Status: implemented in runtime payload scoring plus pre-capture camera/ROI readiness guard; needs physical-device threshold calibration.
5. Add feature/media manifest for derived mobile capture features. Status: implemented as derivatives-only manifest with raw media disabled in payload and backend validator.

DoD:
- Single-button record flow works on physical iPhone and Android.
- Generated payload validates against schema and uploads to `capture-packages`.
- Measurement marked `repeat/reject` when capture quality fails thresholds.

## B2: Sync and resilience
1. Extend offline queue to support both `paired-measurements` and `capture-packages` as independent jobs. Status: implemented.
2. Add idempotent retry policies per endpoint and per status code. Status: implemented for network/transient retry, Clinical Hub auth/permission credential-repair retry, and validation/conflict non-retryable handling.
3. Add background sync trigger on connectivity restore. Status: implemented for foreground app connectivity restore via NetInfo, plus interval and AppState fallback; OS background task scheduling remains out of scope until native/background execution policy is chosen.

DoD:
- Airplane-mode scenario retains both payload types.
- Sync replay recovers with no duplicates after network restore.

## B3: Release and tester delivery
1. Configure Expo project credentials and EAS secrets.
2. Wire CI dispatch for preview builds with release notes. Status: release notes input/artifact and manifest digest traceability implemented; authenticated EAS trigger still waits for Expo/EAS credentials.
3. Set distribution channels:
- iOS TestFlight (internal group). Status: SOP/handoff format implemented; actual channel setup remains external to repository automation.
- Android Internal Testing (Play). Status: SOP/handoff format implemented; actual channel setup remains external to repository automation.
4. Add install/runbook for clinic operators. Status: implemented for field-test handoff, with store rollout handoff artifact linking operator notes/evidence.

DoD:
- Testers receive installable builds via TestFlight/Internal Testing.
- Every build has linked commit SHA and changelog.

## B4: Quality and validation readiness
1. Add unit tests for capture payload generation and local validation. Status: implemented for paired payload, capture package payload, capture contract generation, ROI signal, runtime metrics, and backend capture contract validation.
2. Add E2E mobile smoke tests (session create -> submit -> queue -> sync). Status: implemented as deterministic repository-level paired+capture queue replay after network restore, plus a validated iOS+Android physical-device smoke log schema/template; real physical-device/live Clinical Hub smoke evidence still required.
3. Export nightly comparison summary and gate snapshot to Clinical Hub. Status: implemented
   as an offline snapshot builder with SHA-256 manifest, a first-class
   `method_comparison_summary` Clinical Hub report type, and optional CI upload when live
   `CLINICAL_HUB_URL`/`CLINICAL_HUB_API_KEY` secrets are configured.

DoD:
- Mobile regression suite blocks broken payload changes.
- Pilot gate report includes mobile build ID and schema version. Status: implemented via
  `gate_summary_traceability_v0.1` in `evaluate-gates` output and wired in
  `pilot-automation-smoke`.

## 4) Immediate next PRs

- PR-1 (this branch): secure storage + capture scaffold upload + EAS profiles/workflow.
- PR-2 (implemented in current branch): queue refactor for multi-endpoint offline jobs + sync engine.
- PR-3 (partially implemented): runtime adapters for audio+IMU + camera preview/ROI lock gating + runtime contract generation + local proxy metrics/quality derivation.
- PR-4 (partially implemented): release manifest, release notes, physical-device smoke evidence, and TestFlight/Play rollout handoff generation in CI; signed store distribution remains externally blocked.

## 5) Exit criteria for pilot start

All of the following must be true:
1. Installable iOS and Android build distributed to pilot testers.
2. Real capture payloads (not scaffold) uploaded and validated in Clinical Hub.
3. Offline queue proves lossless retry for both payload types.
4. Pre-freeze gates pass with target valid-rate and privacy constraints.
5. Signed go/no-go record with release manifest and evidence links.
