# Intended Use (Working Draft v1)

## 1. Document Control

- Version: `1.0-draft`
- Owner: `Product Lead + Clinical Lead`
- Last updated: `2026-02-23`
- Related concept docs:
  - `docs/stage-1-product-definition.md`
  - `docs/stage-2-fusion-development.md`
  - `docs/architecture.md`

## 2. Product Description

- Product name (working): `Mobile Uroflow Concept`
- Product type: software-based uroflowmetry support solution (smartphone app + analytics pipeline)
- Core sensing approach: `RGB video + depth (LiDAR/ToF) + audio` fusion with volume-based estimation `h(t) -> V(t) -> Q(t)`
- Intended stage: investigational R&D and pilot validation

## 3. Intended Purpose

The software is intended to estimate and report uroflowmetry-derived parameters from synchronized smartphone recordings of a calibrated receiving container under controlled capture conditions.

## 4. Intended Users

- Primary users: `both (patients and clinicians)`
- Operator profile: `lay user with in-app onboarding` and `trained clinical user`
- Clinical oversight model: `self-capture with clinician review` or `clinic-supervised capture`

## 5. Intended Use Environment

- Environment: `mixed (home bathroom + outpatient clinic)`
- Required setup:
  - fixed smartphone position (tripod/holder)
  - calibrated transparent receiving container + fiducial marker
  - sufficient lighting and ROI alignment
  - stable field of view without subject-identifying content

## 6. Target Population

- Included population:
  - adults (`>=18 years`)
  - men and women able to void spontaneously
  - symptomatic LUTS/BPH/OAB monitoring cohorts (pilot scope)
- Exclusions:
  - catheterized voiding
  - inability to follow capture protocol
  - inability to provide informed consent
- Pediatric use: `no (out of scope for v1 pilot)`

## 7. Device Inputs and Outputs

Inputs:
- RGB video stream
- LiDAR/ToF depth map and confidence map (when available)
- Audio signal
- Calibration metadata (container profile `V(h)`, fiducial marker)

Outputs:
- Time series: `V(t)`, `Q(t)`
- Scalar metrics:
  - `Qmax`, `Qavg`, `Vvoid`
  - `Flow time`, `Voiding time`, `Time to Qmax`
  - `Hesitancy` (only when protocol start marker is present)
- Quality flags:
  - calibration quality
  - depth confidence
  - glare/lighting issues
  - incomplete capture
  - `Vvoid < 150 ml` flag
- Measurement status: `valid / repeat / reject`

## 8. Clinical Claims (Draft)

Candidate claims (subject to validation and regulatory strategy):
- Reports uroflowmetry-derived parameters from calibrated recordings.
- Detects and flags low-quality recordings and suboptimal voided volume conditions.
- Provides trend-ready structured output (`V(t)`, `Q(t)`, scalar metrics, quality metadata).

## 9. Non-Claims / Limitations (Mandatory)

- Does not measure detrusor or urethral pressures.
- Does not measure post-void residual (PVR) without external modality.
- Does not provide standalone diagnosis.
- Does not replace clinician judgment.
- Not validated for pediatric use.

## 10. Performance Targets (Draft)

- Supported flow range: `0-50 ml/s`
- Supported voided volume range: `0-1000 ml`
- Minimum interpretable voided volume rule: `>150 ml` (otherwise mark as `repeat/review`)
- Supported capture rates:
  - RGB: `>=30 fps` (preferred 60 fps)
  - Depth: frame-synchronous with confidence gating
  - Audio: timestamp-synchronized with capture session
- Report generation latency target: `<10 s` after capture end on supported device profile

## 11. Key Risks and Risk Controls (High-Level)

- Geometry drift / poor alignment -> calibration verification + pre-check UI
- Low depth confidence / visual artifacts -> confidence gating + RGB fallback + QC flag
- Incomplete stream capture into container -> invalid measurement flag + repeat guidance
- Privacy risk from raw media -> derivatives-only default + explicit consent for raw export

## 12. Regulatory Positioning (Working Assumption)

- US: likely aligns with urine flow/volume measuring system pathway when medical claims are made.
- EU: software medical device evaluation likely under MDR Rule 11 logic depending on final claims and clinical impact.

## 13. Open Decisions

1. Home-first or clinic-first launch sequence
2. Final wording of medical claims for first submission
3. Country-by-country regulatory priority
4. Whether to include stream-angle/spray features in v1 product UI or keep QC-only

## 14. Approval

- Product lead: `[name/date/signature]`
- Clinical lead: `[name/date/signature]`
- RA/QA lead: `[name/date/signature]`
