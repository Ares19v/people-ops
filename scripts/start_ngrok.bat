@echo off
setlocal
echo =======================================================
echo          Starting Ngrok Public Tunnel for People-Ops
echo =======================================================

REM Set path to ngrok binary if not already in system PATH
set "NGROK_BIN=%LOCALAPPDATA%\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe"

where ngrok >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "NGROK_EXEC=ngrok"
) else if exist "%NGROK_BIN%" (
    set "NGROK_EXEC=%NGROK_BIN%"
) else (
    echo [ERROR] ngrok.exe not found!
    echo Please install ngrok or ensure it is located in your LOCALAPPDATA folder.
    pause
    exit /b 1
)

echo.
echo Tunneling Vite Frontend on port 5173 (which reverse-proxies FastAPI Backend on port 38290)...
echo.
"%NGROK_EXEC%" http 5173

pause
