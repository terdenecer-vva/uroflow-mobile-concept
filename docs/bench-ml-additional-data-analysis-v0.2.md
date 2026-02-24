# Additional Data Analysis v0.2

Дата анализа: `2026-02-24`  
Входные файлы:
- `Uroflow_Bench_BOM_Variants_v0.2.xlsx`
- `Uroflow_Bench_SOP_BOM_v0.2.docx`
- `Uroflow_ML_Training_Pipeline_Spec_v1.0.docx`

## Что извлечено в репозиторий

- Bench-пакет: `docs/bench-package-v0.2/`
  - BOM variants (`low/mid/high`), wiring, mechanics, acceptance criteria.
  - Нормализованный BOM по позициям (`bench_bom_line_items_v0.2.csv`).
- ML pipeline-пакет: `docs/ml-pipeline-package-v1.0/`
  - Гейты готовности моделей (`training_gates_v1.0.csv`).
  - Чеклист этапов обучения/валидации (`pipeline_stage_checklist_v1.0.csv`).
  - Контракт структуры dataset record (`dataset_record_contract_v1.0.md`).

## Ключевые выводы по bench

- `Mid` — оптимальный уровень для основной разработки:
  - управляемый профиль потока,
  - достаточная точность эталона,
  - умеренная сложность сборки.
- `Low` годится для быстрого старта, но ограничен по воспроизводимости профиля.
- `High` нужен для финальной трассируемости ошибок и подготовки к клинической фазе.
- Критично соблюдать синхронизацию `t0` и критерии приёмки данных (монотонность `m(t)`, валидный интеграл объёма, полный metadata trail).

## Ключевые выводы по ML pipeline

- Спецификация v1.0 задаёт корректную двухмодельную архитектуру (Model A + Model B) и quality-gating.
- Основной риск переобучения явно закрыт через grouped split (`subject`, `toilet`, `device`, `site`).
- Для выхода в клинически пригодный контур не хватает одного шага: зафиксировать числовые пороги MAE/Bland-Altman в pilot protocol и привязать их к CI release-gates.

## Рекомендуемые следующие действия

1. Сформировать реальный BOM-cost sheet (цены/поставщики) на базе `bench_bom_line_items_v0.2.csv`.
2. Поднять `Mid` стенд как baseline и прогнать acceptance criteria из `bench_acceptance_criteria_v0.2.csv`.
3. Создать `dataset_version v0.1` с grouped split manifests и запустить первый regression suite по `training_gates_v1.0.csv`.
