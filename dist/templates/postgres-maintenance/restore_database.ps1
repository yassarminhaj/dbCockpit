param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [string]$HostName,
    [string]$Port,
    [string]$Database,
    [string]$User,
    [string]$PgBin,
    [switch]$Force
)

. "$PSScriptRoot\_maintenance_common.ps1"

$config = Get-DbConfig
if (-not $HostName) { $HostName = $config.Host }
if (-not $Port) { $Port = $config.Port }
if (-not $Database) { $Database = $config.Database }
if (-not $User) { $User = $config.User }

$resolvedBackup = (Resolve-Path -LiteralPath $BackupFile).Path
$pgRestore = Find-PostgresTool -ToolName "pg_restore" -PgBin $PgBin

Confirm-DestructiveAction -Force:$Force -Message "Restore will overwrite database objects in '$Database' from '$resolvedBackup'."

if ($config.Password) {
    $env:PGPASSWORD = $config.Password
}

Write-Host "Restoring database '$Database' from $resolvedBackup"
& $pgRestore `
    --host $HostName `
    --port $Port `
    --username $User `
    --dbname $Database `
    --clean `
    --if-exists `
    --no-owner `
    --verbose `
    $resolvedBackup

if ($LASTEXITCODE -ne 0) {
    throw "Database restore failed with exit code $LASTEXITCODE."
}

Write-Host "Database restore complete."
