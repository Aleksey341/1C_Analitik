$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$pythonw = Join-Path $root ".venv\Scripts\pythonw.exe"
$config = Join-Path $root "config.yaml"

if (-not (Test-Path $pythonw)) {
    Write-Host "Virtual environment not found." -ForegroundColor Red
    Write-Host "Run .\install.ps1 first."
    exit 1
}

if (-not (Test-Path $config)) {
    Write-Host "config.yaml not found." -ForegroundColor Red
    Write-Host "Run .\install.ps1 first."
    exit 1
}

Start-Process -FilePath $pythonw -ArgumentList "`"$root\run_gui.pyw`"" -WorkingDirectory $root
