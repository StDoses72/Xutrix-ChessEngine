$ErrorActionPreference = "Stop"

$runner = Join-Path $PSScriptRoot "run_lichess_bot.py"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")

$processes = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and (
        $_.CommandLine.Contains($runner) -or
        $_.CommandLine.Contains((Join-Path $root "c_engine\xutrix.exe"))
    )
}

if (-not $processes) {
    Write-Host "Xutrix Lichess bot is not running."
    exit 0
}

$processes | Select-Object ProcessId, ParentProcessId, Name, CommandLine | Format-List
