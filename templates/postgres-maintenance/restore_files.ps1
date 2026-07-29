param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [string]$UploadPath,
    [switch]$Force
)

. "$PSScriptRoot\_maintenance_common.ps1"

$resolvedBackup = (Resolve-Path -LiteralPath $BackupFile).Path
$targetPath = Get-UploadPath -UploadPath $UploadPath

Confirm-DestructiveAction -Force:$Force -Message "Restore will replace files in '$targetPath' from '$resolvedBackup'."

Write-Host "Clearing upload folder: $targetPath"
Get-ChildItem -LiteralPath $targetPath -Force | Remove-Item -Recurse -Force

Write-Host "Restoring files from $resolvedBackup"
Expand-Archive -LiteralPath $resolvedBackup -DestinationPath $targetPath -Force

$emptyMarker = Join-Path $targetPath ".empty-upload-folder"
if (Test-Path -LiteralPath $emptyMarker) {
    Remove-Item -LiteralPath $emptyMarker -Force
}

Write-Host "File restore complete."
