# Roadmap

## Phase 0: Setup

- [x] Создать репозиторий и структуру проекта
- [x] Добавить доменные модели и базовые формулы метрик
- [x] Добавить первичные тесты

## Phase 1: Product Definition & Feasibility

- [x] Сформировать исследовательскую базу по рынку/методам/регуляторике
- [x] Зафиксировать документ этапа 1 (scope MVP, claims/non-claims, DoD)
- [x] Подготовить шаблоны: Intended Use, DPIA checklist, Pilot protocol
- [ ] Утвердить Intended Use и целевую популяцию
- [ ] Утвердить quality flags и критерии приемки измерений
- [ ] Сформировать DPIA checklist и retention policy
- [ ] Подготовить pilot-протокол (Bland-Altman, ICC, MAE/RMSE)
- [ ] Сформировать FTO backlog по видео-урофлоуметрии

## Phase 2: Fusion MVP Foundations (video + audio + LiDAR/ToF)

- [x] Зафиксировать концепт этапа 2 (fusion-архитектура и DoD)
- [ ] Реализовать синхронный capture `RGB/depth/audio`
- [x] Реализовать baseline-оценку `h(t) -> V(t) -> Q(t)` для синхронизированных рядов
- [x] Реализовать confidence-gating depth и fallback на RGB waterline (series-level baseline)
- [x] Ввести quality flags и правила `valid / repeat / reject` (baseline rules)
- [x] Добавить CLI `analyze-level-series` и экспорт uncertainty (`sigma_Q`)
- [x] Зафиксировать и валидировать iOS capture JSON contract (`ios_capture_v1`) + конверсия в fusion payload
- [ ] Обновить privacy-контур: derivatives-only, TTL, consent flows

## Phase 3: Synthetic Validation & Bench Tests

- [x] Зафиксировать stage-3 концепт (multimodal strategy + global regulatory/privacy frame)
- [x] Генератор синтетических потоков и water-bench сценариев
- [x] Расширенный набор unit/integration тестов (synthetic + contract-to-fusion pipeline)
- [x] Подготовить bench package v0.2 (BOM variants, wiring, mechanics, acceptance criteria)
- [ ] Бенчмарки устойчивости к шуму/бликам/наклону
- [x] Оценка propagation of uncertainty (`sigma_h -> sigma_V -> sigma_Q`) для series-level baseline

## Phase 4: CV Prototype

- [ ] Детекция струи на ограниченном датасете
- [ ] Классификация паттернов кривой и событий
- [ ] Оценка угла/распыления как QC-модуль (не основной измеритель)

## Phase 5: Mobile MVP

- [x] Зафиксировать iOS/CoreML архитектуру MVP v0.1
- [x] Подготовить 12-недельный sprint/backlog план (Jira/Linear-ready)
- [x] Подготовить import-ready backlog package для Linear (`CSV/JSON`)
- [x] Подготовить ML training package v1.0 (gates/checklist/data contract)
- [ ] Прототип мобильного клиента
- [ ] Захват и on-device обработка fusion-данных
- [ ] Отображение отчёта на устройстве

## Phase 6: Clinical & Regulatory

- [x] Подготовить one-pager протокол клинического исследования (draft)
- [x] Сформировать регуляторную матрицу (РФ/Китай/ЕС/США) для planning
- [x] Подготовить ethics package (ICF/SOP/eCRF/data handling appendix)
- [x] Подготовить bilingual ethics templates (RU/EN) для site onboarding
- [x] Ввести claims governance policy и claim registry process
- [x] Подготовить ISO 14971 risk management draft + risk register
- [x] Подготовить certification pathway draft по юрисдикциям
