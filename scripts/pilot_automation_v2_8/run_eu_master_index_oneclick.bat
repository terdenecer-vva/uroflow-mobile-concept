@echo off
setlocal

set SUBMISSION_ROOT=%1
if "%SUBMISSION_ROOT%"=="" (
  echo Usage: %~n0 ^<SUBMISSION_BUILD_ROOT^>
  echo Example: %~n0 ..\..
  exit /b 1
)

set SCRIPT_DIR=%~dp0

python "%SCRIPT_DIR%scripts\build_eu_master_index.py" ^
  --build_root "%SUBMISSION_ROOT%" ^
  --annex_index "06_EU_MDR/Annex_II_III_Submission_Folder/EU_MDR_AnnexII_III_Submission_Folder_Index_v2.4.xlsx" ^
  --gspr "06_EU_MDR/Uroflow_EU_MDR_GSPR_Checklist_AnnexI_v1.3_EXECUTED_EVIDENCE_AUTO.xlsx" ^
  --evidence_manifest "05_Clinical/Uroflow_P0_Pilot_Readiness_Evidence_Manifest_v1.0.xlsx" ^
  --out "06_EU_MDR/Uroflow_EU_MDR_AnnexII_III_Master_Index_v1.1_EXECUTED.xlsx"

echo DONE. Master index written to: 06_EU_MDR\Uroflow_EU_MDR_AnnexII_III_Master_Index_v1.1_EXECUTED.xlsx
endlocal
