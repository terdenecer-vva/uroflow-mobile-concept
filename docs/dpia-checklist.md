# DPIA Checklist (Template)

Use this checklist before any pilot or production processing of `video/audio/depth` uroflowmetry data.

## 1. Processing Overview

- Project / feature name:
- Controller entity:
- Processor(s):
- DPO / privacy contact:
- Assessment date:
- Assessment owner:

## 2. Scope of Processing

- [ ] Data sources documented (app capture, manual inputs, clinician portal)
- [ ] Processing purposes documented
- [ ] Processing locations documented (on-device, cloud regions, backups)
- [ ] Data lifecycle mapped (collection -> storage -> sharing -> deletion)

## 3. Data Categories and Sensitivity

- [ ] Health data identified (uroflow metrics, derived clinical indicators)
- [ ] Raw media identified (video/audio/depth)
- [ ] Metadata identified (device IDs, timestamps, calibration profile)
- [ ] Any special-category data beyond health identified

## 4. Lawful Basis and Art. 9 Basis (GDPR)

- [ ] Art. 6 lawful basis selected and justified
- [ ] Art. 9 condition selected and justified for health data
- [ ] Consent flow documented where required
- [ ] Withdrawal/revocation process documented

## 5. Necessity and Proportionality

- [ ] Data minimization implemented (derivatives-only default)
- [ ] Purpose limitation implemented
- [ ] Storage limitation/retention periods defined
- [ ] Access controls least-privilege by role
- [ ] User transparency notices complete and understandable

## 6. Risk Assessment

For each risk, document severity, likelihood, and residual risk after controls:

| Risk | Affected Data | Likelihood | Severity | Existing Controls | Residual Risk | Owner |
|---|---|---|---|---|---|---|
| Unauthorized access to raw media | video/audio/depth |  |  | encryption + RBAC |  |  |
| Re-identification from context | video/metadata |  |  | ROI-only capture + de-identification |  |  |
| Excessive retention | all |  |  | TTL + auto-delete jobs |  |  |
| Insecure transfer to cloud | media/metrics |  |  | TLS + signed URLs + short expiry |  |  |

## 7. Technical and Organizational Measures

- [ ] Encryption at rest and in transit
- [ ] Key management documented
- [ ] Audit logging enabled and monitored
- [ ] Incident response runbook updated
- [ ] Vendor due diligence completed (if processors used)
- [ ] Data export controls and approval workflow defined

## 8. Data Subject Rights

- [ ] Access request process
- [ ] Rectification process
- [ ] Erasure process
- [ ] Restriction/objection process
- [ ] Portability export process
- [ ] SLA targets for rights requests

## 9. International Transfers

- [ ] Transfer map completed
- [ ] Transfer mechanism documented (if outside jurisdiction)
- [ ] Supplemental safeguards assessed

## 10. Retention and Deletion Policy

- Raw media retention:
- Derived metrics retention:
- Logs retention:
- Backup retention:
- Hard delete SLA:

- [ ] Automatic deletion verified in test
- [ ] Deletion evidence/audit trail available

## 11. Residual Risk and Decision

- Residual risk summary:
- [ ] Proceed
- [ ] Proceed with conditions
- [ ] Block until controls implemented

Decision owner:
Date:

## 12. Reassessment Triggers

- [ ] New data category introduced
- [ ] New processor / new region
- [ ] New AI model with material behavior change
- [ ] Security incident involving health data
- [ ] Regulatory update affecting lawful basis or controls
