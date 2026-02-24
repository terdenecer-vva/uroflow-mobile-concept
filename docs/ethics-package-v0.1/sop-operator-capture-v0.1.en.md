# SOP Operator Capture v0.1 (Clinical Site)

Date: 2026-02-24
Use: iPhone capture collected in parallel with standard uroflowmetry

## 1) SOP Objective

Ensure a consistent, reproducible, and privacy-safe capture procedure while
minimizing artifacts.

## 2) Operator Responsibilities

- Verify participant consent before starting.
- Prepare device and recording environment.
- Execute capture strictly according to checklist.
- Document deviations and repeat reasons.

## 3) Pre-Start Checklist

1. Consent and `subject_id` verified.
2. iPhone charged and app profile set correctly.
3. Privacy-by-default mode enabled (ROI-only, no raw storage by default).
4. Phone mounted stably; frame contains bowl/water only.
5. AR setup confirms readiness (ROI, exposure, stability).

## 4) Recording Procedure

1. Start recording before voiding begins.
2. Ensure phone remains stationary.
3. Do not interfere unless there is a critical reason.
4. Stop recording after confirmed event completion.
5. Verify summary quality status (`valid/repeat/reject`).

## 5) Repeat Rules

Repeat is mandatory when:
- status is `reject`;
- ROI is lost;
- significant device movement occurred;
- recording is invalid or interrupted.

Repeat may be allowed with note when:
- status is `repeat` and investigator approves.

## 6) Deviation Logging

If deviations occur, operator records:
- deviation type;
- step where it occurred;
- action taken (repeat/exclude);
- comments.

## 7) Post-Procedure Checklist

1. Session data linked to `subject_id`.
2. Capture quality recorded in eCRF.
3. Deviations entered in log.
4. Device returned to baseline state.

## 8) Escalation Criteria

Escalate to study coordinator if:
- recurrent technical failures occur;
- abnormal recordings may affect participant safety;
- confidentiality breach is suspected.
