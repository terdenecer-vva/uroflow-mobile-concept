@echo off
set DATASET_ROOT=%1
set MANIFEST_PATH=%2
set SUBMISSION_BUILD_ROOT=%3

if "%DATASET_ROOT%"=="" goto usage
if "%MANIFEST_PATH%"=="" goto usage
if "%SUBMISSION_BUILD_ROOT%"=="" goto usage

set SCRIPT_DIR=%~dp0
python "%SCRIPT_DIR%scripts\build_g1_evidence_bundle.py" --dataset_root "%DATASET_ROOT%" --manifest "%MANIFEST_PATH%" --submission_build_root "%SUBMISSION_BUILD_ROOT%" --out_dir "%SCRIPT_DIR%outputs\g1" --make_plots --make_pdf
echo Done. Outputs: %SCRIPT_DIR%outputs\g1
exit /b 0

:usage
echo Usage: %0 ^<DATASET_ROOT^> ^<MANIFEST_PATH^> ^<SUBMISSION_BUILD_ROOT^>
exit /b 1
