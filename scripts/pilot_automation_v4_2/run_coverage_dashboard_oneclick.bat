@echo off
set DATASET_ROOT=%1
set MANIFEST=%2

if "%DATASET_ROOT%"=="" goto :usage
if "%MANIFEST%"=="" goto :usage

python scripts\run_coverage_dashboard.py --dataset_root "%DATASET_ROOT%" --manifest "%MANIFEST%" --targets config\coverage_targets_config.json
exit /b 0

:usage
echo Usage: run_coverage_dashboard_oneclick.bat ^<DATASET_ROOT^> ^<MANIFEST.csv^|xlsx^>
exit /b 1
