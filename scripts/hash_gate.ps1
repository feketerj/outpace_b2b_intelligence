$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir

Write-Host "=== HASH GATE ==="
Write-Host "Timestamp: $([DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ'))"
Write-Host "Repo root: $RepoRoot"
Write-Host "Verifying artifacts via scripts/verify_hashes.py"
Write-Host ""

Set-Location $RepoRoot

try {
    python scripts/verify_hashes.py
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "=== HASH GATE: PASS ==="
        exit 0
    }
    throw "Verification failed"
} catch {
    Write-Host ""
    Write-Host "=== HASH GATE: FAIL ==="
    Write-Host "One or more artifacts failed integrity verification."
    exit 1
}
