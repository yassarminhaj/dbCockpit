Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-ProjectRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

function Get-EnvFileValues {
    param(
        [string]$EnvPath = (Join-Path (Get-ProjectRoot) ".env")
    )

    $values = @{}
    if (-not (Test-Path -LiteralPath $EnvPath)) {
        return $values
    }

    Get-Content -LiteralPath $EnvPath | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }

        $parts = $line.Split("=", 2)
        $key = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        $values[$key] = $value
    }

    return $values
}

function Get-DbConfig {
    $envValues = Get-EnvFileValues

    $config = @{
        Host = "localhost"
        Port = "5432"
        Database = "defect_tracker"
        User = "postgres"
        Password = ""
    }

    if ($envValues.ContainsKey("POSTGRES_DB")) { $config.Database = $envValues.POSTGRES_DB }
    if ($envValues.ContainsKey("POSTGRES_USER")) { $config.User = $envValues.POSTGRES_USER }
    if ($envValues.ContainsKey("POSTGRES_PASSWORD")) { $config.Password = $envValues.POSTGRES_PASSWORD }
    if ($envValues.ContainsKey("POSTGRES_PORT")) { $config.Port = $envValues.POSTGRES_PORT }
    if ($envValues.ContainsKey("POSTGRES_HOST_PORT")) { $config.Port = $envValues.POSTGRES_HOST_PORT }

    if ($envValues.ContainsKey("DATABASE_URL")) {
        $url = $envValues.DATABASE_URL -replace "^postgresql\+psycopg2://", "postgresql://"
        try {
            $uri = [Uri]$url
            if ($uri.Host) { $config.Host = $uri.Host }
            if ($uri.Port -gt 0) { $config.Port = [string]$uri.Port }
            if ($uri.AbsolutePath.Length -gt 1) { $config.Database = $uri.AbsolutePath.TrimStart("/") }
            if ($uri.UserInfo) {
                $userInfoParts = $uri.UserInfo.Split(":", 2)
                if ($userInfoParts[0]) { $config.User = [Uri]::UnescapeDataString($userInfoParts[0]) }
                if ($userInfoParts.Count -gt 1) { $config.Password = [Uri]::UnescapeDataString($userInfoParts[1]) }
            }
        } catch {
            Write-Warning "Could not parse DATABASE_URL from .env. Falling back to POSTGRES_* values."
        }
    }

    if (($config.Host -in @("db", "postgres", "database")) -and $envValues.ContainsKey("POSTGRES_HOST_PORT")) {
        $config.Host = "localhost"
        $config.Port = $envValues.POSTGRES_HOST_PORT
    }

    return $config
}

function Get-UploadPath {
    param(
        [string]$UploadPath
    )

    if ($UploadPath) {
        return (Resolve-PathOrCreate -PathValue $UploadPath -Directory)
    }

    $envValues = Get-EnvFileValues
    $projectRoot = Get-ProjectRoot
    $configuredPath = "uploads"

    if ($envValues.ContainsKey("UPLOAD_FOLDER") -and $envValues.UPLOAD_FOLDER) {
        $configuredPath = $envValues.UPLOAD_FOLDER
    }

    if ([System.IO.Path]::IsPathRooted($configuredPath)) {
        return (Resolve-PathOrCreate -PathValue $configuredPath -Directory)
    }

    return (Resolve-PathOrCreate -PathValue (Join-Path $projectRoot $configuredPath) -Directory)
}

function Resolve-PathOrCreate {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue,
        [switch]$Directory
    )

    if ($Directory -and -not (Test-Path -LiteralPath $PathValue)) {
        New-Item -ItemType Directory -Path $PathValue | Out-Null
    }

    return (Resolve-Path -LiteralPath $PathValue).Path
}

function Find-PostgresTool {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ToolName,
        [string]$PgBin
    )

    if ($PgBin) {
        $candidate = Join-Path $PgBin "$ToolName.exe"
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    $fromPath = Get-Command $ToolName -ErrorAction SilentlyContinue
    if ($fromPath) {
        return $fromPath.Source
    }

    $knownCandidates = @(
        "C:\Program Files\PostgreSQL\18\bin\$ToolName.exe",
        "C:\Program Files\PostgreSQL\17\bin\$ToolName.exe",
        "C:\Program Files\PostgreSQL\16\bin\$ToolName.exe",
        "C:\Program Files\PostgreSQL\15\bin\$ToolName.exe"
    )

    foreach ($candidate in $knownCandidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    throw "Could not find $ToolName. Add PostgreSQL bin to PATH or pass -PgBin 'C:\Program Files\PostgreSQL\18\bin'."
}

function Get-BackupStamp {
    param(
        [string]$BackupStamp
    )

    if ($BackupStamp) {
        return $BackupStamp
    }

    return (Get-Date -Format "yyyyMMdd_HHmmss")
}

function Confirm-DestructiveAction {
    param(
        [string]$Message,
        [switch]$Force
    )

    if ($Force) {
        return
    }

    $answer = Read-Host "$Message Type YES to continue"
    if ($answer -ne "YES") {
        throw "Operation cancelled."
    }
}
