# Архитектура (v2, fusion: video + audio + LiDAR/ToF)

## 1. Capture Layer

- Синхронный захват `RGB-видео + depth + audio`.
- Общие timestamps для всех каналов.
- Контроль условий съёмки: стабильность, пересвет, видимость маркера.

## 2. Calibration Layer

- Fiducial-маркер (масштаб и поза камеры).
- Калиброванная геометрия приёмника (`V(h)`).
- ROI-only режим (только зона приёмника).

## 3. Estimation Layer

- Оценка уровня `h(t)` из depth и RGB.
- Преобразование `h(t) -> V(t)`.
- Вычисление `Q(t)=dV/dt` со сглаживанием.
- Оценка неопределённости (`sigma_h`, `sigma_V`, `sigma_Q`).

## 4. Sensor Fusion Layer

- Audio onset/end для start/stop.
- Depth confidence gating (отбрасывание низкой уверенности).
- Late fusion независимых оценок с весами по uncertainty.

## 5. Metrics & Quality Layer

- Метрики: `Qmax`, `Qavg`, `Vvoid`, `Flow/Voiding time`, `TQmax`, `Hesitancy`.
- Классификация паттернов кривой (intermittent/staccato/plateau и т.д.).
- Quality flags: геометрия, объём, шум/блики, полнота акта.

## 6. Privacy & Security Layer

- On-device обработка по умолчанию.
- Хранение деривативов (`V(t)`, `Q(t)`, метрики) вместо raw-медиа.
- Сырой видео/аудио экспорт только по явному согласию и с TTL.
- Шифрование данных, аудит доступа, журнал событий.

## 7. Integration Layer

- Экспорт `CSV` для исследований.
- Экспорт `FHIR Observation` для интеграции с EHR.
- Версионирование алгоритма и модели для воспроизводимости.
