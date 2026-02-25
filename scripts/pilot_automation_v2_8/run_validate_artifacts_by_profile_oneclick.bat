@echo off
set DATASET_ROOT=%1
set MANIFEST=%2
set PROFILE=%3
if "%DATASET_ROOT%"=="" goto usage
if "%MANIFEST%"=="" goto usage
if "%PROFILE%"=="" set PROFILE=P0

set SCRIPT_DIR=%~dp0
python "%SCRIPT_DIR%scripts\validate_artifacts_by_profile.py" --dataset_root "%DATASET_ROOT%" --manifest "%MANIFEST%" --profile %PROFILE% --out_dir "%SCRIPT_DIR%outputs\validate_artifacts"
exit /b %ERRORLEVEL%

:usage
echo Usage: %0 ^<DATASET_ROOT^> ^<MANIFEST.csv^|xlsx^> [PROFILE P0^|P1^|P2^|P3]
exit /b 1
