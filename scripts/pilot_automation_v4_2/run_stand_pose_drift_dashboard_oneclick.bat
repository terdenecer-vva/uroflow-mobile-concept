@echo off
set DATASET_ROOT=%1
set MANIFEST=%2
if "%DATASET_ROOT%"=="" goto usage
if "%MANIFEST%"=="" goto usage
python scripts\run_stand_pose_drift_dashboard.py --dataset_root "%DATASET_ROOT%" --manifest "%MANIFEST%" --config config\stand_pose_drift_config.json
exit /b 0
:usage
echo Usage: %0 ^<DATASET_ROOT^> ^<MANIFEST.csv^|xlsx^>
exit /b 1
