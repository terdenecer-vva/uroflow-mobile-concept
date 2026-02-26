Uroflow Smartphone Uroflowmetry – Submission Build v2.5
Date: 2026-02-24

What's new in v2.5 (vs v2.4)
- Pilot Automation v1.1 (folder 10_Pilot_Automation/)
  1) Auto-generate CSR-style TFL outputs from the GOLDEN dataset:
     - Bland–Altman (bias, SD, 95% LoA)
     - MAE / MAPE
     - Record-level listings
     - Output as:
       - Filled CSR TFL Excel workbook (based on 05_Clinical/Uroflow_CSR_TFL_Workbook_v1.0.xlsx)
       - Optional BA plots (PNG) + summary PDF report
  2) Drift dashboard:
     - Stratified performance by site_id / toilet_id / iphone_model / noise_level / posture / sex
     - Flags "performance drift" vs overall baseline
  3) G1 evidence bundle builder:
     - Runs golden-dataset metrics + drift dashboard
     - Evaluates acceptance thresholds (config-driven)
     - Produces a G1 evidence summary workbook + auto-filled Pilot-freeze V&V report (executed)

Purpose
- Provide a submission-ready folder build (structured) for a smartphone-based uroflowmetry SaMD (iPhone: audio + RGB video + optional LiDAR/ARKit).
- Focus on "launch-ready" execution artefacts (not only templates), including:
  - Golden synchronous dataset acquisition (iPhone + reference uroflowmeter)
  - Daily QA of the golden dataset + issue logging
  - Controlled freeze procedure for dataset_id / model_id / QS thresholds
  - Pilot execution runbook (site operations)
  - Pilot-freeze V&V report shell tied to Evidence IDs
  - NEW: automated G1 performance evidence generation

How to use
1) Start with 00_README_and_Indexes/Uroflow_Master_Submission_Index_v2.5.xlsx
2) Pilot Automation:
   - See folder 10_Pilot_Automation/
   - One-click scripts:
     - run_daily_qa_oneclick.sh / .bat
     - run_tfl_oneclick.sh / .bat
     - run_drift_dashboard_oneclick.sh / .bat
     - run_g1_evidence_oneclick.sh / .bat
3) Golden dataset:
   - See folder 03_Data_Golden_Dataset/ for acquisition SOP + schema + coverage targets and tracker
4) Clinical pilot:
   - See folder 05_Clinical/ for protocol + ICF + site startup + runbook + logs
5) Controlled freezes:
   - See folder 01_Product_QMS/ for freeze procedure and executed baseline logs

Notes
- The automation scripts are designed to run OFFLINE.
- For Russian deployments, keep golden dataset storage/processing within the permitted data residency constraints and/or on secure local infrastructure.

