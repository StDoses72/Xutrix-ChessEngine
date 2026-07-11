$ErrorActionPreference = "Continue"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$runner = Join-Path $PSScriptRoot "run_lichess_bot.py"
$engine = Join-Path $root "c_engine\xutrix.exe"
$pidFile = Join-Path $PSScriptRoot "bot.pid"

$all = Get-CimInstance Win32_Process
$ids = New-Object System.Collections.Generic.HashSet[int]

if (Test-Path -LiteralPath $pidFile) {
    $pidText = (Get-Content -Raw -LiteralPath $pidFile).Trim()
    if ($pidText -match '^\d+$') {
        $pidProcess = $all | Where-Object { $_.ProcessId -eq [int]$pidText } | Select-Object -First 1
        if ($pidProcess -and $pidProcess.CommandLine -and (
            $pidProcess.CommandLine.Contains($runner) -or
            $pidProcess.CommandLine.Contains($engine)
        )) {
            [void]$ids.Add([int]$pidText)
        }
    }
}

foreach ($process in $all) {
    if ($process.CommandLine -and (
        $process.CommandLine.Contains($runner) -or
        $process.CommandLine.Contains($engine)
    )) {
        [void]$ids.Add([int]$process.ProcessId)
    }
}

$changed = $true
while ($changed) {
    $changed = $false
    foreach ($process in $all) {
        if (-not $ids.Contains([int]$process.ParentProcessId) -or $ids.Contains([int]$process.ProcessId)) {
            continue
        }

        $name = [System.IO.Path]::GetFileName($process.Name)
        $cmd = $process.CommandLine
        $isBotChild = $cmd -and (
            $cmd.Contains($runner) -or
            $cmd.Contains($engine) -or
            ($name -in @("python.exe", "python") -and (
                $cmd.Contains("bot\venv\Scripts\python.exe") -or
                $cmd.Contains("multiprocessing.spawn")
            ))
        )

        if ($isBotChild) {
            [void]$ids.Add([int]$process.ProcessId)
            $changed = $true
        }
    }
}

if ($ids.Count -eq 0) {
    Write-Host "Xutrix Lichess bot is not running."
    exit 0
}

foreach ($id in ($ids | Sort-Object -Descending)) {
    try {
        $process = Get-Process -Id $id -ErrorAction Stop
        Write-Host "Stopping PID=$id NAME=$($process.ProcessName)"
        Stop-Process -Id $id -Force -ErrorAction Stop
    } catch {
        Write-Host "PID=$id already stopped."
    }
}

Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
Write-Host "Stopped Xutrix Lichess bot."
