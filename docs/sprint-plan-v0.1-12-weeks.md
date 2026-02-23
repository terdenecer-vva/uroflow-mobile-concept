# Sprint Plan v0.1 (12 недель): Jira/Linear-ready

Дата: 2026-02-23
Горизонт: 6 спринтов по 2 недели
Релизная цель: Clinical Pilot Readiness (Gate G2)

## 1) Команда и роли

- `PM/PO` — продуктовые решения, приоритизация, scope freeze.
- `iOS Lead` — capture pipeline, AR/ROI UX, on-device orchestration.
- `ML Lead` — fusion model, quality score, uncertainty, evaluation.
- `Data Engineer` — eCRF/data pipeline, quality monitoring, traceability.
- `Clinical Lead` — SOP клиники, endpoints, protocol execution.
- `RA/QA Lead` — claims governance, risk/QMS, ethics/regulatory pack.
- `Security/Privacy Lead` — DPIA, retention, access control, incident process.

## 2) Релизные критерии к концу 12 недель

1. Frozen MVP v0.1 алгоритм (`model + thresholds + quality policy`).
2. Полный пакет клинического старта (protocol + ICF + SOP + eCRF + data appendix).
3. Отслеживаемость версии алгоритма в каждом отчёте (audit trail).
4. Pre-pilot acceptance на bench + dry-run клиники.

## 3) Спринты и эпики

## Sprint 1-2 (Weeks 1-4): Capture & Protocol Hardening

| ID | Epic | Task | Owner | DoD | Depends on |
|---|---|---|---|---|---|
| CAP-01 | Capture | Стабильный сбор `audio/video/IMU` с общим timestamp | iOS Lead | Drift потоков <= 50 мс на 20 тестах | - |
| CAP-02 | Capture | Интеграция depth availability и fallback flags | iOS Lead | Depth validity логируется в контракт | CAP-01 |
| CAP-03 | UX | AR onboarding для установки ROI воды | iOS Lead | 90% тестовых пользователей проходят setup < 40 сек | CAP-01 |
| CAP-04 | Contract | Финализация `ios_capture_v1` полей и валидации | Data Engineer | JSON schema freeze + backward compatibility rules | CAP-01, CAP-02 |
| CLN-01 | Clinical | Версия SOP оператора съёмки для клиники | Clinical Lead | Документ утвержден и обучено >= 2 оператора | CAP-03 |
| GOV-01 | Governance | Freeze intended use и non-claims MVP | RA/QA Lead | Подписанный intended-use memo | - |

## Sprint 3-4 (Weeks 5-8): Model Freeze Candidate + Evidence Base

| ID | Epic | Task | Owner | DoD | Depends on |
|---|---|---|---|---|---|
| ML-01 | Model | Реализация late-fusion baseline в train pipeline | ML Lead | Reproducible training run + versioned artifact | CAP-04 |
| ML-02 | Model | Uncertainty calibration (`sigma_h/sigma_V/sigma_Q`) | ML Lead | Coverage-check uncertainty на validation set | ML-01 |
| ML-03 | Quality | Quality-score engine + reject/repeat policy | ML Lead | Quality reasons в отчёте и логах | ML-01 |
| BEN-01 | Bench | Noise/tilt/toilet variability stress tests | ML Lead | Bench report с MAE/RMSE и fail cases | ML-01 |
| DATA-01 | Data | Dataset manifest + lineage + leakage checks | Data Engineer | Dataset card + split report | CAP-04 |
| SEC-01 | Security | Threat/Risk workshop для pilot scope | Security/Privacy Lead | Risk register v0.1 + owners | GOV-01 |

## Sprint 5 (Weeks 9-10): Clinical Package Assembly

| ID | Epic | Task | Owner | DoD | Depends on |
|---|---|---|---|---|---|
| ETH-01 | Ethics | Финал ICF шаблона + локализация под центр | RA/QA Lead | ICF v1.0 подписан PI/RA | CLN-01, GOV-01 |
| ETH-02 | Ethics | eCRF и data dictionary для pilot | Data Engineer | eCRF поля утверждены статистиком и клиникой | DATA-01 |
| ETH-03 | Ethics | Data handling appendix (retention/access/de-identification) | Security/Privacy Lead | Approved data appendix v1.0 | SEC-01 |
| CLN-02 | Clinical | Statistical Analysis Plan (SAP) v1.0 | Clinical Lead | SAP утвержден до первого пациента | BEN-01 |
| GOV-02 | Governance | Claims governance и phrase library | RA/QA Lead | Claim matrix утверждена для UI/маркетинга | GOV-01 |
| QA-01 | Quality | Pilot release checklist + DHF index | RA/QA Lead | Checklist complete, gaps owner-assigned | ETH-01, ETH-03 |

## Sprint 6 (Weeks 11-12): Dry Run and Go/No-Go

| ID | Epic | Task | Owner | DoD | Depends on |
|---|---|---|---|---|---|
| DRY-01 | Clinical Ops | Dry-run на 10-15 записях в клинике | Clinical Lead | Dry-run report + corrective actions | ETH-01, ETH-02 |
| DRY-02 | Model Ops | Frozen model `fusion_v0.1.0` и hash-tracking | ML Lead | Model freeze memo + artifact hash in reports | ML-03 |
| DRY-03 | Data Ops | End-to-end audit trail проверка | Data Engineer | Любая запись трассируется до версии модели/конфига | DRY-02 |
| DRY-04 | Security | Access control + incident drill | Security/Privacy Lead | Drill проведен, corrective actions закрыты | ETH-03 |
| GATE-01 | Governance | Go/No-Go board | PM/PO | Протокол решения и список блокеров | DRY-01..04 |

## 4) Бэклог после Go (Weeks 13+)

- Multi-center readiness (2-й центр, новый туалетный парк, переносимость).
- Региональные адаптации пакета (EU/US/CN).
- PMCF/post-market monitoring framework.

## 5) Минимальная структура задач в Linear/Jira

Поля для каждой задачи:
- `Task ID`
- `Epic`
- `Owner`
- `Priority`
- `DoD`
- `Dependencies`
- `Risk if delayed`
- `Evidence artifact` (ссылка на отчёт/док)

Definition of Done для инженерных задач:
- код + тесты + документация + воспроизводимый запуск.

Definition of Done для клинических/регуляторных задач:
- документ версии `vX.Y` + список согласующих + дата утверждения.
