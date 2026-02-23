# DPIA Checklist (Working Draft v1)

Use this checklist before any pilot or production processing of `video/audio/depth` uroflowmetry data.

## 1. Processing Overview

- Project / feature name: `Mobile Uroflow Concept - Fusion MVP`
- Controller entity: `TBD legal entity`
- Processor(s): `none by default (on-device mode)`
- DPO / privacy contact: `TBD`
- Assessment date: `2026-02-23`
- Assessment owner: `Privacy Lead + Product Lead`

## 2. Scope of Processing

- [x] Data sources documented (app capture, calibration metadata, optional clinician review)
- [x] Processing purposes documented
- [x] Processing locations documented (on-device by default; cloud optional)
- [x] Data lifecycle mapped (collection -> storage -> sharing -> deletion)

Processing purpose (v1):
- estimate uroflowmetry metrics from calibrated capture
- provide quality validation and repeat/reject guidance
- support pilot-level method comparison against reference uroflowmeter

## 3. Data Categories and Sensitivity

- [x] Health data identified (uroflow metrics, derived clinical indicators)
- [x] Raw media identified (video/audio/depth)
- [x] Metadata identified (timestamps, calibration profile, device characteristics)
- [x] Special-category handling acknowledged (health-data treatment by default)

## 4. Lawful Basis and Art. 9 Basis (GDPR)

- [ ] Art. 6 lawful basis selected and justified by legal counsel
- [ ] Art. 9 condition selected and justified by legal counsel
- [x] Consent flow required for raw media retention/export
- [x] Withdrawal/revocation process required in UX and backend

Working assumption for pilot planning only:
- explicit informed consent is mandatory before capture and any export of raw media.

## 5. Necessity and Proportionality

- [x] Data minimization implemented (derivatives-only default)
- [x] Purpose limitation implemented in design docs
- [x] Storage limitation/retention periods defined (draft)
- [ ] Access controls least-privilege by role implemented and tested
- [ ] User transparency notices reviewed by legal/privacy

## 6. Risk Assessment

| Risk | Affected Data | Likelihood | Severity | Existing Controls | Residual Risk | Owner |
|---|---|---|---|---|---|---|
| Unauthorized access to raw media | video/audio/depth | Medium | High | encryption + derivatives-only default + role-bound export | Medium | Security Lead |
| Re-identification from scene context | video/metadata | Medium | High | ROI-only capture guidance + de-identification + manual review policy | Medium | Privacy Lead |
| Excessive retention | all | Medium | High | TTL + auto-delete jobs + deletion audit trail | Low-Medium | Data Platform |
| Insecure transfer to cloud | media/metrics | Low-Medium | High | TLS + signed URLs + short expiry + no-default-upload | Low-Medium | Backend Lead |
| Misuse of metrics as diagnosis | metrics/report | Medium | Medium-High | non-claims in UI/report + clinician-review framing | Medium | Product + Clinical |

## 7. Technical and Organizational Measures

- [x] Encryption at rest and in transit required
- [x] Key management required
- [x] Audit logging required for access/export/delete events
- [ ] Incident response runbook linked to project playbook
- [ ] Vendor due diligence completed (if processors used)
- [x] Data export controls and approval workflow required

## 8. Data Subject Rights

- [ ] Access request process documented
- [ ] Rectification process documented
- [ ] Erasure process documented
- [ ] Restriction/objection process documented
- [ ] Portability export process documented
- [ ] SLA targets approved by legal/privacy

## 9. International Transfers

- [x] Transfer map completed for current design (`none by default`)
- [ ] Transfer mechanism documented (if cloud region is outside jurisdiction)
- [ ] Supplemental safeguards assessed (if transfer is introduced)

## 10. Retention and Deletion Policy (Draft)

- Raw media retention: `disabled by default`; if explicit consent enabled -> `max 30 days`
- Derived metrics retention: `24 months` (pilot analytics and reproducibility)
- Logs retention: `180 days`
- Backup retention: `35 days rolling`
- Hard delete SLA after request/expiry: `<=7 days`

- [ ] Automatic deletion verified in integration test
- [ ] Deletion evidence/audit trail verified in pilot dry-run

## 11. Residual Risk and Decision

- Residual risk summary: medium residual privacy risk remains until legal basis, rights handling, and deletion tests are fully validated.
- [ ] Proceed
- [x] Proceed with conditions
- [ ] Block until controls implemented

Conditions before pilot data collection:
1. Legal confirmation of Art. 6 and Art. 9 basis.
2. Approved consent and privacy notice text.
3. Verified deletion and access-control tests.

Decision owner: `[name]`
Date: `[YYYY-MM-DD]`

## 12. Reassessment Triggers

- [x] New data category introduced
- [x] New processor / new region
- [x] New AI model with material behavior change
- [x] Security incident involving health data
- [x] Regulatory update affecting lawful basis or controls
