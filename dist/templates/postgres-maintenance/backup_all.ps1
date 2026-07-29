param(
    [string]$BackupStamp,
    [string]$UploadPath,
    [string]$PgBin
)

. "$PSScriptRoot\_maintenance_common.ps1"

$stamp = Get-BackupStamp -BackupStamp $BackupStamp

Write-Host "Creating full backup set with stamp: $stamp"
$dbBackup = & "$PSScriptRoot\backup_database.ps1" -BackupStamp $stamp -PgBin $PgBin
$fileBackup = & "$PSScriptRoot\backup_files.ps1" -BackupStamp $stamp -UploadPath $UploadPath

Write-Host ""
Write-Host "Full backup complete."
Write-Host "Database: $dbBackup"
Write-Host "Files:    $fileBackup"
