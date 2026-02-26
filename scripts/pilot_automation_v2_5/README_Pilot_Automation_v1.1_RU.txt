Uroflow Pilot Automation Pack v1.1 (OFFLINE)
Дата: 2026-02-24

Что нового (v1.1)
1) Генерация TFL/CSR-выходов по "золотому" датасету (golden dataset):
   - Bland–Altman (bias, SD, 95% LoA)
   - MAE / MAPE
   - Листинг по каждой записи
   - Выход: заполненный Excel-шаблон CSR TFL (05_Clinical/Uroflow_CSR_TFL_Workbook_v1.0.xlsx)
   - Опционально: BA-графики (PNG) + краткий PDF-отчет

2) Drift dashboard:
   - Стратифицированная оценка точности по site_id / toilet_id / iphone_model / noise_level / posture / sex
   - Флаги "дрейфа" (ухудшение относительно общего baseline)

3) G1 evidence bundle builder:
   - Запуск TFL + drift
   - Проверка критериев приемки (config-driven)
   - Формирование G1 evidence summary (XLSX)
   - Автозаполнение Pilot-freeze V&V report (DOCX, executed)

Запуск (one-click)
- run_tfl_oneclick.sh / .bat
- run_drift_dashboard_oneclick.sh / .bat
- run_g1_evidence_oneclick.sh / .bat

Примечания
- Скрипты рассчитаны на офлайн-исполнение.
- Для РФ: хранение/обработка "золотого" датасета организуется на локальной инфраструктуре или в допустимом контуре данных.


Пример (синтетический датасет для теста)
- sample/sample_dataset_v1.1/
  - manifest.csv
  - records/Rxxxxxx/Q_ref.csv + Q_pred.csv + app_result.json
Запуск:
  ./run_tfl_oneclick.sh sample/sample_dataset_v1.1 sample/sample_dataset_v1.1/manifest.csv
  ./run_g1_evidence_oneclick.sh sample/sample_dataset_v1.1 sample/sample_dataset_v1.1/manifest.csv <PATH_TO_Submission_Build_v2.5>
