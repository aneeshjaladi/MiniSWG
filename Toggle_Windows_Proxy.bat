@echo off
title Toggle Windows Proxy - MiniSWG
cd /d "%~dp0"

echo [*] Toggling Windows System Proxy status...
python -m miniswg.winproxy toggle 8080

echo.
timeout /t 3 >nul
