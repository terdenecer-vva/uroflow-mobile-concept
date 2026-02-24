@echo off
set TFL_CSV=%1

if "%TFL_CSV%"=="" goto usage

set SCRIPT_DIR=%~dp0
python "%SCRIPT_DIR%scripts\run_drift_dashboard.py" --tfl_csv "%TFL_CSV%" --out_dir "%SCRIPT_DIR%outputs\drift"
echo Done. Outputs: %SCRIPT_DIR%outputs\drift
exit /b 0

:usage
echo Usage: %0 ^<TFL_RECORD_LEVEL_CSV^>
echo Example: %0 outputs\tfl\tfl_record_level.csv
exit /b 1
