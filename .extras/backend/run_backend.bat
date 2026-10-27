@echo off
title PeopleOps Backend Server
cd /d "%~dp0"
set PYTHONPATH=.
if "%PORT%"=="" if not "%BACKEND_PORT%"=="" set PORT=%BACKEND_PORT%
if "%PORT%"=="" set PORT=38290
echo Starting PeopleOps Backend on random port %PORT%...
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port %PORT% --reload
pause
