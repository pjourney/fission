[CmdletBinding()]
param(
    [string]$BuildDirectory = (Join-Path (Split-Path $PSScriptRoot -Parent) 'build\windows-release'),
    [string]$OutputDirectory = (Join-Path (Split-Path $PSScriptRoot -Parent) 'test-output'),
    [switch]$SkipSmoke,
    [switch]$SkipPersistence,
    [switch]$WorkspacesOnly,
    [switch]$CanvasOnly,
    [switch]$SearchOnly,
    [switch]$HistoryOnly,
    [switch]$MoveOnly,
    [switch]$RibbonOnly,
    [switch]$SolidOnly,
    [ValidateRange(15,300)][int]$TimeoutSeconds = 180
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$BuildDirectory = (Resolve-Path -LiteralPath $BuildDirectory).Path
$binaryRoot = Join-Path $BuildDirectory 'bin'
$executable = Join-Path $binaryRoot 'Fission.exe'
if (-not (Test-Path -LiteralPath $executable)) { throw 'Build or stage Fission before testing.' }
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$OutputDirectory = (Resolve-Path -LiteralPath $OutputDirectory).Path
$environmentNames = @('PATH', 'PYTHONHOME', 'FREECAD_USER_HOME', 'TEMP', 'TMP', 'QT_QPA_PLATFORM', 'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH', 'FISSION_SOURCE_ROOT', 'FISSION_TEST_OUTPUT', 'FISSION_PERSISTENCE_PHASE')
$savedEnvironment = @{}
foreach ($name in $environmentNames) { $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }

function Invoke-FissionMacro([string]$Name, [string]$Macro, [string]$Profile, [string]$Marker) {
    $markerPath = Join-Path $OutputDirectory $Marker
    if (Test-Path -LiteralPath $markerPath) { Remove-Item -LiteralPath $markerPath }
    $arguments = @('-u', ('"' + (Join-Path $OutputDirectory $Profile) + '"'), '--write-log', '--log-file', ('"' + (Join-Path $OutputDirectory ($Name + '.log')) + '"'), ('"' + (Join-Path $projectRoot $Macro) + '"'))
    $process = Start-Process -FilePath $executable -ArgumentList $arguments -WorkingDirectory $binaryRoot -WindowStyle Hidden -PassThru
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        Stop-Process -Id $process.Id
        throw "$Name timed out. See $OutputDirectory\$Name.log."
    }
    if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $markerPath)) { throw "$Name did not complete; inspect its log." }
    if ((Get-Content -LiteralPath $markerPath -Raw).Trim() -ne 'PASS') { throw "$Name failed; inspect the JSON report in $OutputDirectory." }
    Write-Output "$Name passed in the native application (PID $($process.Id))."
}

try {
    $env:PATH = "$binaryRoot;$env:PATH"
    $env:PYTHONHOME = $binaryRoot
    $env:FREECAD_USER_HOME = Join-Path $OutputDirectory 'runtime-user-home'
    $env:TEMP = Join-Path $OutputDirectory 'temp'
    $env:TMP = $env:TEMP
    New-Item -ItemType Directory -Force -Path $env:FREECAD_USER_HOME, $env:TEMP | Out-Null
    $env:QT_QPA_PLATFORM = 'windows'
    $env:QT_PLUGIN_PATH = $binaryRoot
    $env:QT_QPA_PLATFORM_PLUGIN_PATH = Join-Path $binaryRoot 'platforms'
    $env:FISSION_SOURCE_ROOT = $projectRoot
    $env:FISSION_TEST_OUTPUT = $OutputDirectory
    if ($WorkspacesOnly) { Invoke-FissionMacro 'native-workspaces' 'tests\workspaces.FCMacro' 'workspace.cfg' 'workspace-complete.txt' }
    if ($CanvasOnly) { Invoke-FissionMacro 'native-canvas' 'tests\canvas.FCMacro' 'canvas.cfg' 'canvas-complete.txt' }
    if ($SearchOnly) { Invoke-FissionMacro 'native-search' 'tests\search.FCMacro' 'search.cfg' 'search-complete.txt' }
    if ($HistoryOnly) { Invoke-FissionMacro 'native-history' 'tests\history.FCMacro' 'history.cfg' 'history-complete.txt' }
    if ($RibbonOnly) { Invoke-FissionMacro 'native-ribbon' 'tests\ribbon.FCMacro' 'ribbon.cfg' 'ribbon-complete.txt' }
    if ($SolidOnly) { Invoke-FissionMacro 'native-solid' 'tests\solid.FCMacro' 'solid.cfg' 'solid-complete.txt' }
    if ($MoveOnly) { Invoke-FissionMacro 'native-move' 'tests\move.FCMacro' 'move.cfg' 'move-complete.txt' }
    if (-not $WorkspacesOnly -and -not $CanvasOnly -and -not $SearchOnly -and -not $HistoryOnly -and -not $MoveOnly -and -not $RibbonOnly -and -not $SolidOnly -and -not $SkipSmoke) { Invoke-FissionMacro 'native-smoke' 'tests\smoke.FCMacro' 'user.cfg' 'smoke-complete.txt' }
    if (-not $WorkspacesOnly -and -not $CanvasOnly -and -not $SearchOnly -and -not $HistoryOnly -and -not $MoveOnly -and -not $RibbonOnly -and -not $SolidOnly -and -not $SkipPersistence) {
        foreach ($phase in @('write', 'read')) {
            $env:FISSION_PERSISTENCE_PHASE = $phase
            Invoke-FissionMacro ('persistence-' + $phase) 'tests\persistence.FCMacro' 'persistence.cfg' ('persistence-' + $phase + '-complete.txt')
        }
    }
} finally {
    foreach ($name in $environmentNames) { [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process') }
}
