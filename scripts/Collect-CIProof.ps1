# CI Proof Collector for GitHub Actions
# ======================================
# Usage: .\Collect-CIProof.ps1 -Repo "owner/repo" [-RunId "123456"] [-OutDir "C:\path"]
#
# If RunId is omitted, uses the latest workflow run.
# Outputs are written to Desktop by default.

param(
    [Parameter(Mandatory=$true)]
    [string]$Repo,
    
    [Parameter(Mandatory=$false)]
    [string]$RunId,
    
    [Parameter(Mandatory=$false)]
    [string]$OutDir = "$env:USERPROFILE\Desktop"
)

$ErrorActionPreference = "Stop"

# Ensure output directory exists
if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

Write-Host ""
Write-Host "========================================================================"
Write-Host "CI PROOF COLLECTOR"
Write-Host "========================================================================"
Write-Host ""
Write-Host "Repository: $Repo"
Write-Host "Output Dir: $OutDir"
Write-Host "Timestamp:  $timestamp"
Write-Host ""

# Get run ID if not provided
if (-not $RunId) {
    Write-Host "Fetching latest workflow run..."
    $latestRun = gh run list --repo $Repo --limit 1 --json databaseId,status,conclusion,name,headBranch | ConvertFrom-Json
    if (-not $latestRun -or $latestRun.Count -eq 0) {
        Write-Host "ERROR: No workflow runs found."
        Read-Host "Press Enter to exit"
        exit 1
    }
    $RunId = $latestRun[0].databaseId
    Write-Host "Latest run ID: $RunId"
    Write-Host "Workflow:      $($latestRun[0].name)"
    Write-Host "Branch:        $($latestRun[0].headBranch)"
    Write-Host "Status:        $($latestRun[0].status)"
    Write-Host "Conclusion:    $($latestRun[0].conclusion)"
}

Write-Host ""
Write-Host "Fetching run details for ID: $RunId"

# Get run details
$runJson = gh run view $RunId --repo $Repo --json databaseId,status,conclusion,name,jobs,url,createdAt,updatedAt
$run = $runJson | ConvertFrom-Json

$runUrl = $run.url
$runStatus = $run.status
$runConclusion = $run.conclusion
$runName = $run.name

Write-Host "Run URL:    $runUrl"
Write-Host "Status:     $runStatus"
Write-Host "Conclusion: $runConclusion"
Write-Host ""

