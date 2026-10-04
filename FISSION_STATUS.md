# Fission 0.1 Alpha

The initial Alpha milestone is implemented and validated in the native Windows
application. Fission is built from pinned recursive FreeCAD source; it retains
engine version 27.1 for document compatibility and presents its own Alpha label.
It includes a unified Design ribbon, Browser, horizontal Timeline, native task
editors, original branding, command search and Fusion-familiar default input.

## Verified on this machine

Validation date: 2026-10-03. Windows 11 x64, MSVC 14.50.35717, Qt/PySide 6.11.1,
Python 3.14.7, OpenCASCADE 8.0.1. FreeCAD pin:
`c1c0b506213e072d6f1498739abb1c3890159426`.

| Check | Result |
| --- | --- |
| Native source compilation and Fission launch | Passed |
| Native CTest executables | 26/26 passed |
| Core document, spreadsheet, Part, PartDesign, Sketcher and Mesh Python tests | 903 run; passed with one skip |
| Fission history and real Qt shortcut tests | 41/41 passed |
| Native command-line CAD workflow | 13/13 passed |
| Integrated native GUI cases | 23/23 passed |
| Settings writer/reader in separate processes | Both passed |
| Engine patch against pristine pinned source | All 15 adaptations applied and matched expected contents |

The native GUI checks cover fully constrained sketches, Extrude, Fillet, Hole,
Linear Pattern, real FCStd save/reopen/recompute and existing upstream FCStd
round trips, STEP solid reimport and watertight STL reimport, Browser/Timeline
selection and ordering, sketch editing, native suppression/errors, rename/Undo,
visibility, native shortcut collisions, typing guards, and model/sketch keys.
Camera checks cover MMB pan, Shift+MMB orbit, Ctrl+Shift+MMB drag zoom, wheel,
F6 Fit, orientation-cube picking and Home.

The interactive workflow actually presses Ctrl+N, creates a sketch through its
native attachment panel, presses E to preview/commit a 24,000 mm³ Extrude, edits
the Timeline feature and cancels a 38,400 mm³ preview, commits a 28,800 mm³ edit,
then presses Ctrl+Z to restore the original solid. F opens a native edge Fillet
preview and commits valid geometry. Tasks stay in Design and belong to the
correct document with multiple documents open. Component activation tests verify
that Create Sketch targets the selected component, including an empty component
when the document's only existing Body belongs elsewhere.

Restart checks verify Light appearance, CAD navigation, Custom shortcuts,
window geometry, Browser width and Timeline height. Test profiles and TEMP are
isolated. Local reports, CAD files and screenshots remain in `test-output`;
engine reports remain in `build/windows-release`. Repeat commands and untouched
baseline comparisons are documented in FISSION_BUILD.md.

The complete upstream Python suite is not claimed as passing. The untouched
baseline had 14 TEMP-related errors among 3,178 tests; the 226 affected tests
passed with isolated TEMP. A later full-suite run stalled in a CAM icon test.
Four baseline native GIL failures were fixed only in upstream test bodies.
No geometry-kernel algorithm was changed.

## Delivery

The portable runtime passed the same 23 native GUI cases and both restart
checks, plus 13 command-line CAD checks. A fresh portable profile activated all
nine required workbenches and verified that the Fission UI, Part, PartDesignGui,
Sketcher and Mesh modules loaded from the staged runtime. Its executable and
native shared modules match the build by SHA256. The matching source snapshot
passed byte verification against 17,815 source files.

Extract `dist/Fission-Alpha-Windows-x64.zip` and open `Fission/bin/Fission.exe`.
The companion `dist/Fission-Alpha-source.zip` includes the matching applied
source. `dist/package-manifest.json` records executable/module, patch and archive
hashes. The tested unpacked runtime also remains under `dist/staging`.

The runtime includes an original editable `examples/machined-plate.FCStd` design.
Dependency notices, licenses/SBOM and FreeCAD attribution accompany the runtime;
the source snapshot includes recursive engine/submodule source, UI, patches,
scripts and a SHA256 manifest. No upstream submission or remote push was made.

## Partial functionality and known differences

- Native FreeCAD feature panels retain their fields and geometry semantics.
  Press Pull maps to sketch Extrude; general face offset, Fusion replay/rollback
  and universal feature reordering are not implemented.
- Move / Copy offers transactional translation and parametric linked copies,
  plus native Transform. Native assembly commands are accessible, but a full
  assembly/joint modeling workflow has not received the same end-to-end coverage.
- Drawing and Manufacture open native TechDraw/CAM workspaces. Their Fission
  presentation and shortcut coverage remain partial. Surface and Mesh commands
  are accessible; their complete specialist workflows need further validation.
- Sheet Metal is not bundled. Available addon commands can enable its tab;
  bundling an addon requires provenance, license and version review.
- Configurable marking menus, cloud/data collaboration, selection modes,
  midpoint modifier and several specialty Fusion commands remain future work.
  Unsupported shortcuts are reserved with an explanation; exact differences
  are in FISSION_SHORTCUTS.md.
- Native camera/SpaceMouse code paths are retained, but this build has no enabled
  SpaceMouse backend and hardware input was not validated.
- This is an unsigned portable development release, built from a development
  FreeCAD pin with the installed newer compiler. No signed installer is supplied.

## Beta priorities

Refine Surface/Mesh and assembly workflows, integrate cohesive Drawing/CAM
presentation, extend selection and marking menus, complete remaining shortcut
mappings, review optional Sheet Metal integration, and expand performance and
specialist geometry acceptance coverage.
