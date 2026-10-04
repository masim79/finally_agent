#Requires -Version 5.1
<#
.SYNOPSIS
    Stop and remove the FinAlly container.
.DESCRIPTION
    The named volume (and therefore the database) is left untouched. Safe to
    run even if nothing is running.
#>

$ErrorActionPreference = "Stop"

# See start_windows.ps1 for why this helper exists: in Windows PowerShell
# 5.1, redirecting a native exe's stderr wraps each line in a
# NativeCommandError record, which $ErrorActionPreference = "Stop" above
# turns into a *terminating* error. $LASTEXITCODE (reassigned inside the
# function's own scope, so "Continue" never leaks to the caller) is the
# reliable success signal here, not $?.
function Invoke-DockerQuiet {
    param([Parameter(Mandatory)][string[]]$DockerArgs)
    $ErrorActionPreference = "Continue"
    & docker @DockerArgs *> $null
    return $LASTEXITCODE
}

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

if ((Invoke-DockerQuiet -DockerArgs @("info")) -ne 0) {
    Write-Host "Docker does not appear to be running - nothing to stop."
    exit 0
}

docker compose down

Write-Host "FinAlly stopped. Your portfolio data is preserved (volume: finally-data)."
