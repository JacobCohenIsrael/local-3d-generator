@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1"
if errorlevel 1 (
  echo.
  echo Setup stopped. Read the message above or see SETUP.md.
  pause
  exit /b 1
)
