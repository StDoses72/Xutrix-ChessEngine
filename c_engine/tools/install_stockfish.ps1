$ErrorActionPreference = "Stop"

$stockfishUrl = "https://github.com/official-stockfish/Stockfish/releases/download/sf_18/stockfish-windows-x86-64-avx2.zip"
$installDir = Join-Path $PSScriptRoot "stockfish"
$zipPath = Join-Path $installDir "stockfish-windows-x86-64-avx2.zip"
$extractDir = Join-Path $installDir "extracted"
$targetExe = Join-Path $installDir "stockfish.exe"

New-Item -ItemType Directory -Force -Path $installDir | Out-Null

Write-Host "Downloading Stockfish from official release:"
Write-Host $stockfishUrl
Invoke-WebRequest -Uri $stockfishUrl -OutFile $zipPath

if (Test-Path $extractDir) {
    Remove-Item -LiteralPath $extractDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $extractDir | Out-Null

Expand-Archive -LiteralPath $zipPath -DestinationPath $extractDir -Force

$exe = Get-ChildItem -Path $extractDir -Recurse -Filter "*.exe" |
    Where-Object { $_.Name -like "stockfish*.exe" } |
    Select-Object -First 1

if (-not $exe) {
    throw "No stockfish executable found in downloaded archive."
}

Copy-Item -LiteralPath $exe.FullName -Destination $targetExe -Force

Write-Host "Installed Stockfish:"
Write-Host $targetExe
& $targetExe
