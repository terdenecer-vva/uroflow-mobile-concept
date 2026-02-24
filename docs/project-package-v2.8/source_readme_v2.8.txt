Uroflow Smartphone Uroflowmetry – Submission Build v2.8
Date: 2026-02-24

What’s new in v2.8 (vs v2.7)
1) EU MDR GSPR evidence-link auto-execution (Evidence_ID -> file paths -> SHA256):
   - New automation extends the executed GSPR with *evidence bundle* traceability.
   - Output (generated in this build):
     06_EU_MDR/Uroflow_EU_MDR_GSPR_Checklist_AnnexI_v1.3_EXECUTED_EVIDENCE_AUTO.xlsx
   - Also copied into Annex II/III folder:
     06_EU_MDR/Annex_II_III_Submission_Folder/4_GSPR/Uroflow_EU_MDR_GSPR_Checklist_AnnexI_v1.3_EXECUTED_EVIDENCE_AUTO.xlsx

2) EU Annex II/III index updated to reference the evidence-linked executed GSPR:
   - New index:
     06_EU_MDR/Annex_II_III_Submission_Folder/EU_MDR_AnnexII_III_Submission_Folder_Index_v2.4.xlsx
   - G2 bundle builder default updated to v2.4.

3) “Executed” DHF status updater (file-level):
   - New automation produces an auditable DHF register with:
     Exists (Y/N), Resolved path, SHA256 short, Last checked.
   - Output (generated in this build):
     01_Product_QMS/Uroflow_DHF_Index_Status_Register_v1.3_EXECUTED_AUTO.xlsx

4) Region packs (RU + CN) to lock conservative claims and avoid class escalation:
   - Russia pack:
     11_Region_Packs/RU_Roszdravnadzor/
   - China pack:
     11_Region_Packs/CN_NMPA/
   - Includes claim/evidence matrices for early planning.

5) Evidence bundles folder added (recommended storage location):
   - 12_Evidence_Bundles/Evidence_Files/
   - Filenames should match the Pilot Readiness Evidence Manifest (Expected file name).

Quick start (offline)
A) Update GSPR with evidence links:
   10_Pilot_Automation/run_gspr_evidence_autofill_oneclick.(sh|bat) <SUBMISSION_BUILD_ROOT>

B) Update DHF executed status:
   10_Pilot_Automation/run_dhf_status_update_oneclick.(sh|bat) <SUBMISSION_BUILD_ROOT>

C) G2 bundle build (EU+US):
   10_Pilot_Automation/run_g2_bundle_oneclick.(sh|bat) <SUBMISSION_BUILD_ROOT>

Notes
- Evidence-linking is filename-based by design (robust across folder layouts).
- Large raw datasets (audio/video) should NOT be placed into Evidence_Files.

Folder layout (additions)
- 11_Region_Packs/       → RU/CN claim+evidence packs
- 12_Evidence_Bundles/   → storage for executed evidence attachments
