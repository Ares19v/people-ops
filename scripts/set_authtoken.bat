@echo off
setlocal
echo =======================================================
echo          Configure Ngrok Authtoken for People-Ops
echo =======================================================

set "NGROK_BIN=%LOCALAPPDATA%\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe"

where ngrok >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "NGROK_EXEC=ngrok"
) else if exist "%NGROK_BIN%" (
    set "NGROK_EXEC=%NGROK_BIN%"
) else (
    echo [ERROR] ngrok.exe not found!
    pause
    exit /b 1
)

if "%~1"=="" (
    set /p "TOKEN=Enter your ngrok authtoken (from dashboard.ngrok.com): "
) else (
    set "TOKEN=%~1"
)

if "%TOKEN%"=="" (
    echo [ERROR] No authtoken entered.
    pause
    exit /b 1
)

"%NGROK_EXEC%" config add-authtoken %TOKEN%
echo.
echo [SUCCESS] Ngrok authtoken saved! You can now run start_ngrok.bat.
pause
