$ErrorActionPreference = "Stop"

$gccDir = "C:\msys64\ucrt64\bin"
$windowsApps = Join-Path $env:USERPROFILE "AppData\Local\Microsoft\WindowsApps"
$scope = "User"
$old = [Environment]::GetEnvironmentVariable("Path", $scope)

$parts = @()
if ($old) {
    foreach ($part in @($old -split ";" | Where-Object { $_ -and $_.Trim() })) {
        if ($part.Contains($windowsApps) -and $part.Contains($gccDir)) {
            $parts += $windowsApps
            $parts += $gccDir
        } else {
            $parts += $part
        }
    }
}

$normalized = @()
$hasGcc = $false
foreach ($part in $parts) {
    $clean = $part.Trim().TrimEnd("\")
    if (-not $clean) {
        continue
    }
    if ($clean -ieq $gccDir) {
        $hasGcc = $true
    }
    if ($normalized -notcontains $clean) {
        $normalized += $clean
    }
}

if (-not $hasGcc) {
    $normalized += $gccDir
    Write-Output "added: $gccDir"
} else {
    Write-Output "already present: $gccDir"
}

$newPath = $normalized -join ";"
[Environment]::SetEnvironmentVariable("Path", $newPath, $scope)
Write-Output ([Environment]::GetEnvironmentVariable("Path", $scope))
