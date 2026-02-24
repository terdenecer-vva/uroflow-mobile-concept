# eCRF Data Dictionary v0.1 (English)

Date: 2026-02-24
Purpose: standardized pilot data capture

## 1) Identification and Visit

| Field | Type | Required | Description |
|---|---|---|---|
| `study_id` | string | yes | Study code |
| `site_id` | string | yes | Site code |
| `subject_id` | string | yes | Pseudonymous participant code |
| `visit_id` | string | yes | Visit identifier |
| `session_id` | string | yes | Capture session identifier |
| `operator_id` | string | yes | Operator code |
| `visit_datetime` | datetime | yes | Visit date/time |

## 2) Demographics and Context

| Field | Type | Required | Description |
|---|---|---|---|
| `sex_at_birth` | enum | yes | male/female/other |
| `age_years` | int | yes | Age |
| `voiding_position` | enum | yes | standing/sitting |
| `diagnostic_group` | enum | no | BPH/stricture/neurogenic/other |

## 3) Reference Uroflowmetry

| Field | Type | Required | Description |
|---|---|---|---|
| `ref_qmax_ml_s` | float | yes | Reference Qmax |
| `ref_qavg_ml_s` | float | yes | Reference Qavg |
| `ref_vvoid_ml` | float | yes | Reference Vvoid |
| `ref_flow_time_s` | float | no | Reference flow time |
| `ref_tqmax_s` | float | no | Reference TQmax |
| `ref_curve_class` | enum | no | bell/plateau/intermittent/staccato/other |

## 4) App Output (Smartphone)

| Field | Type | Required | Description |
|---|---|---|---|
| `app_version` | string | yes | App version |
| `model_version` | string | yes | Model version |
| `model_hash` | string | yes | Model artifact hash |
| `app_qmax_ml_s` | float | yes | App Qmax |
| `app_qavg_ml_s` | float | yes | App Qavg |
| `app_vvoid_ml` | float | yes | App Vvoid |
| `app_flow_time_s` | float | no | App flow time |
| `app_tqmax_s` | float | no | App TQmax |
| `quality_status` | enum | yes | valid/repeat/reject |
| `quality_score` | int | yes | 0-100 |

## 5) Quality Reasons (multi-select)

| Field | Type | Required | Description |
|---|---|---|---|
| `qr_low_snr` | bool | yes | Low SNR |
| `qr_motion` | bool | yes | Device motion |
| `qr_roi_lost` | bool | yes | ROI lost |
| `qr_not_in_water` | bool | yes | Impact not in water |
| `qr_low_volume` | bool | yes | Low volume |
| `qr_other_text` | string | no | Other reason |

## 6) Procedural Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `attempt_number` | int | yes | Attempt number within visit |
| `repeat_required` | bool | yes | Repeat required |
| `repeat_reason` | string | no | Repeat reason |
| `protocol_deviation` | bool | yes | SOP deviation |
| `deviation_comment` | string | no | Deviation comment |

## 7) PVR (separate workflow)

| Field | Type | Required | Description |
|---|---|---|---|
| `pvr_available` | bool | yes | Separate PVR available |
| `pvr_ml` | float | no | PVR value |
| `pvr_method` | enum | no | bladder_scan/ultrasound/manual_entry |

## 8) Derived Analysis Fields

| Field | Formula | Comment |
|---|---|---|
| `delta_qmax` | `app_qmax_ml_s - ref_qmax_ml_s` | Bland-Altman |
| `delta_qavg` | `app_qavg_ml_s - ref_qavg_ml_s` | Bland-Altman |
| `delta_vvoid` | `app_vvoid_ml - ref_vvoid_ml` | Bland-Altman |
| `abs_pct_error_qmax` | `abs(delta_qmax)/ref_qmax*100` | MAPE |

## 9) eCRF Validation Rules

- All required fields must be completed before visit lock.
- If `quality_status=reject`, `repeat_reason` is mandatory.
- If `protocol_deviation=true`, `deviation_comment` is mandatory.
- If `pvr_available=false`, `pvr_ml` must remain empty.
