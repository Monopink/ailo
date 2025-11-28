# Pack Project for Deployment (Windows PowerShell)
# Usage: .\pack-for-windows.ps1

$ErrorActionPreference = "Stop"

# Configuration
$ProjectRoot = (Get-Item (Split-Path -Parent $PSScriptRoot)).Parent.FullName
$Timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$DeployPackage = "says-test-deploy-$Timestamp.tar.gz"
$TempDir = Join-Path $env:TEMP "says-deploy-$(Get-Date -Format 'yyyyMMddHHmmss')"

Write-Host "[INFO] Packing project..." -ForegroundColor Blue
Write-Host "[INFO] Project root: $ProjectRoot" -ForegroundColor Blue

# Create temporary directory
New-Item -ItemType Directory -Path $TempDir -Force | Out-Null
$PackDir = Join-Path $TempDir "says"
New-Item -ItemType Directory -Path $PackDir -Force | Out-Null

Write-Host "[INFO] Copying files..." -ForegroundColor Blue

# Copy backend
Copy-Item -Path (Join-Path $ProjectRoot "backend") -Destination $PackDir -Recurse -Force

# Copy deployment
Copy-Item -Path (Join-Path $ProjectRoot "deployment") -Destination $PackDir -Recurse -Force

# Copy nginx
Copy-Item -Path (Join-Path $ProjectRoot "nginx") -Destination $PackDir -Recurse -Force

Write-Host "[INFO] Cleaning up unnecessary files..." -ForegroundColor Blue

# Remove __pycache__
Get-ChildItem -Path $PackDir -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

# Remove analyzer/test caches
Get-ChildItem -Path $PackDir -Recurse -Directory -Filter ".mypy_cache" | Remove-Item -Recurse -Force
Get-ChildItem -Path $PackDir -Recurse -Directory -Filter ".pytest_cache" | Remove-Item -Recurse -Force
Get-ChildItem -Path $PackDir -Recurse -Directory -Filter ".ruff_cache" | Remove-Item -Recurse -Force

# Remove .pyc files
Get-ChildItem -Path $PackDir -Recurse -File -Filter "*.pyc" | Remove-Item -Force

# Remove .log files
Get-ChildItem -Path $PackDir -Recurse -File -Filter "*.log" | Remove-Item -Force

# Remove logs directories
Get-ChildItem -Path $PackDir -Recurse -Directory -Filter "logs" | Remove-Item -Recurse -Force

# Remove .git directories
Get-ChildItem -Path $PackDir -Recurse -Directory -Filter ".git" | Remove-Item -Recurse -Force

# Remove venv
$VenvPath = Join-Path $PackDir "backend\venv"
if (Test-Path $VenvPath) {
    Remove-Item -Path $VenvPath -Recurse -Force
}

# Remove .env.test (will be uploaded separately)
$EnvTestPath = Join-Path $PackDir "deployment\.env.test"
if (Test-Path $EnvTestPath) {
    Remove-Item -Path $EnvTestPath -Force
}

# Remove default.conf (test environment uses test.conf)
$DefaultConfPath = Join-Path $PackDir "nginx\conf.d\default.conf"
if (Test-Path $DefaultConfPath) {
    Remove-Item -Path $DefaultConfPath -Force
    Write-Host "[INFO] Removed default.conf (test environment uses test.conf)" -ForegroundColor Yellow
}

Write-Host "[INFO] Creating archive..." -ForegroundColor Blue

# Check if tar is available (Windows 10 1803+)
if (Get-Command tar.exe -ErrorAction SilentlyContinue) {
    # Use built-in tar
    $CurrentLocation = Get-Location
    Set-Location $TempDir
    & tar.exe -czf $DeployPackage says
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
    Write-Host "[INFO] You can also manually create the archive using 7-Zip or WinRAR" -ForegroundColor Yellow
    Write-Host "[INFO] Archive the 'says' folder in: $TempDir" -ForegroundColor Yellow
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
Write-Host "2. Create .env.test from .env.test.example" -ForegroundColor White
Write-Host "3. Upload .env.test to server" -ForegroundColor White
Write-Host "   Target: /opt/says-test/says/deployment/.env.test" -ForegroundColor White
Write-Host "4. SSH to server and run deployment scripts" -ForegroundColor White
Write-Host ""
Write-Host "Package location: $PackagePath" -ForegroundColor Cyan
