param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")),
    [string]$JobPattern = "label_mixed_d20_15k_shard_",
    [string]$LabeledDir = "",
    [string]$MergedOut = "",
    [string]$WeightOut = "",
    [int]$Hidden = 128,
    [int]$Epochs = 80,
    [int]$BatchSize = 1024,
    [double]$LearningRate = 0.003,
    [int]$PollSeconds = 300,
    [string]$BootstrapPython = "",
    [string]$TrainVenv = ""
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path $Root).Path
Set-Location $Root
$env:PYTHONUNBUFFERED = "1"

if (-not $LabeledDir) {
    $LabeledDir = Join-Path $Root "data\labeled\mixed_2025_q1_hikaru_d20_15k_shards"
}
if (-not $MergedOut) {
    $MergedOut = Join-Path $Root "data\labeled\mixed_2025_q1_hikaru_d20_15k_merged.jsonl"
}
if (-not $WeightOut) {
    $WeightOut = Join-Path $Root "weights\mixed_2025_q1_hikaru_d20_15k_h128.nnue"
}
if (-not $BootstrapPython) {
    $candidate = Join-Path $Root "..\bot\venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $candidate) {
        $BootstrapPython = (Resolve-Path $candidate).Path
    } else {
        $BootstrapPython = "python"
    }
}
if (-not $TrainVenv) {
    $TrainVenv = Join-Path $Root ".venv"
}

$TrainPython = Join-Path $TrainVenv "Scripts\python.exe"

Write-Output "coordinator started: $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))"
Write-Output "root: $Root"
Write-Output "job pattern: $JobPattern"
Write-Output "labeled dir: $LabeledDir"

while ($true) {
    $running = Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and $_.CommandLine.Contains($JobPattern)
    }
    if (-not $running) {
        break
    }

    $flushed = 0
    if (Test-Path -LiteralPath $LabeledDir) {
        $sum = Get-ChildItem -LiteralPath $LabeledDir -Filter "*.jsonl" -ErrorAction SilentlyContinue |
            ForEach-Object { (Get-Content -LiteralPath $_.FullName | Measure-Object -Line).Lines } |
            Measure-Object -Sum
        if ($null -ne $sum.Sum) {
            $flushed = [int]$sum.Sum
        }
    }

    Write-Output "waiting labels: running_processes=$($running.Count) flushed_lines=$flushed time=$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))"
    Start-Sleep -Seconds $PollSeconds
}

Write-Output "label shards completed: $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))"
if (-not (Test-Path -LiteralPath $LabeledDir)) {
    throw "Missing labeled shard directory: $LabeledDir"
}

$inputs = Get-ChildItem -LiteralPath $LabeledDir -Filter "*.jsonl" | Sort-Object Name
if (-not $inputs) {
    throw "No labeled shard files found in $LabeledDir"
}

foreach ($input in $inputs) {
    $count = (Get-Content -LiteralPath $input.FullName | Measure-Object -Line).Lines
    Write-Output "$($input.Name): $count"
}

$inputPaths = $inputs | ForEach-Object { $_.FullName }
& $BootstrapPython .\tools\merge_positions.py --inputs $inputPaths --out $MergedOut --shuffle --seed 72
if ($LASTEXITCODE -ne 0) {
    throw "merge_positions.py failed with exit code $LASTEXITCODE"
}

if (-not (Test-Path -LiteralPath $TrainPython)) {
    python -m venv $TrainVenv
}

& $TrainPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "pip upgrade failed with exit code $LASTEXITCODE"
}

& $TrainPython -m pip install -r .\tools\requirements-training.txt
if ($LASTEXITCODE -ne 0) {
    throw "dependency install failed with exit code $LASTEXITCODE"
}

& $TrainPython .\tools\train_nnue.py `
    --input $MergedOut `
    --out $WeightOut `
    --hidden $Hidden `
    --epochs $Epochs `
    --batch-size $BatchSize `
    --lr $LearningRate `
    --activation-scale 16
if ($LASTEXITCODE -ne 0) {
    throw "train_nnue.py failed with exit code $LASTEXITCODE"
}

Write-Output "coordinator finished: $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))"
Write-Output "merged: $MergedOut"
Write-Output "weight: $WeightOut"
