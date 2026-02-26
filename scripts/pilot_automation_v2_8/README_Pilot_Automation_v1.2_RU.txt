Uroflow Pilot Automation Pack v1.2 (OFFLINE)
Дата: 2026-02-24

Что нового (v1.2)
1) Автогенерация CSR DOCX (нумерация T/F/L + автоматическая подстановка)
   - Скрипт: scripts/generate_csr_autodraft.py
   - Шаблоны:
       * ../05_Clinical/Uroflow_CSR_Template_v1.1_AUTOFILL.docx (EN)
       * ../05_Clinical/Uroflow_CSR_Template_v1.1_AUTOFILL_RU.docx (RU)
   - Выход: outputs/csr_autodraft/Uroflow_CSR_Autodraft_<LANG>_tfl.docx

2) One-click сценарий сборки CSR
   - Запуск: run_csr_autodraft_oneclick.sh / .bat
   - Шаги:
       a) расчёт TFL + построение BA графиков (outputs/tfl/)
       b) формирование CSR auto-draft (EN + RU)

3) Сборщик пакета доказательств G2 (EU MDR + US FDA)
   - Скрипт: scripts/build_g2_submission_bundle.py
   - Запуск: run_g2_bundle_oneclick.sh / .bat
   - Берёт индексы:
       * EU MDR: 06_EU_MDR/Annex_II_III_Submission_Folder/EU_MDR_AnnexII_III_Submission_Folder_Index_*.xlsx
       * FDA:    07_US_FDA/FDA_Submission_Folder/FDA_Submission_Folder_Index_*.xlsx
   - Формирует:
       * outputs/g2_bundle/G2_Submission_Bundle_<timestamp>/ (копии файлов)
       * outputs/g2_bundle/G2_Bundle_Reports_<timestamp>/g2_bundle_summary.json
       * EXECUTED индексы (Present/SHA256/Bundle path)
       * отчёт по отсутствующим файлам (MISSING)

4) Валидатор профилей data artifacts (интеграция v3.4)
   - Скрипт: scripts/validate_artifacts_by_profile.py
   - Конфиг: config/data_artifact_profile_config.json
   - Запуск: run_validate_artifacts_by_profile_oneclick.sh / .bat
   - Режимы:
       * фиксированный профиль: --profile P0|P1|P2|P3
       * профиль из манифеста: --use_manifest_profile (берёт profile_id, при пустом значении использует config.default_profile)
   - Выход:
       * outputs/validate_artifacts/artifact_profile_validation.json
       * outputs/validate_artifacts/artifact_profile_validation.csv

Рекомендуемый цикл работы
A) Ежедневный QA:
   run_daily_qa_oneclick.sh <DATASET_ROOT> <MANIFEST_PATH>

A2) Гейт профиля артефактов:
   run_validate_artifacts_by_profile_oneclick.sh <DATASET_ROOT> <MANIFEST_PATH> [P0|P1|P2|P3]

B) TFL + графики:
   run_tfl_oneclick.sh <DATASET_ROOT> <MANIFEST_PATH>

C) CSR auto-draft:
   run_csr_autodraft_oneclick.sh <DATASET_ROOT> <MANIFEST_PATH>

D) G2 bundle (из корня submission build):
   run_g2_bundle_oneclick.sh ../..   (если запуск из 10_Pilot_Automation/)

Примечания
- Пакет рассчитан на полностью офлайн-режим (важно для РФ / on-prem).
- Для клинических данных: сырые видео/аудио не хранить без явного одобрения (privacy-by-default).
