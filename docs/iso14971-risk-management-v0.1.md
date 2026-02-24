# ISO 14971 Risk Management File v0.1 (Draft)

Дата: 2026-02-24
Статус: рабочий draft для MVP v0.1
Стандартная основа: ISO 14971:2019 (+ применимые локальные требования)

## 1) Область применения

Этот файл описывает процесс управления рисками для software-first
смартфон-урофлоуметра (iPhone), включая:
- захват сигналов (audio/video/depth/IMU),
- расчёт `Q(t)` и метрик,
- quality-классификацию `valid/repeat/reject`,
- отчётность и экспорт данных.

## 2) Risk management policy

Цели:
- снизить риск ошибочной клинической интерпретации;
- снизить риск утечки/неправомерной обработки данных;
- обеспечить трассируемость mitigations и verification evidence.

Ключевой принцип:
- при сомнительном качестве измерения система обязана понижать confidence,
  маркировать запись и инициировать повтор, а не скрыто "достраивать" результат.

## 3) Risk acceptability criteria (MVP)

Шкалы:
- Severity (`S`): 1..5
- Probability (`P`): 1..5
- Risk index `R = S * P`

Пороги:
- `R <= 4`: Acceptable with routine controls
- `5 <= R <= 9`: ALARP, требует обоснования и мониторинга
- `R >= 10`: Unacceptable до внедрения дополнительных controls

## 4) Risk management process

1. Идентификация hazards и hazardous situations.
2. Оценка initial risk (`S`, `P`, `R`).
3. Определение risk controls (design / protective / information for safety).
4. Verification/validation каждого control.
5. Оценка residual risk.
6. Residual risk review на уровне системы.
7. Post-market feedback loop (после пилота).

## 5) Hazard categories

- `CLN`: клинический риск неверного измерения/интерпретации.
- `SW`: software defect / regression / model drift.
- `UX`: риск неправильного использования (misuse).
- `SEC`: cybersecurity и integrity.
- `PRV`: privacy и data governance.
- `OPS`: организационные и процессные риски центра.

## 6) Top risks for MVP v0.1

1. Некорректный `Qmax` из-за артефакта в конце мочеиспускания.
2. Неверное определение начала/конца события.
3. Потеря ROI или движение устройства без корректного reject.
4. Деградация модели на новых туалетах/условиях.
5. Использование low-quality записи как клинически достоверной.
6. Нарушение privacy/локализации данных.

Подробный реестр: `docs/risk-register-v0.1.csv`.

## 7) Mandatory controls (baseline)

Design controls:
- ROI-only pipeline и жесткие quality gates.
- uncertainty propagation (`sigma_h/sigma_V/sigma_Q`) и policy-based decisioning.
- claim boundaries: no diagnosis / no treatment recommendation.

Protective measures:
- role-based access, audit logs, model hash traceability.
- regional data handling policies and retention limits.

Information for safety:
- in-app disclaimers для low-quality output.
- operator SOP and repeat rules.
- clinical report flags with explicit status.

## 8) Verification evidence map

Для каждого control должны быть evidence-артефакты:
- test report (unit/integration/bench),
- clinical dry-run report,
- security drill report,
- document approval record (ICF/SOP/claims governance).

## 9) Residual risk review

Residual risk review board:
- Clinical Lead
- RA/QA Lead
- ML Lead
- Security/Privacy Lead

Решения:
- accept residual risk,
- request additional controls,
- block release.

## 10) Change management triggers

Обязательный re-assessment риска при:
- изменении intended use или claims,
- изменении архитектуры модели или quality thresholds,
- новых клинических данных, меняющих risk profile,
- security/privacy инцидентах.

## 11) Post-pilot risk loop

После первых 100-150 пациентов:
- пересчитать вероятность ключевых hazardous situations;
- обновить risk index и control plan;
- пересмотреть release gates для multi-center rollout.

## 12) Required next artifacts

1. `Risk Traceability Matrix` (risk -> control -> test -> result).
2. Formal `Benefit-Risk` summary for pilot dossier.
3. Post-market signal intake template.
