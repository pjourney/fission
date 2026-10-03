[CmdletBinding()]
param(
    [ValidateRange(1,32)][int]$Jobs=12,
    [switch]$Baseline,
    [switch]$Test
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'scripts\checkout-engine.ps1')
& (Join-Path $PSScriptRoot 'scripts\setup-dependencies.ps1')
if (-not $Baseline) {
    $runtimeRoot = Join-Path $PSScriptRoot '.deps\LibPack-26.3.0-v3.5.5-x64-Release\bin'
    $env:QT_QPA_PLATFORM='offscreen'
    $env:QT_QPA_PLATFORM_PLUGIN_PATH=Join-Path $runtimeRoot 'platforms'
    & (Join-Path $runtimeRoot 'python.exe') (Join-Path $PSScriptRoot 'scripts\build-branding.py')
    if ($LASTEXITCODE -ne 0) { throw 'Branding generation failed.' }
    & (Join-Path $PSScriptRoot 'scripts\apply-fission.ps1')
}
& (Join-Path $PSScriptRoot 'scripts\build.ps1') -Jobs $Jobs
if (-not $Baseline) { & (Join-Path $PSScriptRoot 'scripts\install-ui.ps1') }
if ($Test) { & (Join-Path $PSScriptRoot 'scripts\test-upstream.ps1'); & (Join-Path $PSScriptRoot 'scripts\test-cad-smoke.ps1') }
