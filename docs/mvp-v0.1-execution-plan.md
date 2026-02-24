# MVP v0.1 Execution Plan: от R&D к клиническому пилоту

Дата: 2026-02-23
Область: смартфон-урофлоуметр (iPhone, режим `water-impact`, без насадок)

## 1) Цель этапа

Собрать и верифицировать минимально жизнеспособное медицинское ПО,
которое:
- стабильно рассчитывает `Q(t), Qmax, Qavg, Vvoid, Flow time, TQmax`;
- выдаёт `quality score` и причины недостоверности;
- проходит клинический пилот с парным сравнением против эталонного урофлоуметра;
- имеет документацию, достаточную для старта регуляторного маршрута.

## 2) Scope MVP v0.1 (фиксируем границы)

Включено:
- только режим мочеиспускания `в воду`;
- сенсоры: `audio + video ROI + IMU`, LiDAR/TrueDepth как бонус-нормализация;
- on-device inference и derivatives-first хранение;
- отчёт для врача: кривая `Q(t)`, ключевые метрики, quality-флаги.

Не включено:
- автоматическая постановка диагноза;
- рекомендации по лечению;
- прямое измерение `PVR`.

## 3) Phase-gate план (12 месяцев)

## Gate G0 (Недели 1-6): Engineering Foundation

Выход:
- iOS capture pipeline с синхронными потоками (`audio/video/depth/IMU`);
- стабилизированный ROI-only preprocessing;
- офлайн replay pipeline для воспроизводимого расчёта;
- финальная спецификация capture contract (`ios_capture_v1`).

Go/No-Go критерии:
- синхронизация потоков не хуже ±50 мс;
- >95% записей проходят базовый валидатор контракта;
- end-to-end расчёт выполняется на целевых iPhone в пределах UX-бюджета времени.

## Gate G1 (Недели 7-14): Bench + Model Baseline

Выход:
- bench-протокол с шумовыми сценариями;
- baseline fusion model (audio/video/geometry late fusion);
- uncertainty и quality-менеджмент в отчёте;
- отчёт по устойчивости (MAE/RMSE, пригодность измерений по quality).

Go/No-Go критерии:
- устойчивость к шумам/движению в заранее заданных пределах;
- корректная маркировка `valid/repeat/reject` на bench-кейсах;
- отсутствие критичных деградаций на новых туалетах (leave-one-toilet-out).

## Gate G2 (Недели 15-20): Clinical Readiness

Выход:
- утверждённый one-pager протокол пилота;
- пакет для этического комитета;
- eCRF и data management план;
- frozen алгоритм для пилота + план изменения версии.

Go/No-Go критерии:
- согласован набор endpoints и статистический план;
- формализован SOP сбора данных и контроля качества;
- готова матрица рисков и mitigations для пилота.

## Gate G3 (Недели 21-36): Clinical Pilot (1 центр)

Выход:
- 100-150 пациентов, парные измерения (эталон + iPhone);
- первичный анализ Bland-Altman/MAE/MAPE;
- отчёт по качеству и повторяемости;
- решение о масштабировании в мультицентр.

Go/No-Go критерии:
- выполнение минимальных критериев точности по первичным endpoint;
- приемлемая доля измерений класса `valid`;
- отсутствие неприемлемых safety/quality отклонений.

## Gate G4 (Недели 37-52): Multi-region Preparation

Выход:
- обновлённый intended use и claims policy по регионам;
- пакет техдоков под выбранные маршруты (РФ/Китай/ЕС/США);
- план мультицентровой валидации.

Go/No-Go критерии:
- согласованный регуляторный маршрут по каждому рынку;
- завершённые пробелы в QMS, privacy, cybersecurity.

## 4) Рабочие потоки и владельцы

Поток A: iOS Engineering
- захват потоков, AR-позиционирование, ROI-only pipeline, CoreML inference.

Поток B: ML/Signal Processing
- feature extraction, fusion model, uncertainty, quality score, drift monitoring.

Поток C: Clinical Science
- протокол, центры, обучение персонала, мониторинг данных, статистика.

Поток D: Regulatory/Quality
- intended use, risk management (ISO 14971), QMS/QMSR, DHF/техдок.

Поток E: Data Protection/Security
- DPIA/PIPL/HIPAA/152-ФЗ контуры, ключи, аудит, retention, incident response.

## 5) Критические риски и immediate mitigations

Риск: деградация на новых санузлах.
Мера: leave-one-toilet-out валидация и toilet-specific calibration.

Риск: нестабильный пользовательский протокол съёмки.
Мера: AR-мастер, жесткие quality gates, автоматическое повторение.

Риск: регуляторный дрейф claims.
Мера: claims governance board, freeze словаря claims перед пилотом.

Риск: privacy/локализация данных.
Мера: on-device default, региональные контуры хранения, policy-as-code.

## 6) Deliverables текущего шага (что должно быть в репо)

- one-pager исследования: `docs/clinical-protocol-one-pager-v0.1.md`
- CoreML/iOS архитектура: `docs/coreml-architecture-v0.1.md`
- регуляторная матрица: `docs/regulatory-matrix-ru-cn-eu-us-v0.1.md`
- sprint/backlog план: `docs/sprint-plan-v0.1-12-weeks.md`
- ethics package: `docs/ethics-package-v0.1/`
- claims governance: `docs/claims-governance-v0.1.md`
- ISO 14971 draft: `docs/iso14971-risk-management-v0.1.md`
- risk register: `docs/risk-register-v0.1.csv`
- certification pathway: `docs/certification-pathway-v0.1.md`

## 7) Decision Log (решения, которые нельзя откладывать)

1. Финальный intended use MVP v0.1.
2. Пороги качества для допуска кривой в отчёт врачу.
3. Минимальные acceptance-границы по endpoint для Gate G3.
4. Регион запуска первого пилота (предложение: РФ, 1 клиника).
