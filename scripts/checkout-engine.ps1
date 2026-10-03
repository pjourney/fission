[CmdletBinding()]
param([string]$SourceDirectory = (Join-Path (Split-Path $PSScriptRoot -Parent) 'upstream-src'))
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$sourceLock = Get-Content -LiteralPath (Join-Path $projectRoot 'source-lock.json') -Raw | ConvertFrom-Json
if (-not (Test-Path -LiteralPath (Join-Path $SourceDirectory '.git'))) {
    & git clone --recursive --depth 1 $sourceLock.repository $SourceDirectory
    if ($LASTEXITCODE -ne 0) { throw 'Recursive engine clone failed.' }
}
$revision = & git -C $SourceDirectory rev-parse HEAD
if ($revision -ne $sourceLock.revision) {
    if (& git -C $SourceDirectory status --porcelain) { throw 'Engine has local modifications; do not overwrite them.' }
    $remote = if ((& git -C $SourceDirectory remote) -contains 'upstream') { 'upstream' } else { 'origin' }
    & git -C $SourceDirectory fetch --depth 1 $remote $sourceLock.revision
    if ($LASTEXITCODE -ne 0) { throw 'Pinned engine revision could not be fetched.' }
    & git -C $SourceDirectory checkout --detach $sourceLock.revision
    if ($LASTEXITCODE -ne 0) { throw 'Pinned engine checkout failed.' }
}
& git -C $SourceDirectory submodule update --init --recursive
if ($LASTEXITCODE -ne 0) { throw 'Recursive engine submodules could not be established.' }
Write-Host "FreeCAD engine pinned to $($sourceLock.revision)"
