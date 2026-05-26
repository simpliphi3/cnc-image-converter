# CNC Image Converter — first-time setup on Windows.
# Run from PowerShell at the repo root:
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $repo

function Write-Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

Write-Step "Checking prerequisites"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv (Python package manager)..."
    irm https://astral.sh/uv/install.ps1 | iex
    $env:Path = "$HOME\.local\bin;$env:Path"
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "Node.js is not installed."
    Write-Host "Please install Node 20+ from https://nodejs.org/ and re-run this script."
    exit 1
}

Write-Step "Creating Python environment and installing backend deps"
uv sync

Write-Step "Installing frontend deps and building static UI"
Push-Location frontend
npm install
npm run build
Pop-Location

Write-Step "Configuring .env"
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example."
}
$envContent = Get-Content ".env" -Raw
if ($envContent -notmatch "OPENAI_API_KEY=\S") {
    $k = Read-Host "Paste OPENAI_API_KEY (or blank to skip)"
    if ($k) { (Get-Content ".env") -replace "OPENAI_API_KEY=.*", "OPENAI_API_KEY=$k" | Set-Content ".env" }
}
$envContent = Get-Content ".env" -Raw
if ($envContent -notmatch "GOOGLE_API_KEY=\S") {
    $k = Read-Host "Paste GOOGLE_API_KEY (or blank to skip)"
    if ($k) { (Get-Content ".env") -replace "GOOGLE_API_KEY=.*", "GOOGLE_API_KEY=$k" | Set-Content ".env" }
}

Write-Step "Done"
Write-Host "To launch the app: double-click scripts\start.bat (or run it from PowerShell)."
Write-Host "The browser will open at http://127.0.0.1:7777 a few seconds later."
