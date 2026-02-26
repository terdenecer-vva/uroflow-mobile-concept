Pilot Automation README v1.8 (v3.8 patch)
----------------------------------------

New in this patch:
1) LIVE on-device privacy guardrails validator:
   - scripts/validate_privacy_live_guardrails.py
   - run_privacy_live_guardrails_oneclick.(sh|bat)
   Output: outputs/privacy_live_guardrails/

2) Pre-freeze gates UPDATED:
   - scripts/run_pre_freeze_gates.py
   - config/pre_freeze_gates_config.json now includes required gate PRIV_LIVE
   Output: outputs/pre_freeze_gates/

3) Guarded DatasetRelease builder (blocks unless gates pass) + DHF freeze logging:
   - scripts/build_dataset_release_bundle_guarded.py
   - scripts/log_freeze_event_to_dhf.py
   - run_dataset_release_guarded_oneclick.(sh|bat)
   Output: outputs/dataset_release/ and outputs/freeze_events/

Still included from v3.7:
- Content-level privacy guardrails v2 (ROI video): validate_privacy_content_guardrails_v2.py
- StandPose drift dashboard: run_stand_pose_drift_dashboard.py

Typical pilot sequence (daily)
------------------------------
1) run_privacy_live_guardrails_oneclick.(sh|bat)
2) run_privacy_content_guardrails_v2_oneclick.(sh|bat)  (if ROI video stored)
3) run_stand_pose_drift_dashboard_oneclick.(sh|bat)
4) run_pre_freeze_gates_oneclick.(sh|bat)

Before dataset_id freeze
-----------------------
- Ensure Pre-Freeze Gates OVERALL=PASS
- Then run_dataset_release_guarded_oneclick.(sh|bat)

