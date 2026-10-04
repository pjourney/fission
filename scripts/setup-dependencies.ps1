[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$dependencyRoot = Join-Path $projectRoot '.deps'
New-Item -ItemType Directory -Force -Path $dependencyRoot | Out-Null

function Get-VerifiedDownload([string]$Name, [string]$Url, [string]$Sha256) {
    $destination = Join-Path $dependencyRoot $Name
    if (-not (Test-Path -LiteralPath $destination) -or (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -ne $Sha256) {
        & curl.exe -L --fail --retry 3 --output $destination $Url
        if ($LASTEXITCODE -ne 0) { throw "Download failed: $Name" }
    }
    if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -ne $Sha256) { throw "SHA256 mismatch: $Name" }
    return $destination
}

# Hashes are the official release-asset SHA256 digests published by GitHub.
$extractor = Get-VerifiedDownload '7zr.exe' 'https://github.com/ip7z/7zip/releases/download/26.03/7zr.exe' 'ad4c82fadcbdf93c03b4fc440f300509c7d60c5c2f4d183e35d9d70d6957037d'
$extra = Get-VerifiedDownload '7z2603-extra.7z' 'https://github.com/ip7z/7zip/releases/download/26.03/7z2603-extra.7z' '191894e6acb3647ffb69ce630479ff318523b2e2b9890aa7f05c1127c2e59b8f'
$sevenZipRoot = Join-Path $dependencyRoot '7zip'
if (-not (Test-Path -LiteralPath (Join-Path $sevenZipRoot 'x64\7za.exe'))) {
    & $extractor x $extra "-o$sevenZipRoot" -y
    if ($LASTEXITCODE -ne 0) { throw '7-Zip Extra extraction failed.' }
}
$libPackName = 'LibPack-26.3.0-v3.5.5-x64-Release'
$libPackArchive = Get-VerifiedDownload "$libPackName.7z" "https://github.com/FreeCAD/FreeCAD-LibPack/releases/download/3.5.5/$libPackName.7z" 'f7638af6be3a2ea75995dbc74a5cd1408e6d20aefda45a11be1f343e910eeedb'
$libPackRoot = Join-Path $dependencyRoot $libPackName
if (-not (Test-Path -LiteralPath (Join-Path $libPackRoot 'FREECAD_LIBPACK_VERSION'))) {
    & (Join-Path $sevenZipRoot 'x64\7za.exe') x $libPackArchive "-o$dependencyRoot" -y
    if ($LASTEXITCODE -ne 0) { throw 'LibPack extraction failed.' }
}
Write-Output "Dependencies ready: $libPackRoot"
