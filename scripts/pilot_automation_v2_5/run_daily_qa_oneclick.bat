@echo off
set DATASET_ROOT=%1
set MANIFEST_PATH=%2

if "%DATASET_ROOT%"=="" goto usage
if "%MANIFEST_PATH%"=="" goto usage

set SCRIPT_DIR=%~dp0
python "%SCRIPT_DIR%scripts\run_daily_qa.py" --dataset_root "%DATASET_ROOT%" --manifest "%MANIFEST_PATH%" --out "%SCRIPT_DIR%outputs" --write_checksums
goto end

:usage
echo Usage: run_daily_qa_oneclick.bat ^<DATASET_ROOT^> ^<MANIFEST_PATH^>
:end
