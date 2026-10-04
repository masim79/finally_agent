#Requires -Version 5.1
<#
.SYNOPSIS
    Build (if needed) and launch the FinAlly container.
.DESCRIPTION
    Safe to run more than once - `docker compose up` is idempotent, and
    re-running just reattaches to (or recreates, with -Build) the existing
    service.
.PARAMETER Build
    Force a rebuild of the image before starting.
.PARAMETER NoOpen
    Don't open a browser once the app is healthy.
#>
param(
    [switch]$Build,
    [switch]$NoOpen
)

$ErrorActionPreference = "Stop"

# In Windows PowerShell 5.1, redirecting a native exe's stderr (2>, *>, 2>&1)
# wraps each line in a NativeCommandError record. Combined with
# $ErrorActionPreference = "Stop" above, that becomes a *terminating* error -
# even when the command exits 0, since `docker compose` routinely logs
# routine progress to stderr. $LASTEXITCODE is the reliable success signal
# for a native command, not $?, so every docker invocation below runs inside
# this helper, which drops back to "Continue" just for the call (the
# reassignment is local to the function's scope and does not leak out).
function Invoke-DockerQuiet {
    param([Parameter(Mandatory)][string[]]$DockerArgs)
    $ErrorActionPreference = "Continue"
    & docker @DockerArgs *> $null
    return $LASTEXITCODE
}

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

$Port = if ($env:FINALLY_PORT) { $env:FINALLY_PORT } else { "8000" }
$Url = "http://localhost:$Port"

if ((Invoke-DockerQuiet -DockerArgs @("info")) -ne 0) {
    Write-Host "Docker does not appear to be running. Start Docker Desktop and try again."
    exit 1
}

if (-not (Test-Path (Join-Path $RootDir ".env"))) {
    Write-Host "No .env file found - copy .env.example to .env to enable live AI chat"
    Write-Host "and/or real market data. The app will still start and work fine without it"
    Write-Host "(simulator market data, chat disabled unless LLM_MOCK=true)."
    Write-Host ""
}

Write-Host "Starting FinAlly..."
if ($Build) {
    docker compose up -d --build
} else {
    docker compose up -d
}
# Left unredirected on purpose so build/pull progress streams live to the
# console - checked via $LASTEXITCODE (the reliable signal for a native exe)
# rather than $?, since nothing here wraps stderr in a NativeCommandError.
if ($LASTEXITCODE -ne 0) {
    Write-Host "docker compose up failed. Check 'docker compose logs' for details."
    exit 1
}

Write-Host -NoNewline "Waiting for the app to become healthy"
$healthy = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $status = docker inspect --format='{{.State.Health.Status}}' finally 2>$null
    } catch {
        $status = $null
    }
    if ($status -eq "healthy") {
        $healthy = $true
        break
    }
    Write-Host -NoNewline "."
    Start-Sleep -Seconds 1
}
Write-Host ""

if (-not $healthy) {
    Write-Warning "App did not report healthy within 60s - check 'docker compose logs' for details."
}

Write-Host "FinAlly is running at $Url"

if (-not $NoOpen) {
    Start-Process $Url
}
