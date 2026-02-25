Submission Build v4.2 - Release Notes (Uroflow Smartphone Uroflowmetry)
======================================================================

Focus of v4.2
-------------
Make the project "real pilot launch-ready" by adding:
1) A mandatory Pilot Freeze Kit (dataset_id + lock records + evidence hashes),
2) A practical Ethics/IRB submission pack index and templates for RU/EU/US,
3) Automation updates so DatasetRelease creation produces traceable artifacts by default.

New / Updated Items
-------------------
A) Mandatory Pilot Freeze Kit
- 15_Dataset_Model_Release/Uroflow_Pilot_Freeze_Kit_Spec_v1.0_(EN|RU).docx
- 15_Dataset_Model_Release/Uroflow_Pilot_Freeze_Kit_Template_v1.0.xlsx
- 15_Dataset_Model_Release/Freeze_Kits/   (output folder; generated during freeze)

Automation:
- 10_Pilot_Automation/scripts/build_pilot_freeze_kit.py
- 10_Pilot_Automation/run_freeze_kit_oneclick.(sh|bat)

B) DatasetRelease builder patched (v4.2)
- 10_Pilot_Automation/scripts/build_dataset_release_bundle_guarded.py
Changes:
- Auto-detects lock ids from the latest lock DOCX in 01_Product_QMS/ if not provided.
- Auto-generates Freeze Kit after DatasetRelease ZIP is created (best-effort).
- Writes lock file path + SHA256 into dataset_release_manifest.json.

C) Ethics/IRB submission pack (RU/EU/US)
- 19_Ethics_Submission_Packs/Ethics_Submission_Pack_Index_v1.0.xlsx
- 19_Ethics_Submission_Packs/Uroflow_Ethics_Submission_Pack_Guide_v1.0_(EN|RU).docx
- 05_Clinical/*  (templates: cover letter, synopsis, consent, recruitment, privacy addendum, SOP, DMP summary, risk summary)

Automation (optional):
- 10_Pilot_Automation/scripts/build_ethics_submission_pack.py
- 10_Pilot_Automation/run_build_ethics_submission_pack_oneclick.(sh|bat)

Key One-Click Commands
----------------------
1) Pre-freeze readiness gates:
   10_Pilot_Automation/run_pre_freeze_gates_oneclick.(sh|bat) <DATASET_ROOT> <MANIFEST.csv|xlsx>

2) DatasetRelease + Freeze Kit (Freeze Kit is auto-generated):
   10_Pilot_Automation/run_dataset_release_guarded_oneclick.(sh|bat) <DATASET_ROOT> <MANIFEST.csv|xlsx> [DATASET_ID] [OPERATOR_ID]

3) Freeze Kit only (if needed):
   10_Pilot_Automation/run_freeze_kit_oneclick.(sh|bat) <DATASET_ROOT> [DATASET_ID] [OPERATOR_ID]

4) Build Ethics/IRB submission pack ZIP from index:
   10_Pilot_Automation/run_build_ethics_submission_pack_oneclick.(sh|bat) <RU_EC|EU_Ethics|US_IRB>

Notes
-----
- Ethics pack templates MUST be adapted to local site requirements (logos, PI details, translations).
- Claims/Intended Use must remain within Claim Set A (see 01_Product_QMS Claims Lock) to avoid raising the regulatory class.
- Freeze Kit is considered mandatory for any dataset_id intended for clinical analysis or regulatory evidence.

