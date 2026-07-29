param(
    [string]$UploadPath,
    [switch]$Force
)

. "$PSScriptRoot\_maintenance_common.ps1"

$targetPath = Get-UploadPath -UploadPath $UploadPath

Confirm-DestructiveAction -Force:$Force -Message "This will delete all files inside '$targetPath'."

Get-ChildItem -LiteralPath $targetPath -Force | Remove-Item -Recurse -Force
Write-Host "Upload folder cleaned: $targetPath"
