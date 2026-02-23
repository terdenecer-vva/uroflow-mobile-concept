# Pilot Protocol v1 (Working Draft)

## 1. Protocol Metadata

- Protocol ID: `UF-PILOT-001`
- Version: `1.0-draft`
- Date: `2026-02-23`
- Sponsor / institution: `Mobile Uroflow Concept R&D`
- Principal investigator: `Vladimir Vorobev (acting PI for pilot preparation)`
- Clinical site(s): `Single partner urology outpatient site (CLN-01) + optional supervised home arm`

## 2. Objective

Primary objective:
- Assess agreement between smartphone-derived uroflow metrics and reference uroflowmeter metrics.

Secondary objectives:
- Evaluate repeatability and measurement quality flags.
- Assess robustness across capture conditions (lighting, depth confidence, container alignment).

## 3. Study Design

- Type: prospective paired-comparison pilot
- Reference method: certified clinical uroflowmeter (gravimetric preferred)
- Test method: smartphone fusion pipeline (`RGB + depth + audio`)
- Unit of analysis: paired measurement (test + reference)
- Study mode: observational, non-interventional measurement comparison

## 4. Population

Inclusion criteria:
- Adults (`>=18 years`) able to void spontaneously
- Able to provide informed consent
- Able to follow capture instructions

Exclusion criteria:
- Catheterized voiding
- Inability to complete protocol capture safely
- Missing consent or withdrawal of consent

## 5. Sample Size (Pilot)

- Target participants: `20-30`
- Target paired measurements: `>=90`
- Repeat measurements per participant: `2-4 when feasible`

Note: this pilot is for variance estimation, workflow validation, and failure-mode discovery; not definitive clinical performance claims.

## 6. Measurement Workflow

1. Verify setup and calibration (fiducial + container profile + camera stability).
2. Start synchronized smartphone capture (`RGB/depth/audio`) and reference recording.
3. Record voiding event and derive `V(t), Q(t)`.
4. Collect reference outputs from clinical uroflowmeter.
5. Attach quality flags and protocol deviations.
6. Repeat measurement if `Vvoid < 150 ml` or status is `repeat/reject`.

## 7. Endpoints

Primary endpoints:
- Agreement for `Qmax`, `Qavg`, `Vvoid` versus reference.

Secondary endpoints:
- Agreement for timing metrics (`Flow time`, `Voiding time`, `TQmax`).
- Repeatability metrics within participant.
- Invalid/failed capture rate and root-cause categories.

## 8. Statistical Analysis Plan

- Continuous agreement: Bland-Altman (bias, limits of agreement)
- Error metrics: MAE, RMSE for `Qmax`, `Qavg`, `Vvoid`
- Reliability: ICC for repeated measurements (where available)
- Subgroup analyses (sample permitting): sex, age band, `Vvoid` strata (`<150`, `150-300`, `>300 ml`)

## 9. Data Quality and QC Rules

Mandatory QC fields per measurement:
- Calibration status
- Depth confidence status
- Lighting/glare status
- Incomplete capture indicator
- `Vvoid < 150 ml` flag

Decision logic:
- `valid` -> include in primary analysis
- `repeat` -> include only repeated valid measurement in primary analysis
- `reject` -> exclude from primary analysis; include in failure analysis

## 10. Safety, Ethics, and Privacy

- Informed consent required before data capture
- Derivatives-only storage default; raw media only with explicit consent
- De-identification and role-based access controls required
- Incident reporting path and escalation owner defined before first participant

## 11. Operational Roles

- Clinical operator: `site uroflow nurse/technician`
- Technical operator: `mobile app study engineer`
- Data manager: `study data manager`
- Statistician: `biostatistics lead`
- Privacy officer: `DPO/privacy lead`

## 12. Deliverables

- Pilot dataset with audit trail
- Interim analysis report
- Final pilot report with go/no-go recommendation
- Updated risk register and protocol v2 proposal

## 13. Go/No-Go Criteria (Draft Targets)

Targets to be met on primary analysis set:
- `Qmax MAE <= 3.0 ml/s`
- `Qavg MAE <= 2.0 ml/s`
- `Vvoid MAE <= 25 ml` or `<=10%` relative error (whichever is larger)
- Valid-capture rate `>=85%`
- Failed/reject capture rate `<=15%`
- ICC (`Qmax`, repeated measures) `>=0.75`

Outcome:
- [ ] Go to pivotal planning
- [ ] Iterate MVP and rerun pilot
- [ ] Stop
