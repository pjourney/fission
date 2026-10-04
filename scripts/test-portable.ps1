[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$RuntimeDirectory,
    [string]$OutputDirectory,
    [switch]$SkipGui
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RuntimeDirectory = (Resolve-Path -LiteralPath $RuntimeDirectory).Path
if (-not $OutputDirectory) { $OutputDirectory = Join-Path (Split-Path $RuntimeDirectory -Parent) 'verification' }
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$OutputDirectory = (Resolve-Path -LiteralPath $OutputDirectory).Path
$binaryRoot = Join-Path $RuntimeDirectory 'bin'
$commandExecutable = Join-Path $binaryRoot 'FissionCmd.exe'
$guiExecutable = Join-Path $binaryRoot 'Fission.exe'
foreach ($executable in @($commandExecutable, $guiExecutable)) {
    if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) { throw "Missing staged native executable: $executable" }
}
$environmentNames = @('PATH', 'PYTHONHOME', 'FREECAD_USER_HOME', 'TEMP', 'TMP', 'QT_QPA_PLATFORM',
    'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH', 'FISSION_SMOKE_OUTPUT', 'FISSION_PORTABLE_ROOT', 'FISSION_PORTABLE_TEST_OUTPUT')
$savedEnvironment = @{}
foreach ($name in $environmentNames) { $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
$env:PATH = "$binaryRoot;$env:PATH"
$env:PYTHONHOME = $binaryRoot
$env:FREECAD_USER_HOME = Join-Path $OutputDirectory 'command-home'
$env:TEMP = Join-Path $OutputDirectory 'temp'
$env:TMP = $env:TEMP
$env:FISSION_SMOKE_OUTPUT = Join-Path $OutputDirectory 'cad'
New-Item -ItemType Directory -Force -Path $env:FREECAD_USER_HOME, $env:TEMP | Out-Null
$cadOutput = & $commandExecutable (Join-Path $PSScriptRoot 'baseline-cad-smoke.py') 2>&1
$cadExit = $LASTEXITCODE
$cadOutput | Set-Content -LiteralPath (Join-Path $OutputDirectory 'portable-cad.log') -Encoding utf8
if ($cadExit -ne 0 -or -not ($cadOutput | Select-String -SimpleMatch 'BASELINE_CAD_SMOKE_OK 13 checks')) {
    throw 'Staged native command-line CAD smoke failed.'
}
if (-not $SkipGui) {
    Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
    Remove-Item Env:QT_PLUGIN_PATH -ErrorAction SilentlyContinue
    Remove-Item Env:QT_QPA_PLATFORM_PLUGIN_PATH -ErrorAction SilentlyContinue
    $env:FREECAD_USER_HOME = Join-Path $OutputDirectory ('gui-home-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    New-Item -ItemType Directory -Force -Path $env:FREECAD_USER_HOME | Out-Null
    $env:FISSION_PORTABLE_ROOT = $RuntimeDirectory
    $env:FISSION_PORTABLE_TEST_OUTPUT = $OutputDirectory
    $reportPath = Join-Path $OutputDirectory 'portable-gui-report.json'
    if (Test-Path -LiteralPath $reportPath) { Remove-Item -LiteralPath $reportPath }
    $macro = Join-Path $PSScriptRoot 'portable-gui-smoke.FCMacro'
    $log = Join-Path $OutputDirectory 'portable-gui.log'
    $arguments = @('--write-log', '--log-file', ('"' + $log + '"'), ('"' + $macro + '"'))
    $process = Start-Process -FilePath $guiExecutable -ArgumentList $arguments -WorkingDirectory $OutputDirectory -WindowStyle Hidden -PassThru
    if (-not $process.WaitForExit(60000)) {
        Stop-Process -Id $process.Id
        throw 'Staged GUI verification timed out after 60 seconds.'
    }
    if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $reportPath)) {
        throw "Staged GUI did not complete verification: exit $($process.ExitCode). See $log."
    }
    $report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
    if (-not $report.passed) { throw "Staged GUI verification failed: $($report.error)" }
    Write-Output "Staged native GUI verified $($report.workbenches.Count) workbenches; Fission module: $($report.module_path)"
}
Write-Output "Staged native CAD passed 13 checks; evidence: $OutputDirectory"
} finally {
    foreach ($name in $environmentNames) { [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process') }
}
