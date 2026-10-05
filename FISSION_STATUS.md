# Fission 0.4 Alpha

Fission `0.4.0-alpha` refines the S command toolbox with complete results,
contextual readiness, reliable native canvas focus, and persistent recent
launches. Design, Drawing, and Manufacture retain the shared shell, configurable
marking menu, native selection tools, and FreeCAD CAD operations.
The pinned engine keeps version 27.1 for document compatibility. Sketch solving,
geometry, native feature tasks, Undo, and file formats remain authoritative.

## Current validation

Status date: October 5, 2026. Windows 11 x64, MSVC 14.50.35717, Qt/PySide 6.11.1,
Python 3.14.7, OpenCASCADE 8.0.1. FreeCAD pin:
`c1c0b506213e072d6f1498739abb1c3890159426`.

| Check | Current evidence |
| --- | --- |
| Native source compilation | Passed |
| Native CTest executables | 26/26 passed |
| Fission profile/history/marking/search and real Qt tests | 111/111 passed |
| Build-tree integrated native GUI suite | 37/37 passed |
| Installed portable integrated native GUI suite | 37/37 passed |
| Portable settings writer/reader in separate processes | Both passed |
| Installed command-line CAD workflows | 13/13 passed |
| Installed native workbenches and module/resource paths | All nine passed |
| Native patch generation and fresh pinned application | All 25 adaptations passed in 0.3; engine patch unchanged |

The installed GUI repeats the build-tree workflows with its own profile,
embedded Python, native modules, and resources. Actual Qt events invoke native
tools and tasks. These are selected acceptance workflows rather than complete
coverage of every exposed command. The source/runtime hashes and archive
integrity checks are recorded in the delivery manifests.

## Command toolbox acceptance

S opens the native toolbox from Browser or canvas. Every registered command is
searchable; the focused run displays all 599 entries. Names and aliases are
case/whitespace tolerant, and native IDs support literal and word searches.
Matching relevance precedes workspace ties. Empty searches prioritize the
current context and recent successful launches. Ready/Unavailable states and
current shortcuts remain visible; Up/Down skip unavailable rows.

Native action flags supply readiness for loaded commands. Current Fission ribbon
and factory-key tools also work without stock workbench actions. Inactive
workbench tools remain listed as unavailable. This avoids querying native
commands that assume a missing viewer. Selection observation follows the native
action-update delay with one coalesced refresh; closing search removes its
observer and stops its timer. Document/view/context changes, disposed native
handles, a reopened toolbox, and a newly opened modal/popup invalidate dispatch.

Actual Return events launch New Design and native Fillet. Fillet preview, Cancel
rollback, OK with one Undo step, and Ctrl+Z restoration pass. Searching Line from
the Browser during Sketcher editing restores native canvas focus; two canvas
clicks create a real solver-valid line. Finish Sketch releases the native task
and the document saves as FCStd. Escape restores the originating Browser focus.
Visible readiness follows actual selection changes, and closing the owning
document safely invalidates an open search.

History stores at most 12 unique command IDs in versioned Fission settings. A
successful launch means accepted command invocation; cancelling its later CAD
task does not remove it from history. Failed/unavailable launches are excluded.
A separate writer/reader process verifies history reload alongside the existing
appearance, navigation, shortcuts, and layout checks.

## Canvas acceptance

Rectangle and concave freehand tests select actual Part geometry. The concave
fixture contains opposite bounding-box corners while excluding the center,
verifying that polygon selection bypasses the rectangle-only shortcut. Native
handler overlap guards, Ctrl addition, Escape, and cursor/picking restoration pass.
Closing a viewer with an armed native selector releases shared ownership and
allows selection and marking menus in the remaining document.
Paint tests sample frontmost geometry along real strokes, honor a native selection
gate, preserve exact linked parent/subpaths on Escape, and retain another
document's selection. Native idle Assembly editing permits all three tools.
The tested display used device-pixel ratio 1; physical-pixel conversion is
implemented, while multi-monitor scaling coverage remains a future check.

The marking menu opens through Alt+RMB and a custom keyboard shortcut. Disabled
and empty slots retain their directions, Escape and center clicks cancel,
screen-fitting shifts cannot turn a stationary click into a command, and native
right-click menus and MMB camera navigation continue to work. Typing, Classic
profile, disabled configuration, and active feature-task guards pass.

Selecting a real edge and choosing Fillet opens the actual native task. Tests
verify preview geometry, Cancel rollback, OK with one Undo step, and Ctrl+Z
restoration. In native Sketcher editing, the menu starts Line; two actual canvas
clicks create a real line and Finish Sketch releases the native task. Selection
wrappers remain inactive in Sketcher. New Design from Drawing keeps the newly
created document active after deferred workspace/layout restoration.

