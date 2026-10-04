[CmdletBinding()]
param(
    [string]$SourceDirectory = (Join-Path (Split-Path $PSScriptRoot -Parent) 'upstream-src'),
    [string]$BuildDirectory = (Join-Path (Split-Path $PSScriptRoot -Parent) 'build\windows-release'),
    [ValidateRange(1, 32)][int]$Jobs = 12,
    [switch]$ConfigureOnly,
    [switch]$BuildOnly
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'windows-environment.ps1')
Initialize-FissionBuildEnvironment
$projectRoot = Split-Path $PSScriptRoot -Parent
$libPackRoot = Join-Path $projectRoot '.deps\LibPack-26.3.0-v3.5.5-x64-Release'
if (-not (Test-Path -LiteralPath (Join-Path $libPackRoot 'FREECAD_LIBPACK_VERSION'))) {
    throw 'Run scripts\setup-dependencies.ps1 first.'
}
New-Item -ItemType Directory -Force -Path $BuildDirectory | Out-Null
if (-not $BuildOnly) {
    $configureArguments = @(
        '-S', $SourceDirectory, '-B', $BuildDirectory, '-G', 'Ninja',
        '-DCMAKE_BUILD_TYPE=Release',
        "-DCMAKE_INSTALL_PREFIX=$projectRoot\dist\Fission",
        "-DFREECAD_LIBPACK_DIR=$libPackRoot",
        '-DFREECAD_COPY_DEPEND_DIRS_TO_BUILD=ON',
        '-DFREECAD_COPY_LIBPACK_BIN_TO_BUILD=ON',
        '-DFREECAD_COPY_PLUGINS_BIN_TO_BUILD=ON',
        '-DFREECAD_RELEASE_PDB=OFF', '-DFREECAD_USE_MP_COMPILE_FLAG=OFF',
        "-DFREECAD_PARALLEL_COMPILE_JOBS:STRING=$Jobs",
        '-DFREECAD_PARALLEL_LINK_JOBS:STRING=1',
        '-DBUILD_GUI=ON', '-DBUILD_TEST=ON', '-DENABLE_DEVELOPER_TESTS=ON',
        '-DBUILD_SKETCHER=ON', '-DBUILD_PART=ON', '-DBUILD_PART_DESIGN=ON',
        '-DBUILD_MESH=ON', '-DBUILD_MESH_PART=ON', '-DBUILD_SURFACE=ON',
        '-DBUILD_ASSEMBLY=ON', '-DBUILD_TECHDRAW=ON', '-DBUILD_CAM=ON',
        '-DBUILD_FEM=OFF', '-DBUILD_BIM=OFF', '-DBUILD_ROBOT=OFF'
    )
    & $script:FissionCMake @configureArguments 2>&1 | Tee-Object -FilePath (Join-Path $BuildDirectory 'configure.log')
    if ($LASTEXITCODE -ne 0) { throw 'CMake configuration failed. See configure.log.' }
}
if (-not $ConfigureOnly) {
    & $script:FissionCMake --build $BuildDirectory --parallel $Jobs 2>&1 | Tee-Object -FilePath (Join-Path $BuildDirectory 'build.log')
    if ($LASTEXITCODE -ne 0) { throw 'Compilation failed. See build.log.' }
}
