@echo off
set DATASET_ROOT=%1
set MANIFEST=%2
set DATASET_ID=%3
set OPERATOR_ID=%4
if "%DATASET_ROOT%"=="" goto :usage
if "%MANIFEST%"=="" goto :usage

set CMD=python scripts\build_dataset_release_bundle_guarded.py --dataset_root "%DATASET_ROOT%" --manifest "%MANIFEST%"
if not "%DATASET_ID%"=="" set CMD=%CMD% --dataset_id "%DATASET_ID%"
if not "%OPERATOR_ID%"=="" set CMD=%CMD% --operator_id "%OPERATOR_ID%"

%CMD%
exit /b 0

:usage
echo Usage: %0 ^<DATASET_ROOT^> ^<MANIFEST.csv^|xlsx^> [DATASET_ID] [OPERATOR_ID]
exit /b 1