Preferences tests use actual Qt controls for all seven contexts, command/Empty/
unavailable slots, staged Cancel, OK, Reset Context, and Reset All. Accepting
untouched preferences preserves native wheel-zoom reversal. Separate writer
and reader processes verify custom slots, an unavailable addon ID, the menu's
disabled setting, Light appearance, CAD navigation, custom shortcuts, window
geometry, Browser/Timeline sizes, and hidden cube/navigation-strip preferences.

## Continuing CAD coverage

The integrated suite also covers constrained Sketch/Extrude/Fillet/Hole/Pattern,
native feature and component editing, suppression/error recovery, FCStd
save/reopen and expressions, upstream document compatibility, STEP/STL roundtrips,
Browser/Timeline selection and ordering, real modeling shortcuts, typing guards,
camera gestures, Fit, cube picking, and Home.

Drawing creates and edits a native page/projection group with SVG/PDF/FCStd
exports. Manufacture edits a native CAM Job/Profile and generates cutting motion
with a visible toolpath. Surface/Mesh cases verify native geometry and file
roundtrips. Stitch tests actual Cancel/OK, whole-object/face inputs, tolerance,
six source links, closed-shell geometry, Undo/Redo, and reopen. Native Assembly
tests insertion, Fixed/Revolute joints, J, solver alignment, contextual panel
restoration, and external-link save/reopen. Broader specialist coverage remains
partial.

## Reports and delivery

Primary local evidence:

- `test-output/search-portable/smoke-results.json` and `persistence-report.json`:
  all 37 installed GUI cases and separate restart processes, with native models,
  exports, screenshots, logs, and completion markers.
- `test-output/search-full/smoke-results.json`: passing 37-case build-tree run.
- `test-output/search-focused-4/search-results.json`: three focused native search
  groups, complete catalog/readiness checks, Fillet transactions and Sketcher clicks.
- `build/search-combined-tests.log`: 111 presentation/unit/real Qt checks.
- `test-output/canvas-4/canvas-results.json`: four focused canvas groups, including
  native sketch clicks and unchanged preference/geometry state.
- `test-output/assembly-patch-validation.json`: deterministic generation,
  fresh-baseline application, normalized source equality, and reverse checking
  for all 25 adaptations.
- `dist/0.4.0-alpha/staging/<stage>/verification`: installed native
  GUI/module/workbench checks and 13 command-line CAD cases.

Extract `dist/0.4.0-alpha/Fission-Alpha-Windows-x64.zip` and open
`Fission/bin/Fission.exe`. The companion `Fission-Alpha-source.zip` contains the
matching applied engine/submodule and Fission source. `package-manifest.json`,
`stage-manifest.json`, and `SOURCE_SHA256.json` record archive/native/source hashes.
Native binaries under `bin`, `Mod`, and installed `lib` aliases are refreshed and
verified. Final packaging repeats command-line CAD checks and tests both ZIPs.
The runtime includes the editable machined-plate example and dependency licenses,
notices, and SBOM. Earlier 0.1, 0.2, and 0.3 artifacts are preserved. No remote push or
upstream submission was made.

## Prior evidence and remaining scope

The October 3, 0.1 run passed 903 selected core Python tests with one skip.
The complete upstream Python suite is not claimed as passing: the untouched
baseline had 14 TEMP-related errors among 3,178 tests, the 226 affected cases
passed with isolated TEMP, and a later full run stalled in a CAM icon test.
Four baseline native GIL failures were fixed only in upstream test bodies.
No geometry-kernel algorithm was changed.

- Native FreeCAD fields and CAD semantics remain. Press Pull maps to sketch
  Extrude; general face offset, Fusion replay/rollback, universal reordering,
  and exact inference parity are incomplete.
- Rectangle/freehand use native projected-center/crossing semantics and can
  include occluded geometry. Paint selects frontmost whole objects, including
  links. Active feature tasks and Sketcher keep native selection ownership.
- The marking menu is original Fission UI. Alt+RMB is scoped to Fission navigation;
  other presets use its button or custom key. Drawing sheets keep native menus.
- Additional joint types, large assemblies, Surface/Mesh GUI tools, Drawing
  annotation/dimension coverage, CAM operations, simulation, and post processors
  need broader acceptance.
- Sheet Metal is not bundled. Form, generative design, electronics, cloud/data
  collaboration, midpoint inference parity, and remaining reserved keys are
  outside this release. See `FISSION_SHORTCUTS.md` for explicit differences.
- SpaceMouse hardware was not validated and no backend is enabled in this build.
  This remains an unsigned portable development release without a signed installer.
