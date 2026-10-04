[CmdletBinding()]
param(
    [string]$BuildDirectory = (Join-Path (Split-Path $PSScriptRoot -Parent) 'build\windows-release')
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$binaryRoot = Join-Path $BuildDirectory 'bin'
$commandExecutable = Join-Path $binaryRoot 'FissionCmd.exe'
if (-not (Test-Path -LiteralPath $commandExecutable)) { $commandExecutable = Join-Path $binaryRoot 'FreeCADCmd.exe' }
$env:FISSION_SMOKE_OUTPUT = Join-Path $projectRoot 'build\baseline-smoke'
$env:PYTHONHOME = $binaryRoot
$env:FREECAD_USER_HOME = Join-Path $BuildDirectory 'cad-test-home'
New-Item -ItemType Directory -Force -Path $env:FREECAD_USER_HOME | Out-Null
$env:PATH = "$binaryRoot;$env:PATH"
$reportPath = Join-Path $env:FISSION_SMOKE_OUTPUT 'report.json'
if (Test-Path -LiteralPath $reportPath) { Remove-Item -LiteralPath $reportPath }
$smokeOutput = & $commandExecutable (Join-Path $PSScriptRoot 'baseline-cad-smoke.py') 2>&1
$smokeExit = $LASTEXITCODE
$smokeOutput | Tee-Object -FilePath (Join-Path $BuildDirectory 'cad-smoke.log')
if ($smokeExit -ne 0 -or -not ($smokeOutput | Select-String -SimpleMatch 'BASELINE_CAD_SMOKE_OK') -or -not (Test-Path -LiteralPath $reportPath)) {
    throw 'Native CAD smoke test failed. See cad-smoke.log.'
}
$report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
if ($report.passed -lt 12) { throw 'Native CAD smoke test did not complete all expected checks.' }
Write-Output "Verified $($report.passed) CAD checks; artifacts: $env:FISSION_SMOKE_OUTPUT"
