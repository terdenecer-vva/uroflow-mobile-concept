# Mobile Uroflow Concept
[![CI](https://github.com/terdenecer-vva/uroflow-mobile-concept/actions/workflows/ci.yml/badge.svg)](https://github.com/terdenecer-vva/uroflow-mobile-concept/actions/workflows/ci.yml)

Концептуальный репозиторий для разработки программного обеспечения мобильного урофлоуметра.

## Цель

Построить pipeline, который по видео с камеры смартфона оценивает ключевые параметры мочеиспускания и формирует кривую потока.

## Что может считать система (MVP)

- `Voided Volume (Vvoid)` — объём мочеиспускания, мл
- `Qmax` — максимальная скорость потока, мл/с
- `Qavg` — средняя скорость потока, мл/с
- `Voiding Time (VT)` — общее время мочеиспускания, с
- `Flow Time (FT)` — время фактического потока, с
- `Time to Qmax (TQmax)` — время до достижения максимального потока, с
- `Intermittency` — число прерываний потока

## Предлагаемый технологический контур

1. Захват видео с мобильной камеры.
2. Детекция струи/зоны попадания (CV-модуль).
3. Калибровка масштаба (по эталонной геометрии или AR-маркерам).
4. Оценка расхода по кадрам и агрегация во временной ряд `Q(t)`.
5. Расчёт уродинамических метрик.
6. Формирование отчёта и визуализация кривой.

## Быстрый старт

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[video,dev]"
ruff check .
pytest -q
python examples/demo_metrics.py
```

## Анализ видео (CLI)

```bash
uroflow-mobile analyze-video /path/to/mobile_recording.mp4 \
  --known-volume-ml 280 \
  --output-csv /path/to/flow_curve.csv \
  --output-json /path/to/summary.json
```

## Анализ синхронизированных рядов уровня (Phase 2 foundation)

```bash
uroflow-mobile analyze-level-series examples/level_series_sample.json \
  --ml-per-mm 8.0 \
  --output-csv examples/level_series_fusion_curve.csv \
  --output-json examples/level_series_fusion_summary.json
```

Формат входного JSON:
- `timestamps_s` — временная шкала
- `depth_level_mm` или `level_mm` — уровень из depth-канала
- `rgb_level_mm` — опорный уровень из RGB waterline (опционально fallback)
- `depth_confidence` — confidence глубины (`0..1`, опционально)

В summary и CSV для `analyze-level-series` также экспортируются:
- `level_uncertainty_mm` (`sigma_h`)
- `volume_uncertainty_ml` (`sigma_V`)
- `flow_uncertainty_ml_s` (`sigma_Q`)

Ключевые параметры:

- `--known-volume-ml` — калибрует кривую так, чтобы интеграл дал заданный объём.
- `--roi x,y,w,h` — ограничивает область анализа для устойчивости.
- `--motion-threshold` и `--min-active-pixels` — фильтрация шумов.

## Генерация synthetic bench-сценариев (Phase 3)

```bash
uroflow-mobile generate-synthetic-bench \
  --profile intermittent \
  --scenario reflective_bowl \
  --target-volume-ml 320 \
  --ml-per-mm 8.0 \
  --output-json examples/synth_reflective.json \
  --output-csv examples/synth_reflective.csv
```

Профили:
- `bell`
- `plateau`
- `intermittent`
- `staccato`

Сценарии:
- `quiet_lab`
- `reflective_bowl`
- `phone_motion`

## Контракт iOS-capture (валидация и экспорт в fusion payload)

```bash
uroflow-mobile validate-capture-contract \
  examples/ios_capture_contract_sample.json \
  --output-level-json examples/ios_capture_level_payload.json
```

`output-level-json` можно напрямую передавать в `analyze-level-series`.

## Структура

- `docs/` — архитектура, ограничения, roadmap
- `docs/stage-1-product-definition.md` — формализация первого этапа концепции
- `docs/stage-2-fusion-development.md` — развитие концепции v2 (video+audio+LiDAR/ToF)
- `docs/stage-3-multimodal-global-strategy.md` — мультимодальная стратегия и региональные рамки (RU/CN/EU/US)
- `docs/stage-3-synthetic-bench-and-ios-contract.md` — реализация synthetic-bench и iOS capture contract
- `docs/mvp-v0.1-execution-plan.md` — phase-gate план от R&D до клинического пилота
- `docs/sprint-plan-v0.1-12-weeks.md` — детальный 12-недельный sprint/backlog план (owner/DoD/dependencies)
- `docs/clinical-protocol-one-pager-v0.1.md` — one-pager протокол исследования для ethics/IRB
- `docs/coreml-architecture-v0.1.md` — спецификация iOS/CoreML sensor-fusion архитектуры
- `docs/regulatory-matrix-ru-cn-eu-us-v0.1.md` — регуляторная матрица по регионам
- `docs/ethics-package-v0.1/` — шаблоны ICF/SOP/eCRF/data handling appendix
- `docs/linear-import-v0.1/` — import-ready backlog package для Linear (CSV/JSON + инструкция)
- `docs/claims-governance-v0.1.md` — policy управления claims и процесс согласования формулировок
- `docs/iso14971-risk-management-v0.1.md` — risk management file draft (ISO 14971)
- `docs/risk-register-v0.1.csv` — risk register для operational tracking
- `docs/certification-pathway-v0.1.md` — практический маршрут подготовки к регистрации по регионам
- `docs/intended-use-v1.md` — документ Intended Use v1.0
- `docs/dpia-checklist.md` — DPIA checklist v1.0 для данных видео/аудио/depth
- `docs/pilot-protocol-v1.md` — pilot-протокол v1.0 сравнения с эталоном
- `docs/edc-v1.1/` — canonical EDC schema v1.1 (dictionary/codelists/crosswalk/rules)
- `docs/edc-v1.1/redcap/` — import-ready REDCap profile v1.1
- `docs/edc-v1.1/openclinica/` — import-ready OpenClinica profile v1.1 (incl. ODM XML)
- `src/uroflow_mobile/` — доменные модели и расчёт метрик
- `tests/` — базовые тесты расчёта метрик
- `examples/` — демо-скрипты
- `scripts/normalize_edc_dictionary_v1_1.py` — генератор пакета `docs/edc-v1.1`
- `scripts/generate_redcap_profile_v1_1.py` — генератор REDCap Data Dictionary из canonical EDC
- `scripts/generate_redcap_dry_run_records_v1_1.py` — генератор REDCap dry-run импортных записей
- `scripts/generate_openclinica_profile_v1_1.py` — генератор OpenClinica профиля из canonical EDC

## Важно

Проект предназначен для R&D и не является медицинским изделием. Для клинического применения потребуются валидация, сертификация и соответствие требованиям законодательства.
