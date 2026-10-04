[CmdletBinding()]
param(
    [string]$BuildDirectory = (Join-Path (Split-Path $PSScriptRoot -Parent) 'build\windows-release'),
    [string]$PythonSuite = '0',
    [switch]$SkipCpp,
    [switch]$SkipPython
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'windows-environment.ps1')
Initialize-FissionBuildEnvironment
$binaryRoot = Join-Path $BuildDirectory 'bin'
$moduleDirectories = Get-ChildItem -LiteralPath (Join-Path $BuildDirectory 'Mod') -Directory | ForEach-Object FullName
$env:PATH = ($moduleDirectories -join ';') + ";$binaryRoot;$env:PATH"
$env:PYTHONHOME = $binaryRoot
$env:FREECAD_USER_HOME = Join-Path $BuildDirectory 'test-home'
New-Item -ItemType Directory -Force -Path $env:FREECAD_USER_HOME | Out-Null
$testTempDirectory = Join-Path $BuildDirectory 'test-temp'
New-Item -ItemType Directory -Force -Path $testTempDirectory | Out-Null
$env:TEMP = $testTempDirectory
$env:TMP = $testTempDirectory
$env:QT_QPA_PLATFORM = 'offscreen'
$env:QT_PLUGIN_PATH = $binaryRoot
$env:QT_QPA_PLATFORM_PLUGIN_PATH = Join-Path $binaryRoot 'platforms'
$results = @()
if (-not $SkipCpp) {
    & $script:FissionCTest --test-dir $BuildDirectory --output-on-failure --timeout 180 --output-junit (Join-Path $BuildDirectory 'upstream-ctest.xml') 2>&1 | Tee-Object -FilePath (Join-Path $BuildDirectory 'upstream-ctest.log')
    $results += @{ suite = 'CTest'; exitCode = $LASTEXITCODE }
}
if (-not $SkipPython) {
    $commandExecutable = Join-Path $binaryRoot 'FissionCmd.exe'
    if (-not (Test-Path -LiteralPath $commandExecutable)) { $commandExecutable = Join-Path $binaryRoot 'FreeCADCmd.exe' }
    & $commandExecutable -t $PythonSuite 2>&1 | Tee-Object -FilePath (Join-Path $BuildDirectory 'upstream-python-tests.log')
    $results += @{ suite = 'FreeCAD Python app tests'; exitCode = $LASTEXITCODE }
}
$results | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $BuildDirectory 'upstream-test-results.json') -Encoding utf8
if ($results | Where-Object { $_.exitCode -ne 0 }) { throw 'Upstream test failures. Inspect the logs and upstream-test-results.json.' }
