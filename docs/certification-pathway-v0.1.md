# Certification Pathway v0.1 (RU/CN/EU/US)

Дата: 2026-02-24
Статус: planning draft
Назначение: практический маршрут от clinical pilot к регистрации по регионам

## 1) Стратегия выхода по этапам

Этап A (MVP pilot):
- один основной регион запуска (предложение: РФ, 1 центр),
- claims только measurement + monitoring,
- сбор clinical evidence и operational evidence.

Этап B (Bridge):
- harmonized technical package,
- адаптация доказательной базы под требования региона,
- pre-submission consultations (где применимо).

Этап C (Regional submissions):
- отдельные регуляторные пакеты RU/CN/EU/US,
- синхронизированное управление версиями алгоритма.

## 2) Общие pre-submission условия (для всех регионов)

1. Frozen intended use + claims policy.
2. Risk management file (ISO 14971) и traceability matrix.
3. Software lifecycle package (requirements, architecture, V&V).
4. Clinical evidence package (pilot + performance analysis).
5. Cybersecurity и privacy package.
6. QMS readiness package.

## 3) Региональные дорожные карты

## Россия (РФ)

Цель v0.1:
- подготовка пакета для госрегистрации в рамках действующих правил.

Ключевые шаги:
1. Уточнить классификацию и код номенклатуры с локальным RA.
2. Подготовить техдок и клинические материалы для пилота/регистрации.
3. Подготовить и проверить локализацию data processing контура.
4. Провести pre-audit completeness пакета перед подачей.

Deliverables:
- RU submission checklist,
- локальные формы и инструкции,
- evidence map по требованиям РФ.

## Китай (NMPA)

Цель v0.1:
- сформировать bridge-пакет под standalone medical software route.

Ключевые шаги:
1. Pre-gap analysis against NMPA software expectations.
2. Определить локальную стратегию клинической валидности.
3. Подготовить data governance и separate-consent контур.
4. Сформировать локализованный технический досье план.

Deliverables:
- CN readiness memo,
- localized clinical-evidence mapping,
- legal/privacy checklist under PIPL assumptions.

## ЕС (MDR)

Цель v0.1:
- подготовка MDR technical documentation skeleton (Rule 11 sensitive).

Ключевые шаги:
1. Подтвердить classification hypothesis и claim boundaries.
2. Подготовить структуру Annex II/III tech docs.
3. Подготовить clinical evaluation + PMCF framework.
4. Сверить QMS и software lifecycle evidence с ожиданиями MDR.

Deliverables:
- EU dossier skeleton,
- CER/PMCF outline,
- NB discussion brief.

## США (FDA)

Цель v0.1:
- подготовить regulatory strategy memo (включая classification/exemption logic).

Ключевые шаги:
1. Сформировать device classification memo по intended use.
2. Подготовить software V&V и cybersecurity readiness package.
3. Подготовить quality-system readiness under QMSR logic.
4. Подготовить pre-sub style question set (если выбрано).

Deliverables:
- US regulatory strategy memo,
- cybersecurity package,
- QMSR readiness checklist.

## 4) 6-месячный execution timeline

Месяц 1:
- claims freeze,
- ISO14971 draft,
- submission skeleton by region.

Месяц 2:
- pilot dry-run evidence,
- SOP/ICF/eCRF finalization,
- cybersecurity process baseline.

Месяц 3:
- pilot start,
- monthly safety/quality review,
- regional gap closure iteration.

Месяц 4:
- interim clinical analysis,
- residual risk reassessment,
- draft regional submission artifacts.

Месяц 5:
- finalize technical evidence packages,
- regulatory/legal review loop by region.

Месяц 6:
- go/no-go for first submission,
- submission readiness sign-off.

## 5) Go/No-Go criteria before first submission

1. Нет открытых high-risk items без mitigations.
2. Вся критическая evidence-трассировка замкнута (risk -> control -> verification).
3. Клинические endpoint результаты соответствуют заранее зафиксированным порогам.
4. Claims registry и release-content audit закрыты без блокеров.
5. Региональные privacy/data controls подтверждены документально.

## 6) Роли и ответственность

- `RA Lead`: региональная стратегия и submission orchestration.
- `QA Lead`: quality system и DHF completeness.
- `Clinical Lead`: clinical evidence package и medical rationale.
- `ML Lead`: algorithm evidence, drift control, model versioning.
- `Security/Privacy Lead`: cybersecurity/data governance package.

## 7) Связанные документы

- `docs/regulatory-matrix-ru-cn-eu-us-v0.1.md`
- `docs/iso14971-risk-management-v0.1.md`
- `docs/claims-governance-v0.1.md`
- `docs/clinical-protocol-one-pager-v0.1.md`
