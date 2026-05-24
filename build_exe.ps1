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
    --name DefectMaintenanceConsole `
    app.py

if ($LASTEXITCODE -ne 0) {
    throw "Executable build failed."
}

$DistConfig = Join-Path $ProjectRoot "dist\config"
$DistLogs = Join-Path $ProjectRoot "dist\logs"
New-Item -ItemType Directory -Path $DistConfig -Force | Out-Null
New-Item -ItemType Directory -Path $DistLogs -Force | Out-Null

Copy-Item `
    -LiteralPath (Join-Path $ProjectRoot "config\profiles.json") `
    -Destination (Join-Path $DistConfig "profiles.json") `
    -Force

Write-Host ""
Write-Host "Build complete."
Write-Host "Executable:"
Write-Host "  $(Join-Path $ProjectRoot 'dist\DefectMaintenanceConsole.exe')"
Write-Host ""
Write-Host "Editable runtime files:"
Write-Host "  $(Join-Path $ProjectRoot 'dist\config\profiles.json')"
Write-Host "  $(Join-Path $ProjectRoot 'dist\logs')"
