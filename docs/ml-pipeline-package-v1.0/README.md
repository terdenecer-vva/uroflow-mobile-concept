# ML Pipeline Package v1.0

Источник данных:
- `Uroflow_ML_Training_Pipeline_Spec_v1.0.docx`

Пакет фиксирует внедрение воспроизводимого цикла обучения/валидации для двух моделей:
- `Model A`: `t_start/t_end` + артефакты + quality.
- `Model B`: регрессия `Q(t)` (10 Гц) + неопределенность `sigma(t)`.

## Файлы
- `training_gates_v1.0.csv` — измеримые критерии готовности модели.
- `pipeline_stage_checklist_v1.0.csv` — этапы пайплайна и ожидаемые артефакты.
- `dataset_record_contract_v1.0.md` — контракт структуры record-level данных.

## Ключевые требования спецификации
- Grouped split: `subject-wise`, `toilet-wise (LOTO)`, `device-wise`, `site-wise`.
- Единая временная сетка: `10 Гц` после синхронизации по `beep/LED`.
- Quality gating как обязательный safety-слой перед выводом метрик.
- On-device совместимость (`CoreML`) с валидацией latency/memory/stability.

## Практический порядок внедрения
1. Зафиксировать `dataset_version` и групповые split-конфиги.
2. Реализовать `Model A` с приоритетом на recall артефактов `flush/not_in_water`.
3. Реализовать `Model B` с NLL + физическими штрафами (`dQ/dt`, non-negative).
4. Привязать CI-regression suite к `training_gates_v1.0.csv`.
5. Выпускать каждую версию модели с `model card` + `data card`.
