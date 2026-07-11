$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
$runner = Join-Path $PSScriptRoot "run_lichess_bot.py"
$logDir = Join-Path $PSScriptRoot "logs"
$pidFile = Join-Path $PSScriptRoot "bot.pid"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing bot\venv. Create it with: python -m venv bot\venv"
}

if (-not (Test-Path -LiteralPath $runner)) {
    throw "Missing bot\run_lichess_bot.py."
}

$existing = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and $_.CommandLine.Contains($runner)
}

if ($existing) {
    $ids = ($existing | Select-Object -ExpandProperty ProcessId) -join ", "
    Write-Host "Xutrix Lichess bot is already running: $ids"
    exit 0
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$stdout = Join-Path $logDir "lichess-bot-$stamp.out.log"
$stderr = Join-Path $logDir "lichess-bot-$stamp.err.log"
$launchScript = Join-Path $logDir "lichess-bot-$stamp.launch.ps1"

$launchContent = @"
`$ErrorActionPreference = "Stop"
Set-Location -LiteralPath "$root"
`$env:PYTHONUNBUFFERED = "1"
& "$python" "$runner" 1>> "$stdout" 2>> "$stderr"
"@

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($launchScript, $launchContent, $utf8NoBom)

$commandLine = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$launchScript`""
$result = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = $commandLine
    CurrentDirectory = $root
}

if ($result.ReturnValue -ne 0) {
    throw "Failed to start Xutrix Lichess bot. Win32_Process.Create returned $($result.ReturnValue)."
}

Set-Content -LiteralPath $pidFile -Encoding ascii -Value $result.ProcessId
Write-Host "Started Xutrix Lichess bot. PID=$($result.ProcessId)"
Write-Host "stdout: $stdout"
Write-Host "stderr: $stderr"
