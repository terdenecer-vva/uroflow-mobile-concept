@echo off
setlocal enabledelayedexpansion

set DATASET_ROOT=%1
set MANIFEST=%2

if "%DATASET_ROOT%"=="" (
  echo Usage: %0 ^<DATASET_ROOT^> ^<MANIFEST_PATH^>
  exit /b 1
)
if "%MANIFEST%"=="" (
  echo Usage: %0 ^<DATASET_ROOT^> ^<MANIFEST_PATH^>
  exit /b 1
)

set SCRIPT_DIR=%~dp0

echo [1/3] Running TFL generator (with BA plots)...
python "%SCRIPT_DIR%scripts\run_tfl_from_golden_dataset.py" --dataset_root "%DATASET_ROOT%" --manifest "%MANIFEST%" --make_plots

echo [2/3] Generating CSR auto-draft (EN)...
python "%SCRIPT_DIR%scripts\generate_csr_autodraft.py" --tfl_dir "%SCRIPT_DIR%outputs\tfl" --csr_template "%SCRIPT_DIR%..\05_Clinical\Uroflow_CSR_Template_v1.1_AUTOFILL.docx" --out_dir "%SCRIPT_DIR%outputs\csr_autodraft" --lang EN

echo [3/3] Generating CSR auto-draft (RU)...
python "%SCRIPT_DIR%scripts\generate_csr_autodraft.py" --tfl_dir "%SCRIPT_DIR%outputs\tfl" --csr_template "%SCRIPT_DIR%..\05_Clinical\Uroflow_CSR_Template_v1.1_AUTOFILL_RU.docx" --out_dir "%SCRIPT_DIR%outputs\csr_autodraft" --lang RU

echo DONE. Outputs in: %SCRIPT_DIR%outputs\csr_autodraft
