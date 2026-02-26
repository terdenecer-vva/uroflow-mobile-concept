Uroflow Pilot Automation Pack v1.2 (OFFLINE)
Date: 2026-02-24

What's new (v1.2)
1) CSR DOCX auto-draft (T/F/L numbering + auto-insertion)
   - Script: scripts/generate_csr_autodraft.py
   - Templates:
       * ../05_Clinical/Uroflow_CSR_Template_v1.1_AUTOFILL.docx (EN)
       * ../05_Clinical/Uroflow_CSR_Template_v1.1_AUTOFILL_RU.docx (RU)
   - Output: outputs/csr_autodraft/Uroflow_CSR_Autodraft_<LANG>_tfl.docx

2) One-click CSR build workflow
   - Runner: run_csr_autodraft_oneclick.sh / .bat
   - Steps:
       a) Run TFL generator with BA plots (outputs/tfl/)
       b) Generate CSR auto-draft (EN + RU)

3) G2 Submission Bundle Builder (EU MDR + US FDA)
   - Script: scripts/build_g2_submission_bundle.py
   - Runner: run_g2_bundle_oneclick.sh / .bat
   - Reads:
       * EU MDR index: 06_EU_MDR/Annex_II_III_Submission_Folder/EU_MDR_AnnexII_III_Submission_Folder_Index_*.xlsx
       * FDA index:    07_US_FDA/FDA_Submission_Folder/FDA_Submission_Folder_Index_*.xlsx
   - Output:
       * outputs/g2_bundle/G2_Submission_Bundle_<timestamp>/ (copied files)
       * outputs/g2_bundle/G2_Bundle_Reports_<timestamp>/g2_bundle_summary.json
       * EXECUTED indexes with Present/SHA256/Bundle path
       * MISSING items reports

4) Data artifact profile validator (v3.4 integration)
   - Script: scripts/validate_artifacts_by_profile.py
   - Config: config/data_artifact_profile_config.json
   - Runner: run_validate_artifacts_by_profile_oneclick.sh / .bat
   - Supports:
       * fixed profile: --profile P0|P1|P2|P3
       * per-record profile: --use_manifest_profile (reads profile_id; falls back to config.default_profile)
   - Output:
       * outputs/validate_artifacts/artifact_profile_validation.json
       * outputs/validate_artifacts/artifact_profile_validation.csv

Core workflow (recommended)
A) Daily QA:
   run_daily_qa_oneclick.sh <DATASET_ROOT> <MANIFEST_PATH>

A2) Artifact profile gate:
   run_validate_artifacts_by_profile_oneclick.sh <DATASET_ROOT> <MANIFEST_PATH> [P0|P1|P2|P3]

B) TFL + plots:
   run_tfl_oneclick.sh <DATASET_ROOT> <MANIFEST_PATH>

C) CSR auto-draft:
   run_csr_autodraft_oneclick.sh <DATASET_ROOT> <MANIFEST_PATH>

D) G2 bundle (from submission build):
   run_g2_bundle_oneclick.sh ../..   (if running from 10_Pilot_Automation/)

Notes
- Everything is offline by design (important for Russia / on-prem).
- For clinical datasets, do not store raw video/audio unless explicitly approved (privacy-by-default).
