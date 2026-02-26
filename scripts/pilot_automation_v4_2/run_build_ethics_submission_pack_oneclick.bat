@echo off
set REGION=%1
if "%REGION%"=="" (
  echo Usage: %0 ^<RU_EC^|EU_Ethics^|US_IRB^>
  exit /b 1
)
python scripts\build_ethics_submission_pack.py --region "%REGION%"
