# Intended Use Draft (Template)

## 1. Document Control

- Version: `0.1-draft`
- Owner: `Product + Clinical Lead`
- Last updated: `YYYY-MM-DD`
- Related concept docs:
  - `docs/stage-1-product-definition.md`
  - `docs/stage-2-fusion-development.md`

## 2. Product Description

- Product name (working): `Mobile Uroflow Concept`
- Product type: software-based uroflowmetry support solution (smartphone app + analytics pipeline)
- Core sensing approach: `video + depth + audio` fusion with volume-based estimation `h(t) -> V(t) -> Q(t)`

## 3. Intended Purpose

Software is intended to estimate and report uroflowmetry parameters from smartphone recordings of a calibrated receiving container under controlled capture conditions.

## 4. Intended Users

- Primary users: `[patients / clinicians / both]`
- Operator profile: `[lay user with onboarding / trained clinical user]`
- Clinical oversight model: `[self-use with clinician review / clinic-only]`

## 5. Intended Use Environment

- Environment: `[home bathroom / outpatient clinic / mixed]`
- Required setup: fixed phone position, calibrated container, sufficient lighting, ROI alignment

## 6. Target Population

- Included population: `[define age, sex, symptoms group]`
- Exclusions: `[catheterized patients, inability to void independently, etc.]`
- Pediatric use: `[yes/no + constraints]`

## 7. Device Inputs and Outputs

Inputs:
- RGB video
- LiDAR/ToF depth map (when available)
- Audio signal
- Calibration metadata (container profile, fiducial marker)

Outputs:
- Time series: `V(t)`, `Q(t)`
- Scalar metrics: `Qmax`, `Qavg`, `Vvoid`, `Flow time`, `Voiding time`, `Time to Qmax`, `Hesitancy` (if protocol supports)
- Quality flags and measurement validity status

## 8. Clinical Claims (Draft)

Candidate claims (subject to validation and regulatory strategy):
- Reports uroflowmetry-derived parameters from calibrated recordings.
- Flags low-quality recordings and suboptimal voided volume conditions.

## 9. Non-Claims / Limitations (Mandatory)

- Does not measure detrusor or urethral pressures.
- Does not measure post-void residual (PVR) without external modality.
- Does not provide standalone diagnosis.
- Does not replace clinician judgment.

## 10. Performance Targets (Draft)

- Supported flow range: `0-50 ml/s` (target alignment with ICS-style ranges)
- Supported voided volume range: `0-1000 ml`
- Minimum interpretable voided volume rule: `>150 ml` (otherwise mark as repeat/review)
- Output latency target: `[e.g. <10 s after capture end]`

## 11. Key Risks and Risk Controls (High-Level)

- Geometry drift / poor alignment -> calibration verification + pre-check UI
- Low depth confidence / visual artifacts -> confidence gating + fallback logic + QC flag
- Incomplete capture of stream into container -> invalid measurement flag + repeat guidance
- Privacy risk from raw media -> derivatives-only default + explicit consent for raw export

## 12. Regulatory Positioning (Working Assumption)

- US: likely falls under urine flow/volume measuring system pathway when medical claims are made.
- EU: software medical device evaluation likely under MDR Rule 11 logic depending on final claims.

## 13. Open Decisions

1. Home-use vs clinic-use primary indication
2. Lay-use instructions and training burden
3. Final claim language for first regulatory submission
4. Country launch sequence and regulatory priority

## 14. Approval

- Product lead: `[name/date/signature]`
- Clinical lead: `[name/date/signature]`
- RA/QA lead: `[name/date/signature]`
