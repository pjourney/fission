# Fission 0.8 Alpha

Fission `0.8.0-alpha` adds native Revolve Cut, Sweep Cut, Loft Cut, construction
Axis and Point, and component-scoped New Body. Their menus preserve existing
primary tools and protect native task, edit, and transaction ownership. Native
datum OK/Cancel now ends edit mode in the owning document after successful
completion; invalid input retains its task for correction.
The ribbon retains repaired icons, Sketcher and primitive menus, and readable
Dark/Light document panels.
Transactional Move / Copy retains design-axis translation, rotation, live
preview, and native linked copies in the source component.
Browser and Timeline retain keyboard editing, inline rename, multi-object native
deletion, and Create Sketch scoped to the active component. Design, Drawing,
and Manufacture retain the shared
shell, complete S command toolbox with persistent recents, configurable
marking menu, native selection tools, and FreeCAD CAD operations.
The pinned engine keeps version 27.1 for document compatibility. Sketch solving,
geometry, native feature tasks, Undo, and file formats remain authoritative.

## Current validation

Status date: October 6, 2026. Windows 11 x64, MSVC 14.50.35717, Qt/PySide 6.11.1,
Python 3.14.7, OpenCASCADE 8.0.1. FreeCAD pin:
`c1c0b506213e072d6f1498739abb1c3890159426`.

| Check | Current evidence |
| --- | --- |
| Native source compilation | Passed |
| Native CTest executables | 26/26 passed |
| Fission profiles/history/modeling/move/icons/panels/marking/search and real Qt tests | 190/190 passed |
| Build-tree integrated native GUI suite | 53/53 passed |
| Installed portable integrated native GUI suite | 53/53 passed |
| Registered ribbon positions and native menu choices | 127 visible icons; 16 families / 69 choices |
| Portable settings writer/reader in separate processes | Both passed |
| Installed command-line CAD workflows | 13/13 passed |
| Installed native workbenches and module/resource paths | All nine passed |
| Native patch generation and fresh pinned application | All 26 adaptations passed, including datum edit completion |

The installed GUI repeats the build-tree workflows with its own profile,
embedded Python, native modules, and resources. Actual Qt events invoke native
tools and tasks. These are selected acceptance workflows rather than complete
coverage of every exposed command. The source/runtime hashes and archive
integrity checks are recorded in the delivery manifests.

## Ribbon and native tool acceptance

The native inventory identified 40 blank ribbon positions caused by resource
names, SVG suffix handling, or commands registered before native QActions exist.
The shared resolver now uses the backend command's actual pixmap through
FreeCAD's icon cache. Ribbon, search, and marking menu share this resolver.
Original MIT SVGs distinguish 16 Fission shell tools; three further glyphs cover
native fallback, measure, and recompute. Valid native CAD artwork is preserved.
All 127 registered ribbon positions paint at 16 and 26 pixels in Dark and Light
themes. The sole unregistered optional backend, CAM_Surface, is omitted.

Arrow menus expose 16 tool families with 69 registered native choices. Sketcher
offers center/rounded rectangles, three-point circles and ellipses, arc variants,
polygons, straight/arc slots, control/fit-point splines, split/extend, projection,
intersection, sketch copying, and dimensional constraints. Primitive and
Primitive Cut each expose Box, Cylinder, Sphere, Cone, Ellipsoid, Torus, Prism,
and Wedge through their native indexed action groups. Primary button behavior
and keyboard defaults retain their existing tools.

Native tests create a center rectangle and three-point circle through actual
canvas clicks, preserving Sketcher task ownership. Primitive menu tests open
native Box and subtractive Cylinder tasks, verify preview and Cancel, commit
with native Undo/Redo, and save/reopen parametric FCStd geometry. Choice readiness
is refreshed before opening and checked again after the popup releases focus.
Changed document, viewer, edit owner, or workbench prevents stale dispatch.
These cases validate selected operations; exposing a native choice does not
establish completed acceptance for every specialist tool.

