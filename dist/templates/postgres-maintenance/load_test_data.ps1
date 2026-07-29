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
$seedSql = Join-Path $projectRoot "database\seed.sql"

if (-not (Test-Path -LiteralPath $seedSql)) {
    throw "Seed file not found: $seedSql"
}

if ($config.Password) {
    $env:PGPASSWORD = $config.Password
}

$rowCountQuery = @"
select coalesce(sum(
    (
        xpath(
            '/row/c/text()',
            query_to_xml(
                format('select count(*) as c from %I.%I', n.nspname, c.relname),
                false,
                true,
                ''
            )
        )
    )[1]::text::bigint
), 0) as total_rows
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public'
  and c.relkind = 'r';
"@

Write-Host "Checking whether public tables are empty..."
$rawCount = & $psql `
    --host $HostName `
    --port $Port `
    --username $User `
    --dbname $Database `
    --tuples-only `
    --no-align `
    --command $rowCountQuery

if ($LASTEXITCODE -ne 0) {
    throw "Could not verify table emptiness. Ensure schema exists before loading test data."
}

$totalRows = [int]($rawCount | Select-Object -Last 1).Trim()

if ($totalRows -gt 0 -and -not $Force) {
    throw "Test data was not loaded. Public tables appear to contain $totalRows rows. Reset Database first, then Load Test Data."
}

Write-Host "Loading test data from $seedSql..."
& $psql --host $HostName --port $Port --username $User --dbname $Database --file $seedSql
if ($LASTEXITCODE -ne 0) {
    throw "Seed script failed with exit code $LASTEXITCODE."
}

Write-Host "Test data load complete."
