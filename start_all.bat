@echo off
setlocal
title PeopleOps - Backend + Frontend + ngrok
cd /d "%~dp0"

REM Backend port must be free, otherwise uvicorn fails to bind.
set "BACKEND_PID="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":38290 .*LISTENING"') do set "BACKEND_PID=%%P"
if defined BACKEND_PID (
    echo [WARN] Port 38290 is already in use by PID %BACKEND_PID%.
    choice /M "Stop that process and continue"
    if errorlevel 2 (
        echo Aborted.
        exit /b 1
    )
    taskkill /PID %BACKEND_PID% /F >nul 2>&1
)

REM A leftover ngrok keeps the fixed domain online (ERR_NGROK_334) and makes the new tunnel fail.
tasklist /FI "IMAGENAME eq ngrok.exe" 2>nul | find /I "ngrok.exe" >nul
if not errorlevel 1 (
    echo [WARN] An ngrok process is already running and holds the tunnel domain.
    choice /M "Stop it and continue"
    if errorlevel 2 (
        echo Aborted.
        exit /b 1
    )
    taskkill /IM ngrok.exe /F >nul 2>&1
)

if not exist "node_modules\concurrently" if not exist "frontend\node_modules\.bin\concurrently.cmd" (
    echo Installing frontend dependencies...
    call npm --prefix frontend install
)

echo Starting backend (38290), frontend (Vite) and ngrok tunnel. Press Ctrl+C to stop all.
call npm --prefix frontend run dev:all
