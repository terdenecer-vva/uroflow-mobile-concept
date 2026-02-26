@echo off
setlocal enabledelayedexpansion

set SUBMISSION_ROOT=%1

if "%SUBMISSION_ROOT%"=="" (
  echo Usage: %0 ^<SUBMISSION_BUILD_ROOT^>
  echo Example: %0 ..\..
  exit /b 1
)

set SCRIPT_DIR=%~dp0

python "%SCRIPT_DIR%scripts\build_g2_submission_bundle.py" --submission_root "%SUBMISSION_ROOT%" --out_dir "%SCRIPT_DIR%outputs\g2_bundle" --zip_bundle

echo DONE. Bundle outputs in: %SCRIPT_DIR%outputs\g2_bundle
