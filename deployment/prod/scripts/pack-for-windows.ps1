# Pack Project for Production Deployment (Windows, local only)
# Usage: .\pack-for-windows.ps1

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SharedScript = Join-Path $ScriptDir "..\..\scripts\pack-windows-lib.ps1"
. $SharedScript

Invoke-PackDeployment -Environment "prod" -PackagePrefix "ailo-prod-deploy"
