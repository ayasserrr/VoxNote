# Start VoxNote on Windows: opens the API and the web app in two PowerShell windows.
#   ./scripts/dev.ps1      then open http://localhost:5173
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; .\.venv\Scripts\uvicorn app.main:app --reload --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\frontend'; npm run dev"
Write-Host "VoxNote is starting: API http://localhost:8000  ·  App http://localhost:5173 (close the two windows to stop)"
