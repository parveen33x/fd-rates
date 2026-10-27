<#
.SYNOPSIS
    Autonomous FD Rate Sync - Sheet First Review Workflow
.DESCRIPTION
    Strict 2-Stage Process:
    Stage 1: Crawls official sources, normalizes tenures, calculates diffs, and updates Google Sheet.
    Stage 2: Stops completely and presents the Google Sheet link for User Review.
    Stage 3: Strapi CMS is ONLY updated when explicitly instructed by the user after reviewing the sheet.
#>
param(
    [string]$TargetBank = $null
)

$ErrorActionPreference = 'Stop'
$rootDir = "C:\Users\parveen.kumar\.gemini\antigravity\scratch\fd_rate_sync_engine"
$diffScript = Join-Path $rootDir "src\compare_and_diff.ps1"
$sheetScript = Join-Path $rootDir "src\sync_sheets.ps1"
$diffDataPath = Join-Path $rootDir "data\diff_summary.json"
$configPath = Join-Path $rootDir "config\banks_config.json"
$sheetUrl = "https://docs.google.com/spreadsheets/d/1oeSytWn5llasTaoYlqZp7DiPNA5-_xylB-4hPKAFzEY/edit"

Write-Host "`n=================================================================" -ForegroundColor Cyan
Write-Host "   AUTONOMOUS FD RATE SYNC (SHEET-FIRST REVIEW PROCESS)          " -ForegroundColor Cyan
Write-Host "=================================================================`n" -ForegroundColor Cyan

# Step 1: Normalization & Diffing
Write-Host "[Step 1/2] Crawling Official Sources & Calculating Rate Diffs..." -ForegroundColor Yellow
& powershell -ExecutionPolicy Bypass -File $diffScript

$diff = Get-Content $diffDataPath -Raw -Encoding UTF8 | ConvertFrom-Json
$config = Get-Content $configPath -Raw -Encoding UTF8 | ConvertFrom-Json

# Step 2: Google Sheets Synchronization
Write-Host "`n[Step 2/2] Syncing All Comparison Tables to Google Sheet..." -ForegroundColor Yellow
& powershell -ExecutionPolicy Bypass -File $sheetScript

Write-Host "`n=================================================================" -ForegroundColor Green
Write-Host "   STAGE 1 COMPLETE: GOOGLE SHEET IS FULLY UPDATED & READY!      " -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Green
Write-Host "Total Banks Monitored : $($diff.totalBanks)"
Write-Host "Banks with Changes    : $($diff.banksWithChanges.Count)"
Write-Host "Total Rate Hikes      : $($diff.totalHikes) (Green Rows in Sheet)" -ForegroundColor Green
Write-Host "Total Rate Cuts       : $($diff.totalCuts) (Red Rows in Sheet)" -ForegroundColor Red
Write-Host "New Special Slabs     : $($diff.totalNewSlabs) (Yellow Rows in Sheet)" -ForegroundColor Yellow
Write-Host "`n>> REVIEW LINK: $sheetUrl" -ForegroundColor Cyan

Write-Host "`nChanged Banks List:" -ForegroundColor White
foreach ($bName in $diff.banksWithChanges) {
    $cfg = $config | Where-Object { $_.bankName -eq $bName }
    $sId = if ($cfg) { "Strapi ID: $($cfg.strapiId)" } else { "No Strapi ID" }
    Write-Host "  * $bName ($sId)" -ForegroundColor Gray
}

Write-Host "`n-----------------------------------------------------------------" -ForegroundColor Yellow
Write-Host "   POLICY: NO CHANGES HAVE BEEN MADE TO STRAPI CMS.             " -ForegroundColor Yellow
Write-Host "   Next Step: Please review the Google Sheet tabs above.         " -ForegroundColor Yellow
Write-Host "   Whenever you approve a bank, instruct the agent to sync it!   " -ForegroundColor Yellow
Write-Host "-----------------------------------------------------------------`n" -ForegroundColor Yellow
