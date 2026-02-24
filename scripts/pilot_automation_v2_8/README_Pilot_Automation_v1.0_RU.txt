Uroflow Pilot Automation Pack v1.0 (offline)

Назначение
----------
Пакет содержит "в один клик" инструменты для ежедневного QA синхронного "золотого" датасета
(iPhone audio/video/depth + эталонный урофлоуметр) и для генерации Freeze Bundle (dataset_id/model_id/QS).

Ключевые проверки (автоматические)
----------------------------------
1) Schema validation:
   - проверка наличия обязательных колонок manifest (CSV/XLSX),
   - проверка обязательных полей (non-empty),
   - проверка code-lists (sex/posture/noise_level/lighting и т.п.) и допустимых значений.

2) Record integrity:
   - наличие meta.json, Q_ref.csv (и ref_params.json если требуется протоколом),
   - корректность JSON/CSV (парсится),
   - базовые sanity-checks по Q_ref(t): t монотонно возрастает, Q>=0.

3) Q_ref integral consistency (QA-003):
   - V_int = ∫Q_ref(t) dt,
   - сравнение с Vvoid_ref_ml из manifest (если заполнено),
   - PASS если abs(delta) <= max(10 мл, 5%).

4) Sync check (audio ↔ Q_ref onset/proxy):
   - детекция onset в audio (wav; если m4a — используем ffmpeg при наличии),
   - построение proxy_Q_audio(t) по энергии/спектральной "шумности" после onset,
   - корреляция proxy_Q_audio(t) с Q_ref(t) (после выравнивания по onset),
   - флаг "review" если corr < порога или onset вне допустимого диапазона.

5) Checksums:
   - SHA256 по всем файлам записей,
   - формирование checksums.sha256 (для freeze bundle и контроля целостности).

Выходные артефакты
------------------
- outputs/<YYYY-MM-DD>/qa_record_level.csv
- outputs/<YYYY-MM-DD>/qa_summary.json
- outputs/<YYYY-MM-DD>/daily_qa_report.xlsx
- outputs/<YYYY-MM-DD>/daily_qa_report.pdf
- checksums.sha256 (в корне dataset_root или в outputs)

Как запустить (one-click)
-------------------------
1) Подготовьте Python 3.10+ и зависимости (см. requirements_full.txt).
2) Укажите dataset_root и путь к manifest (CSV или XLSX).
3) Выполните:

    python scripts/run_daily_qa.py --dataset_root <PATH> --manifest <PATH_TO_MANIFEST> --out outputs

Freeze bundle
-------------
    python scripts/freeze_bundle_generator.py --dataset_root <PATH> --manifest <PATH_TO_MANIFEST> \
        --freeze_config config/freeze_config_template.json --out outputs

Примечание по аудио
-------------------
Для sync-check желательно хранить audio.wav (48 kHz mono).
Если храните audio.m4a, установите ffmpeg и скрипт конвертирует временный wav автоматически.

Ограничения
-----------
- Скрипты не выполняют OCR/vision-анализ видео; видео проверяется только на наличие/целостность файла.
- Для детального анализа видео-ROI можно добавить отдельный модуль позже (opencv), но это увеличит зависимости.
