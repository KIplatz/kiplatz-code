# SPDX-License-Identifier: AGPL-3.0-or-later
param([string]$Rettungsschluessel = "",
      [switch]$OhneUnterschrift)
$bauUmgebung = Join-Path $PSScriptRoot "..\werkzeuge\bau_umgebung.ps1"
if (Test-Path $bauUmgebung) { . $bauUmgebung }
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$dist = Join-Path $here "dist"
$arbeit = Join-Path $dist "portable"
$pyVersion = "3.14.7"
$pyUrl = "https://www.python.org/ftp/python/$pyVersion/python-$pyVersion-embed-amd64.zip"
$pySha = "d297e5ff019966817ad8502465176139f2d3d840fa4ed84b13bed399a6ab1f15"
$pyZip = Join-Path $dist "python-$pyVersion-embed-amd64.zip"

New-Item -ItemType Directory -Force $dist | Out-Null
if (Test-Path $arbeit) { Remove-Item -Recurse -Force $arbeit }
New-Item -ItemType Directory -Force (Join-Path $arbeit "python") | Out-Null
New-Item -ItemType Directory -Force (Join-Path $arbeit "node-agent") | Out-Null

if (-not (Test-Path $pyZip)) {
    Write-Host "Hole Python $pyVersion (embeddable) von python.org ..."
    Invoke-WebRequest -Uri $pyUrl -OutFile $pyZip -UseBasicParsing
}
$hash = (Get-FileHash $pyZip -Algorithm SHA256).Hash.ToLower()
if ($hash -ne $pySha) { Remove-Item $pyZip; throw "Prüfsumme des Python-Pakets stimmt nicht ($hash); Datei verworfen." }
Expand-Archive -Path $pyZip -DestinationPath (Join-Path $arbeit "python") -Force
$pyTag = "python" + (($pyVersion -split '\.')[0..1] -join '')
[System.IO.File]::WriteAllText((Join-Path $arbeit "python\$pyTag._pth"), "$pyTag.zip`n.`nLib\site-packages`nimport site`n")

$sp = Join-Path $arbeit "python\Lib\site-packages"
New-Item -ItemType Directory -Force $sp | Out-Null
Write-Host "Installiere Pakete nach $sp ..."
$ErrorActionPreference = "Continue"
$pyReihe = ($pyVersion -split '\.')[0..1] -join '.'
& cmd /c "python -m pip install --quiet --require-hashes --no-deps --python-version $pyReihe --implementation cp --platform win_amd64 --target `"$sp`" -r `"$(Join-Path $here 'requirements-bau.txt')`" 2>&1" | Out-Null
$rc = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($rc -ne 0) { throw "pip install fehlgeschlagen (Exit $rc)." }
Get-ChildItem $sp -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

Get-ChildItem $here -Filter "*.py" | Copy-Item -Destination (Join-Path $arbeit "node-agent")
& cmd /c "python `"$(Join-Path $here 'sauber_ausliefern.py')`" `"$(Join-Path $here 'webapp')`" `"$(Join-Path $arbeit 'node-agent\webapp')`""
if ($LASTEXITCODE -ne 0) { throw "Das Fenster ließ sich nicht reinigen (Exit $LASTEXITCODE)." }
Copy-Item -Recurse (Join-Path $here "skills_vorlagen") (Join-Path $arbeit "node-agent\skills_vorlagen")
Copy-Item (Join-Path $here "requirements.txt") (Join-Path $arbeit "node-agent")
Copy-Item (Join-Path $here "neuerungen_en.json") (Join-Path $arbeit "node-agent")
Copy-Item (Join-Path $here "..\SCHNITTSTELLE.md") (Join-Path $arbeit "node-agent")

$eingebettet = Join-Path $arbeit "python\python.exe"
& $eingebettet (Join-Path $here "bau_verpacken.py") (Join-Path $arbeit "node-agent")
if ($LASTEXITCODE -ne 0) { throw "Verpacken fehlgeschlagen (Exit $LASTEXITCODE)." }
& $eingebettet (Join-Path $here "bau_verpacken.py") --pruefen (Join-Path $arbeit "node-agent")
if ($LASTEXITCODE -ne 0) { throw "Ein verpacktes Modul lässt sich nicht laden (Exit $LASTEXITCODE)." }

python -c "import sys; sys.path.insert(0, r'$here'); import app_install; app_install.starter_anlegen(r'$arbeit')"
if ($LASTEXITCODE -ne 0) { throw "Starter konnte nicht angelegt werden." }
$sig = Get-AuthenticodeSignature (Join-Path $arbeit "KIplatz.exe")
if ($sig.Status -ne "Valid" -or $sig.SignerCertificate.Subject -notlike "*Python Software Foundation*") { throw "Der Starter trägt keine gültige Unterschrift der Python Software Foundation." }

$basis = Join-Path $env:TEMP ("CommunityAI-Zip-Selbsttest-" + (Get-Date -Format "yyyyMMddTHHmmss"))
$p = Start-Process -FilePath (Join-Path $arbeit "python\pythonw.exe") -ArgumentList "`"$(Join-Path $arbeit 'node-agent\app_web.py')`"", "--selbsttest", "--basis", "`"$basis`"" -PassThru -Wait -WindowStyle Hidden
$report = Join-Path (Join-Path $basis "diagnose") "selbsttest.txt"
if (Test-Path $report) { Get-Content $report | ForEach-Object { "  $_" } }
if ($p.ExitCode -ne 0) { throw "Selbsttest des ZIP-Programms fehlgeschlagen (Exit $($p.ExitCode))." }

