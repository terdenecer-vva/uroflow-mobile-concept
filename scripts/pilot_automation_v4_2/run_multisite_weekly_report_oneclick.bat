@echo off
set DATASET_ROOT=%1
set MANIFEST=%2

if "%DATASET_ROOT%"=="" goto :usage
if "%MANIFEST%"=="" goto :usage

python scripts\generate_multisite_weekly_report.py --dataset_root "%DATASET_ROOT%" --manifest "%MANIFEST%"
exit /b 0

:usage
echo Usage: run_multisite_weekly_report_oneclick.bat ^<DATASET_ROOT^> ^<MANIFEST.csv^|xlsx^>
exit /b 1
