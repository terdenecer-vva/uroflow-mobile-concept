# Data Handling Appendix v0.1 (English)

Date: 2026-02-24
Scope: app and clinical pilot for MVP v0.1

## 1) Principles

- Data minimization: store derived data by default.
- Privacy by default: do not store raw audio/video without separate consent.
- Least privilege: role-based access only.
- Traceability: every record must map to model/config version.

## 2) Data Classes

Class A (study identifiers):
- `study_id`, `site_id`, `subject_id`, `session_id`.

Class B (medical derived data):
- `Q(t)`, summary metrics, quality score/reasons, uncertainty.

Class C (optional raw media):
- audio/video/depth (only with separate consent and approved policy).

## 3) Storage Policy

- Class A/B: store in secured study environment per local policy.
- Class C: separate protected environment with stricter retention limits.
- Deletion: on retention expiry or lawful data subject request.

## 4) Access Control

Roles:
- `Clinical Operator` - create/view sessions for own site.
- `Clinical PI` - full access to site data.
- `Data Manager` - de-identified exports and quality checks.
- `ML Engineer` - de-identified datasets only.
- `RA/QA` - audit logs and compliance reports.

## 5) De-identification and Exports

- Remove direct identifiers before analytics export.
- Mapping key remains separately controlled by authorized site personnel.
- External sharing uses de-identified datasets only.

## 6) Logging and Audit

Log at minimum:
- who created/modified/exported each record and when;
- app and model version;
- quality deviation reasons and repeat decisions.

At least monthly:
- unauthorized access audit;
- log integrity and completeness review.

## 7) Incident Response

Critical incidents include:
- data leakage;
- unauthorized access;
- loss of media/device containing study data.

Response sequence:
1. Immediate containment.
2. Notify responsible owners.
3. Assess impact and affected subjects.
4. Apply corrective actions and document outcome.

## 8) Regional Notes (planning)

- Russia: account for localization requirements for Russian citizen data.
- EU: health data as special category; lawful basis and safeguards required.
- China: sensitive PI treatment and separate consent requirements.
- US: HIPAA constraints in covered entity/business associate workflows.

## 9) Site Readiness Checklist

- [ ] Local retention schedule approved.
- [ ] Role owners assigned.
- [ ] De-identification process validated.
- [ ] Incident tabletop drill completed.
- [ ] Data handling SOP signed.
