Uroflow Pilot Automation Pack v1.0 (offline)

Purpose
-------
One-click tools for daily QA of the synchronous "golden" dataset
(iPhone audio/video/depth + reference uroflowmeter) and for generating Freeze Bundles (dataset_id/model_id/QS).

Automated checks
----------------
1) Schema validation (manifest CSV/XLSX): required columns, required fields, code-lists.
2) Record integrity: required files (meta.json, Q_ref.csv), parseability, basic sanity checks.
3) Q_ref integral consistency: V_int = ∫Q_ref(t) dt vs Vvoid_ref_ml (if provided), PASS if abs(delta) <= max(10 ml, 5%).
4) Sync check (audio ↔ Q_ref onset/proxy): audio onset detection + audio proxy flow correlation with Q_ref.
5) Checksums: SHA256 for all record files, checksums.sha256.

Outputs
-------
- outputs/<YYYY-MM-DD>/qa_record_level.csv
- outputs/<YYYY-MM-DD>/qa_summary.json
- outputs/<YYYY-MM-DD>/daily_qa_report.xlsx
- outputs/<YYYY-MM-DD>/daily_qa_report.pdf
- checksums.sha256 (dataset root or outputs)

Run (one-click)
---------------
    python scripts/run_daily_qa.py --dataset_root <PATH> --manifest <MANIFEST.csv|.xlsx> --out outputs

Freeze bundle
-------------
    python scripts/freeze_bundle_generator.py --dataset_root <PATH> --manifest <MANIFEST> \
        --freeze_config config/freeze_config_template.json --out outputs

Audio note
----------
Prefer audio.wav (48 kHz mono). If you only store audio.m4a, install ffmpeg; scripts will convert to a temp wav.

Limitations
-----------
No deep video ROI analysis (file presence/valid header only). Video ROI analytics can be added later (opencv), increasing deps.
