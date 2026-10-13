# SPDX-License-Identifier: AGPL-3.0-or-later
$ErrorActionPreference = "Stop"
$specFile = Join-Path $PSScriptRoot "CommunityAI.spec"
$exePath = Join-Path (Join-Path $PSScriptRoot "dist") "CommunityAI.exe"

Write-Host "Baue $exePath ..."
python -m PyInstaller --noconfirm $specFile
if (-not (Test-Path $exePath)) { Write-Error "Build fehlgeschlagen: $exePath fehlt."; exit 1 }
$hash = (Get-FileHash $exePath -Algorithm SHA256).Hash
Write-Host "SHA256: $hash"

Write-Host "Selbsttest ohne Fenster (Testbetrieb, eigener Basisordner im TEMP) ..."
$basis = Join-Path $env:TEMP ("CommunityAI-Selbsttest-" + (Get-Date -Format "yyyyMMddTHHmmss"))
try {
    $proc = Start-Process -FilePath $exePath -ArgumentList "--selbsttest", "--basis", "`"$basis`"" -PassThru -Wait -WindowStyle Hidden -ErrorAction Stop
} catch {
    Write-Host "SELBSTTEST NICHT MOEGLICH (NICHT GETESTET): $($_.Exception.Message)"
    exit 3
}
$report = Join-Path (Join-Path $basis "diagnose") "selbsttest.txt"
if (Test-Path $report) { Get-Content $report | ForEach-Object { "  $_" } }
if ($proc.ExitCode -ne 0) { Write-Error "Selbsttest der EXE fehlgeschlagen (Exit Code $($proc.ExitCode))."; exit 1 }
Write-Host "OK: $exePath besteht den Selbsttest (kein Fenster geoeffnet, nichts installiert)."
