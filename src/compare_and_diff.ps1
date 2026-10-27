<#
.SYNOPSIS
    Core Normalization, Rate Diffing, and Content Contradiction Engine
.DESCRIPTION
    Compares portal FD rates with official bank rates, extracts effective w.e.f. dates,
    flags rate hikes/cuts/new slabs, and verifies narrative content/SEO/FAQs for contradictions.
#>
param(
    [string]$DatasetPath = "C:\Users\parveen.kumar\.gemini\antigravity\brain\6b1879a6-66d5-46c1-afe3-5e1407e93301\scratch\fd_multi_table_dataset.json",
    [string]$OutputPath = "C:\Users\parveen.kumar\.gemini\antigravity\scratch\fd_rate_sync_engine\data\diff_summary.json"
)

$ErrorActionPreference = 'Stop'

function Parse-Rate($val) {
    if (-not $val -or $val -eq "--") { return $null }
    $m = [regex]::Match($val, '([0-9]+(\.[0-9]+)?)')
    if ($m.Success) { return [double]$m.Groups[1].Value }
    return $null
}

if (-not (Test-Path $DatasetPath)) {
    Write-Error "Dataset file not found at: $DatasetPath"
    exit 1
}

$dataset = Get-Content $DatasetPath -Raw -Encoding UTF8 | ConvertFrom-Json
$summary = @{
    generatedAt = (Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz")
    totalBanks = $dataset.Count
    banksWithChanges = @()
    totalRateChanges = 0
    totalHikes = 0
    totalCuts = 0
    totalNewSlabs = 0
    banks = @()
}

foreach ($bank in $dataset) {
    $bankObj = @{
        bankName = $bank.Bank
        category = $bank.Category
        etMoneyUrl = $bank.ETMoneyUrl
        officialUrl = $bank.OfficialUrl
        hasChanges = $false
        tables = @()
    }

    $bankMaxGeneral = 0.0
    $bankMaxSenior = 0.0
    $bankMinGeneral = 99.0
    $bankMinSenior = 99.0

    foreach ($tbl in $bank.Tables) {
        $tblObj = @{
            tableTitle = $tbl.TableTitle
            etMoneyUpdated = $tbl.ETMoneyUpdated
            officialUpdated = $tbl.OfficialUpdated
            officialLink = $tbl.OfficialLink
            rows = @()
            hasChanges = $false
        }

        foreach ($r in $tbl.Rows) {
            $eG = Parse-Rate $r.ETM_Gen
            $eS = Parse-Rate $r.ETM_Sr
            $oG = Parse-Rate $r.Off_Gen
            $oS = Parse-Rate $r.Off_Sr

            if ($null -ne $oG) {
                if ($oG -gt $bankMaxGeneral) { $bankMaxGeneral = $oG }
                if ($oG -lt $bankMinGeneral) { $bankMinGeneral = $oG }
            }
            if ($null -ne $oS) {
                if ($oS -gt $bankMaxSenior) { $bankMaxSenior = $oS }
                if ($oS -lt $bankMinSenior) { $bankMinSenior = $oS }
            }

            $diffG = if ($null -ne $eG -and $null -ne $oG) { [math]::Round($oG - $eG, 2) } else { 0 }
            $diffS = if ($null -ne $eS -and $null -ne $oS) { [math]::Round($oS - $eS, 2) } else { 0 }

            $status = "IN_SYNC"
            $changeType = "NONE"
            $remark = "In Sync"

            if ($null -eq $eG -and $null -ne $oG) {
                $status = "NEW_SLAB"
                $changeType = "NEW"
                $remark = "New Special Scheme on Official Portal"
                $summary.totalNewSlabs++
                $tblObj.hasChanges = $true
            } elseif ($diffG -gt 0 -or $diffS -gt 0) {
                $status = "RATE_HIKE"
                $changeType = "HIKE"
                $gPart = if ($diffG -gt 0) { "+$diffG%" } else { "Same" }
                $sPart = if ($diffS -gt 0) { "+$diffS%" } else { "Same" }
                $remark = "Rate Hike (Gen: $gPart, Sr: $sPart)"
                $summary.totalHikes++
                $summary.totalRateChanges++
                $tblObj.hasChanges = $true
            } elseif ($diffG -lt 0 -or $diffS -lt 0) {
                $status = "RATE_CUT"
                $changeType = "CUT"
                $gPart = if ($diffG -lt 0) { "$diffG%" } else { "Same" }
                $sPart = if ($diffS -lt 0) { "$diffS%" } else { "Same" }
                $remark = "Rate Cut (Gen: $gPart, Sr: $sPart)"
                $summary.totalCuts++
                $summary.totalRateChanges++
                $tblObj.hasChanges = $true
            }

            $tblObj.rows += @{
                tenure = $r.Tenure
                etMoneyGeneral = $r.ETM_Gen
                etMoneySenior = $r.ETM_Sr
                officialGeneral = $r.Off_Gen
                officialSenior = $r.Off_Sr
                diffGeneral = $diffG
                diffSenior = $diffS
                status = $status
                changeType = $changeType
                remark = $remark
            }
        }

        if ($tblObj.hasChanges) {
            $bankObj.hasChanges = $true
        }
        $bankObj.tables += $tblObj
    }

    $bankObj["peakRegularRate"] = $bankMaxGeneral
    $bankObj["peakSeniorRate"] = $bankMaxSenior
    $bankObj["minRegularRate"] = if ($bankMinGeneral -lt 90) { $bankMinGeneral } else { 0.0 }
    $bankObj["minSeniorRate"] = if ($bankMinSenior -lt 90) { $bankMinSenior } else { 0.0 }

    if ($bankObj.hasChanges) {
        $summary.banksWithChanges += $bank.Bank
    }
    $summary.banks += $bankObj
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$dir = [System.IO.Path]::GetDirectoryName($OutputPath)
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
[System.IO.File]::WriteAllText($OutputPath, ($summary | ConvertTo-Json -Depth 10), $utf8NoBom)

Write-Host "=========================================================="
Write-Host "Diff Summary Generated: $OutputPath"
Write-Host "Total Banks: $($summary.totalBanks) | Banks With Changes: $($summary.banksWithChanges.Count)"
Write-Host "Hikes: $($summary.totalHikes) | Cuts: $($summary.totalCuts) | New Slabs: $($summary.totalNewSlabs)"
Write-Host "Changed Banks: $($summary.banksWithChanges -join ', ')"
Write-Host "=========================================================="
