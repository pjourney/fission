[CmdletBinding()]
param(
    [string]$BuildDirectory = (Join-Path (Split-Path $PSScriptRoot -Parent) 'build\windows-release')
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$binaryRoot = Join-Path $BuildDirectory 'bin'
$executable = Join-Path $binaryRoot 'FreeCAD.exe'
$outputDirectory = Join-Path $projectRoot 'build\baseline-gui'
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$env:FISSION_GUI_SMOKE_OUTPUT = $outputDirectory
$env:FREECAD_USER_HOME = Join-Path $outputDirectory 'home'
New-Item -ItemType Directory -Force -Path $env:FREECAD_USER_HOME | Out-Null
$env:PYTHONHOME = $binaryRoot
$env:PATH = "$binaryRoot;$env:PATH"
$reportPath = Join-Path $outputDirectory 'gui-report.json'
if (Test-Path -LiteralPath $reportPath) { Remove-Item -LiteralPath $reportPath }
$macro = Join-Path $PSScriptRoot 'baseline-gui-smoke.FCMacro'
$logPath = Join-Path $outputDirectory 'FreeCAD.log'
$arguments = @('--write-log', '--log-file', ('"' + $logPath + '"'), ('"' + $macro + '"'))
$process = Start-Process -FilePath $executable -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru
if (-not $process.WaitForExit(60000)) {
    Stop-Process -Id $process.Id
    throw 'Baseline GUI smoke test timed out after 60 seconds.'
}
if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $reportPath)) {
    throw 'Baseline GUI did not complete the smoke macro. Inspect build\baseline-gui\FreeCAD.log.'
}
$report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
if (-not $report.passed) { throw "Baseline GUI test failed: $($report.error)" }
Write-Output "Native GUI/viewport and $($report.workbenches.Count) required workbenches verified; screenshot: $outputDirectory\baseline-window.png"