# Determine success or failure path
if ($runConclusion -eq "success") {
    Write-Host "========================================================================"
    Write-Host "SUCCESS PATH: Collecting proof evidence"
    Write-Host "========================================================================"
    Write-Host ""
    
    # Download logs
    $logFile = "$OutDir\ci_run_${RunId}_${timestamp}.log"
    Write-Host "Downloading logs to: $logFile"
    gh run view $RunId --repo $Repo --log > $logFile 2>&1
    
    # Search for canonical proof strings
    Write-Host ""
    Write-Host "Searching for canonical proof strings..."
    
    $logContent = Get-Content $logFile -Raw
    
    # Find SYNC-02 line
    $sync02Lines = Select-String -Path $logFile -Pattern "SYNC-02: admin_sync_returns_full_contract" | Select-Object -First 2
    $sync02Count = ($logContent | Select-String -Pattern "SYNC-02: admin_sync_returns_full_contract" -AllMatches).Matches.Count
    
    # Find Marker Gate line
    $markerGateLines = Select-String -Path $logFile -Pattern "MARKER GATE PASSED: tenant=" | Select-Object -First 1
    
    # List artifacts
    Write-Host ""
    Write-Host "Fetching artifacts..."
    $artifactsJson = gh run view $RunId --repo $Repo --json artifacts
    $artifacts = ($artifactsJson | ConvertFrom-Json).artifacts
    
    $hasMarkerArtifact = $false
    $hasCarfaxArtifact = $false
    foreach ($art in $artifacts) {
        if ($art.name -eq "sync-contract-marker") { $hasMarkerArtifact = $true }
        if ($art.name -eq "carfax-reports") { $hasCarfaxArtifact = $true }
    }
    
    # Build evidence block
    $evidenceFile = "$OutDir\CI_EVIDENCE_${RunId}_${timestamp}.txt"
    
    $evidenceBlock = @"
CI EVIDENCE
-----------
Run URL:
$runUrl

SYNC-02 Log Line:
$($sync02Lines | ForEach-Object { $_.Line.Trim() } | Select-Object -First 1)

SYNC-02 Count: $sync02Count

Marker Gate Log Line:
$($markerGateLines | ForEach-Object { $_.Line.Trim() } | Select-Object -First 1)

Artifacts:
- sync-contract-marker: $(if ($hasMarkerArtifact) { "PRESENT" } else { "ABSENT" })
- carfax-reports: $(if ($hasCarfaxArtifact) { "PRESENT" } else { "ABSENT" })

DECISION:
$(if ($sync02Count -eq 1 -and $markerGateLines -and $hasMarkerArtifact -and $hasCarfaxArtifact) { "DEPLOY-READY" } else { "NOT DEPLOY-READY" })

Validation:
- SYNC-02 count = 1: $(if ($sync02Count -eq 1) { "PASS" } else { "FAIL (count=$sync02Count)" })
- Marker gate present: $(if ($markerGateLines) { "PASS" } else { "FAIL" })
- sync-contract-marker artifact: $(if ($hasMarkerArtifact) { "PASS" } else { "FAIL" })
- carfax-reports artifact: $(if ($hasCarfaxArtifact) { "PASS" } else { "FAIL" })
"@
    
    # Write to file
    $evidenceBlock | Out-File -FilePath $evidenceFile -Encoding UTF8
    
    Write-Host ""
    Write-Host "========================================================================"
    Write-Host "EVIDENCE WRITTEN TO: $evidenceFile"
    Write-Host "========================================================================"
    Write-Host ""
    Write-Host $evidenceBlock
    Write-Host ""
    Write-Host "========================================================================"
    Write-Host "PASTE THE ABOVE CI EVIDENCE BLOCK TO THE AGENT"
    Write-Host "========================================================================"
    
} else {
    Write-Host "========================================================================"
    Write-Host "FAILURE PATH: Collecting triage evidence"
    Write-Host "========================================================================"
    Write-Host ""
    
    # Download logs
    $logFile = "$OutDir\ci_run_${RunId}_${timestamp}_FAILED.log"
    Write-Host "Downloading logs to: $logFile"
    gh run view $RunId --repo $Repo --log > $logFile 2>&1
    
    # Find failed jobs
    $failedJobs = $run.jobs | Where-Object { $_.conclusion -eq "failure" }
    
    # Build failure summary
    $summaryFile = "$OutDir\ci_run_${RunId}_${timestamp}_FAILED_summary.txt"
    
    $summaryBlock = @"
FAILED RUN SUMMARY
==================
Run URL: $runUrl
Run ID: $RunId
Workflow: $runName
Status: $runStatus
Conclusion: $runConclusion

FAILED JOBS:
"@
    
    foreach ($job in $failedJobs) {
        $summaryBlock += "`n  Job: $($job.name)"
        $summaryBlock += "`n  Conclusion: $($job.conclusion)"
        
        # Get failed steps
        $failedSteps = $job.steps | Where-Object { $_.conclusion -eq "failure" }
        foreach ($step in $failedSteps) {
            $summaryBlock += "`n  Failed Step: $($step.name)"
            $summaryBlock += "`n  Step Conclusion: $($step.conclusion)"
        }
        $summaryBlock += "`n"
    }
    
    $summaryBlock += @"

LOG TAIL (last 100 lines):
==========================
"@
    
    # Get last 100 lines of log
    $logTail = Get-Content $logFile -Tail 100
    $summaryBlock += "`n" + ($logTail -join "`n")
    
    # Write summary
    $summaryBlock | Out-File -FilePath $summaryFile -Encoding UTF8
    
    Write-Host ""
    Write-Host "========================================================================"
    Write-Host "FAILURE SUMMARY WRITTEN TO: $summaryFile"
    Write-Host "FULL LOG WRITTEN TO: $logFile"
    Write-Host "========================================================================"
    Write-Host ""
    Write-Host $summaryBlock
    Write-Host ""
    Write-Host "========================================================================"
    Write-Host "RERUN COMMAND:"
    Write-Host "  gh run rerun $RunId --repo $Repo --failed"
    Write-Host ""
    Write-Host "PASTE THE ABOVE FAILURE SUMMARY TO THE AGENT"
    Write-Host "========================================================================"
}

Write-Host ""
Read-Host "Press Enter to exit"
