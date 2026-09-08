# Build 1C Analitik / MeetingBridge.exe with PyInstaller (one-folder).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
  $python = (Get-Command python).Source
}

& $python -m pip install -q pyinstaller customtkinter

& $python -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --name MeetingBridge `
  --paths $PSScriptRoot `
  --collect-all customtkinter `
  --collect-all sherpa_onnx `
  --collect-all pyaudiowpatch `
  --add-data "$PSScriptRoot\skills;skills" `
  --hidden-import meeting_bridge.gui `
  --hidden-import meeting_bridge.first_run `
  --hidden-import meeting_bridge.session `
  --hidden-import meeting_bridge.capture `
  --hidden-import meeting_bridge.stt `
  --hidden-import meeting_bridge.devices `
  --hidden-import meeting_bridge.writer `
  --hidden-import meeting_bridge.config `
  --hidden-import meeting_bridge.skills `
  --hidden-import meeting_bridge.llm_client `
  "$PSScriptRoot\run_gui.pyw"

$dist = Join-Path $PSScriptRoot "dist\MeetingBridge"
Copy-Item "$PSScriptRoot\config.example.yaml" "$dist\config.example.yaml" -Force
New-Item -ItemType Directory -Force "$dist\scripts" | Out-Null
Copy-Item "$PSScriptRoot\scripts\download_model.py" "$dist\scripts\download_model.py" -Force

Write-Host "Built: $dist\MeetingBridge.exe"
Write-Host "The installer will add the STT model and create shortcuts automatically."
