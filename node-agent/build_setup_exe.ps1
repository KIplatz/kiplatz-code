# SPDX-License-Identifier: AGPL-3.0-or-later
$ErrorActionPreference = "Stop"

$specFile = Join-Path $PSScriptRoot "CommunityAINetwork-NodeSetup.spec"
$distDir = Join-Path $PSScriptRoot "dist"
$exePath = Join-Path $distDir "CommunityAINetwork-NodeSetup.exe"

Write-Host "Baue $exePath ..."
python -m PyInstaller --noconfirm $specFile

if (-not (Test-Path $exePath)) {
    Write-Error "Build fehlgeschlagen: $exePath wurde nicht erzeugt."
    exit 1
}

Write-Host "Starte $exePath fuer einen Start-Rauchtest ..."
$proc = Start-Process -FilePath $exePath -PassThru
Start-Sleep -Seconds 3

if ($proc.HasExited) {
    Write-Error "Die EXE ist sofort beendet worden (Exit Code $($proc.ExitCode)). Build gilt als NICHT verifiziert."
    exit 1
}

Stop-Process -Id $proc.Id -Force
Write-Host "OK: $exePath wurde erzeugt und startet ohne sofortigen Absturz."
Write-Host "Hinweis: Dies ist nur ein Start-Rauchtest, kein Test des vollstaendigen Pairing-Ablaufs."
