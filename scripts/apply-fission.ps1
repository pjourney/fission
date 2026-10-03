[CmdletBinding()]
param(
    [string]$SourceDirectory = (Join-Path (Split-Path $PSScriptRoot -Parent) 'upstream-src'),
    [string]$BuildDirectory = (Join-Path (Split-Path $PSScriptRoot -Parent) 'build\windows-release')
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$sourceLock = Get-Content -LiteralPath (Join-Path $projectRoot 'source-lock.json') -Raw | ConvertFrom-Json
$revision = & git -C $SourceDirectory rev-parse HEAD
if ($revision -ne $sourceLock.revision) { throw 'Engine revision differs from source-lock.json; review patches before updating.' }
$patchFile = Join-Path $projectRoot 'patches\0001-fission-identity-navigation.patch'
& git -C $SourceDirectory apply --reverse --check $patchFile 2>$null
if ($LASTEXITCODE -ne 0) {
    & git -C $SourceDirectory apply --check $patchFile
    if ($LASTEXITCODE -ne 0) { throw 'Engine patch does not apply cleanly.' }
    $branch = & git -C $SourceDirectory branch --show-current
    if ($branch -ne 'codex/fission-engine') {
        & git -C $SourceDirectory switch -c codex/fission-engine
        if ($LASTEXITCODE -ne 0) { throw 'Could not create Fission engine branch.' }
    }
    if ((& git -C $SourceDirectory remote) -notcontains 'upstream') { & git -C $SourceDirectory remote rename origin upstream }
    & git -C $SourceDirectory apply $patchFile
    if ($LASTEXITCODE -ne 0) { throw 'Engine patch failed.' }
}
Copy-Item -LiteralPath (Join-Path $projectRoot 'Mod\Fission\resources\fission.ico') -Destination (Join-Path $SourceDirectory 'src\Main\icon.ico') -Force
& (Join-Path $PSScriptRoot 'install-ui.ps1') -BuildDirectory $BuildDirectory
