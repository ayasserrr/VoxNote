# One-time setup on Windows (PowerShell):  ./scripts/setup.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host "-> created .env (add a free GROQ_API_KEY or GEMINI_API_KEY)" }
python -m venv backend\.venv
backend\.venv\Scripts\python -m pip install --upgrade pip
backend\.venv\Scripts\pip install -r backend\requirements-dev.txt
Push-Location frontend; npm install; Pop-Location
Write-Host "Done. Start everything with:  ./scripts/dev.ps1   ->  http://localhost:5173"
