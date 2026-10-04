# Fission 0.2 Alpha

Fission `0.2.0-alpha` extends the native Windows application with a shared
Design, Drawing, and Manufacture shell, contextual Surface/Mesh tools, and a
native Surface Stitch adapter. The pinned FreeCAD engine retains version 27.1
for document compatibility; product labels use **Fission 0.2 Alpha**. Geometry,
sketch solving, recompute, native task editors, Undo, and file formats remain
upstream implementations.

## Current validation

Status date: 2026-10-04. Windows 11 x64, MSVC 14.50.35717, Qt/PySide 6.11.1,
Python 3.14.7, OpenCASCADE 8.0.1. FreeCAD pin:
`c1c0b506213e072d6f1498739abb1c3890159426`.

| Check | Current evidence |
| --- | --- |
| Native source compilation and Fission launch | Passed |
| Native CTest executables | 26/26 passed |
| Fission history/profile and real Qt tests | 43/43 passed |
| Targeted native Drawing, CAM, and workspace/navigation acceptance | 3/3 passed |
| Native Surface/Mesh App-only specialist workflows | 2/2 passed |
| Actual GUI Stitch, whole-object and face selections | Passed |
| Final portable integrated native GUI suite | 30/30 passed |
| Portable settings writer/reader in separate processes | Both passed |
| Installed portable command-line geometry checks | 13/13 passed |
| Installed native workbenches and module/resource paths | All nine passed |
| Native identity/navigation/task/Assembly patch | All 21 adaptations passed fresh-baseline application and byte verification |
| Portable native paths and matching source | 509 native paths and 17,822 source files verified |

The final portable run passed all 30 cases, including native feature/component
editing, Surface/Mesh context and catalog checks with real geometry/file
workflows, Assembly, and workspace controls. It repeats the passing build-tree
suite against the installed runtime. Real Qt events exercise modeling
shortcuts and typing guards; native task panels exercise preview, OK, Cancel,
Undo, and document ownership. These checks cover selected workflows and do not
establish completion for every command exposed in the ribbon.

Drawing acceptance creates a native TechDraw page and projection group, edits
the actual projection task, and writes real SVG, PDF, and FCStd files. Manufacture
acceptance creates a native CAM Job and tool controller, edits a Profile
operation, generates cutting motion, and verifies its visible toolpath preview
and saved document. Workspace acceptance presses the real cycle and visibility
shortcuts, checks native cube state and the navigation strip, and protects an
active task. Browser remains available in all three workspaces; Timeline belongs
to Design, with separate persisted dock layouts.

Assembly acceptance inserts three native linked components, creates Fixed and
Revolute joints through actual task panels, exercises J, and verifies native
solver alignment. The assembly and its external source files save/reopen with
valid geometry and links. Browser reactivation and solver-panel restoration
pass while the Design shell remains active. The native Assembly Python wrapper
exposes its document-provider API; TaskView retains document-owned contextual
panels after operation dialogs close, and a Qt `QPointer` tracks the solver
panel's lifetime. The portable run recorded 241 real before-change GUI observer
calls with the native derived Assembly binding. It also restored an inactive
assembly insertion task's solver panel and survived its native Cancel operation.

Surface specialist tests create six real `Surface::Filling` features linked to
boundary edges and a real `Surface::Sewing` feature linked to those surfaces.
They verify a closed shell, native Part solid conversion, boundary-edit recompute,
FCStd save/reopen, and STEP export/reimport with valid geometry. The GUI Stitch
test clicks the actual Qt Cancel and OK buttons for whole-object and face
selections, changes tolerance from 0.0001 to 0.0002 mm, checks all six native links,
and verifies a closed shell enclosing 3,000 mm³ when converted to a solid.
Native Undo/Redo restores source visibility and the feature; FCStd reopen
preserves its geometry and dependencies. Stitch produces a shell; conversion
to a solid remains a separate native operation.

Mesh specialist tests tessellate an actual bored Part solid through MeshPart,
convert the native mesh through `Part.Shape.makeShapeFromMesh`, and convert a
closed shell to a valid Part solid. They reject an opened mesh, save/reopen FCStd,
export/reimport STL and PLY, and roundtrip the converted B-rep through STEP.
These conversions create static native geometry. The tests validate real APIs
and files, and the integrated run checks the live Surface/Mesh ribbon catalog
and context. GUI completion of every repair, curve, and conversion tool remains
a separate task.

Separate writer and reader processes passed persistence checks for Light
appearance, native CAD navigation, Custom Alt+F, window geometry, Browser width,
Timeline height, and panel layout. Hidden cube/navigation-strip preferences
survive restart, including a newly created native 3D viewer.

Current local evidence includes:

- `test-output/iteration-portable/smoke-results.json` and
  `test-output/iteration-portable/persistence-report.json`: primary final GUI
  and restart evidence for the installed runtime, with native models,
  interchange files, screenshots, logs, and completion markers.
- `dist/0.2.0-alpha/staging/20261004-012143-745/verification/portable-gui-report.json`
  and `verification/cad/report.json`: installed module/resource paths, all nine
  workbenches, a rendered native solid, and 13 geometry checks.
- The same stage's `stage-manifest.json` and `source-verification.json`: native
  hashes and matching applied-source byte verification.
- `test-output/iteration-workspaces-3/workspace-results.json` and its Drawing,
  CAM, and navigation artifacts.
