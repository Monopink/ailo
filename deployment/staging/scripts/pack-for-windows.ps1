# Pack Project for Staging Deployment (Windows PowerShell)
# Usage: .\pack-for-windows.ps1

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SharedScript = Join-Path $ScriptDir "..\..\scripts\pack-windows-lib.ps1"
. $SharedScript

Invoke-PackDeployment -Environment "staging" -PackagePrefix "ailo-staging-deploy"
