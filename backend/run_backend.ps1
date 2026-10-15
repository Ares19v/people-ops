$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
$env:PYTHONPATH = ".\.venv\Lib\site-packages;."
Write-Host "Starting PeopleOps Backend on http://127.0.0.1:8000..." -ForegroundColor Green
py -V:Astral/CPython3.11.15 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
