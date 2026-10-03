[CmdletBinding()]
param([string]$Document)
$ErrorActionPreference = 'Stop'
$binary = Join-Path $PSScriptRoot 'build\windows-release\bin\Fission.exe'
if (-not (Test-Path -LiteralPath $binary)) { throw 'Build Fission first; see FISSION_BUILD.md.' }
$launch = @{ FilePath=$binary; WorkingDirectory=(Split-Path $binary -Parent) }
if ($Document) { $launch.ArgumentList = @('"' + (Resolve-Path -LiteralPath $Document).Path + '"') }
Start-Process @launch
