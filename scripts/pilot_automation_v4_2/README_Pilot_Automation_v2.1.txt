Pilot Automation README v2.1 (Submission_Build_v4.2)
---------------------------------------------------

Goal
----
Provide repeatable, auditable automation to:
- validate per-record privacy + capture contract + sync readiness,
- compute dataset-level readiness gates (pre-freeze),
- enforce record-level inclusion rules for DatasetRelease,
- generate the mandatory Pilot Freeze Kit (dataset_id + lock records + evidence hashes),
- and support multi-site execution (coverage dashboard + weekly ops report).

New in v4.2
-----------
1) Mandatory Pilot Freeze Kit (executed artifact)
   - scripts/build_pilot_freeze_kit.py
   - 15_Dataset_Model_Release/Uroflow_Pilot_Freeze_Kit_Template_v1.0.xlsx
   - 15_Dataset_Model_Release/Uroflow_Pilot_Freeze_Kit_Spec_v1.0_(EN|RU).docx
   Output (under Submission Build):
     15_Dataset_Model_Release/Freeze_Kits/FreezeKit_<dataset_id>_<timestampUTC>.xlsx
     15_Dataset_Model_Release/Freeze_Kits/FreezeKit_<dataset_id>_<timestampUTC>.json

   One-click:
     run_freeze_kit_oneclick.(sh|bat) <DATASET_ROOT> [DATASET_ID] [OPERATOR_ID]

2) DatasetRelease builder now auto-detects lock ids and auto-generates Freeze Kit
   - scripts/build_dataset_release_bundle_guarded.py (patched to v4.2)
   Behavior:
     - If --claims_lock_id / --acceptance_lock_id are not provided, they are derived from the latest lock DOCX in 01_Product_QMS/.
     - After DatasetRelease ZIP is created, Freeze Kit is generated automatically (best-effort).
     - Freeze Kit is appended to DHF_Freeze_Event_Log.xlsx as event_type=FreezeKit.

3) Ethics/IRB submission pack builder (region ZIP from index)
   - scripts/build_ethics_submission_pack.py
   - 19_Ethics_Submission_Packs/Ethics_Submission_Pack_Index_v1.0.xlsx
   One-click:
     run_build_ethics_submission_pack_oneclick.(sh|bat) <RU_EC|EU_Ethics|US_IRB>

Typical pilot workflow (daily / per batch)
-----------------------------------------
A) Lightweight validators
1) run_privacy_live_guardrails_oneclick.(sh|bat)
2) run_ios_capture_contract_validation_oneclick.(sh|bat)
3) run_privacy_guardrails_consistency_oneclick.(sh|bat)
4) run_sync_validation_oneclick.(sh|bat)
5) run_daily_qa_oneclick.(sh|bat)
6) run_record_level_gates_oneclick.(sh|bat)

B) As-needed (site checks)
7) run_stand_pose_drift_dashboard_oneclick.(sh|bat)
8) run_privacy_content_guardrails_v2_oneclick.(sh|bat)   (if ROI video stored)

C) Multi-site management
9) run_coverage_dashboard_oneclick.(sh|bat)
10) run_multisite_weekly_report_oneclick.(sh|bat)

D) Freeze decision, DatasetRelease, and Freeze Kit
11) run_pre_freeze_gates_oneclick.(sh|bat)
12) run_dataset_release_guarded_oneclick.(sh|bat)
    -> automatically generates Freeze Kit under 15_Dataset_Model_Release/Freeze_Kits/

Notes
-----
- Ethics pack builder is optional; many sites require their own cover pages/portal exports.
- Freeze Kit is considered mandatory for any dataset_id used as evidence (clinical analysis or regulatory).
