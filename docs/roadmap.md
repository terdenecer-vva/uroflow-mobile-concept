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
- [ ] Бенчмарки устойчивости к шуму/бликам/наклону
- [x] Оценка propagation of uncertainty (`sigma_h -> sigma_V -> sigma_Q`) для series-level baseline

## Phase 4: CV Prototype

- [ ] Детекция струи на ограниченном датасете
- [ ] Классификация паттернов кривой и событий
- [ ] Оценка угла/распыления как QC-модуль (не основной измеритель)

## Phase 5: Mobile MVP

- [ ] Прототип мобильного клиента
- [ ] Захват и on-device обработка fusion-данных
- [ ] Отображение отчёта на устройстве

## Phase 6: Clinical & Regulatory

- [ ] План клинической валидации
- [ ] Анализ рисков и ISO 14971
- [ ] Путь к сертификации (по юрисдикции)
