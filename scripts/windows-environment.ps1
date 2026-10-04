Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Initialize-FissionBuildEnvironment {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (-not (Test-Path -LiteralPath $vswhere)) {
        throw 'Install Visual Studio 2022/2026 Build Tools with Desktop development with C++, CMake, and a Windows SDK.'
    }
    $vsRoot = (& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath).Trim()
    if (-not $vsRoot) { throw 'No Visual Studio C++ build environment was found.' }
    Import-Module (Join-Path $vsRoot 'Common7\Tools\Microsoft.VisualStudio.DevShell.dll')
    $toolsets = Get-ChildItem -LiteralPath (Join-Path $vsRoot 'VC\Tools\MSVC') -Directory
    $v143 = $toolsets | Where-Object Name -Like '14.4*' | Sort-Object Name -Descending | Select-Object -First 1
    $devArguments = '-arch=x64 -host_arch=x64'
    if ($v143) {
        $devArguments += ' -vcvars_ver=' + $v143.Name
    } else {
        Write-Warning 'LibPack 3.5.5 tests the v143 toolset. Using the installed newer MSVC toolset; see FISSION_BUILD.md.'
    }
    Enter-VsDevShell -VsInstallPath $vsRoot -SkipAutomaticLocation -DevCmdArguments $devArguments
    $script:FissionCMake = Join-Path $vsRoot 'Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
    $script:FissionCTest = Join-Path $vsRoot 'Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\ctest.exe'
    $ninjaDirectory = Join-Path $vsRoot 'Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja'
    $env:PATH = "$ninjaDirectory;$env:PATH"
    if (-not (Test-Path -LiteralPath $script:FissionCMake)) { throw 'Visual Studio CMake component is required.' }
}
