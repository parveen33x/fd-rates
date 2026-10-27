$spreadsheetId = "1oeSytWn5llasTaoYlqZp7DiPNA5-_xylB-4hPKAFzEY"
$jsonPath = Join-Path $PSScriptRoot "..\data\fd_multi_table_dataset.json"
if (-not (Test-Path $jsonPath)) {
    $jsonPath = "C:\Users\parveen.kumar\.gemini\antigravity\brain\6b1879a6-66d5-46c1-afe3-5e1407e93301\scratch\fd_multi_table_dataset.json"
}
$data = Get-Content $jsonPath -Raw -Encoding UTF8 | ConvertFrom-Json

function Normalize-Rate($val) {
    if (-not $val) { return $null }
    $m = [regex]::Match($val, '([0-9]+(\.[0-9]+)?)')
    if ($m.Success) { return [double]$m.Groups[1].Value }
    return $null
}

$sheetList = & gsheets readonly list-sheets $spreadsheetId --json | ConvertFrom-Json
$sheetIdMap = @{}
foreach ($s in $sheetList) {
    $sheetIdMap[$s.title] = $s.id
}

$batchOps = @()
$formatRequests = @()

# Helper to create repeatCell request
function New-RepeatCell($sheetId, $startRow, $endRow, $startCol, $endCol, $bgR, $bgG, $bgB, $fgR, $fgG, $fgB, $bold) {
    return @{
        repeatCell = @{
            range = @{
                sheetId = $sheetId
                startRowIndex = $startRow
                endRowIndex = $endRow
                startColumnIndex = $startCol
                endColumnIndex = $endCol
            }
            cell = @{
                userEnteredFormat = @{
                    backgroundColor = @{ red = $bgR; green = $bgG; blue = $bgB }
                    textFormat = @{
                        foregroundColor = @{ red = $fgR; green = $fgG; blue = $fgB }
                        bold = $bold
                    }
                }
            }
            fields = "userEnteredFormat(backgroundColor,textFormat)"
        }
    }
}

# 1. Build Master Sheet ("fd_rates_comparison_2026")
$masterId = $sheetIdMap["fd_rates_comparison_2026"]
$masterMatrix = @()
$masterMatrix += ,@(
    "Status", "Change Details", "Bank / NBFC Name", "Table Name / Deposit Tier",
    "ET Money Table Heading", "Official Update Date (w.e.f.)", "Tenure / Scheme",
    "ET Money General Rate", "ET Money Senior Rate", "Official General Rate",
    "Official Senior Rate", "Verified Official URL"
)

# Clear existing Master and Bank tabs first in batchOps
$batchOps += @{ op = "clear"; range = "fd_rates_comparison_2026!A1:Z500" }

# Reset Master background formatting first
if ($null -ne $masterId) {
    $formatRequests += New-RepeatCell $masterId 0 400 0 12 1.0 1.0 1.0 0.118 0.161 0.231 $false
    # Header row (Row 0): Dark Green #10663F
    $formatRequests += New-RepeatCell $masterId 0 1 0 12 0.063 0.40 0.247 1.0 1.0 1.0 $true
    $formatRequests += @{
        updateSheetProperties = @{
            properties = @{
                sheetId = $masterId
                gridProperties = @{ frozenRowCount = 1 }
            }
            fields = "gridProperties.frozenRowCount"
        }
    }
}

$masterRowIdx = 1
$csvExportRows = @()

