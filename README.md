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

Ключевые параметры:

- `--known-volume-ml` — калибрует кривую так, чтобы интеграл дал заданный объём.
- `--roi x,y,w,h` — ограничивает область анализа для устойчивости.
- `--motion-threshold` и `--min-active-pixels` — фильтрация шумов.

## Структура

- `docs/` — архитектура, ограничения, roadmap
- `docs/stage-1-product-definition.md` — формализация первого этапа концепции
- `docs/stage-2-fusion-development.md` — развитие концепции v2 (video+audio+LiDAR/ToF)
- `docs/intended-use-v1.md` — документ Intended Use v1.0
- `docs/dpia-checklist.md` — DPIA checklist v1.0 для данных видео/аудио/depth
- `docs/pilot-protocol-v1.md` — pilot-протокол v1.0 сравнения с эталоном
- `src/uroflow_mobile/` — доменные модели и расчёт метрик
- `tests/` — базовые тесты расчёта метрик
- `examples/` — демо-скрипты

## Важно

Проект предназначен для R&D и не является медицинским изделием. Для клинического применения потребуются валидация, сертификация и соответствие требованиям законодательства.
