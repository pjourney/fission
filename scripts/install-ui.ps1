[CmdletBinding()]
param([string]$BuildDirectory = (Join-Path (Split-Path $PSScriptRoot -Parent) 'build\windows-release'))
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$moduleTarget = Join-Path $BuildDirectory 'Mod\Fission'
New-Item -ItemType Directory -Force -Path $moduleTarget | Out-Null
Copy-Item -Path (Join-Path $projectRoot 'Mod\Fission\*') -Destination $moduleTarget -Recurse -Force
$binTarget = Join-Path $BuildDirectory 'bin'
New-Item -ItemType Directory -Force -Path $binTarget | Out-Null
@'
<?xml version="1.0" encoding="utf-8"?>
<Branding version="1.0">
  <Application>Fission</Application>
  <ExeName>Fission</ExeName>
  <ExeVendor>Fission</ExeVendor>
  <AppDataSkipVendor>true</AppDataSkipVendor>
  <WindowTitle>Fission</WindowTitle>
  <WindowIcon>fission</WindowIcon>
  <ProgramLogo>fission</ProgramLogo>
  <SplashScreen>fissionsplash</SplashScreen>
  <AboutImage>fissionsplash</AboutImage>
  <StartWorkbench>FissionWorkbench</StartWorkbench>
  <NavigationStyle>Gui::FissionNavigationStyle</NavigationStyle>
  <DesktopFileName>org.fission.Fission</DesktopFileName>
  <BuildVersionMajor>0</BuildVersionMajor>
  <BuildVersionMinor>1</BuildVersionMinor>
  <BuildVersionPoint>0</BuildVersionPoint>
  <BuildVersionSuffix>dev</BuildVersionSuffix>
  <BuildRepositoryURL>https://github.com/pjourney/fission</BuildRepositoryURL>
  <CopyrightInfo>Fission is based on the FreeCAD open-source project. Original copyrights and licenses apply.</CopyrightInfo>
</Branding>
'@ | Set-Content -LiteralPath (Join-Path $binTarget 'branding.xml') -Encoding utf8
Write-Host "Fission presentation installed in $BuildDirectory"
