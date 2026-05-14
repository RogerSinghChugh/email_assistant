# dev.ps1 — start everything for local development in one shot.
#
# Spawns the Django server and Celery worker in new PowerShell windows so each
# keeps its own log stream you can scroll and Ctrl+C independently. Redis is
# assumed to be running (in WSL or wherever); we just probe it and warn.
#
# Usage:  .\dev.ps1
#
# Stop everything: close (or Ctrl+C in) each spawned window. To stop everything
# at once from this shell:  Get-Process python,celery -ErrorAction SilentlyContinue | Stop-Process

$ErrorActionPreference = "Stop"

$python = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
$celery = Join-Path $PSScriptRoot "venv\Scripts\celery.exe"

if (-not (Test-Path $python)) {
    Write-Error "venv not found at $python — run 'python -m venv venv ; venv\Scripts\pip install -r requirements.txt' first."
    exit 1
}

# --- Redis preflight (best-effort) ---------------------------------------
$redisHost = "127.0.0.1"
$redisPort = 6379
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $tcp.Connect($redisHost, $redisPort)
    $tcp.Close()
    Write-Host "[ok] Redis reachable at ${redisHost}:${redisPort}" -ForegroundColor Green
} catch {
    Write-Warning "Redis NOT reachable at ${redisHost}:${redisPort}."
    Write-Warning "  - In WSL: sudo service redis-server start"
    Write-Warning "  - On Windows: start Memurai/Redis service"
    Write-Warning "Continuing — services will start but writes/reads to Redis will fail until it's up."
}

# --- Spawn windows --------------------------------------------------------
$repo = $PSScriptRoot

Write-Host ""
Write-Host "[1/2] Starting Django server in a new window…" -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$repo'; & '$python' manage.py runserver"
) | Out-Null

Write-Host "[2/2] Starting Celery worker in a new window…" -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$repo'; & '$celery' -A email_assistant worker -l info --pool=threads --concurrency=8 -Q email_assistant"
) | Out-Null

# Give them a moment to bind ports / connect to broker
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "All services launching. Open these once they're ready:" -ForegroundColor Green
Write-Host "  Demo UI       http://localhost:8000/"
Write-Host "  Swagger docs  http://localhost:8000/api/docs/"
Write-Host "  Healthcheck   http://localhost:8000/health/"
Write-Host ""
Write-Host "To stop everything from this shell:"
Write-Host "  Get-Process python,celery -ErrorAction SilentlyContinue | Stop-Process"
