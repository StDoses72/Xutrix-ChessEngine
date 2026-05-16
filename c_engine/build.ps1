$ErrorActionPreference = "Stop"

$sources = Get-ChildItem -Path "$PSScriptRoot\src" -Filter "*.c" | ForEach-Object { $_.FullName }
$out = Join-Path $PSScriptRoot "xutrix.exe"

if (Get-Command cl -ErrorAction SilentlyContinue) {
    cl /nologo /std:c11 /O2 /W4 /Fe:$out $sources
    exit $LASTEXITCODE
}

if (Get-Command gcc -ErrorAction SilentlyContinue) {
    gcc -std=c11 -O2 -Wall -Wextra -Wpedantic -o $out $sources
    exit $LASTEXITCODE
}

$msysGcc = "C:\msys64\ucrt64\bin\gcc.exe"
if (Test-Path $msysGcc) {
    $env:PATH = "C:\msys64\ucrt64\bin;" + $env:PATH
    & $msysGcc -std=c11 -O2 -Wall -Wextra -Wpedantic -o $out $sources
    exit $LASTEXITCODE
}

if (Get-Command clang -ErrorAction SilentlyContinue) {
    clang -std=c11 -O2 -Wall -Wextra -Wpedantic -o $out $sources
    exit $LASTEXITCODE
}

Write-Error "No C compiler found. Install Visual Studio Build Tools, MinGW-w64, or LLVM/Clang, then run this script again."
