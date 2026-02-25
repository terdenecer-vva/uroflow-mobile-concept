@echo off
set DATASET_ROOT=%1
set DATASET_ID=%2
set OPERATOR_ID=%3
if "%DATASET_ROOT%"=="" (
  echo Usage: %0 ^<DATASET_ROOT^> [DATASET_ID] [OPERATOR_ID]
  exit /b 1
)
set CMD=python scripts\build_pilot_freeze_kit.py --dataset_root "%DATASET_ROOT%"
if not "%DATASET_ID%"=="" set CMD=%CMD% --dataset_id "%DATASET_ID%"
if not "%OPERATOR_ID%"=="" set CMD=%CMD% --operator_id "%OPERATOR_ID%"
%CMD%
