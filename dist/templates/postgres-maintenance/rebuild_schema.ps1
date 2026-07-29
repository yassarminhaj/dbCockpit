param(
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

$projectRoot = Get-ProjectRoot
$psql = Find-PostgresTool -ToolName "psql" -PgBin $PgBin
$resetSql = Join-Path $projectRoot "database\maintenance\reset_database.sql"
$schemaSql = Join-Path $projectRoot "database\schema.sql"

Confirm-DestructiveAction -Force:$Force -Message "This will drop and recreate all Defect Tracker app tables in '$Database'. No seed data will be loaded."

if ($config.Password) {
    $env:PGPASSWORD = $config.Password
}

Write-Host "Dropping existing app tables..."
& $psql --host $HostName --port $Port --username $User --dbname $Database --file $resetSql
if ($LASTEXITCODE -ne 0) {
    throw "Reset script failed with exit code $LASTEXITCODE."
}

Write-Host "Recreating empty schema..."
& $psql --host $HostName --port $Port --username $User --dbname $Database --file $schemaSql
if ($LASTEXITCODE -ne 0) {
    throw "Schema script failed with exit code $LASTEXITCODE."
}

Write-Host "Schema rebuild complete. Tables are empty."
