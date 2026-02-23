# CoreML Architecture v0.1: sensor fusion для смартфон-урофлоуметра

Дата: 2026-02-23
Версия: Draft v0.1
Платформа: iPhone (iOS 17+ целевой профиль)

## 1) Цель архитектуры

On-device оценка `Q(t)` и uncertainty для free-flow теста,
с минимальной латентностью и контролем качества записи.

## 2) Потоки данных

Потоки захвата:
- Audio: 44.1/48 kHz mono
- RGB video: 30-60 fps
- Depth: 15-30 fps (если доступен)
- IMU: до 100 Hz

Нормализация по времени:
- общая тайм-ось inference: 10 Hz (окно 100 мс)
- выравнивание по timestamp, nearest-neighbor + интерполяция для медленных потоков

## 3) Препроцессинг

Audio branch:
- STFT -> log-mel (64-128 полос)
- признаки: band energy, spectral centroid/rolloff, entropy, SNR

Video branch (ROI-only):
- стабилизация ROI
- optical flow magnitude
- splash/ripple признаки
- бинарный признак "в воду / не в воду"

Geometry/IMU branch:
- distance, angle, ROI scale, depth validity
- IMU jitter / movement score

## 4) Модель late fusion (MVP)

Audio encoder:
- 1D-CNN блоки по временным mel-признакам

Video encoder:
- lightweight 2D-CNN по ROI фреймам
- temporal head (GRU или temporal conv)

Geometry encoder:
- MLP на числовых признаках

Fusion head:
- concat(audio, video, geometry)
- shared dense layers
- два выхода:
  - `Q_hat(t)` (regression)
  - `sigma_hat(t)` (aleatoric uncertainty)

## 5) Пост-процессинг физической правдоподобности

- hard clamp: `Q(t) >= 0`
- ограничение dQ/dt (soft penalty/фильтрация)
- сглаживание с учётом uncertainty (например, Kalman-like)
- контроль интеграла `Vvoid = ∫Q(t)dt`

## 6) Quality engine

Выход quality score 0-100 и причины:
- low SNR
- high motion
- lost ROI
- impact not-in-water
- insufficient volume
- low confidence ratio

Политика:
- `valid`: показывать метрики без ограничений
- `repeat`: показывать метрики с предупреждением
- `reject`: не использовать для клинической интерпретации

## 7) CoreML deployment budget

Целевые ограничения (на устройство среднего/верхнего сегмента):
- inference latency <= 50 мс на окно 100 мс
- memory footprint модели <= 30-50 MB
- отсутствие заметного thermal throttling при тесте до 120 секунд

Оптимизации:
- quantization (FP16/int8 где допустимо)
- раздельные lightweight heads
- батчирование окон по 5-10 шагов при офлайн-анализе

## 8) Версионирование модели и воспроизводимость

- Model ID: `fusion_vX.Y.Z`
- фиксировать feature schema version
- логировать calibration params и thresholds
- хранить hash модели в каждом клиническом отчёте

## 9) План обучения

Ground truth:
- парная запись с эталонным урофлоуметром

Dataset splits:
- train/val/test без утечки по пациенту
- отдельный внешний test: новые туалеты/клиники

Validation loops:
- offline model metrics
- bench stress tests
- clinical pre-pilot freeze

## 10) API контракты между слоями

Capture output -> contract:
- `ios_capture_v1` JSON

Contract -> fusion input:
- `timestamps_s`, `depth_level_mm`, `rgb_level_mm`, `depth_confidence`, `meta`

Fusion output:
- `Q(t)`, метрики, `sigma_h/sigma_V/sigma_Q`, quality flags

## 11) Что не делаем в v0.1

- автоматическое диагностическое заключение
- персонализированные лечебные рекомендации
- PVR estimation без внешнего датчика
