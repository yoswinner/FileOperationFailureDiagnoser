# PowerShell script to prepare attributes for Teacher Demonstration Fixtures
# Safe, narrowly scoped to artifacts/review3/demo_fixtures/teacher_demo only.

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$demoDir = Join-Path $projectRoot "artifacts\review3\demo_fixtures\teacher_demo"

if (-not (Test-Path $demoDir)) {
    Write-Error "Demo directory does not exist: $demoDir"
    exit 1
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Preparing Teacher Demonstration Fixtures" -ForegroundColor Cyan
Write-Host " Target Directory: $demoDir" -ForegroundColor Gray
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Prepare 02_read_only_file.txt (Set ReadOnly)
$roFile = Join-Path $demoDir "02_read_only_file.txt"
if (Test-Path $roFile) {
    Set-ItemProperty -Path $roFile -Name IsReadOnly -Value $true
    Write-Host "[OK] Set ReadOnly attribute on: 02_read_only_file.txt" -ForegroundColor Green
} else {
    Write-Warning "File not found: $roFile"
}

# 2. Prepare 03_hidden_archive_file.txt (Set Hidden + Archive)
$hiddenFile = Join-Path $demoDir "03_hidden_archive_file.txt"
if (Test-Path $hiddenFile) {
    $item = Get-Item $hiddenFile -Force
    $item.Attributes = [System.IO.FileAttributes]::Hidden -bor [System.IO.FileAttributes]::Archive
    Write-Host "[OK] Set Hidden + Archive attributes on: 03_hidden_archive_file.txt" -ForegroundColor Green
} else {
    Write-Warning "File not found: $hiddenFile"
}

# 3. Prepare 04_system_attribute_file.txt (Set System + Archive)
$sysFile = Join-Path $demoDir "04_system_attribute_file.txt"
if (Test-Path $sysFile) {
    $item = Get-Item $sysFile -Force
    $item.Attributes = [System.IO.FileAttributes]::System -bor [System.IO.FileAttributes]::Archive
    Write-Host "[OK] Set System + Archive attributes on: 04_system_attribute_file.txt" -ForegroundColor Green
} else {
    Write-Warning "File not found: $sysFile"
}

Write-Host "`nPreparation complete. All fixtures ready for demonstration." -ForegroundColor Green
Write-Host "Run 'scripts/restore_teacher_demo_fixtures.ps1' after the demo to reset attributes.`n" -ForegroundColor Yellow
