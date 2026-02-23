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
- [ ] Реализовать оценку `h(t) -> V(t) -> Q(t)` в калиброванной геометрии
- [ ] Реализовать confidence-gating depth и fallback на RGB waterline
- [ ] Ввести quality flags и правила `valid / repeat / reject`
- [ ] Обновить privacy-контур: derivatives-only, TTL, consent flows

## Phase 3: Synthetic Validation & Bench Tests

- [ ] Генератор синтетических потоков и water-bench сценариев
- [ ] Расширенный набор unit/integration тестов
- [ ] Бенчмарки устойчивости к шуму/бликам/наклону
- [ ] Оценка propagation of uncertainty (`sigma_h -> sigma_V -> sigma_Q`)

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