foreach ($b in $data) {
    $tabName = $b.Bank
    $sId = $sheetIdMap[$tabName]
    
    $batchOps += @{ op = "clear"; range = "'$tabName'!A1:Z200" }
    if ($null -ne $sId) {
        # Clear formatting on Bank Tab first
        $formatRequests += New-RepeatCell $sId 0 200 0 6 1.0 1.0 1.0 0.118 0.161 0.231 $false
    }
    
    $bankMatrix = @()
    # Row 0: Bank Main Banner
    $bankMatrix += ,@("$($b.Bank) - Fixed Deposit Interest Rates Comparison (ET Money vs Official Website)", "", "", "", "", "")
    # Row 1: Links and Category
    $bankMatrix += ,@("Category: $($b.Category)", "Total Rate Tables: $($b.Tables.Count)", "ET Money URL:", $b.ETMoneyUrl, "Verified Official Portal:", $b.OfficialUrl)
    # Row 2: Blank spacer
    $bankMatrix += ,@("", "", "", "", "", "")
    
    if ($null -ne $sId) {
        # Format Row 0 (Main Banner): Dark Teal #064E3B
        $formatRequests += New-RepeatCell $sId 0 1 0 6 0.024 0.306 0.231 1.0 1.0 1.0 $true
        # Format Row 1 (Links bar): Light Slate #F1F5F9
        $formatRequests += New-RepeatCell $sId 1 2 0 6 0.945 0.961 0.976 0.118 0.161 0.231 $true
        # Freeze top 2 rows
        $formatRequests += @{
            updateSheetProperties = @{
                properties = @{
                    sheetId = $sId
                    gridProperties = @{ frozenRowCount = 2 }
                }
                fields = "gridProperties.frozenRowCount"
            }
        }
    }
    
    $currentRow = 3
    
    # Render each table separately!
    for ($tIdx = 0; $tIdx -lt $b.Tables.Count; $tIdx++) {
        $tbl = $b.Tables[$tIdx]
        
        # Table Section Title Row
        $bankMatrix += ,@($tbl.TableTitle, "", "", "", "", "")
        if ($null -ne $sId) {
            # Deep Blue/Slate Banner #1E3A8A -> (0.118, 0.227, 0.541), White Bold
            $formatRequests += New-RepeatCell $sId $currentRow ($currentRow + 1) 0 6 0.118 0.227 0.541 1.0 1.0 1.0 $true
        }
        $currentRow++
        
        # Table Update Date & Link Row
        $bankMatrix += ,@($tbl.ETMoneyUpdated, "", $tbl.OfficialUpdated, "", "Official Table Link:", $tbl.OfficialLink)
        if ($null -ne $sId) {
            # Soft Blue Info Bar #E0F2FE -> (0.878, 0.949, 0.996), Dark Blue Bold (0.012, 0.412, 0.631)
            $formatRequests += New-RepeatCell $sId $currentRow ($currentRow + 1) 0 6 0.878 0.949 0.996 0.012 0.412 0.631 $true
        }
        $currentRow++
        
        # Table Column Headers Row
        $bankMatrix += ,@("Deposit Tenure / Scheme", "ET Money (General)", "ET Money (Senior)", "Official Rate (General)", "Official Rate (Senior)", "Change / Highlight Status")
        if ($null -ne $sId) {
            # Dark Green Header #10663F -> (0.063, 0.40, 0.247), White Bold
            $formatRequests += New-RepeatCell $sId $currentRow ($currentRow + 1) 0 6 0.063 0.40 0.247 1.0 1.0 1.0 $true
        }
        $currentRow++
        
        # Table Data Rows
        foreach ($r in $tbl.Rows) {
            $statusStr = "No Change (In Sync)"
            $statusType = "Match"
            
            if ($r.ETM_Gen -eq "--" -or -not $r.ETM_Gen) {
                $statusStr = "NEW SPECIAL SCHEME (Official Portal)"
                $statusType = "New Scheme"
            } else {
                $eG = Normalize-Rate $r.ETM_Gen
                $oG = Normalize-Rate $r.Off_Gen
                $eS = Normalize-Rate $r.ETM_Sr
                $oS = Normalize-Rate $r.Off_Sr
                $diffG = if ($eG -ne $null -and $oG -ne $null) { [math]::Round($oG - $eG, 2) } else { 0 }
                $diffS = if ($eS -ne $null -and $oS -ne $null) { [math]::Round($oS - $eS, 2) } else { 0 }
                
                $gPart = if ($diffG -gt 0) { "+$diffG%" } elseif ($diffG -lt 0) { "$diffG%" } else { "Same" }
                $sPart = if ($diffS -gt 0) { "+$diffS%" } elseif ($diffS -lt 0) { "$diffS%" } else { "Same" }
                
                if ($diffG -gt 0 -or $diffS -gt 0) {
                    $statusStr = "HIGHER ON OFFICIAL (Gen: $gPart, Sr: $sPart)"
                    $statusType = "Rate Hike"
                } elseif ($diffG -lt 0 -or $diffS -lt 0) {
                    $statusStr = "LOWER ON OFFICIAL (Gen: $gPart, Sr: $sPart)"
                    $statusType = "Rate Cut"
                }
            }
            
            # Add to Bank Tab matrix
            $bankMatrix += ,@($r.Tenure, $r.ETM_Gen, $r.ETM_Sr, $r.Off_Gen, $r.Off_Sr, $statusStr)
            
            # Highlight on Bank Tab
            if ($null -ne $sId) {
                if ($statusType -eq "Rate Hike") {
                    $formatRequests += New-RepeatCell $sId $currentRow ($currentRow + 1) 0 6 0.863 0.988 0.906 0.082 0.502 0.239 $true
                } elseif ($statusType -eq "Rate Cut") {
                    $formatRequests += New-RepeatCell $sId $currentRow ($currentRow + 1) 0 6 0.996 0.886 0.886 0.725 0.11 0.11 $true
                } elseif ($statusType -eq "New Scheme") {
                    $formatRequests += New-RepeatCell $sId $currentRow ($currentRow + 1) 0 6 0.996 0.953 0.78 0.706 0.325 0.035 $true
                }
            }
            $currentRow++
            
            # Add to Master Sheet matrix
            $masterMatrix += ,@(
                $statusType, $statusStr, $b.Bank, $tbl.TableTitle,
                $tbl.ETMoneyUpdated, $tbl.OfficialUpdated, $r.Tenure,
                $r.ETM_Gen, $r.ETM_Sr, $r.Off_Gen, $r.Off_Sr, $tbl.OfficialLink
            )
            
            # Highlight on Master Sheet
            if ($null -ne $masterId) {
                if ($statusType -eq "Rate Hike") {
                    $formatRequests += New-RepeatCell $masterId $masterRowIdx ($masterRowIdx + 1) 0 12 0.863 0.988 0.906 0.082 0.502 0.239 $true
                } elseif ($statusType -eq "Rate Cut") {
                    $formatRequests += New-RepeatCell $masterId $masterRowIdx ($masterRowIdx + 1) 0 12 0.996 0.886 0.886 0.725 0.11 0.11 $true
                } elseif ($statusType -eq "New Scheme") {
                    $formatRequests += New-RepeatCell $masterId $masterRowIdx ($masterRowIdx + 1) 0 12 0.996 0.953 0.78 0.706 0.325 0.035 $true
                }
            }
            $masterRowIdx++
            
            $csvExportRows += [PSCustomObject]@{
                "Status" = $statusType
                "Change Details" = $statusStr
                "Bank / NBFC Name" = $b.Bank
                "Table Name / Deposit Tier" = $tbl.TableTitle
                "ET Money Table Heading" = $tbl.ETMoneyUpdated
                "Official Update Date (w.e.f.)" = $tbl.OfficialUpdated
                "Tenure / Scheme" = $r.Tenure
                "ET Money General Rate" = $r.ETM_Gen
                "ET Money Senior Rate" = $r.ETM_Sr
                "Official General Rate" = $r.Off_Gen
                "Official Senior Rate" = $r.Off_Sr
                "Verified Official URL" = $tbl.OfficialLink
            }
        }
        
        # Add 2 blank separator rows before next table!
        $bankMatrix += ,@("", "", "", "", "", "")
        $bankMatrix += ,@("", "", "", "", "", "")
        $currentRow += 2
    }
    
    $batchOps += @{
        op = "write"
        range = "'$tabName'!A1"
        data = $bankMatrix
    }
    
    if ($null -ne $sId) {
        $formatRequests += @{
            autoResizeDimensions = @{
                dimensions = @{
                    sheetId = $sId
                    dimension = "COLUMNS"
                    startIndex = 0
                    endIndex = 6
                }
            }
        }
    }
}

