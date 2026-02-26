# Mobile Uroflow Concept
[![CI](https://github.com/terdenecer-vva/uroflow-mobile-concept/actions/workflows/ci.yml/badge.svg)](https://github.com/terdenecer-vva/uroflow-mobile-concept/actions/workflows/ci.yml)
[![Mobile CI](https://github.com/terdenecer-vva/uroflow-mobile-concept/actions/workflows/mobile-ci.yml/badge.svg)](https://github.com/terdenecer-vva/uroflow-mobile-concept/actions/workflows/mobile-ci.yml)
[![Clinical Hub Contract](https://github.com/terdenecer-vva/uroflow-mobile-concept/actions/workflows/clinical-hub-contract.yml/badge.svg)](https://github.com/terdenecer-vva/uroflow-mobile-concept/actions/workflows/clinical-hub-contract.yml)

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

## Сквозной анализ iOS-capture с quality score

```bash
uroflow-mobile analyze-capture-session examples/ios_capture_contract_sample.json \
  --output-csv examples/ios_capture_session_curve.csv \
  --output-json examples/ios_capture_session_summary.json
```

Команда:
- валидирует capture payload;
- автоматически берёт `ml_per_mm` из `session.calibration` (можно переопределить через `--ml-per-mm`);
- детектирует интервал мочеиспускания (`start/end`) по audio+ROI+flow;
- строит fusion-кривую и summary;
- рассчитывает итоговый `quality score` и решение `valid/repeat/reject`.

## Clinical Hub API (app vs reference)

Запуск API для сбора парных измерений `приложение vs эталонный урофлоуметр`:

```bash
PYTHONPATH=src python -m uroflow_mobile.cli serve-clinical-hub \
  --db-path data/clinical_hub.db \
  --api-key YOUR_SHARED_PILOT_KEY \
  --host 0.0.0.0 \
  --port 8000
```

Для более безопасного multi-site пилота можно задать policy map ключей:

```bash
PYTHONPATH=src python -m uroflow_mobile.cli serve-clinical-hub \
  --db-path data/clinical_hub.db \
  --api-key-map-json config/clinical_hub_api_keys.json \
  --host 0.0.0.0 \
  --port 8000
```

Пример `config/clinical_hub_api_keys.json`:

```json
{
  "op-site-1-key": {"role": "operator", "site_id": "SITE-001", "operator_id": "OP-001"},
  "inv-site-2-key": {"role": "investigator", "site_id": "SITE-002"},
  "dm-key": {"role": "data_manager"}
}
```

Экспорт БД в CSV:

```bash
PYTHONPATH=src python -m uroflow_mobile.cli export-paired-measurements \
  --db-path data/clinical_hub.db \
  --output-csv data/paired_measurements_export.csv
```

Для проверки целостности выгрузки можно сразу записать SHA-256 manifest:

```bash
PYTHONPATH=src python -m uroflow_mobile.cli export-paired-measurements \
  --db-path data/clinical_hub.db \
  --output-csv data/paired_measurements_export.csv \
  --sha256-file data/paired_measurements_export.csv.sha256
```

Экспорт audit trail:

```bash
PYTHONPATH=src python -m uroflow_mobile.cli export-audit-events \
  --db-path data/clinical_hub.db \
  --output-csv data/audit_events_export.csv
```

Экспорт capture packages:

```bash
PYTHONPATH=src python -m uroflow_mobile.cli export-capture-packages \
  --db-path data/clinical_hub.db \
  --output-csv data/capture_packages_export.csv
```

Объединённый экспорт `paired + capture` (для анализа соответствия и покрытия capture-пакетами):

```bash
PYTHONPATH=src python -m uroflow_mobile.cli export-paired-with-capture \
  --db-path data/clinical_hub.db \
  --output-csv data/paired_with_capture_export.csv
```

Экспорт coverage summary в CSV (и опционально в PDF):

```bash
PYTHONPATH=src python -m uroflow_mobile.cli export-capture-coverage-summary \
  --db-path data/clinical_hub.db \
  --site-id SITE-001 \
  --sync-id SYNC-20260225 \
  --quality-status all \
  --output-csv data/capture_coverage_summary.csv \
  --output-pdf data/capture_coverage_summary.pdf
```

Экспорт coverage summary с оценкой pilot-гейтов:

```bash
PYTHONPATH=src python -m uroflow_mobile.cli export-capture-coverage-summary \
  --db-path data/clinical_hub.db \
  --site-id SITE-001 \
  --quality-status all \
  --output-csv data/capture_coverage_summary.csv \
  --targets-config config/coverage_targets_config.v1.json \
  --gates-output-json data/capture_coverage_gates.json \
  --fail-on-hard-gates
```

Экспорт pilot automation reports (`qa_summary`, `g1_eval`, `tfl_summary`, `drift_summary`):

```bash
PYTHONPATH=src python -m uroflow_mobile.cli export-pilot-automation-reports \
  --db-path data/clinical_hub.db \
  --output-csv data/pilot_automation_reports_export.csv
```

Сводка точности `app vs reference` (MAE/bias/RMSE/correlation/LoA):

```bash
PYTHONPATH=src python -m uroflow_mobile.cli summarize-paired-measurements \
  --db-path data/clinical_hub.db \
  --quality-status valid \
  --output-json data/method_comparison_summary.json
```

REST endpoint для дашборда пилота:

```bash
GET /api/v1/comparison-summary?site_id=SITE-001&quality_status=valid
GET /api/v1/capture-coverage-summary?site_id=SITE-001&sync_id=SYNC-20260225&quality_status=all
GET /api/v1/capture-coverage-summary.csv?site_id=SITE-001&sync_id=SYNC-20260225&quality_status=all
```

## GitHub Actions: daily coverage report

Workflow: `.github/workflows/capture-coverage-report.yml`

Data source priority:

1. `secret` `CLINICAL_HUB_URL` (API mode, preferred)
2. `secret` `CLINICAL_HUB_DB_URL` (download SQLite DB)
3. local `db_path` input on manual run

Recommended repo configuration (`gh` CLI):

```bash
gh secret set CLINICAL_HUB_URL --body "https://your-hub.example.com"
gh secret set CLINICAL_HUB_API_KEY --body "<site_or_data_manager_key>"
gh variable set CLINICAL_HUB_SITE_ID --body "SITE-001"
gh variable set CLINICAL_HUB_COVERAGE_TARGETS_CONFIG --body "config/coverage_targets_config.v1.json"
gh variable set CLINICAL_HUB_ENFORCE_COVERAGE_GATES --body "true"
```

Optional DB mode:

```bash
gh secret set CLINICAL_HUB_DB_URL --body "https://secure-storage.example.com/clinical_hub.db"
```

Capture package endpoints:

```bash
POST /api/v1/capture-packages
GET /api/v1/capture-packages
GET /api/v1/capture-packages/{id}
GET /api/v1/capture-packages.csv
GET /api/v1/paired-with-capture.csv
```

`POST /api/v1/capture-packages` идемпотентен по
`site_id + subject_id + session_id + attempt_number + package_type`:
- тот же payload → `200` с существующей записью;
- другой payload при той же identity → `409`.

Pilot automation endpoints:

```bash
POST /api/v1/pilot-automation-reports
GET /api/v1/pilot-automation-reports
GET /api/v1/pilot-automation-reports/{id}
GET /api/v1/pilot-automation-reports.csv
```

`POST /api/v1/pilot-automation-reports` идемпотентен по
`site_id + report_date + report_type + package_version + model_id + dataset_id`:
- тот же payload → `200` с существующей записью;
- другой payload при той же identity → `409`.

Автозагрузка отчётов из CI в Clinical Hub:
- workflow `pilot-automation-smoke` использует
  `scripts/post_pilot_reports_to_clinical_hub.py`;
- шаг выполняется только если заданы секреты
  `CLINICAL_HUB_URL` и `CLINICAL_HUB_API_KEY`;
- `site_id` берётся из GitHub variable `CLINICAL_HUB_SITE_ID` (fallback: `CI-SMOKE`).

Audit endpoint:

```bash
GET /api/v1/auth-context
GET /api/v1/audit-events?limit=200
```

Рекомендуемые заголовки для трассировки:
- `x-api-key` — общий ключ пилота
- `x-operator-id` — оператор/медсестра
- `x-site-id` — площадка/клиника
- `x-actor-role` — роль (`operator`, `investigator`, `data_manager`)
- `x-request-id` — уникальный ID запроса

Site scope enforcement:
- для `operator` и `investigator` доступ автоматически ограничивается `x-site-id`;
- запрос с `site_id`, не совпадающим с `x-site-id`, возвращает `403`;
- для `operator` обязательно должен быть определён actor `operator_id` (через `x-operator-id`,
  session payload или `operator_id` из policy map), иначе запрос отклоняется `403`;
- для `operator` чтение/выгрузка автоматически фильтруются по `operator_id`,
  а запись с другим `operator_id` блокируется `403`;
- `data_manager` и `admin` могут работать кросс-сайтово.

Если включён `--api-key-map-json`, роль и site scope берутся из policy map ключа
(заголовки `x-site-id`/`x-actor-role` становятся вторичными).

## Оценка release gates (G0/G1/G2)

```bash
uroflow-mobile evaluate-gates /path/to/metrics.json \
  --config-json docs/project-package-v1.5/gates-config-v1.json \
  --gates G0 G1 \
  --output-json /path/to/gate_summary.json
```

Для проверки строго по submission-ready порогам из пакета v2.8:

```bash
uroflow-mobile evaluate-gates /path/to/metrics.json \
  --config-json docs/project-package-v2.8/gates-config-v2.8.json \
  --gates G0 G1 BENCH_G0 BENCH_G1
```

Формат `metrics.json`:
- плоский объект метрик (`{"qmax_mae_ml_s": 2.1, ...}`)
- или объект вида `{"metrics": {...}}`.

Exit code:
- `0` — все выбранные gates пройдены
- `1` — хотя бы один gate не пройден

## Сборка metrics.json из clinical/bench CSV

```bash
uroflow-mobile build-gate-metrics \
  --clinical-csv examples/gates/clinical_fixture.csv \
  --bench-csv examples/gates/bench_fixture.csv \
  --output-json examples/gates/gate_metrics.json
```

Для реальных выгрузок EDC можно подключить профиль маппинга:

```bash
uroflow-mobile generate-gate-profile-template \
  --clinical-csv /path/to/clinic_export.csv \
  --bench-csv /path/to/bench_export.csv \
  --profile-name clinic_export_v1 \
  --output-yaml /path/to/clinic_profile.yaml

uroflow-mobile build-gate-metrics \
  --clinical-csv /path/to/redcap_export.csv \
  --profile-yaml /path/to/clinic_profile.yaml \
  --profile-name clinic_export_v1 \
  --overrides-json /path/to/manual_metrics.json \
  --output-json /path/to/gate_metrics.json
```

Валидация профиля стала строже: `column_map` должен быть однозначным.
Если два source-столбца маппятся в один и тот же target, команда завершится с ошибкой,
чтобы исключить тихие конфликты в метриках.

Backfill недостающих метрик напрямую из pilot-automation артефактов:

```bash
uroflow-mobile build-gate-metrics \
  --tfl-summary-json /path/to/tfl_summary.json \
  --drift-summary-json /path/to/drift_summary.json \
  --g1-eval-json /path/to/g1_eval.json \
  --qa-summary-json /path/to/qa_summary.json \
  --output-json /path/to/gate_metrics.json
```

После этого можно запустить gate-check:

```bash
uroflow-mobile evaluate-gates examples/gates/gate_metrics.json \
  --config-json docs/project-package-v2.8/gates-config-v2.8.json \
  --gates G0 BENCH_G0
```

## Mobile app (iPhone + Android)

Кроссплатформенный клиент для полевого ввода парных измерений:

```bash
cd apps/field-mobile
npm install
npm run start
```

В мобильном клиенте есть встроенный раздел `Comparison Summary`, который подтягивает
`/api/v1/comparison-summary` и показывает текущую сходимость с эталонным урофлоуметром.
Также реализована offline-очередь отправки и ручная синхронизация pending-записей.

## Интеграция Project Package v2.8

Новые данные из `Uroflow_Project_Package_v2.8.zip` интегрированы в двух контурах:

- инвентаризация и аналитическая выжимка пакета в `docs/project-package-v2.8/`;
- импорт исполняемых pilot-скриптов в `scripts/pilot_automation_v2_8/`.

Извлечение и инвентаризация:

```bash
.venv/bin/python scripts/extract_project_package_v2_8.py \
  --zip-path "/Users/denecer/Yandex.Disk.localized/Научные материалы/Патентные заявки/Урофлоуметр/Uroflow_Project_Package_v2.8.zip" \
  --output-dir docs/project-package-v2.8 \
  --automation-out scripts/pilot_automation_v2_8
```

Краткий smoke для pilot automation:

```bash
.venv/bin/python scripts/pilot_automation_v2_8/scripts/validate_artifacts_by_profile.py \
  --dataset_root /path/to/sample_dataset_v1.1 \
  --manifest /path/to/sample_dataset_v1.1/manifest.csv \
  --profile P0 \
  --config scripts/pilot_automation_v2_8/config/data_artifact_profile_config.json \
  --out_dir docs/project-package-v2.8/automation_smoke/artifact_profile

.venv/bin/python scripts/pilot_automation_v2_8/scripts/run_daily_qa.py \
  --dataset_root /path/to/sample_dataset_v1.1 \
  --manifest /path/to/sample_dataset_v1.1/manifest.csv \
  --out docs/project-package-v2.8/automation_smoke \
  --write_checksums
```

Для профильно-ориентированных наборов в манифест добавлено поле `profile_id` (`P0..P3`).
Если использовать `--use_manifest_profile`, пустое/отсутствующее `profile_id` падает на `default_profile` из
`scripts/pilot_automation_v2_8/config/data_artifact_profile_config.json`.

Примечание: `scripts/pilot_automation_v2_8/scripts/` импортирован как внешний vendor-пакет,
поэтому исключён из `ruff`-проверок проекта. Пакет `v2.5` сохранён в репозитории для ретроспективной сверки.

## Структура

- `docs/` — архитектура, ограничения, roadmap
- `docs/project-package-v2.8/` — инвентаризация/анализ submission-ready пакета v2.8
- `docs/project-package-v2.8/v2.8-recommendations-integration-plan.md` — план интеграции рекомендаций v2.8
- `docs/project-package-v2.5/` — инвентаризация/анализ нового submission-ready пакета v2.5
- `docs/project-package-v2.5/v2.5-recommendations-integration-plan.md` — план интеграции рекомендаций v2.5
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
- `docs/bench-package-v0.2/` — bench BOM/SOP package (variants, wiring, mechanics, acceptance)
- `docs/ml-pipeline-package-v1.0/` — ML training pipeline package (gates, checklist, data contract)
- `docs/bench-ml-additional-data-analysis-v0.2.md` — сводный анализ дополнительных bench/ML материалов
- `docs/project-package-v1.5/gate-mapping-profiles-v1.yaml` — YAML-профили маппинга колонок для REDCap/OpenClinica экспортов
- `docs/real-mobile-pilot-mvp.md` — практический запуск реального pilot-контура (iPhone/Android + Clinical Hub)
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
- `scripts/extract_bench_bom_v0_2.py` — генератор CSV-пакета bench BOM из XLSX
- `scripts/extract_project_package_v2_8.py` — извлечение и инвентаризация ZIP `Uroflow_Project_Package_v2.8`
- `scripts/pilot_automation_v2_8/` — импортированный automation toolkit v2.8 (QA/TFL/Drift/G1/G2/supporting utilities)
- `scripts/extract_project_package_v2_5.py` — извлечение и инвентаризация ZIP `Uroflow_Project_Package_v2.5`
- `scripts/pilot_automation_v2_5/` — импортированный automation toolkit (QA/TFL/Drift/G1 evidence)
- `apps/field-mobile/` — Expo React Native приложение для iPhone/Android (полевой сбор paired data)

## Важно

Проект предназначен для R&D и не является медицинским изделием. Для клинического применения потребуются валидация, сертификация и соответствие требованиям законодательства.
