param(
    [string]$BackupStamp,
    [string]$DatabaseBackupFile,
    [string]$FilesBackupFile,
    [string]$UploadPath,
    [string]$PgBin,
    [switch]$Force
)

. "$PSScriptRoot\_maintenance_common.ps1"

$projectRoot = Get-ProjectRoot

if ($BackupStamp) {
    $dbDir = Join-Path $projectRoot "database\backups\database"
    $filesDir = Join-Path $projectRoot "database\backups\files"
    $dbMatches = Get-ChildItem -LiteralPath $dbDir -Filter "*_$BackupStamp.dump" -ErrorAction SilentlyContinue
    $fileMatches = Get-ChildItem -LiteralPath $filesDir -Filter "uploads_$BackupStamp.zip" -ErrorAction SilentlyContinue

    if ($dbMatches.Count -ne 1) {
        throw "Expected one database backup for stamp '$BackupStamp', found $($dbMatches.Count)."
    }

    if ($fileMatches.Count -ne 1) {
        throw "Expected one file backup for stamp '$BackupStamp', found $($fileMatches.Count)."
    }

    $DatabaseBackupFile = $dbMatches[0].FullName
    $FilesBackupFile = $fileMatches[0].FullName
}

if (-not $DatabaseBackupFile -or -not $FilesBackupFile) {
    throw "Provide either -BackupStamp or both -DatabaseBackupFile and -FilesBackupFile."
}

Confirm-DestructiveAction -Force:$Force -Message "Full restore will replace database contents and upload files."

& "$PSScriptRoot\restore_database.ps1" -BackupFile $DatabaseBackupFile -PgBin $PgBin -Force
& "$PSScriptRoot\restore_files.ps1" -BackupFile $FilesBackupFile -UploadPath $UploadPath -Force

Write-Host "Full restore complete."