- `test-output/iteration-full-8/smoke-results.json` and
  `test-output/iteration-full-8/persistence-report.json`, with separate completion
  markers and native logs.
- `test-output/iteration-full-8/stitch/gui-stitch-report.json`, including
  `fission-gui-stitch.FCStd`, plus native Drawing, CAM, Surface/Mesh, and Assembly
  models, interchange files, and screenshots from the integrated run.
- `test-output/specialist/specialist-report.json`, `surface-envelope.FCStd`,
  `mesh-conversion.FCStd`, and native interchange files.
- `test-output/assembly-patch-validation.json`, confirming deterministic patch
  generation, fresh pinned-baseline application, normalized byte matches, and
  reverse checking for all 21 adaptations.

Reports and completion markers identify the tested process and output. A
completion marker alone does not imply that every case passed. Repeat commands
and untouched baseline comparisons are documented in FISSION_BUILD.md.

## Prior Alpha evidence

The October 3, 2026, 0.1 Alpha validation ran 903 core document, spreadsheet,
Part, PartDesign, Sketcher, and Mesh Python tests successfully with one skip.
It also passed 13 command-line CAD cases, 23 native GUI cases, and settings
writer/reader checks in separate processes. These are dated prior-release
results, not a fresh run of the expanded 0.2 suite.

Those GUI cases covered constrained sketches, Extrude, Fillet, Hole, Linear
Pattern, FCStd save/reopen and dimension recompute, upstream FCStd compatibility,
STEP solid and watertight STL reimport, Browser/Timeline selection and ordering,
native sketch/feature editing, suppression/error recovery, rename/Undo,
visibility, shortcut collisions and typing guards. Camera checks covered MMB
pan, Shift+MMB orbit, Ctrl+Shift+MMB drag zoom, wheel, F6 Fit, cube picking and Home.
Restart checks verified Light appearance, CAD navigation, Custom shortcuts,
window geometry, Browser width and Timeline height in isolated profiles.

The complete upstream Python suite is not claimed as passing. The untouched
baseline had 14 TEMP-related errors among 3,178 tests; the 226 affected tests
passed with isolated TEMP. A later full-suite run stalled in a CAM icon test.
Four baseline native GIL failures were fixed only in upstream test bodies.
No geometry-kernel algorithm was changed.

## Delivery

The verified portable runtime and matching source snapshot are staged at
`dist/0.2.0-alpha/staging/20261004-012143-745`, preserving the earlier 0.1
artifacts. Stage verification covers 509 native paths, including 46 refreshed
`lib` aliases, and 17,822 matching source files: 17,755 engine files and 67
Fission files. Native DLL/PYD copies under `bin`, `Mod`, and `lib` are refreshed
and compared with the built binaries, so an installed alias cannot silently
retain an older module.

Final archive generation uses that verified stage, refreshes its documentation
and matching source, reruns independent command-line geometry checks, and
checks both ZIPs with `7za t`. `package-manifest.json` records the generated
archive sizes/hashes, executable/module hashes, patch hashes, and source pin;
matching-source byte verification is recorded in `SOURCE_SHA256.json`.
Extract `dist/0.2.0-alpha/Fission-Alpha-Windows-x64.zip` and open
`Fission/bin/Fission.exe`. The companion `Fission-Alpha-source.zip` supplies the
matching applied source.

The runtime includes an original editable `examples/machined-plate.FCStd` design.
Dependency notices, licenses/SBOM, and FreeCAD attribution accompany the runtime;
the source snapshot includes recursive engine/submodule source, UI, patches,
scripts, and a SHA256 manifest. No upstream submission or remote push was made.

## Partial functionality and known differences

- Native FreeCAD feature panels retain their fields and geometry semantics.
  Press Pull maps to sketch Extrude; general face offset, Fusion replay/rollback,
  and universal feature reordering are not implemented.
- Move / Copy offers transactional translation and parametric linked copies,
  plus native Transform. Native Assembly insertion, Fixed/Revolute joints,
  solver, and external-link roundtrips pass; broader joint types, assembly
  simulation, and large-assembly coverage remain partial.
- Drawing and Manufacture now use the shared Fission shell with native
  TechDraw/CAM editors. Selected page/projection and Job/Profile workflows pass;
  coverage of every dimension, annotation, machining operation, simulation, and
  post processor is incomplete. Surface/Mesh API workflows and GUI Stitch pass;
  their broader specialist GUI coverage remains partial.
- Sheet Metal is not bundled. Available addon commands can enable its tab;
  bundling requires provenance, license, and version review.
- Configurable marking menus, cloud/data collaboration, selection modes,
  midpoint modifier, and several specialty Fusion commands remain future work.
  Unsupported shortcuts are reserved with an explanation; exact differences
  are in FISSION_SHORTCUTS.md.
- Native camera/SpaceMouse code paths are retained, but this build has no enabled
  SpaceMouse backend and hardware input was not validated.
- This is an unsigned portable development release, built from a development
  FreeCAD pin with the installed newer compiler. No signed installer is supplied.

## Beta priorities

Extend selection and marking menus, review optional Sheet Metal integration,
and test larger documents and assemblies for performance. Expand
compound-geometry cases, additional Assembly joint types, and native GUI
coverage for Surface/Mesh tools, Drawing dimensions/annotations, CAM operations,
simulation, and post processing. Finish remaining shortcut mappings while
retaining explicit differences from Fusion.
