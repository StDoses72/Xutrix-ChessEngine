$ErrorActionPreference = "Stop"

powershell -ExecutionPolicy Bypass -File "$PSScriptRoot\build.ps1"

$cases = @(
    @{ Depth = 1; Fen = ""; Expected = "20" },
    @{ Depth = 2; Fen = ""; Expected = "400" },
    @{ Depth = 3; Fen = ""; Expected = "8902" },
    @{ Depth = 4; Fen = ""; Expected = "197281" },
    @{ Depth = 1; Fen = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"; Expected = "48" },
    @{ Depth = 2; Fen = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"; Expected = "2039" },
    @{ Depth = 3; Fen = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"; Expected = "97862" }
)

foreach ($case in $cases) {
    if ($case.Fen) {
        $output = & "$PSScriptRoot\xutrix.exe" perft $case.Depth $case.Fen
    } else {
        $output = & "$PSScriptRoot\xutrix.exe" perft $case.Depth
    }
    $firstLine = ($output | Select-Object -First 1)
    if ($firstLine -notmatch "= $($case.Expected)$") {
        Write-Error "Perft failed for depth $($case.Depth). Expected $($case.Expected), got: $firstLine"
    }
    Write-Host "ok depth $($case.Depth): $($case.Expected)"
}

$best = & "$PSScriptRoot\xutrix.exe" best 3
if (($best | Select-Object -First 1) -notmatch "^bestmove [a-h][1-8][a-h][1-8][qrbn]?$") {
    Write-Error "Search smoke test failed: $($best | Select-Object -First 1)"
}
Write-Host "ok search smoke"
