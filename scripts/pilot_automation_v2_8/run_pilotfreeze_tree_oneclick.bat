@echo off
setlocal

set SUBMISSION_ROOT=%1
set OUT_DIR=%2
set DRY_RUN=%3

if "%SUBMISSION_ROOT%"=="" (
  echo Usage: %~n0 ^<SUBMISSION_BUILD_ROOT^> ^<OUT_DIR^> [--dry_run]
  echo Example: %~n0 ..\.. .\outputs\pilotfreeze_tree
  exit /b 1
)
if "%OUT_DIR%"=="" (
  echo Usage: %~n0 ^<SUBMISSION_BUILD_ROOT^> ^<OUT_DIR^> [--dry_run]
  exit /b 1
)

set SCRIPT_DIR=%~dp0
set EXTRA_LIST=%SCRIPT_DIR%config\pilotfreeze_extra_includes.txt

set CMD=python "%SCRIPT_DIR%scripts\build_pilotfreeze_submission_tree.py" --build_root "%SUBMISSION_ROOT%" --out_dir "%OUT_DIR%" --eu_index "06_EU_MDR/Annex_II_III_Submission_Folder/EU_MDR_AnnexII_III_Submission_Folder_Index_v2.3.xlsx" --us_index "07_US_FDA/FDA_Submission_Folder/FDA_Submission_Folder_Index_v2.3.xlsx" --extra_list "%EXTRA_LIST%"

if "%DRY_RUN%"=="--dry_run" (
  %CMD% --dry_run
) else (
  %CMD%
)

echo DONE. Pilot-freeze tree built into: %OUT_DIR%
endlocal
