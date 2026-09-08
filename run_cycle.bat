@echo off
title MacroListing - Cycle Runner
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo   Menjalankan ZeusX Cycle Runner
echo ============================================================
echo.
python cycle_runner.py %*
pause
