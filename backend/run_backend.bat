@echo off
title PeopleOps Backend Server
cd /d "%~dp0"
set PYTHONPATH=.\.venv\Lib\site-packages;.
echo Starting PeopleOps Backend on port 8000...
py -V:Astral/CPython3.11.15 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause
