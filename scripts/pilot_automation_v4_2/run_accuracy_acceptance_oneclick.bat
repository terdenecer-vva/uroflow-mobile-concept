@echo off
set DATASET_ROOT=%1
set MANIFEST=%2
if "%DATASET_ROOT%"=="" goto usage
if "%MANIFEST%"=="" goto usage
python scripts\compute_accuracy_acceptance.py --dataset_root "%DATASET_ROOT%" --manifest "%MANIFEST%"
exit /b 0
:usage
echo Usage: %0 ^<DATASET_ROOT^> ^<MANIFEST.csv^|xlsx^>
exit /b 1
