# SPDX-License-Identifier: AGPL-3.0-or-later
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Security
$bauUmgebung = Join-Path $PSScriptRoot "..\..\werkzeuge\bau_umgebung.ps1"
if (Test-Path $bauUmgebung) { . $bauUmgebung }
$ks = $env:KIPLATZ_UPLOAD_KEYSTORE_DATEI
$pw = $env:KIPLATZ_UPLOAD_PASSWORT_DATEI
if (-not $ks -or -not $pw) { throw "Upload-Schlüssel nicht angegeben: KIPLATZ_UPLOAD_KEYSTORE_DATEI und KIPLATZ_UPLOAD_PASSWORT_DATEI setzen" }
if (-not (Test-Path $ks) -or -not (Test-Path $pw)) { throw "Upload-Schlüssel fehlt: $ks" }
if (-not $env:JAVA_HOME -or -not $env:ANDROID_HOME) { throw "JAVA_HOME und ANDROID_HOME setzen" }
$env:KIPLATZ_UPLOAD_KEYSTORE = $ks
try {
    $env:KIPLATZ_UPLOAD_PW = [Text.Encoding]::UTF8.GetString([Security.Cryptography.ProtectedData]::Unprotect([IO.File]::ReadAllBytes($pw), $null, "CurrentUser"))
    Push-Location (Join-Path $PSScriptRoot "..\android")
    try {
        $p = Start-Process -FilePath ".\gradlew.bat" -ArgumentList @("bundleRelease", "--no-daemon", "--console=plain") -NoNewWindow -Wait -PassThru
        if ($p.ExitCode -ne 0) { throw "Bau fehlgeschlagen ($($p.ExitCode))" }
    } finally { Pop-Location }
} finally {
    $env:KIPLATZ_UPLOAD_PW = $null
    $env:KIPLATZ_UPLOAD_KEYSTORE = $null
}
$aab = Join-Path $PSScriptRoot "..\android\app\build\outputs\bundle\release\app-release.aab"
Get-Item $aab | Select-Object FullName, Length
