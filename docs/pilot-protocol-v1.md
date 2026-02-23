# Pilot Protocol v1 (Template)

## 1. Protocol Metadata

- Protocol ID: `UF-PILOT-001`
- Version: `0.1-draft`
- Date: `YYYY-MM-DD`
- Sponsor / institution:
- Principal investigator:
- Clinical site(s):

## 2. Objective

Primary objective:
- Assess agreement between smartphone-derived uroflow metrics and reference uroflowmeter metrics.

Secondary objectives:
- Evaluate repeatability and measurement quality flags.
- Assess robustness across capture conditions.

## 3. Study Design

- Type: prospective paired-comparison pilot
- Reference method: certified clinical uroflowmeter
- Test method: smartphone fusion pipeline (`RGB + depth + audio`)
- Unit of analysis: paired measurement (test + reference)

## 4. Population

Inclusion criteria (draft):
- Adults able to void spontaneously
- Able to provide informed consent

Exclusion criteria (draft):
- Inability to follow protocol
- Conditions that invalidate safe participation (per investigator)

## 5. Sample Size (Pilot)

- Target participants: `20-30`
- Target paired measurements: `[set target, e.g. >=60]`
- Repeat measurements per participant: `[e.g. 2-3 when feasible]`

Note: this pilot is for variance estimation, workflow validation, and failure-mode discovery; not definitive clinical performance claims.

## 6. Measurement Workflow

1. Verify setup and calibration (fiducial + container profile).
2. Start synchronized capture and reference recording.
3. Record voiding event and derive `V(t), Q(t)`.
4. Collect reference outputs from clinical uroflowmeter.
5. Attach quality flags and protocol deviations.
6. Repeat if `Vvoid < 150 ml` or measurement is flagged invalid.

## 7. Endpoints

Primary endpoints:
- Agreement for `Qmax`, `Qavg`, `Vvoid` versus reference.

Secondary endpoints:
- Agreement for timing metrics (`Flow time`, `Voiding time`, `TQmax`).
- Repeatability metrics within participant.
- Invalid/failed capture rate and reasons.

## 8. Statistical Analysis Plan (Draft)

- Continuous agreement: Bland-Altman (bias, limits of agreement)
- Error metrics: MAE, RMSE
- Reliability: ICC for repeatability where applicable
- Subgroup analyses (if sample allows): sex, age band, `Vvoid` strata

## 9. Data Quality and QC Rules

Mandatory QC fields per measurement:
- Calibration status
- Depth confidence status
- Lighting/glare status
- Incomplete capture indicator
- `Vvoid < 150 ml` flag

Decision logic:
- `valid` -> include in primary analysis
- `repeat` -> acceptable with repeat capture
- `reject` -> exclude from primary analysis; include in failure analysis

## 10. Safety, Ethics, and Privacy

- Informed consent required before data capture
- Derivatives-only storage default; raw media only with explicit consent
- De-identification and access controls enforced
- Incident reporting path defined

## 11. Operational Roles

- Clinical operator:
- Technical operator:
- Data manager:
- Statistician:
- Privacy officer:

## 12. Deliverables

- Pilot dataset with audit trail
- Interim analysis report
- Final pilot report with go/no-go recommendation
- Updated risk register and protocol v2 proposal

## 13. Go/No-Go Criteria (Draft)

Define thresholds before study start:
- Maximum acceptable bias per primary metric
- Maximum acceptable failed-capture rate
- Minimum repeatability threshold (ICC target)
- Minimum percentage of valid captures

Outcome:
- [ ] Go to pivotal planning
- [ ] Iterate MVP and rerun pilot
- [ ] Stop
