# Build MeetingBridge.exe with PyInstaller (one-folder).
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
  --hidden-import meeting_bridge.gui `
  --hidden-import meeting_bridge.session `
  --hidden-import meeting_bridge.capture `
  --hidden-import meeting_bridge.stt `
  --hidden-import meeting_bridge.devices `
  --hidden-import meeting_bridge.writer `
  --hidden-import meeting_bridge.config `
  --hidden-import pyaudiowpatch `
  --hidden-import sherpa_onnx `
  "$PSScriptRoot\run_gui.pyw"

Write-Host "Built: $PSScriptRoot\dist\MeetingBridge\MeetingBridge.exe"
Write-Host "Keep the whole dist\MeetingBridge folder next to config.yaml, models\, and scripts\."
