@echo off
title Stop MiniSWG
cd /d "%~dp0"

echo ==============================================================
echo             MiniSWG - Shutdown and Proxy Restore
echo ==============================================================
echo.
echo [*] Disabling Windows System Proxy...
python -m miniswg.winproxy disable

echo [*] Stopping MiniSWG Proxy processes...
taskkill /FI "WINDOWTITLE eq MiniSWG Proxy Server*" /F >nul 2>&1
powershell -Command "Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*miniswg.proxy*' } | Stop-Process -Force" >nul 2>&1

echo.
echo ==============================================================
echo       MiniSWG has been safely STOPPED!
echo ==============================================================
echo  [+] Windows System Proxy: DISABLED
echo  [+] Direct internet connection has been fully RESTORED.
echo ==============================================================
echo.
timeout /t 3 >nul
