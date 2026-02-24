# Dataset Record Contract v1.0

Контракт основан на `Uroflow_ML_Training_Pipeline_Spec_v1.0`.

## Record-level структура

Для каждого `record_id`:

- `meta.json`
  - `record_id`, `source` (`bench|clinic|home`), `site_id`, `toilet_id`, `device_model`
  - `mode`, `quality_status`, `quality_score`, `artifact_flags`
  - `model_version` (для инференс-логов), `dataset_version`
- `Q_ref.csv`
  - обязательный для `bench` и `clinic`
  - сетка `10 Гц`, колонки: `t_s`, `q_ref_ml_s`
- `Q_pred.csv`
  - предсказания модели на той же сетке `10 Гц`
  - колонки: `t_s`, `q_hat_ml_s`, `sigma_ml_s`
- `quality.json`
  - причины браковки и confidence сигналы
- `audio.m4a` и `roi_video.mp4`
  - только при согласии и необходимости обучения

## Инварианты качества данных

- `t_start < t_end`
- `V_ref ~= ∫Q_ref dt` (допуск задаётся протоколом)
- единая синхронизация по `t0` (`beep` и/или `LED`)
- все модальности приведены к временной сетке `10 Гц`

## Правила split

- Записи одного субъекта не делятся между `train/val/test`.
- Отдельный `toilet-wise` или `room-wise` тест (`LOTO`).
- По возможности отдельный `device-wise` holdout.
- Для мультицентра — отдельный `site-wise` внешний тест.

## Приватность и минимизация

- По умолчанию использовать агрегаты (`Q(t)`, метрики, quality), без хранения сырых медиа.
- Сырые медиа хранить только при явном consent и в ограниченном контуре доступа.
