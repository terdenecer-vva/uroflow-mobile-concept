@echo off
set DATASET_ROOT=%1
set MANIFEST=%2

if "%DATASET_ROOT%"=="" goto :usage
if "%MANIFEST%"=="" goto :usage

python scripts\run_daily_qa_minimal.py --dataset_root "%DATASET_ROOT%" --manifest "%MANIFEST%"
exit /b 0

:usage
echo Usage: run_daily_qa_oneclick.bat ^<DATASET_ROOT^> ^<MANIFEST.csv^|xlsx^>
exit /b 1
