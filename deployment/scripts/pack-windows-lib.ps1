# Shared Windows packing logic for deployment packages.

function Invoke-PackDeployment {
    param(
        [Parameter(Mandatory = $true)][string]$Environment,
        [Parameter(Mandatory = $true)][string]$PackagePrefix
    )

    $ErrorActionPreference = "Stop"

    $ProjectRoot = (Get-Item $PSScriptRoot).Parent.Parent.FullName
    $Timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $DeployPackage = "$PackagePrefix-$Timestamp.tar.gz"
    $TempDir = Join-Path $env:TEMP "ailo-deploy-$(Get-Date -Format 'yyyyMMddHHmmss')"

    Write-Host "[INFO] Packing project for $Environment environment..." -ForegroundColor Blue
    Write-Host "[INFO] Project root: $ProjectRoot" -ForegroundColor Blue

    New-Item -ItemType Directory -Path $TempDir -Force | Out-Null
    $PackDir = Join-Path $TempDir "ailo"
    New-Item -ItemType Directory -Path $PackDir -Force | Out-Null

    Write-Host "[INFO] Copying files..." -ForegroundColor Blue
    Copy-Item -Path (Join-Path $ProjectRoot "backend") -Destination $PackDir -Recurse -Force
    Copy-Item -Path (Join-Path $ProjectRoot "nginx") -Destination $PackDir -Recurse -Force

    $DeploymentPackDir = Join-Path $PackDir "deployment"
    New-Item -ItemType Directory -Path $DeploymentPackDir -Force | Out-Null

    $DeploymentRootFiles = @(
        ".env.example",
        "compose.base.yaml",
        "compose.dozzle.yaml"
    )
    foreach ($FileName in $DeploymentRootFiles) {
        $SourcePath = Join-Path $ProjectRoot "deployment\$FileName"
        if (Test-Path $SourcePath) {
            Copy-Item -Path $SourcePath -Destination $DeploymentPackDir -Force
        } elseif ($Environment -in @("prod", "staging")) {
            throw "Missing required deployment file for $Environment package: deployment\\$FileName"
        }
    }

    foreach ($SharedDir in @("scripts", "fail2ban")) {
        $SourcePath = Join-Path $ProjectRoot "deployment\$SharedDir"
        if (Test-Path $SourcePath) {
            Copy-Item -Path $SourcePath -Destination $DeploymentPackDir -Recurse -Force
        }
    }

    $EnvDir = $Environment
    $EnvSourcePath = Join-Path $ProjectRoot "deployment\$EnvDir"
    if (Test-Path $EnvSourcePath) {
        Copy-Item -Path $EnvSourcePath -Destination $DeploymentPackDir -Recurse -Force
    } else {
        throw "Unknown environment '$Environment' (missing directory: deployment\\$EnvDir)"
    }

    Write-Host "[INFO] Cleaning up..." -ForegroundColor Blue
    Get-ChildItem -Path $PackDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
    Get-ChildItem -Path $PackDir -Recurse -Directory -Filter ".mypy_cache" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
    Get-ChildItem -Path $PackDir -Recurse -Directory -Filter ".mypy_cache2" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
    Get-ChildItem -Path $PackDir -Recurse -Directory -Filter ".pytest_cache" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
    Get-ChildItem -Path $PackDir -Recurse -Directory -Filter ".ruff_cache" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
    Get-ChildItem -Path $PackDir -Recurse -Directory -Filter ".import_linter_cache" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
    Get-ChildItem -Path $PackDir -Recurse -Directory -Filter ".grimp_cache" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
    Get-ChildItem -Path $PackDir -Recurse -Directory -Filter ".cache" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
    Get-ChildItem -Path $PackDir -Recurse -File -Filter "*.pyc" -ErrorAction SilentlyContinue | Remove-Item -Force
    Get-ChildItem -Path $PackDir -Recurse -File -Filter "*.log" -ErrorAction SilentlyContinue | Remove-Item -Force
    Get-ChildItem -Path $PackDir -Recurse -File -Filter "tmpclaude-*-cwd" -ErrorAction SilentlyContinue | Remove-Item -Force
    Get-ChildItem -Path $PackDir -Recurse -Directory -Filter "logs" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
    Get-ChildItem -Path $PackDir -Recurse -Directory -Filter ".git" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force

    $VenvPath = Join-Path $PackDir "backend\venv"
    if (Test-Path $VenvPath) {
        Remove-Item -Path $VenvPath -Recurse -Force
    }
    $DotVenvPath = Join-Path $PackDir "backend\.venv"
    if (Test-Path $DotVenvPath) {
        Remove-Item -Path $DotVenvPath -Recurse -Force
    }

    $EnvFilesToRemove = @(
        "deployment\dev\.env",
        "deployment\staging\.env",
        "deployment\prod\.env",
        "deployment\.env",
        "deployment\.env.test"
    )
    foreach ($EnvFile in $EnvFilesToRemove) {
        $EnvPath = Join-Path $PackDir $EnvFile
        if (Test-Path $EnvPath) {
            Remove-Item -Path $EnvPath -Force
        }
    }

    $HtpasswdFilesToRemove = @(
        "deployment\staging\secrets\.htpasswd",
        "deployment\staging\secrets\.htpasswd_logs",
        "deployment\prod\secrets\.htpasswd",
        "deployment\prod\secrets\.htpasswd_logs"
    )
    foreach ($HtpasswdFile in $HtpasswdFilesToRemove) {
        $HtpasswdPath = Join-Path $PackDir $HtpasswdFile
        if (Test-Path $HtpasswdPath) {
            Remove-Item -Path $HtpasswdPath -Force
        }
    }

    Write-Host "[INFO] Creating archive..." -ForegroundColor Blue
    if (Get-Command tar.exe -ErrorAction SilentlyContinue) {
        $CurrentLocation = Get-Location
        Set-Location $TempDir
        & tar.exe -czf $DeployPackage ailo
        Set-Location $CurrentLocation

        $SourcePath = Join-Path $TempDir $DeployPackage
        $DestPath = Join-Path $ProjectRoot $DeployPackage
        if (Test-Path $DestPath) {
            Remove-Item $DestPath -Force
        }
        Move-Item -Path $SourcePath -Destination $DestPath -Force
    } else {
        Write-Host "[ERROR] tar command not found. Install tar or use WSL." -ForegroundColor Red
        exit 1
    }

    Remove-Item -Path $TempDir -Recurse -Force

    $PackagePath = Join-Path $ProjectRoot $DeployPackage
    $Size = (Get-Item $PackagePath).Length / 1MB
    $SizeFormatted = "{0:N2} MB" -f $Size

    Write-Host "[SUCCESS] Package created: $DeployPackage ($SizeFormatted)" -ForegroundColor Green
    Write-Host ""
    Write-Host "[INFO] Next steps:" -ForegroundColor Blue
    Write-Host "1. Upload $DeployPackage to /home/ubuntu/" -ForegroundColor White
    Write-Host "2. SSH to server and run:" -ForegroundColor White
    Write-Host "   cd /opt/ailo-$Environment/ailo/deployment/$Environment/scripts" -ForegroundColor Cyan
    Write-Host "   ./deploy.sh deploy --package /home/ubuntu/$DeployPackage" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Package location: $PackagePath" -ForegroundColor Cyan
}