Switching Dark/Light appearance refreshes retained Browser item brushes,
Timeline text palettes, and the Browser filter placeholder. Native checks cover
both appearances. Browser/Timeline dock titles and their native Float/Close
controls use matching text colors and native black/white SVG glyphs. Actual
Float/Close clicks and redocking retain readable controls. These scoped changes
apply to Fission's product docks. The [Light ribbon screenshot](docs/fission-ribbon-light.png)
shows the revised workspace and primitive tools.

## Solid cuts, construction datums, and Body acceptance

The Extrude Cut arrow adds Revolve Cut, Sweep Cut, and Loft Cut. These create
native `PartDesign::Groove`, `PartDesign::SubtractivePipe`, and
`PartDesign::SubtractiveLoft` features with their existing tasks and editable
profile, axis, path, and section links. Actual menu clicks exercise angle,
transition, and ruled controls; analytic volumes verify real material removal.
Cancel rolls back the preview; OK commits one Undo operation. Undo/Redo and
FCStd reopen preserve geometry, and source sketch dimension edits recompute
each reopened feature.

The Construction Plane arrow adds native Axis and Point. Their attachment
offset controls, task Cancel/OK, Undo/Redo, edit completion, and FCStd reopen
are tested. A native task repair resets edit mode only in its owning document
after successful OK/Cancel, retaining invalid tasks for correction.

New Body creates a real empty `PartDesign::Body` in the active component or
document root. It clears a selected standalone shape before native invocation
so native Body creation cannot silently import that shape as a base feature.
Cut and datum tools, including Construction Plane, resolve the active component's
unambiguous Body. Existing edits, tasks, modal dialogs, pending or booked
transactions, stale handles,
and mismatched document/component selections block competing operations.
These six added commands also expose readiness in S search. The focused solid
runner contains five groups, including component/root and ownership guards.
Idle Extrude, the full Cut and construction families, and New Component/Body
share these guards. Extrude/Cut retain their explicit Finish Sketch transition.

## Move / Copy acceptance

Actual M opens a native Qt dialog for components, bodies, whole unscaled links,
and standalone Part or Mesh geometry. Translation follows design X/Y/Z axes
through rotated parent components. Rotation applies X, then Y, then Z around
each object's own native placement origin. A selected parent removes selected
descendants before validation, so a component/body/feature selection moves once.
Body-owned modeling features, attached/expression/read-only placements, arrays,
scaled links, mixed unsupported selections, and assembly members are refused.
Assembly members retain native dragging and solver/joint ownership; a whole
assembly container can move. Sources and their dependent selected links must
move separately, preventing compounded geometry transformations.

Live preview changes native placements inside one booked native transaction.
Cancel restores placements and removes temporary copies. Unchanged OK, including
returning preview values to zero, creates no Undo entry. OK commits one operation;
actual Ctrl+Z/Ctrl+Y restore the prior and accepted poses. Native UndoCount
includes the still-active preview transaction. Copies are real App::Link objects,
keep the source's component, and leave source placements unchanged. Both native
LinkTransform modes and link-of-link copies preserve their dependency, geometry,
Undo/Redo, containment, and FCStd save/reopen. Source dimension changes recompute
the copies before and after reopening.

The dialog captures document, viewer, workbench, edit owner, selected identities,
parent frames, link sources/modes, and its booked transaction ID. Existing empty
bookings also block entry. Changed/closed documents and modeling contexts cancel
an owned preview. An externally replaced booking is preserved: native replacement
already commits the preview, whose ordinary Undo remains available after the
foreign operation closes. Closing native Python wrappers cancels safely. Shell
deactivation and shutdown also close the dialog and abort only its own booking.

## Browser and Timeline keyboard acceptance

Arrow keys navigate native object rows; Shift extends selection. Canvas selection
also updates the current keyboard row in both panels without replacing the
selected set. Enter edits one selected feature through its native task; Browser
Enter activates a selected body, component, or assembly. F2 opens an inline editor
containing the native Label, excluding Timeline tip/edit markers. Return commits
one native rename transaction; Escape cancels. Text keys, including E and Delete,
retain their editor behavior. Labels synchronize across both panels and survive
native Undo/Redo and FCStd reopen.

