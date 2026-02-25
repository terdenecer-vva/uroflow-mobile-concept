Pilot Automation README v1.9 (v3.9 patch)
----------------------------------------

New in v3.9:
1) iOS Capture Contract validation (meta.json schema check)
   - scripts/validate_ios_capture_contract.py
   - run_ios_capture_contract_validation_oneclick.(sh|bat)
   Output: outputs/ios_capture_contract/

2) Privacy LIVE vs Content consistency report
   - scripts/validate_privacy_guardrails_consistency.py
   - run_privacy_guardrails_consistency_oneclick.(sh|bat)
   Output: outputs/privacy_consistency/

3) Record-level gates (include/exclude decision)
   - scripts/compute_record_level_gates.py
   - config/record_level_gates_config.json
   - run_record_level_gates_oneclick.(sh|bat)
   Output: outputs/record_level_gates/

4) DatasetRelease builder upgraded (GUARDED + record-level filtering)
   - scripts/build_dataset_release_bundle_guarded.py  (updated)
   - run_dataset_release_guarded_oneclick.(sh|bat)   (same entrypoint)
   Output: outputs/dataset_release/ and outputs/freeze_events/

Still included:
- validate_privacy_live_guardrails.py  (LIVE on-device metadata validator)
- validate_privacy_content_guardrails_v2.py (ROI video content guardrails, offline)
- run_stand_pose_drift_dashboard.py   (StandPose drift dashboard)
- run_pre_freeze_gates.py            (dataset-level gates)

Typical pilot sequence (daily / per batch)
-----------------------------------------
A) Basic validations (lightweight)
1) run_privacy_live_guardrails_oneclick.(sh|bat)
2) run_ios_capture_contract_validation_oneclick.(sh|bat)
3) run_privacy_guardrails_consistency_oneclick.(sh|bat)

B) Optional / as-needed
4) run_privacy_content_guardrails_v2_oneclick.(sh|bat)  (if ROI video stored)
5) run_stand_pose_drift_dashboard_oneclick.(sh|bat)

C) Pre-freeze decision
6) run_pre_freeze_gates_oneclick.(sh|bat)

Before dataset_id freeze
-----------------------
- Ensure Pre-Freeze Gates OVERALL=PASS
- Ensure record-level gates include enough valid records
- Then run_dataset_release_guarded_oneclick.(sh|bat)

Notes
-----
- DatasetRelease builder in v3.9 will auto-run lightweight validators if their outputs are missing.
- It will NOT auto-run heavy ROI video processing; run content guardrails explicitly if ROI video is stored and required.
