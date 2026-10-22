$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
$env:PYTHONPATH = ".\.venv\Lib\site-packages;."
$port = if ($env:PORT) { $env:PORT } elseif ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { "38290" }
Write-Host "Starting PeopleOps Backend on http://127.0.0.1:$port..." -ForegroundColor Green
py -V:Astral/CPython3.11.15 -m uvicorn app.main:app --host 127.0.0.1 --port $port --reload
