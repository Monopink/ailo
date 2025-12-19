# Pack Project for Staging Deployment (Windows PowerShell)
# Usage: .\pack-for-windows.ps1

$ErrorActionPreference = "Stop"

# Configuration
$ProjectRoot = (Get-Item (Split-Path -Parent $PSScriptRoot)).Parent.FullName
$Timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$DeployPackage = "ailo-staging-deploy-$Timestamp.tar.gz"
$TempDir = Join-Path $env:TEMP "ailo-deploy-$(Get-Date -Format 'yyyyMMddHHmmss')"

Write-Host "[INFO] Packing project for staging environment..." -ForegroundColor Blue
Write-Host "[INFO] Project root: $ProjectRoot" -ForegroundColor Blue

# Create temporary directory
New-Item -ItemType Directory -Path $TempDir -Force | Out-Null
$PackDir = Join-Path $TempDir "ailo"
New-Item -ItemType Directory -Path $PackDir -Force | Out-Null

Write-Host "[INFO] Copying files..." -ForegroundColor Blue

# Copy directories
Copy-Item -Path (Join-Path $ProjectRoot "backend") -Destination $PackDir -Recurse -Force
Copy-Item -Path (Join-Path $ProjectRoot "deployment") -Destination $PackDir -Recurse -Force
Copy-Item -Path (Join-Path $ProjectRoot "nginx") -Destination $PackDir -Recurse -Force

Write-Host "[INFO] Cleaning up..." -ForegroundColor Blue

# Remove unnecessary files
Get-ChildItem -Path $PackDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem -Path $PackDir -Recurse -Directory -Filter ".mypy_cache" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem -Path $PackDir -Recurse -Directory -Filter ".pytest_cache" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem -Path $PackDir -Recurse -Directory -Filter ".ruff_cache" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem -Path $PackDir -Recurse -File -Filter "*.pyc" -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem -Path $PackDir -Recurse -File -Filter "*.log" -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem -Path $PackDir -Recurse -Directory -Filter "logs" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem -Path $PackDir -Recurse -Directory -Filter ".git" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force

# Remove venv
$VenvPath = Join-Path $PackDir "backend\venv"
if (Test-Path $VenvPath) {
    Remove-Item -Path $VenvPath -Recurse -Force
}

# Remove env files
Get-ChildItem -Path (Join-Path $PackDir "deployment") -File -Filter ".env*" -ErrorAction SilentlyContinue | Remove-Item -Force

Write-Host "[INFO] Creating archive..." -ForegroundColor Blue

# Check if tar is available
if (Get-Command tar.exe -ErrorAction SilentlyContinue) {
    $CurrentLocation = Get-Location
    Set-Location $TempDir
    & tar.exe -czf $DeployPackage ailo
    Set-Location $CurrentLocation

    # Move to project root
    $SourcePath = Join-Path $TempDir $DeployPackage
    $DestPath = Join-Path $ProjectRoot $DeployPackage
    if (Test-Path $DestPath) {
        Remove-Item $DestPath -Force
    }
    Move-Item -Path $SourcePath -Destination $DestPath -Force
} else {
    Write-Host "[ERROR] tar command not found. Please install tar or use WSL." -ForegroundColor Red
    Write-Host "[INFO] Archive the 'ailo' folder in: $TempDir" -ForegroundColor Yellow
    exit 1
}

# Cleanup
Remove-Item -Path $TempDir -Recurse -Force

$PackagePath = Join-Path $ProjectRoot $DeployPackage
$Size = (Get-Item $PackagePath).Length / 1MB
$SizeFormatted = "{0:N2} MB" -f $Size

Write-Host "[SUCCESS] Package created: $DeployPackage ($SizeFormatted)" -ForegroundColor Green
Write-Host ""
Write-Host "[INFO] Next steps:" -ForegroundColor Blue
Write-Host "1. Upload $DeployPackage to server using xftp" -ForegroundColor White
Write-Host "   Target: /home/ubuntu/" -ForegroundColor White
Write-Host "2. Ensure .env.staging is configured on server" -ForegroundColor White
Write-Host "3. SSH to server and run:" -ForegroundColor White
Write-Host "   cd /opt/ailo-staging/ailo/deployment/scripts" -ForegroundColor Cyan
Write-Host "   ./deploy.sh update" -ForegroundColor Cyan
Write-Host ""
Write-Host "Package location: $PackagePath" -ForegroundColor Cyan
