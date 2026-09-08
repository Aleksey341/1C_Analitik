$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "Meeting Bridge - installation" -ForegroundColor Cyan
Write-Host "Project: $root"

function Get-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @("py", "-3")
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @("python")
    }
    throw "Python 3 not found. Install Python 3.11+ from https://www.python.org/downloads/windows/ and run install.ps1 again."
}

$pythonCmd = Get-PythonCommand

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "[1/4] Creating virtual environment .venv..." -ForegroundColor Yellow
    if ($pythonCmd.Count -eq 2) {
        & $pythonCmd[0] $pythonCmd[1] -m venv .venv
    } else {
        & $pythonCmd[0] -m venv .venv
    }
} else {
    Write-Host "[1/4] Virtual environment already exists."
}

$python = Join-Path $root ".venv\Scripts\python.exe"

Write-Host "[2/4] Installing Python dependencies..." -ForegroundColor Yellow
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt

if (-not (Test-Path ".\config.yaml")) {
    Write-Host "[3/4] Creating local config.yaml..." -ForegroundColor Yellow
    Copy-Item ".\config.example.yaml" ".\config.yaml"
} else {
    Write-Host "[3/4] config.yaml already exists - keeping it unchanged."
}

Write-Host "[4/4] Downloading Russian STT model..." -ForegroundColor Yellow
& $python ".\scripts\download_model.py"

Write-Host ""
Write-Host "Installation complete." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Open config.yaml and set llm.api_key to your OpenAI API key"
Write-Host "   OR set environment variable OPENAI_API_KEY."
Write-Host "2. Double-click MeetingBridge.bat."
Write-Host "3. In the app select microphone and a device marked [Loopback], then click 'Сохранить настройки'."
Write-Host ""
Write-Host "The local config.yaml is ignored by Git and must not be committed."
