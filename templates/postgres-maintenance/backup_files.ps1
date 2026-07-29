param(
    [string]$UploadPath,
    [string]$BackupStamp,
    [string]$BackupRoot
)

. "$PSScriptRoot\_maintenance_common.ps1"

if (-not $BackupRoot) { $BackupRoot = Join-Path (Get-ProjectRoot) "database\backups\files" }

$stamp = Get-BackupStamp -BackupStamp $BackupStamp
$sourcePath = Get-UploadPath -UploadPath $UploadPath
$backupDir = Resolve-PathOrCreate -PathValue $BackupRoot -Directory
$backupFile = Join-Path $backupDir "uploads_$stamp.zip"

Write-Host "Backing up files from '$sourcePath' to $backupFile"

$items = @(Get-ChildItem -LiteralPath $sourcePath -Force)
if ($items.Count -eq 0) {
    $tempDir = Join-Path ([System.IO.Path]::GetTempPath()) "defect_tracker_empty_upload_backup_$stamp"
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $tempDir ".empty-upload-folder") -Value "Upload folder was empty at backup time."
    Compress-Archive -Path (Join-Path $tempDir "*") -DestinationPath $backupFile -Force
    Remove-Item -LiteralPath $tempDir -Recurse -Force
} else {
    Compress-Archive -Path (Join-Path $sourcePath "*") -DestinationPath $backupFile -Force
}

Write-Host "File backup complete: $backupFile"
return $backupFile