Delete invokes native Std_Delete once for the full selected row set. Native
dependency confirmation and Undo remain authoritative. Right-clicking a selected
row preserves multi-selection for Delete. Active feature tasks and pending
transactions block history edits, rename, and deletion; stale or empty rows cannot
dispatch an operation against unrelated native selection. Enter/F2/Delete are
panel operations in all keyboard profiles, including Custom. Arrow/Home/End/Page
navigation, with Ctrl/Shift, retains Qt selection behavior and takes precedence
over native camera shortcuts or custom bindings while a panel has focus.

Document identity is checked before resolving rows and committing labels, so a
closed or switched design cannot redirect an editor to another same-named object.
Create Sketch from either shared panel menu uses Fission's body adapter and
establishes a real Body in the active empty component before the native plane task.

## Command toolbox acceptance

S opens the native toolbox from Browser or canvas. Every registered command is
searchable. Names and aliases are
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

- `test-output/solid-portable/smoke-results.json` and `persistence-report.json`:
  all 53 installed GUI cases and separate restart processes, with native models,
  exports, screenshots, logs, and completion markers.
- `test-output/solid-full/smoke-results.json`: passing 53-case build-tree run.
- `test-output/solid-focused-3/solid-results.json`: five native cut, datum,
  Body, component-scope, and task/transaction ownership groups.
- `test-output/solid-ribbon-final/ribbon-results.json`: three current ribbon
  groups, including Dark/Light dock-title and glyph contrast, native Float/Close
  clicks, and redocking.
- `test-output/ribbon-focused-5/ribbon-results.json`: three native icon/menu,
  primitive task, and Sketcher variant groups from 0.7; 127 rendered positions, 60 native
  choices, Dark/Light colors, and document/edit-owner dispatch guards.
- `test-output/move-focused-4/move-results.json`: four native Move / Copy groups,
  including actual transformed link vertices in both native placement modes.
- `test-output/search-focused-4/search-results.json`: three focused native search
  groups, complete catalog/readiness checks, Fillet transactions and Sketcher clicks.
- `test-output/history-focused-4/history-results.json`: four focused native panel
  groups covering keyboard selection, inline labels, feature tasks, dependency
  prompts, multi-object Delete/Undo, keypad Enter, and component-aware Create Sketch.
- `build/solid-combined-tests.log`: 190 presentation/unit/real Qt checks,
  including 28 modeling scope/ownership checks, native resources, and the 19 original SVGs.
- `test-output/canvas-4/canvas-results.json`: four focused canvas groups, including
  native sketch clicks and unchanged preference/geometry state.
- `test-output/solid-patch-validation.json`: deterministic generation,
  fresh-baseline application, normalized source equality, and reverse checking
  for all 26 adaptations.
- `dist/0.8.0-alpha/staging/<stage>/verification`: installed native
  GUI/module/workbench checks and 13 command-line CAD cases.

Extract `dist/0.8.0-alpha/Fission-Alpha-Windows-x64.zip` and open
`Fission/bin/Fission.exe`. The companion `Fission-Alpha-source.zip` contains the
matching applied engine/submodule and Fission source. `package-manifest.json`,
`stage-manifest.json`, and `SOURCE_SHA256.json` record archive/native/source hashes.
Native binaries under `bin`, `Mod`, and installed `lib` aliases are refreshed and
verified. Final packaging repeats command-line CAD checks and tests both ZIPs.
The runtime includes the editable machined-plate example and dependency licenses,
notices, and SBOM. Earlier 0.1 through 0.7 artifacts are preserved. Tested
milestones publish to the Fission origin repository's main branch after native
acceptance and package verification. The prior 0.7 milestone is published at
`286bd953e2875a31d318531548187b0e3d2e4564`; the 0.8 release follows the same
acceptance and remote-SHA verification gate. No changes are submitted to the
FreeCAD upstream remote.

## Prior evidence and remaining scope

The October 5, 0.7 release passed 162 unit/Qt tests, 48 GUI cases in both build
and portable applications, and separate settings restart checks. Its ribbon
inventory covered 13 families and 60 native menu choices.

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
