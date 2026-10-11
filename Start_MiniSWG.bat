@echo off
title MiniSWG - Secure Web Gateway
cd /d "%~dp0"

echo ==============================================================
echo             MiniSWG - Secure Web Gateway Launcher
echo ==============================================================
echo.
echo [*] Checking Python environment...

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] ERROR: Python is not installed or not in your PATH.
    echo     Please install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

echo [*] Starting MiniSWG Proxy in background...
start "MiniSWG Proxy Server" /min python -m miniswg.proxy --reload

timeout /t 2 /nobreak >nul

echo [*] Enabling Windows System Proxy for all web browsers...
python -m miniswg.winproxy enable 8080

echo [*] Opening Web Admin Dashboard in your browser...
start http://127.0.0.1:8080/admin

echo.
echo ==============================================================
echo       MiniSWG is now PROTECTING your internet traffic!
echo ==============================================================
echo  - Proxy Address:         127.0.0.1:8080
echo  - Windows System Proxy:  ENABLED (Chrome, Edge, etc.)
echo  - Web Admin Dashboard:   http://127.0.0.1:8080/admin
echo.
echo  To STOP MiniSWG and restore direct internet, double-click:
echo  Stop_MiniSWG.bat
echo ==============================================================
echo.
pause
