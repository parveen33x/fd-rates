<#
.SYNOPSIS
    Autonomous FD Rate Sync - Sheet First Review Workflow
.DESCRIPTION
    Runs the Unified Python Scraper Suite:
    1. Crawls live official bank portals & ET Money tables.
    2. Normalizes tenures, calculates rate diffs, detects content contradictions.
    3. Syncs color-coded comparison tables to Google Sheets.
    4. Stops for human review (Strapi CMS is NEVER touched automatically).
#>
param(
    [switch]$SyncSheets = $true,
    [int]$Limit = 0
)

$ErrorActionPreference = 'Stop'
$rootDir = $PSScriptRoot
$pythonExe = "C:\Users\parveen.kumar\AppData\Local\Programs\Python\Python312\python.exe"

if (-not (Test-Path $pythonExe)) {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        $pythonExe = $pythonCmd.Source
    } else {
        Write-Error "Python executable not found. Please install Python 3.12."
        exit 1
    }
}

Set-Location $rootDir
$env:PYTHONPATH = $rootDir
$env:PYTHONUNBUFFERED = "1"

$argsList = @("src/cloud_sync.py")

Write-Host "`n=================================================================" -ForegroundColor Cyan
Write-Host "   RUNNING UNIFIED PYTHON FD RATE CRAWLER (STAGE 1)              " -ForegroundColor Cyan
Write-Host "=================================================================`n" -ForegroundColor Cyan

& $pythonExe $argsList

Write-Host "`n-----------------------------------------------------------------" -ForegroundColor Yellow
Write-Host "   STAGE 1 COMPLETE: Google Sheet & HTML Reports are Ready!      " -ForegroundColor Green
Write-Host "   POLICY: Strapi CMS was NOT modified automatically.            " -ForegroundColor Yellow
Write-Host "   Review link: https://docs.google.com/spreadsheets/d/1oeSytWn5llasTaoYlqZp7DiPNA5-_xylB-4hPKAFzEY/edit" -ForegroundColor Cyan
Write-Host "-----------------------------------------------------------------`n" -ForegroundColor Yellow
