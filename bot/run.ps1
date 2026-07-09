$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$config = Join-Path $PSScriptRoot "config.yml"
$botDir = Join-Path $PSScriptRoot "lichess-bot"
$python = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
$runner = Join-Path $PSScriptRoot "run_lichess_bot.py"
$engine = Join-Path $root "c_engine\xutrix.exe"

if (-not (Test-Path -LiteralPath $config)) {
    throw "Missing bot\config.yml. Copy bot\config.xutrix.example.yml to bot\config.yml and add your Lichess bot token."
}

if (-not (Test-Path -LiteralPath $botDir)) {
    throw "Missing bot\lichess-bot. Clone https://github.com/lichess-bot-devs/lichess-bot.git into bot\lichess-bot."
}

if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing bot\venv. Create it with: python -m venv bot\venv"
}

if (-not (Test-Path -LiteralPath $engine)) {
    throw "Missing c_engine\xutrix.exe. Build it with: powershell -ExecutionPolicy Bypass -File c_engine\build.ps1"
}

if (-not (Test-Path -LiteralPath $runner)) {
    throw "Missing bot\run_lichess_bot.py."
}

& $python $runner
