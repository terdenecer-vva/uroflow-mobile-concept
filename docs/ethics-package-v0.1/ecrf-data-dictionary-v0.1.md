# eCRF Data Dictionary v0.1

Дата: 2026-02-23
Назначение: унификация сбора данных пилота

## 1) Идентификация и визит

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `study_id` | string | yes | Код исследования |
| `site_id` | string | yes | Код центра |
| `subject_id` | string | yes | Псевдоним участника |
| `visit_id` | string | yes | Идентификатор визита |
| `session_id` | string | yes | Идентификатор сессии захвата |
| `operator_id` | string | yes | Код оператора |
| `visit_datetime` | datetime | yes | Дата/время визита |

## 2) Демография и контекст

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `sex_at_birth` | enum | yes | male/female/other |
| `age_years` | int | yes | Возраст |
| `voiding_position` | enum | yes | standing/sitting |
| `diagnostic_group` | enum | no | BPH/stricture/neurogenic/other |

## 3) Эталонная урофлоуметрия

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `ref_qmax_ml_s` | float | yes | Эталон Qmax |
| `ref_qavg_ml_s` | float | yes | Эталон Qavg |
| `ref_vvoid_ml` | float | yes | Эталон Vvoid |
| `ref_flow_time_s` | float | no | Эталон flow time |
| `ref_tqmax_s` | float | no | Эталон TQmax |
| `ref_curve_class` | enum | no | bell/plateau/intermittent/staccato/other |

## 4) Приложение (смартфон)

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `app_version` | string | yes | Версия приложения |
| `model_version` | string | yes | Версия модели |
| `model_hash` | string | yes | Hash артефакта модели |
| `app_qmax_ml_s` | float | yes | Qmax приложения |
| `app_qavg_ml_s` | float | yes | Qavg приложения |
| `app_vvoid_ml` | float | yes | Vvoid приложения |
| `app_flow_time_s` | float | no | Flow time приложения |
| `app_tqmax_s` | float | no | TQmax приложения |
| `quality_status` | enum | yes | valid/repeat/reject |
| `quality_score` | int | yes | 0-100 |

## 5) Quality reasons (multi-select)

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `qr_low_snr` | bool | yes | Низкий SNR |
| `qr_motion` | bool | yes | Движение телефона |
| `qr_roi_lost` | bool | yes | Потеря ROI |
| `qr_not_in_water` | bool | yes | Попадание не в воду |
| `qr_low_volume` | bool | yes | Низкий объём |
| `qr_other_text` | string | no | Прочее |

## 6) Процедурные поля

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `attempt_number` | int | yes | Номер попытки в визите |
| `repeat_required` | bool | yes | Требуется повтор |
| `repeat_reason` | string | no | Причина повтора |
| `protocol_deviation` | bool | yes | Отклонение от SOP |
| `deviation_comment` | string | no | Комментарий |

## 7) PVR (отдельный workflow)

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `pvr_available` | bool | yes | Измерен ли PVR отдельно |
| `pvr_ml` | float | no | Значение PVR |
| `pvr_method` | enum | no | bladder_scan/ultrasound/manual_entry |

## 8) Вычисляемые поля анализа

| Поле | Формула | Комментарий |
|---|---|---|
| `delta_qmax` | `app_qmax_ml_s - ref_qmax_ml_s` | Для Bland-Altman |
| `delta_qavg` | `app_qavg_ml_s - ref_qavg_ml_s` | Для Bland-Altman |
| `delta_vvoid` | `app_vvoid_ml - ref_vvoid_ml` | Для Bland-Altman |
| `abs_pct_error_qmax` | `abs(delta_qmax)/ref_qmax*100` | Для MAPE |

## 9) Правила валидации eCRF

- Все обязательные поля должны быть заполнены до lock визита.
- `quality_status=reject` требует заполненного `repeat_reason`.
- `protocol_deviation=true` требует `deviation_comment`.
- `pvr_available=false` -> `pvr_ml` пустое.
