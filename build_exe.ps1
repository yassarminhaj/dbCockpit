param(
    [string]$Python = "python",
    [switch]$InstallPyInstaller
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

if ($InstallPyInstaller) {
    & $Python -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller installation failed."
    }
}

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name dbCockpit `
    app.py

if ($LASTEXITCODE -ne 0) {
    throw "Executable build failed."
}

$DistConfig = Join-Path $ProjectRoot "dist\config"
$DistLogs = Join-Path $ProjectRoot "dist\logs"
$DistTemplates = Join-Path $ProjectRoot "dist\templates"
New-Item -ItemType Directory -Path $DistConfig -Force | Out-Null
New-Item -ItemType Directory -Path $DistLogs -Force | Out-Null
New-Item -ItemType Directory -Path $DistTemplates -Force | Out-Null

$ProfileSource = Join-Path $ProjectRoot "config\profiles.json"
if (-not (Test-Path -LiteralPath $ProfileSource)) {
    $ProfileSource = Join-Path $ProjectRoot "config\profiles.example.json"
}

Copy-Item `
    -LiteralPath $ProfileSource `
    -Destination (Join-Path $DistConfig "profiles.json") `
    -Force

Copy-Item `
    -LiteralPath (Join-Path $ProjectRoot "templates\postgres-maintenance") `
    -Destination $DistTemplates `
    -Recurse `
    -Force

Write-Host ""
Write-Host "Build complete."
Write-Host "Executable:"
Write-Host "  $(Join-Path $ProjectRoot 'dist\dbCockpit.exe')"
Write-Host ""
Write-Host "Editable runtime files:"
Write-Host "  $(Join-Path $ProjectRoot 'dist\config\profiles.json')"
Write-Host "  $(Join-Path $ProjectRoot 'dist\logs')"
Write-Host "  $(Join-Path $ProjectRoot 'dist\templates')"
