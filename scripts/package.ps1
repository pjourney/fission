[CmdletBinding()]
param(
    [string]$BuildDirectory = (Join-Path (Split-Path $PSScriptRoot -Parent) 'build\windows-release'),
    [string]$OutputDirectory = (Join-Path (Split-Path $PSScriptRoot -Parent) 'dist'),
    [switch]$StageOnly,
    [string]$ReuseStageDirectory
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'windows-environment.ps1')
Initialize-FissionBuildEnvironment
$projectRoot = Split-Path $PSScriptRoot -Parent
$engineRoot = Join-Path $projectRoot 'upstream-src'
$libPackRoot = Join-Path $projectRoot '.deps\LibPack-26.3.0-v3.5.5-x64-Release'
$sevenZip = Join-Path $projectRoot '.deps\7zip\x64\7za.exe'
$buildExecutable = Join-Path $BuildDirectory 'bin\Fission.exe'
if (-not (Test-Path -LiteralPath $buildExecutable)) { throw 'Build the branded Fission.exe before packaging.' }
if (-not (Test-Path -LiteralPath $sevenZip)) { throw 'Run setup-dependencies.ps1 before packaging.' }
$sourceLock = Get-Content -LiteralPath (Join-Path $projectRoot 'source-lock.json') -Raw | ConvertFrom-Json
if ((& git -C $engineRoot rev-parse HEAD) -ne $sourceLock.revision) { throw 'Engine revision does not match source-lock.json.' }

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$OutputDirectory = (Resolve-Path -LiteralPath $OutputDirectory).Path
$stageRoot = Join-Path $OutputDirectory 'staging'
New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null
$stageRoot = (Resolve-Path -LiteralPath $stageRoot).Path
if ($stageRoot.StartsWith($engineRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Packaging output must stay outside the engine source checkout.'
}
if ($stageRoot.StartsWith($projectRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    $relativeStageRoot = $stageRoot.Substring($projectRoot.Length + 1).Replace('\', '/')
    & git -C $projectRoot check-ignore --quiet -- $relativeStageRoot
    if ($LASTEXITCODE -ne 0) { throw 'Choose an ignored output directory so staged files do not enter their own source snapshot.' }
}
if ($ReuseStageDirectory) {
    $stageParent = (Resolve-Path -LiteralPath $ReuseStageDirectory).Path
    if (-not $stageParent.StartsWith($stageRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'ReuseStageDirectory must be a stage beneath OutputDirectory/staging.'
    }
    if ((Split-Path $stageParent -Parent) -ne $stageRoot) { throw 'Reuse the stage parent directory, not a runtime or source subdirectory.' }
} else {
    $stageParent = Join-Path $stageRoot (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
}
$runtimeStage = Join-Path $stageParent 'Fission'
$sourceStage = Join-Path $stageParent 'Fission-source'
New-Item -ItemType Directory -Force -Path $runtimeStage, $sourceStage | Out-Null
$needsNativeInstall = -not $ReuseStageDirectory
foreach ($runtimeFile in @('bin\Fission.exe', 'bin\FissionCmd.exe', 'bin\python314.dll', 'bin\platforms\qwindows.dll')) {
    if (-not (Test-Path -LiteralPath (Join-Path $runtimeStage $runtimeFile))) { $needsNativeInstall = $true }
}
if ($needsNativeInstall) {
    # Upstream LibPack installation expands some destinations to an absolute
    # configure-time prefix. Relocate that prefix in a private generated script
    # so both native targets and their dependencies reach this unique stage.
    $cachePrefix = Get-Content -LiteralPath (Join-Path $BuildDirectory 'CMakeCache.txt') |
        Where-Object { $_.StartsWith('CMAKE_INSTALL_PREFIX:PATH=') } | Select-Object -First 1
    if (-not $cachePrefix) { throw 'The configured CMake install prefix could not be read.' }
    $configuredPrefix = $cachePrefix.Substring('CMAKE_INSTALL_PREFIX:PATH='.Length).Replace('\', '/').TrimEnd('/')
    $portablePrefix = $runtimeStage.Replace('\', '/')
    $installScript = Join-Path $stageParent 'portable-install.cmake'
    $generatedInstall = Get-Content -LiteralPath (Join-Path $BuildDirectory 'cmake_install.cmake') -Raw
    $generatedInstall.Replace($configuredPrefix, $portablePrefix) | Set-Content -LiteralPath $installScript -Encoding utf8
    & $script:FissionCMake "-DCMAKE_INSTALL_PREFIX=$portablePrefix" -P $installScript 2>&1 | Tee-Object -FilePath (Join-Path $stageParent 'install.log')
    if ($LASTEXITCODE -ne 0) { throw 'CMake runtime installation failed.' }
} elseif (-not (Test-Path -LiteralPath (Join-Path $runtimeStage 'bin\Fission.exe'))) {
    throw 'Reused stage does not contain the installed Fission executable.'
}
$nativeBuildFiles = @(
    Get-ChildItem -LiteralPath (Join-Path $BuildDirectory 'bin') -File | Where-Object {
        $_.Extension -in @('.dll', '.pyd') -or $_.Name -in @('Fission.exe', 'FissionCmd.exe')
    }
    Get-ChildItem -LiteralPath (Join-Path $BuildDirectory 'Mod') -File -Recurse | Where-Object {
        $_.Extension -in @('.dll', '.pyd')
    }
)
$buildDirectoryFull = (Resolve-Path -LiteralPath $BuildDirectory).Path
$nativeHashes = [ordered]@{}
foreach ($nativeFile in $nativeBuildFiles) {
    $relativeNativePath = $nativeFile.FullName.Substring($buildDirectoryFull.Length + 1)
    $stagedNativeFile = Join-Path $runtimeStage $relativeNativePath
    if ($ReuseStageDirectory) {
        New-Item -ItemType Directory -Force -Path (Split-Path $stagedNativeFile -Parent) | Out-Null
        Copy-Item -LiteralPath $nativeFile.FullName -Destination $stagedNativeFile -Force
    }
    $nativeHash = (Get-FileHash -LiteralPath $nativeFile.FullName -Algorithm SHA256).Hash
    if ((Get-FileHash -LiteralPath $stagedNativeFile -Algorithm SHA256).Hash -ne $nativeHash) {
        throw "Staged native module differs from build: $relativeNativePath"
    }
    $nativeHashes[$relativeNativePath.Replace('\', '/')] = $nativeHash
}
if ((Get-FileHash -LiteralPath (Join-Path $runtimeStage 'bin\Fission.exe') -Algorithm SHA256).Hash -ne
    (Get-FileHash -LiteralPath $buildExecutable -Algorithm SHA256).Hash) {
    throw 'The staged native executable does not match the built executable.'
}
& (Join-Path $PSScriptRoot 'install-ui.ps1') -BuildDirectory $runtimeStage

$licenseRoot = Join-Path $runtimeStage 'licenses'
New-Item -ItemType Directory -Force -Path $licenseRoot | Out-Null
foreach ($noticeName in @('LICENSE', 'NOTICE.md', 'README.md', 'FISSION_SHORTCUTS.md', 'FISSION_STATUS.md', 'FISSION_BUILD.md')) {
    $noticePath = Join-Path $projectRoot $noticeName
    if (Test-Path -LiteralPath $noticePath) { Copy-Item -LiteralPath $noticePath -Destination $runtimeStage }
}
$exampleRoot = Join-Path $projectRoot 'examples'
if (Test-Path -LiteralPath $exampleRoot -PathType Container) {
    Copy-Item -LiteralPath $exampleRoot -Destination $runtimeStage -Recurse -Force
}
$documentationRoot = Join-Path $projectRoot 'docs'
if (Test-Path -LiteralPath $documentationRoot -PathType Container) {
    Copy-Item -LiteralPath $documentationRoot -Destination $runtimeStage -Recurse -Force
}
@'
Fission Alpha for Windows x64

Extract the complete Fission folder, then open bin\Fission.exe.
Keep bin, Mod, Ext, data, and licenses together. No FreeCAD installation is needed.
See FISSION_SHORTCUTS.md for modeling and navigation controls.

The corresponding source is provided in Fission-Alpha-source.zip. Original
FreeCAD and dependency copyrights and licenses are retained in NOTICE.md and
licenses. This alpha is an unsigned portable application.
'@ | Set-Content -LiteralPath (Join-Path $runtimeStage 'START_HERE.txt') -Encoding utf8
Copy-Item -LiteralPath (Join-Path $engineRoot 'LICENSE') -Destination (Join-Path $licenseRoot 'FreeCAD-LICENSE')
$componentLicenseTarget = Join-Path $licenseRoot 'LibPack-components'
$qtSbomTarget = Join-Path $licenseRoot 'Qt-SBOM'
New-Item -ItemType Directory -Force -Path $componentLicenseTarget, $qtSbomTarget | Out-Null
foreach ($redundantDirectory in @((Join-Path $componentLicenseTarget 'licenses'), (Join-Path $qtSbomTarget 'sbom'))) {
    if (Test-Path -LiteralPath $redundantDirectory -PathType Container) {
        $resolvedRedundant = (Resolve-Path -LiteralPath $redundantDirectory).Path
        $resolvedLicenses = (Resolve-Path -LiteralPath $licenseRoot).Path
        if (-not $resolvedRedundant.StartsWith($resolvedLicenses + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or
            (Get-Item -LiteralPath $resolvedRedundant).LinkType) {
            throw 'Redundant generated license directory is outside its safe stage location.'
        }
        Remove-Item -LiteralPath $resolvedRedundant -Recurse -Force
    }
}
Copy-Item -Path (Join-Path $libPackRoot 'share\licenses\*') -Destination $componentLicenseTarget -Recurse -Force
Copy-Item -Path (Join-Path $libPackRoot 'sbom\*') -Destination $qtSbomTarget -Recurse -Force
foreach ($libNotice in @('COPYING', 'LICENSE_LGPL_21.txt', 'OCCT_LGPL_EXCEPTION.txt', 'manifest.json', 'FREECAD_LIBPACK_VERSION')) {
    Copy-Item -LiteralPath (Join-Path $libPackRoot $libNotice) -Destination $licenseRoot
}

function Get-GitFiles([string]$Repository, [string[]]$Options) {
    $files = & git -C $Repository ls-files -z @Options
    if ($LASTEXITCODE -ne 0) { throw "Could not enumerate source files: $Repository" }
    return (($files -join "`n").Split([char]0) | Where-Object { $_ })
}

function Copy-SourceFile([string]$Repository, [string]$DestinationRoot, [string]$RelativePath) {
    if ([IO.Path]::IsPathRooted($RelativePath) -or $RelativePath.Split('/') -contains '..') { throw 'Unsafe source path.' }
    $from = Join-Path $Repository $RelativePath
    if (-not (Test-Path -LiteralPath $from -PathType Leaf)) { return }
    $to = Join-Path $DestinationRoot $RelativePath
    if (Test-Path -LiteralPath $to -PathType Leaf) {
        $original = Get-Item -LiteralPath $from
        $copied = Get-Item -LiteralPath $to
        if ($original.Length -eq $copied.Length -and $original.LastWriteTimeUtc -eq $copied.LastWriteTimeUtc) { return }
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $to -Parent) | Out-Null
    Copy-Item -LiteralPath $from -Destination $to
}

# The engine snapshot contains its actual applied source, with all recursively
# tracked submodule files. Newly added native Fission files are included as well.
$engineSourceStage = Join-Path $sourceStage 'upstream-src'
$engineFiles = @(
    Get-GitFiles $engineRoot @('--recurse-submodules')
    Get-GitFiles $engineRoot @('--others', '--exclude-standard')
) | Sort-Object -Unique
foreach ($sourceFile in $engineFiles) { Copy-SourceFile $engineRoot $engineSourceStage $sourceFile }
$fissionFiles = Get-GitFiles $projectRoot @('--cached', '--others', '--exclude-standard')
foreach ($sourceFile in $fissionFiles) { Copy-SourceFile $projectRoot $sourceStage $sourceFile }

# Keep a reused source snapshot exact when files were renamed or removed.
# Delete only individual files inside the verified stage's source directory.
$expectedSourcePaths = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($sourceFile in $engineFiles) { [void]$expectedSourcePaths.Add('upstream-src/' + $sourceFile) }
foreach ($sourceFile in $fissionFiles) { [void]$expectedSourcePaths.Add($sourceFile) }
foreach ($generatedName in @('SOURCE_ARCHIVE_README.txt', 'SOURCE_SHA256.json')) { [void]$expectedSourcePaths.Add($generatedName) }
$sourceStageFull = (Resolve-Path -LiteralPath $sourceStage).Path
Get-ChildItem -LiteralPath $sourceStageFull -File -Recurse | ForEach-Object {
    if (-not $_.FullName.StartsWith($sourceStageFull + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Staged source cleanup escaped its intended directory.'
    }
    $relativePath = $_.FullName.Substring($sourceStageFull.Length + 1).Replace('\', '/')
    if (-not $expectedSourcePaths.Contains($relativePath)) { Remove-Item -LiteralPath $_.FullName }
}

@'
This archive contains the exact applied Fission and FreeCAD source used by the
runtime, including all recursively checked out engine submodules and licenses.
It excludes Git history, build intermediates, and downloaded dependencies.

To build this already-patched source snapshot on Windows:
  .\scripts\setup-dependencies.ps1
  .\scripts\build.ps1
  .\scripts\install-ui.ps1

To establish a fresh Git-based development checkout instead, use the source-lock
and checkout-engine/apply-fission scripts as documented in FISSION_BUILD.md.
Dependencies and their source provenance are recorded in source-lock.json and
the runtime licenses/manifest.json, component licenses, and Qt SBOM files.
'@ | Set-Content -LiteralPath (Join-Path $sourceStage 'SOURCE_ARCHIVE_README.txt') -Encoding utf8

& (Join-Path $libPackRoot 'bin\python.exe') (Join-Path $PSScriptRoot 'verify-source-snapshot.py') $projectRoot $sourceStage
if ($LASTEXITCODE -ne 0) { throw 'Staged source snapshot differs from the current applied source.' }

$stageManifest = [ordered]@{
    stageDirectory = $stageParent
    runtimeDirectory = $runtimeStage
    sourceDirectory = $sourceStage
    sourceRevision = $sourceLock.revision
    engineSourceFiles = $engineFiles.Count
    fissionSourceFiles = $fissionFiles.Count
    executableSha256 = (Get-FileHash -LiteralPath $buildExecutable -Algorithm SHA256).Hash
    nativeModuleSha256 = $nativeHashes
}
$stageManifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $stageParent 'stage-manifest.json') -Encoding utf8
if ($StageOnly) {
    Write-Output "Runtime and matching source staged: $stageParent"
    Write-Output "Verify with: .\scripts\test-portable.ps1 -RuntimeDirectory '$runtimeStage'"
    Write-Output $stageParent
    return
}

# Native GUI verification is run explicitly against this stage after final UI
# review. The archive step repeats the independent command-line geometry check.
& (Join-Path $PSScriptRoot 'test-portable.ps1') -RuntimeDirectory $runtimeStage -SkipGui

$runtimeZip = Join-Path $OutputDirectory 'Fission-Alpha-Windows-x64.zip'
$sourceZip = Join-Path $OutputDirectory 'Fission-Alpha-source.zip'
foreach ($archive in @($runtimeZip, $sourceZip)) {
    if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive }
}
Push-Location $stageParent
try {
    & $sevenZip a -tzip -mx=5 -mmt=8 -bsp0 -bso0 -bse1 $runtimeZip 'Fission'
    if ($LASTEXITCODE -ne 0) { throw 'Runtime ZIP creation failed.' }
    & $sevenZip a -tzip -mx=5 -mmt=8 -bsp0 -bso0 -bse1 $sourceZip 'Fission-source'
    if ($LASTEXITCODE -ne 0) { throw 'Matching source ZIP creation failed.' }
} finally { Pop-Location }

foreach ($archive in @($runtimeZip, $sourceZip)) {
    & $sevenZip t -mmt=8 -bsp0 -bso0 -bse1 $archive
    if ($LASTEXITCODE -ne 0) { throw "Archive integrity check failed: $archive" }
}

$stagedExecutable = Join-Path $runtimeStage 'bin\Fission.exe'
$buildHash = (Get-FileHash -LiteralPath $buildExecutable -Algorithm SHA256).Hash
if ((Get-FileHash -LiteralPath $stagedExecutable -Algorithm SHA256).Hash -ne $buildHash) { throw 'Packaged executable differs from the built executable.' }
$packageManifest = [ordered]@{
    createdUtc = (Get-Date).ToUniversalTime().ToString('o')
    platform = 'Windows x64'
    archiveIntegrityVerified = $true
    sourceRevision = $sourceLock.revision
    sourceSubmodules = $sourceLock.submodules
    sourcePatchSha256 = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot 'patches') -Filter '*.patch' | ForEach-Object {
        @{ name = $_.Name; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
    })
    executableSha256 = $buildHash
    nativeModuleSha256 = $nativeHashes
    runtimeDirectory = $runtimeStage
    archives = @(foreach ($archive in @($runtimeZip, $sourceZip)) {
        @{ name = (Split-Path $archive -Leaf); bytes = (Get-Item -LiteralPath $archive).Length; sha256 = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash }
    })
}
$packageManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $OutputDirectory 'package-manifest.json') -Encoding utf8
Write-Output "Portable application: $stagedExecutable"
Write-Output "Runtime archive: $runtimeZip"
Write-Output "Matching source archive: $sourceZip"