$zip = Join-Path $dist "CommunityAI.zip"
$quelle = Join-Path $dist "CommunityAI-quelle.zip"
foreach ($f in @($zip, $quelle)) { if (Test-Path $f) { Remove-Item $f } }
Get-ChildItem (Join-Path $arbeit "node-agent") -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
& cmd /c "python `"$(Join-Path $here 'sauber_ausliefern.py')`" --pruefen `"$(Join-Path $arbeit 'node-agent')`""
if ($LASTEXITCODE -ne 0) { throw "Im Paket steht noch etwas Persönliches (siehe oben); nichts wird ausgeliefert." }
$pakete = Get-ChildItem $sp | Where-Object { $_.Name -ne "__pycache__" } | ForEach-Object { $_.Name } | Sort-Object
[IO.File]::WriteAllText((Join-Path $arbeit "node-agent\pakete.txt"), "# site-packages dieses Baus`n" + ($pakete -join "`n") + "`n")
[IO.File]::WriteAllText((Join-Path $arbeit "node-agent\laufzeit.txt"), "$pyVersion`n")
foreach ($n in @("LIES-MICH.txt", "README.txt")) {
    $t = [IO.File]::ReadAllText((Join-Path $here "verpackung\$n"), [Text.Encoding]::UTF8) -replace "`r?`n", "`r`n"
    [IO.File]::WriteAllText((Join-Path $arbeit $n), $t, (New-Object Text.UTF8Encoding $true))
}
$teile = @("LIES-MICH.txt", "README.txt", "python", "node-agent", "KIplatz.exe", "KIplatz._pth", "$pyTag.dll", "python3.dll", "vcruntime140.dll", "vcruntime140_1.dll") | ForEach-Object { Join-Path $arbeit $_ }
Compress-Archive -Path $teile -DestinationPath $zip -CompressionLevel Optimal
Compress-Archive -Path (Join-Path $arbeit "node-agent") -DestinationPath $quelle -CompressionLevel Optimal
& cmd /c "python `"$(Join-Path $here 'helfer_paket.py')`" `"$(Join-Path $arbeit 'node-agent')`" `"$dist`""
if ($LASTEXITCODE -ne 0) { throw "Helfer-Pakete für Linux und Mac fehlgeschlagen (siehe oben)." }
$helfer = @("KIplatz-Helfer-linux-x64.tar.gz", "KIplatz-Helfer-macos-arm64.tar.gz") | ForEach-Object { Join-Path $dist $_ }
foreach ($f in @($zip, $quelle)) {
    $h = (Get-FileHash $f -Algorithm SHA256).Hash.ToLower()
    [System.IO.File]::WriteAllText("$f.sha256", "$h  $(Split-Path $f -Leaf)`n")
    Write-Host ("{0}: {1:N1} MB, SHA-256 {2}" -f (Split-Path $f -Leaf), ((Get-Item $f).Length / 1MB), $h)
}
Add-Type -AssemblyName System.Security
if ($Rettungsschluessel) {
    if (-not (Test-Path $Rettungsschluessel)) { throw "Rettungsschlüssel fehlt: $Rettungsschluessel" }
    $pemBytes = [IO.File]::ReadAllBytes($Rettungsschluessel); Write-Host "Unterschrift mit dem Rettungsschlüssel"
} elseif ($OhneUnterschrift) {
    $pemBytes = $null; Write-Host "Ohne Unterschrift gebaut: zum Ausprobieren, nicht als Update verteilbar"
} else {
    $verpackt = $env:KIPLATZ_UPDATE_SCHLUESSEL
    if (-not $verpackt) { throw "Kein Signaturschlüssel: KIPLATZ_UPDATE_SCHLUESSEL setzen (DPAPI-Datei) oder mit -OhneUnterschrift bauen" }
    if (-not (Test-Path $verpackt)) { throw "Signaturschlüssel fehlt: $verpackt" }
    $pemBytes = [Security.Cryptography.ProtectedData]::Unprotect([IO.File]::ReadAllBytes($verpackt), $null, "CurrentUser")
}
function Unterschreiben($datei) {
    if ($null -eq $pemBytes) { return }
    $p = New-Object Diagnostics.Process
    $p.StartInfo.FileName = "python"
    $p.StartInfo.Arguments = "-c `"import sys; sys.path.insert(0, r'$here'); import app_install; from pathlib import Path; z = Path(sys.argv[1]); s = app_install.signieren(z.read_bytes(), sys.stdin.buffer.read()); Path(str(z) + app_install.SIGNATUR_ENDUNG).write_text(s + chr(10), encoding='ascii')`" `"$datei`""
    $p.StartInfo.UseShellExecute = $false; $p.StartInfo.RedirectStandardInput = $true
    $p.Start() | Out-Null
    $p.StandardInput.BaseStream.Write($pemBytes, 0, $pemBytes.Length); $p.StandardInput.Close(); $p.WaitForExit()
    if ($p.ExitCode -ne 0) { throw "Unterschrift unter $(Split-Path $datei -Leaf) fehlgeschlagen" }
}
Unterschreiben $zip
Write-Host "Unterschrift Programm-ZIP: OK"
Unterschreiben $quelle
foreach ($h in $helfer) { Unterschreiben $h }
$bau = python -c "import sys; sys.path.insert(0, r'$here'); import app_core; print(app_core.APP_BUILD)"
[System.IO.File]::WriteAllText((Join-Path $dist "bau.txt"), "$bau`n")
$neuester = Join-Path $dist "neuester.txt"
[System.IO.File]::WriteAllText($neuester, "$bau $((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))`n")
Unterschreiben $neuester
$pemBytes = $null
Write-Host "Bau $bau. Fertig: $zip"
