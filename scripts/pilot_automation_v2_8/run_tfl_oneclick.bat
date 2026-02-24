@echo off
set DATASET_ROOT=%1
set MANIFEST_PATH=%2

if "%DATASET_ROOT%"=="" goto usage
if "%MANIFEST_PATH%"=="" goto usage

set SCRIPT_DIR=%~dp0
python "%SCRIPT_DIR%scripts\run_tfl_from_golden_dataset.py" --dataset_root "%DATASET_ROOT%" --manifest "%MANIFEST_PATH%" --out_dir "%SCRIPT_DIR%outputs\tfl" --make_plots --make_pdf
echo Done. Outputs: %SCRIPT_DIR%outputs\tfl
exit /b 0

:usage
echo Usage: %0 ^<DATASET_ROOT^> ^<MANIFEST_PATH^>
exit /b 1
