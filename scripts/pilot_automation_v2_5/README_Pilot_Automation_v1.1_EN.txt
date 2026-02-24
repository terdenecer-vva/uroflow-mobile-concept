Uroflow Pilot Automation Pack v1.1 (OFFLINE)
Date: 2026-02-24

What's new (v1.1)
1) Golden dataset → CSR-style TFL outputs:
   - Bland–Altman (bias, SD, 95% LoA)
   - MAE / MAPE
   - Record-level listings
   - Output: filled CSR TFL Excel template (05_Clinical/Uroflow_CSR_TFL_Workbook_v1.0.xlsx)
   - Optional: BA plots (PNG) + short PDF summary report

2) Drift dashboard:
   - Stratified performance by site_id / toilet_id / iphone_model / noise_level / posture / sex
   - Drift flags vs overall baseline

3) G1 evidence bundle builder:
   - Runs TFL + drift
   - Evaluates acceptance criteria (config-driven)
   - Produces G1 evidence summary workbook (XLSX)
   - Auto-fills Pilot-freeze V&V report (DOCX, executed)

One-click runners
- run_tfl_oneclick.sh / .bat
- run_drift_dashboard_oneclick.sh / .bat
- run_g1_evidence_oneclick.sh / .bat

Notes
- Scripts are designed to run OFFLINE.


Example (synthetic dataset for testing)
- sample/sample_dataset_v1.1/
  - manifest.csv
  - records/Rxxxxxx/Q_ref.csv + Q_pred.csv + app_result.json
Run:
  ./run_tfl_oneclick.sh sample/sample_dataset_v1.1 sample/sample_dataset_v1.1/manifest.csv
  ./run_g1_evidence_oneclick.sh sample/sample_dataset_v1.1 sample/sample_dataset_v1.1/manifest.csv <PATH_TO_Submission_Build_v2.5>
