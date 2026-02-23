# Этап 2: Fusion MVP (video + audio + LiDAR/ToF)

Источник этапа: `/Users/denecer/Yandex.Disk.localized/Научные материалы/Патентные заявки/Урофлоуметр/deep-research-report v2.md`

Связанные шаблоны:
- `docs/intended-use-v1.md`
- `docs/dpia-checklist.md`
- `docs/pilot-protocol-v1.md`

## Цель этапа

Перейти от концепта "только видео" к устойчивому MVP на сенсорном fusion-пайплайне, где:
- основной измерительный канал: `h(t) -> V(t) -> Q(t)`;
- вспомогательные каналы: `audio` (start/stop, паттерн), `depth` (метрика и confidence).

## Основные технические решения (зафиксировано)

1. Базовый режим измерения: `volume-based` (калиброванный приёмник с известной `V(h)`).
2. Основные отчётные параметры: `Qmax`, `Qavg`, `Vvoid`, `Flow time`, `Voiding time`, `TQmax`, `Hesitancy`.
3. Качество измерения как обязательная часть отчёта (quality flags и валидность).
4. On-device обработка по умолчанию и хранение деривативов вместо raw-медиа.

## Минимальные требования к MVP

1. RGB: стабильный захват `30-60 fps`.
2. Depth: использование confidence-карты при расчёте `h(t)`.
3. Audio: синхронные timestamps и детекция onset/end.
4. Калибровка: fiducial + калибровка ёмкости.
5. Интерпретация: явная маркировка записей с `Vvoid < 150 ml` как субоптимальных.

## Технический pipeline (MVP v2)

1. Захват `RGB + depth + audio` с общим временем.
2. ROI-сегментация приёмника.
3. Оценка `h(t)` из depth+RGB (с confidence filtering).
4. Перевод `h(t)` в `V(t)` по функции `V(h)`.
5. Вычисление `Q(t)=dV/dt` и сглаживание.
6. Audio-assisted детекция start/stop и пауз.
7. Расчёт метрик + quality flags + uncertainty.

## Deliverables этапа 2

1. Fusion-spec:
   - формат синхронизации трёх каналов;
   - требования к sampling и time alignment;
   - схема confidence-gating.
2. Calibration-spec:
   - протокол fiducial-калибровки;
   - схема ввода и валидации `V(h)` для контейнеров.
3. Quality framework:
   - список quality flags и порогов;
   - правила "valid / repeat / reject".
4. Privacy pack v2:
   - режимы хранения raw vs derivatives;
   - TTL и policy удаления;
   - обновлённый DPIA checklist.
5. Validation draft v2:
   - pilot-дизайн (20-30 участников);
   - парное сравнение с эталонным урофлоуметром;
   - метрики Bland-Altman, MAE/RMSE, ICC.

## Definition of Done

- [ ] Реализован и описан синхронный capture трёх каналов (`RGB/depth/audio`).
- [ ] Реализован расчёт `h(t) -> V(t) -> Q(t)` с uncertainty-оценкой.
- [ ] Реализован минимум quality flags и правила валидности измерения.
- [ ] Подготовлен pilot-протокол для парного сравнения с эталоном.
- [ ] Обновлён privacy-контур (on-device default, TTL, consent).
- [ ] Подготовлен FTO-backlog для видео/аудио/smart-toilet патентного ландшафта.

## Ключевые риски этапа 2

| Риск | Что ломает | Митигирующее действие |
|---|---|---|
| Ошибки depth на бликах/пене | `h(t)` и все производные метрики | Confidence-gating + fallback на RGB waterline |
| Шумная акустика ванной | неверный start/stop | Audio как вспомогательный канал + кросс-проверка по `V(t)` |
| Неполное попадание в приёмник | заниженный `Vvoid` | QC-флаг и обязательное предупреждение пользователю |
| Drift геометрии/наклон камеры | систематическая ошибка `V(h)` | Fiducial re-check перед измерением |
| Privacy-риск при raw-медиа | юридические и репутационные риски | Derivatives-only по умолчанию, raw только с явным consent |

## План ближайших спринтов

1. Спринт 1: capture + калибровка + water-bench тесты.
2. Спринт 2: стабильный `V(t)/Q(t)` + quality flags + uncertainty.
3. Спринт 3: audio/depth fusion + pilot-ready протокол.

## Текущий статус реализации (2026-02-23)

- Добавлен baseline-модуль: `src/uroflow_mobile/fusion.py`
- Добавлен CLI режим: `uroflow-mobile analyze-level-series`
- Добавлены тесты baseline-fusion: `tests/test_fusion.py`
