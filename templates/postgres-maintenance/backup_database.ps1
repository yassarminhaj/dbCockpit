param(
    [string]$HostName,
    [string]$Port,
    [string]$Database,
    [string]$User,
    [string]$BackupStamp,
    [string]$BackupRoot,
    [string]$PgBin
)

. "$PSScriptRoot\_maintenance_common.ps1"

$config = Get-DbConfig
if (-not $HostName) { $HostName = $config.Host }
if (-not $Port) { $Port = $config.Port }
if (-not $Database) { $Database = $config.Database }
if (-not $User) { $User = $config.User }
if (-not $BackupRoot) { $BackupRoot = Join-Path (Get-ProjectRoot) "database\backups\database" }

$stamp = Get-BackupStamp -BackupStamp $BackupStamp
$backupDir = Resolve-PathOrCreate -PathValue $BackupRoot -Directory
$backupFile = Join-Path $backupDir "$Database`_$stamp.dump"
$pgDump = Find-PostgresTool -ToolName "pg_dump" -PgBin $PgBin

if ($config.Password) {
    $env:PGPASSWORD = $config.Password
}

Write-Host "Backing up database '$Database' to $backupFile"
& $pgDump `
    --host $HostName `
    --port $Port `
    --username $User `
    --format custom `
    --file $backupFile `
    --verbose `
    $Database

if ($LASTEXITCODE -ne 0) {
    throw "Database backup failed with exit code $LASTEXITCODE."
}

Write-Host "Database backup complete: $backupFile"
return $backupFile
