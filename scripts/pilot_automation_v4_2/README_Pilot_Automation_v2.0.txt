Pilot Automation README v2.0 (Submission_Build_v4.0)
---------------------------------------------------

Goal
----
Provide repeatable, auditable automation to:
- validate per-record privacy + capture contract + sync readiness,
- compute dataset-level readiness gates (pre-freeze),
- enforce record-level inclusion rules for DatasetRelease,
- and support multi-site execution (coverage dashboard + weekly ops report).

New in v4.0
-----------
1) Coverage dashboard (multi-site recruitment + strata monitoring)
   - scripts/run_coverage_dashboard.py
   - config/coverage_targets_config.json
   - run_coverage_dashboard_oneclick.(sh|bat)
   Output: outputs/coverage_dashboard/

2) Pre-freeze gates now include COVERAGE
   - scripts/run_pre_freeze_gates.py (patched)
   - config/pre_freeze_gates_config.json (COVERAGE added to required_gates)

3) Minimal sync validation and minimal daily QA (to satisfy SYNC and DAILY_QA gates)
   - scripts/run_sync_validation_minimal.py
   - run_sync_validation_oneclick.(sh|bat)
   Output: outputs/sync_validation/

   - scripts/run_daily_qa_minimal.py
   - run_daily_qa_oneclick.(sh|bat)
   Output: outputs/daily_qa/

4) Multi-site weekly operational report (Excel + JSON)
   - scripts/generate_multisite_weekly_report.py
   - run_multisite_weekly_report_oneclick.(sh|bat)
   Output: outputs/multisite_weekly_report/

Still included (from v3.9)
-------------------------
- validate_privacy_live_guardrails.py
- validate_ios_capture_contract.py
- validate_privacy_guardrails_consistency.py
- compute_record_level_gates.py
- validate_privacy_content_guardrails_v2.py (ROI video offline checks)
- run_stand_pose_drift_dashboard.py
- run_pre_freeze_gates.py
- build_dataset_release_bundle_guarded.py

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

D) Freeze decision and DatasetRelease
11) run_pre_freeze_gates_oneclick.(sh|bat)   (includes SYNC, DAILY_QA, COVERAGE)
12) run_dataset_release_guarded_oneclick.(sh|bat)

Notes
-----
- Coverage targets are defined in config/coverage_targets_config.json and are expected to be tuned per phase (pilot vs clinical).
- If the manifest does not include required coverage columns, COVERAGE will FAIL (as intended) until the manifest template is fixed.
- DatasetRelease builder is guarded: it will not create dataset_id if pre-freeze fails or if too few valid records exist.
