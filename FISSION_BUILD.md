# Building Fission on Windows

From a Fission development checkout, run:

```powershell
.\build.ps1 -Jobs 12
.\Launch-Fission.ps1
```

The root build script establishes the pinned recursive engine checkout, verifies
and extracts dependencies, generates the native icons, applies the two source
patches, compiles the application, and installs the Fission workbench and branding.
The resulting native application is `build/windows-release/bin/Fission.exe`;
its command-line companion is `FissionCmd.exe`.

## Source and toolchain

`source-lock.json` pins FreeCAD commit
`c1c0b506213e072d6f1498739abb1c3890159426` and all recursive submodules. The
checkout is stored in `upstream-src`. Applying Fission creates branch
`codex/fission-engine` and retains the FreeCAD remote as `upstream`. Engine
version 27.1 and its document compatibility rules are preserved; the Fission
presentation has its own Alpha 0.1 label.

Requirements are Windows x64, Git, PowerShell, curl, a Windows SDK, and Visual
Studio C++ Build Tools with CMake and Ninja. Allow at least 25 GB of free space
for source, dependencies, compilation, and packaging. This source requires C++23
and CMake 3.22 or later.

The [official LibPack instructions](https://github.com/FreeCAD/FreeCAD-LibPack)
recommend Visual Studio 2022 v143 (MSVC 14.4). Visual Studio 2026 can also install
component `Microsoft.VisualStudio.Component.VC.14.44.17.14.x86.x64`. The scripts
prefer this toolset when available. This machine built successfully with VS 2026
Build Tools, MSVC 14.50.35717, CMake 4.2.3, and Ninja. An optional quiet v143
installer attempt exited 5007 because elevation was required; it made no change.

`scripts/setup-dependencies.ps1` downloads the official portable 7-Zip Extra and
[LibPack 26.3.0 v3.5.5 x64 Release](https://github.com/FreeCAD/FreeCAD-LibPack/releases/tag/3.5.5),
checks SHA256 digests, and extracts them into `.deps`. This release matches the
checked-out Windows release CI. Its LibPack archive SHA256 is
`f7638af6be3a2ea75995dbc74a5cd1408e6d20aefda45a11be1f343e910eeedb`.
Dependencies include Qt/PySide 6.11.1, Python 3.14.7, OpenCASCADE 8.0.1, Boost
1.91, Eigen 5.0.1, and VTK 9.6.2. Coin and Pivy build from the recursive source
submodules. See the [FreeCAD developer handbook](https://freecad.github.io/DevelopersHandbook/gettingstarted/).

## Build modes

```powershell
# Complete branded application workflow.
.\build.ps1 -Jobs 12

# Untouched upstream baseline, only in a clean engine checkout before patches.
.\build.ps1 -Baseline -Jobs 12

# Reconfigure or rebuild an engine checkout whose patches are already applied.
.\scripts\build.ps1 -ConfigureOnly
.\scripts\build.ps1 -BuildOnly -Jobs 12
```

`-Baseline` skips branding and patches. It does not undo existing Fission changes;
use a separate clean pinned checkout for a later baseline comparison. The lower
level `scripts/build.ps1` compiles the source currently present and does not
perform the complete Fission checkout/patch/UI workflow by itself.

Ninja Release uses 12 compiler jobs and one link job by default. GUI, Sketcher,
Part, Part Design, Surface, Mesh, Assembly, TechDraw, CAM, import/export, and
developer tests are enabled. FEM, BIM, and Robot are excluded from this
mechanical CAD alpha. Dependencies are copied into the runtime. Configuration
and compilation logs are in `build/windows-release/configure.log` and `build.log`.
Downloaded dependencies, engine checkout, build outputs, and packages are ignored
by the Fission root repository.

`patches/0001-fission-identity-navigation.patch` contains native executable
identity, resources, navigation, dock startup migration, and document task ownership
changes. `patches/0002-upstream-test-gil.patch`
repairs four upstream StringHasher tests that call the Python API after engine
initialization releases the GIL. It changes test code only. Patch application is
idempotent and leaves the original source notices intact.

Pinned Part Design source files use CRLF. Patch application uses
`--ignore-space-change` to match context while retaining that source format;
all 15 native adaptations were validated against fresh pinned source blobs.
Every expected adaptation applied and its normalized contents matched the
generated result; failed hunks are not ignored.

## Validation

```powershell
# All 26 native CTest executables plus the core mechanical/document Python suites.
.\scripts\test-upstream.ps1 -PythonSuite 'Document,TestSpreadsheet,TestPartApp,TestPartDesignApp,TestSketcherApp,MeshTestsApp'

# Fully constrained sketch, pad, fillet, hole, save/reopen, edit, STEP and STL.
.\scripts\test-cad-smoke.ps1

# Native presentation, integrated modeling/browser/history/shortcuts, then
# separate process settings writer/reader against a persisted profile.
.\scripts\test-gui.ps1

# Full upstream Python app suite, for a separate extended run.
.\scripts\test-upstream.ps1 -SkipCpp -PythonSuite 0
```

The upstream wrapper supplies local DLL/module paths, an isolated profile and
TEMP/TMP directory, and Qt offscreen. CTest has a 180-second timeout per executable.
Logs, JUnit XML, and exit-code summaries are saved in the build directory.
`-SkipCpp`, `-SkipPython`, and `-PythonSuite` support diagnosed reruns.

The CAD smoke wrapper checks an explicit completion marker and JSON assertions,
because the command-line application can catch Python file errors and still
exit successfully. Its real FCStd, STEP, STL, log, and report are saved under
`build/baseline-smoke`; despite that directory name, the wrapper selects the
branded executable when available.

The untouched baseline compiled and launched before source changes. All eight
required workbenches loaded and activated, and a native viewport rendered a
valid solid. Original logs and binary hashes are retained in
`build/baseline-evidence`; GUI evidence is in `build/baseline-gui`.
The original CTest result was 25/26 executables passing, with four StringHasher
GIL failures in the App executable. After the test-only repair, those tests pass.

The original full Python run executed 3,178 tests with 14 errors, 38 skips, and
four expected failures. Every error came from document/spreadsheet temporary
file handling encountering an inaccessible socket directory in the shared
Windows TEMP. An isolated TEMP rerun passed all 226 affected document/spreadsheet
tests. A subsequent full-suite attempt stalled after a CAM tool-shape icon test
and was stopped; its log is preserved. Therefore the full Python suite is not
reported as passing. The selected core suites and native CAD workflow are the
repeatable release checks.

`scripts/test-gui.ps1` launches `tests/smoke.FCMacro` in the native application,
then `tests/persistence.FCMacro` in separate writer and reader processes. It
uses explicit user configuration files, checks completion markers and exit
codes, and restores its temporary environment. Integrated JSON reports, native
logs, FCStd/STEP/STL files, and screenshots are saved in `test-output`.

The final branded engine passed all 26 CTest executables, all 903 selected core
Python tests (one skip), and all 13 native CAD smoke assertions. Engine branding
keeps its original version fields: overriding them with Alpha 0.1 was found to
trigger legacy color restoration and version-migration test failures, so the
Alpha label is confined to presentation.

## Portable package and matching source

After final native, CAD, and integrated GUI/persistence checks pass:

```powershell
# Stage native runtime, notices, and the matching applied source first.
.\scripts\package.ps1 -StageOnly

# Use the stage path printed above. This launches the staged native GUI too.
.\scripts\test-portable.ps1 -RuntimeDirectory '.\dist\staging\<stage>\Fission'

# Refresh UI/docs/source in that stage and create the final archives.
.\scripts\package.ps1 -ReuseStageDirectory '.\dist\staging\<stage>'
```

The script runs the configured CMake install target into a fresh directory under
`dist/staging`, installs Fission UI files, includes root notices and dependency
licenses/SBOM, and produces:

- `dist/Fission-Alpha-Windows-x64.zip`, containing the complete portable runtime.
- `dist/Fission-Alpha-source.zip`, containing the exact applied Fission/FreeCAD
  source and recursive submodule files, patches, scripts, and notices.
- `dist/package-manifest.json`, recording source pin, patch hashes, executable
  hash, archive hashes/sizes, and staging location.

LibPack's generated installer contains absolute dependency destinations. Packaging
relocates the configured prefix in a private copy of that generated install
script so the complete Python/Qt runtime reaches the same stage as native CAD
modules. Engine source and build configuration are preserved. The source snapshot
is checked against every tracked recursive engine file and every Fission root
source file; `SOURCE_SHA256.json` records their verified byte hashes.

Extract the entire runtime ZIP and open `Fission/bin/Fission.exe`. Preserve its
neighboring `Mod`, `Ext`, `data`, and license directories. Verify the staged
native application itself with a fresh profile before distribution; loading only
the build-tree application does not verify installed module/resource paths.
This is an unsigned portable alpha; no signed installer is produced.

`-ReuseStageDirectory` is restricted to an immediate child of `dist/staging`.
It refreshes the native executable/shared libraries, Fission UI, root documentation,
and the applied source snapshot, then verifies the executable matches the build.
Native DLL/PYD files in both `bin` and `Mod` are copied and individually hashed,
including `Mod/PartDesign/PartDesignGui.pyd` after native task ownership changes.
CMake installation repeats only if essential runtime dependencies are missing. Archive
creation repeats the command-line geometry smoke; `test-portable.ps1` also checks
the installed GUI's home/resource paths, the actual Fission module file path,
all nine required workbenches, and a rendered native solid. Evidence stays beside
the runtime under the stage's `verification` directory, outside the runtime ZIP.
The runtime also includes the sample design and usage notes from `examples`.
Both ZIPs are checked with `7za t` before hashes and the package manifest are
written.

The source archive has already-applied native changes and excludes Git metadata.
Its `SOURCE_ARCHIVE_README.txt` documents rebuilding that snapshot with dependency
setup, `scripts/build.ps1`, and `scripts/install-ui.ps1`. A normal Git development
checkout should use root `build.ps1` instead.