# Add Master write op
$batchOps += @{
    op = "write"
    range = "fd_rates_comparison_2026!A1"
    data = $masterMatrix
}

if ($null -ne $masterId) {
    $formatRequests += @{
        autoResizeDimensions = @{
            dimensions = @{
                sheetId = $masterId
                dimension = "COLUMNS"
                startIndex = 0
                endIndex = 12
            }
        }
    }
}

# Save updated CSV
$csvPath = "C:\Users\parveen.kumar\.gemini\antigravity\brain\6b1879a6-66d5-46c1-afe3-5e1407e93301\scratch\fd_rates_comparison_2026.csv"
$csvExportRows | Export-Csv -Path $csvPath -NoTypeInformation -Encoding UTF8
Write-Host "Saved updated CSV with $($csvExportRows.Count) rows."

# Execute Batch Write
$batchFile = "C:\Users\parveen.kumar\.gemini\antigravity\brain\6b1879a6-66d5-46c1-afe3-5e1407e93301\scratch\gsheets_multi_write.json"
$batchJson = $batchOps | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText($batchFile, $batchJson, (New-Object System.Text.UTF8Encoding($false)))

Write-Host "Executing Google Sheets batch write..."
& gsheets mutate batch $spreadsheetId -f $batchFile

# Execute Raw-Batch Formatting
$rawFile = "C:\Users\parveen.kumar\.gemini\antigravity\brain\6b1879a6-66d5-46c1-afe3-5e1407e93301\scratch\gsheets_multi_format.json"
$rawJson = @{ requests = $formatRequests } | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText($rawFile, $rawJson, (New-Object System.Text.UTF8Encoding($false)))

Write-Host "Applying $($formatRequests.Count) formatting rules via raw-batch..."
& gsheets mutate raw-batch $spreadsheetId -f $rawFile
Write-Host "ALL DONE!"
