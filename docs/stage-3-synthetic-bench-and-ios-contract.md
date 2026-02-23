# Этап 3 (реализация): Synthetic Bench + iOS Capture Contract

Дата: 2026-02-23

## Что реализовано

1. Генератор синтетических стендовых профилей потока:
- профили `bell`, `plateau`, `intermittent`, `staccato`;
- нормировка под заданный `target_volume_ml`;
- генерация `true_flow`, `true_volume`, `true_level`;
- симуляция каналов `depth/rgb/depth_confidence` с preset-сценариями.

2. Preset water-bench сценарии:
- `quiet_lab`
- `reflective_bowl`
- `phone_motion`

3. iOS capture contract v1:
- схема `schema_version = ios_capture_v1`;
- блок `session` (mode, calibration, privacy, metadata);
- массив `samples` с синхронными отсчётами (`t_s`, `depth_level_mm`, `rgb_level_mm`, `depth_confidence`, `roi_valid`, optional audio/motion).

4. CLI для двух задач:
- `uroflow-mobile generate-synthetic-bench`
- `uroflow-mobile validate-capture-contract`

## Модули

- `src/uroflow_mobile/synthetic.py`:
  генерация профилей и сценариев синтетических рядов.
- `src/uroflow_mobile/capture_contract.py`:
  валидация iOS capture JSON и конверсия в payload для fusion.

## Контракт iOS capture (минимальные требования)

Top-level:
- `schema_version`: `ios_capture_v1`
- `session`: объект
- `samples`: массив длиной >= 2

`session`:
- `session_id`: непустая строка
- `started_at`: ISO-8601 timestamp
- `mode`: `water_impact | jet_in_air | porcelain_wall`
- `calibration.ml_per_mm`: положительное число

`samples[i]`:
- `t_s`: строго возрастающее время
- `depth_confidence`: диапазон `[0,1]`
- `roi_valid`: bool
- минимум одно из: `depth_level_mm` или `rgb_level_mm`
- optional: `audio_rms_dbfs`, `motion_norm`

## Поток данных в текущий fusion baseline

`validate-capture-contract` может экспортировать normalized JSON с полями:
- `timestamps_s`
- `depth_level_mm`
- `rgb_level_mm` (если есть)
- `depth_confidence`
- `meta` (`session_id`, `ml_per_mm`)

Этот файл напрямую используется с `analyze-level-series`.

## Примеры

- Сэмпл контракта: `examples/ios_capture_contract_sample.json`
- Генерация synthetic bench:

```bash
uroflow-mobile generate-synthetic-bench \
  --profile intermittent \
  --scenario reflective_bowl \
  --target-volume-ml 320 \
  --ml-per-mm 8.0 \
  --output-json examples/synth_reflective.json \
  --output-csv examples/synth_reflective.csv
```

- Валидация capture и экспорт уровня:

```bash
uroflow-mobile validate-capture-contract \
  examples/ios_capture_contract_sample.json \
  --output-level-json examples/ios_capture_level_payload.json
```
