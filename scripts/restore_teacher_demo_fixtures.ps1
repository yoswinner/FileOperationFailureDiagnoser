# PowerShell script to restore Teacher Demonstration Fixtures to baseline
# Safe, narrowly scoped strictly to artifacts/review3/demo_fixtures/teacher_demo only.

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$demoDir = Join-Path $projectRoot "artifacts\review3\demo_fixtures\teacher_demo"

if (-not (Test-Path $demoDir)) {
    Write-Error "Demo directory does not exist: $demoDir"
    exit 1
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Restoring Teacher Demonstration Fixtures" -ForegroundColor Cyan
Write-Host " Target Directory: $demoDir" -ForegroundColor Gray
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Reset 02_read_only_file.txt
$roFile = Join-Path $demoDir "02_read_only_file.txt"
if (Test-Path $roFile) {
    Set-ItemProperty -Path $roFile -Name IsReadOnly -Value $false
    Write-Host "[OK] Cleared ReadOnly on: 02_read_only_file.txt" -ForegroundColor Green
}

# 2. Reset 03_hidden_archive_file.txt
$hiddenFile = Join-Path $demoDir "03_hidden_archive_file.txt"
if (Test-Path $hiddenFile) {
    $item = Get-Item $hiddenFile -Force
    $item.Attributes = [System.IO.FileAttributes]::Archive
    Write-Host "[OK] Reverted to Archive attribute on: 03_hidden_archive_file.txt" -ForegroundColor Green
}

# 3. Reset 04_system_attribute_file.txt
$sysFile = Join-Path $demoDir "04_system_attribute_file.txt"
if (Test-Path $sysFile) {
    $item = Get-Item $sysFile -Force
    $item.Attributes = [System.IO.FileAttributes]::Archive
    Write-Host "[OK] Reverted to Archive attribute on: 04_system_attribute_file.txt" -ForegroundColor Green
}

# 4. Reset 06_permission_restricted_file.txt (remove any deny ACEs safely if applied)
$permFile = Join-Path $demoDir "06_permission_restricted_file.txt"
if (Test-Path $permFile) {
    try {
        $currentUser = $env:USERNAME
        Start-Process -FilePath "icacls.exe" -ArgumentList "`"$permFile`" /remove:d `"$currentUser`"" -NoNewWindow -Wait
        Write-Host "[OK] Cleaned any test deny ACEs on: 06_permission_restricted_file.txt" -ForegroundColor Green
    } catch {
        Write-Warning "Could not reset ACL on $permFile : $_"
    }
}

Write-Host "`nRestoration complete. All fixtures returned to normal baseline state.`n" -ForegroundColor Green
