# Fission 0.6 Alpha architecture

Fission `0.6.0-alpha` builds the pinned FreeCAD C++ application with a small
identity/navigation patch and a shared native Qt shell for Design, Drawing,
and Manufacture. Product labels use **Fission 0.6 Alpha**. The engine retains
its upstream version for document migrations and FCStd compatibility.

## Core and presentation boundary

OpenCASCADE/Part, PartDesign::Body and features, Sketcher and its solver, Coin/Pivy
viewport, Assembly/Ondsel, Mesh, Surface, TechDraw, CAM, Material, Measure and
FreeCAD's Python API remain upstream implementations. FCStd serialization,
STEP/STL import/export, expressions, dependency tracking, recompute, Undo and
native feature preview/task transactions remain authoritative. C++ DLL/Python
module names remain FreeCAD-compatible even though application executables and
product metadata are Fission.

`Mod/Fission/InitGui.py` registers `FissionWorkbench`, displayed as Design, and
applies first-run defaults in Fission's isolated preference directory.
`fission/commands.py` gives CAD tools cohesive names and dispatches to audited
native commands. `shell.py` owns the compact top workspace ribbon, contextual
Sketch toolbar, navigation strip, local start page and integration controller.
`theme.py` centralizes scoped compact dark/light Qt styling. Native feature
editors occupy the right Tasks panel; native property editing remains available.
New designs contain a real App::Part component and PartDesign::Body; activating
another component changes native active containers rather than a synthetic model.

## Native Move / Copy

`move.py` validates native coordinate-system containment and supported movable
types before opening an application-modal Qt dialog. Selection deduplication uses
GeoFeatureGroup parents, not general dependencies. Linked sources and dependent
links are rejected together to prevent inherited placements compounding a move.
Public native parent placements compose the design frame; the inverse frame maps
the design-axis delta and X/Y/Z rotation back to the object's local Placement or
LinkPlacement. Rotation preserves each target's placement origin. Mesh geometry
and native parametric dependencies remain intact.

Preview lazily opens one native transaction and captures getBookedTransactionID,
which exists before HasPendingTransaction becomes true. Cancel/no-op abort only
that ID; OK revalidates after recompute before committing. Owner document/view/
context, native edit owner, target identities/poses, containment frames, link
modes/sources, and preview-copy identities/poses are checked on updates and a
timer. Foreign bookings are never aborted or committed. Source wrappers invalidated
by native deletion/closure cancel safely; shell deactivation/shutdown rejects the
dialog. Copies use App::Link with LinkTransform false in the source component,
retaining source dependencies and native Undo/FCStd serialization. No custom
document feature, proxy, or geometry kernel is added. Assembly descendants keep
native solver movement ownership; whole assembly containers remain movable.

## Workspaces and layout

The selector and Ctrl+[ / Ctrl+] cycle through Design, Drawing, and Manufacture.
Design uses `FissionWorkbench`; Drawing uses `TechDrawWorkbench`; Manufacture
uses `CAMWorkbench` (`PathWorkbench` is the compatibility fallback). The shared
controller, ribbon, Browser, document label, theme, shortcut dispatcher, and
navigation strip remain active in these workspaces. Native task editors and
document views continue to belong to their native modules. Other workbenches
restore their normal native chrome when the Fission shell deactivates.

Design exposes Solid, Surface, Mesh, Assemble, and Utilities tools, plus Sketch
while an actual sketch is being edited. Sheet Metal appears only when its
addon commands are already registered. Drawing groups native sheet creation,
views, dimensions, annotations, and exports. Manufacture groups native jobs,
tools, milling operations, verification, and post processing. These invoke real
TechDraw and CAM document objects and task editors. Availability follows the
installed modules, active document, selection, and current task state.

Timeline is available only in Design. The controller saves Qt dock states as
`Layout_Design`, `Layout_Drawing`, and `Layout_Manufacture` under
`User parameter:BaseApp/Preferences/Fission`; the older `Layout` remains a
Design fallback. Window `Geometry` is shared. Layout restoration runs after
the native main window restores its own state. Workspace changes are refused
while a native task or modeling transaction is active.

## Browser and Timeline

`browser.py` presents real containment (`Group`, `Origin`, body children) with
product folders, inline labels, visibility, activation and native selection.
Dependency links do not become fake parents. `timeline.py` displays features in
native Document.Objects creation order, preserving per-object Qt items and
scroll/expansion state. App and Gui observers debounce changes; selection
observers synchronize canvas, Browser and Timeline without feedback loops.

Timeline double-click and Browser/Timeline Enter call the native document's
setEdit, reopening the actual feature task panel. Visibility and writable native Suppressed properties use
document transactions. Existing pending task transactions are protected.
Feature and datum task dialogs are explicitly attached to their object's
document, so editing history cannot bind a panel to another open document.
PartDesign editors keep the Design workspace active while using native preview,
OK, Cancel and Undo behavior.

The document views claim unmodified Return/Enter/F2/Delete through local
ShortcutOverride/KeyPress filters. The global shortcut dispatcher defers those
keys only when the actual focused view has the document-panel property, so Custom
bindings remain available outside the panels and inline editors keep text input.
A shared Qt delegate reads the native Label instead of decorated item text and
commits through one guarded document transaction. It captures the owner object's
identity and checks it again before commit. Selection synchronization sets the
current index with NoUpdate, preserving Qt extended selection. Native Std_Delete
receives all selected visible object rows once and retains dependency prompts and
Undo; tasks and pending transactions reject competing history operations.
Native Assembly editing also retains Design. Its registered Python view-provider
wrapper exposes native document-provider methods. TaskView keeps document-owned
contextual solver panels after an operation dialog's OK/Cancel and shows them
for their document; Assembly holds the solver panel through a Qt `QPointer` so
deferred widget deletion cannot leave a dangling pointer.
Native errors/touched states, suppressed features, active edits and body tips
are shown. Origin/container objects are excluded from modeling history.

Creation order is not a Fusion replay timeline. Imported/reordered FreeCAD
documents can differ from their dependency order. `history.py` evaluates local
dependency conflicts, but drag reordering stays disabled because legality also
depends on body topology, feature support and native sequential-model semantics.
The UI explains the limitation and never rewrites the dependency graph.

## Canvas interaction

`marking_config.py` validates versioned portable settings and compass hit tests.
`marking.py` owns a Qt popup with eight fixed sectors. Alt+RMB is scoped to the
active native 3D viewport with Fission navigation; both press and release are
consumed. Plain RMB remains in Coin's native context-menu path. The popup closes
and restores canvas focus before queued dispatch through `Controller.execute`.
Document, context, and viewport identity are checked again before invocation.
Native QAction availability disables slots, and modal dialogs/feature tasks,
typing focus, and live native geometric selection handlers block opening.
Normal sketch editing and idle native Assembly editing retain their own contexts.

The native `Std_FreehandSelection` command appends a selection enum without
renumbering existing values and invokes upstream `FreehandSelection`. A shared
handler preserves native cursor/selection state, gates, Ctrl behavior, and
cancellation. Box and freehand commands reject overlapping handlers across views.
A scoped Qt destruction connection releases shared ownership when an armed viewer
closes; normal completion disconnects it without querying a disposing document.
Concave polygons bypass the bounding-box shortcut that is valid only for rectangles.

`selection.py` paints through native `getObjectInfo` ray picks, interpolating
screen samples and respecting physical-pixel coordinates. It adds whole objects
through native selection, retaining the parent/subpath for linked components.
It never replaces a selection gate or changes geometry. NoResolve snapshots and
document-scoped clearing preserve linked and cross-document selections on Escape.
Stroke release, Escape, view/document changes, deactivation, and shutdown restore
the cursor and release Fission's event filter ownership. Feature tasks and sketch
editing keep their native selection workflow.

## Surface and Mesh adapters

Surface tools expose native filling, boundary/section surfaces, ruled surfaces,
blend curves, extension, and subtraction. `fission/surface.py` supplies
`Fission_Stitch`: its Qt tolerance dialog creates an actual `Surface::Sewing`
feature with native `ShapeList` links to selected faces/shapes. Recompute uses
the upstream sewing implementation; successful creation and source visibility
changes form one Undo transaction. Cancel creates no feature, and invalid
results abort the transaction. Stitch produces a sewn shape or shell; it does
not imply that an open set of faces encloses a solid. **Convert to Solid** is a
separate native Part operation for a closed shell. Shell construction, shape
refinement, and geometry checking remain separate native tools.

Mesh import, tessellation, smoothing, reduction, normal repair, hole filling,
and export use native Mesh/MeshPart implementations. Mesh-to-shape conversion
uses native Part's conversion dialog; its Sew option must be enabled when a
closed shell is required. Solid conversion is a subsequent step. These native
mesh/B-rep conversions create static geometry; Fission does not add synthetic
parametric history or hide the distinction between meshes and solids.

## Input and navigation

`shortcuts.py` provides a pure profile model and Qt event-filter dispatcher.
Factory Fission / Fusion wins over colliding native QAction shortcuts. Context
switching resolves `model`, `sketch`, `assembly`, `surface`, `mesh`, `drawing`,
and `cam`. Sketch follows actual edit state; Drawing and CAM follow the native
workbench; Surface/Mesh/Assembly follow the active Design tab. Measure (I),
Compute (Ctrl+B), Appearance (A), and Move (M) retain Surface/Mesh mappings.
Typing in line/text/numeric editors keeps standard editing behavior. Classic
restores original actions. Custom edits, conflict checking, individual/all reset,
JSON import/export and disk persistence use Fission's parameter namespace.
`search.py` provides S command search over all registered commands, aliases,
normalized words and native IDs. Query relevance precedes context; empty queries
prioritize the current context and successful recent launches. Native availability
uses cached action flags plus context-vetted ribbon/factory commands. Registered
tools from unloaded workbenches remain unavailable. Explicit updates and one
coalesced selection follow-up respect the native 150 ms action-update delay.
Availability is checked again before queued dispatch.
Unavailable rows remain visible, while keyboard navigation skips them. Closing
the toolbox restores its source focus; CAD dispatch focuses the native canvas
after close events have settled. A retained document/view identity and context
prevent a stale search from launching a tool in another document or edit mode.
Versioned bounded history under Fission's `CommandSearchHistory` stores only
successful command IDs, retaining no model contents or queries. Unsupported documented Fusion keys are
reserved with a visible explanation instead of launching unrelated native tools.
Exact mappings and differences are in FISSION_SHORTCUTS.md.

The native `Gui::FissionNavigationStyle` adapts the pinned upstream CAD navigation
implementation, retaining camera mathematics, selection, editing and SpaceMouse
paths. MMB pans; Shift+MMB orbits; Ctrl+Shift+MMB drag-zooms; wheel zooms. FreeCAD's
existing orientation cube remains clickable and original. Native presets remain
selectable. F6 fits the native view. Ctrl+Alt+V updates the native orientation
cube visibility in open 3D views and persists `ShowNaviCube`. Ctrl+Alt+N toggles
the Fission navigation strip and persists `ShowNavigation`. These are display
controls; they do not replace camera or selection behavior. Wheel reversal and
native navigation alternatives remain configurable in preferences. Retaining
SpaceMouse code paths is distinct from validating device hardware and its SDK
in a particular build. Branding uses original SVG assets and a generated
Windows icon.

Fission disables native overlay docks on first launch and restores its Qt dock
state after the native main window finishes restoring its own settings. This
keeps Browser, Timeline and Tasks stable across startup and workspace changes.

## Validation

Pure profile/history tests and optional offscreen Qt tests cover presentation
rules, persistence, and event dispatch. `scripts/test-gui.ps1` runs the native
modeling and restart suites; `-WorkspacesOnly` runs serial workspace acceptance.
`tests/workspace_workflows.py` exercises native TechDraw and CAM editors and
exports. `tests/specialist_workflows.py` creates real Surface and Mesh models,
tests save/reopen and interchange, and exposes the actual GUI Stitch
accept/cancel/Undo/Redo case to the serial runner. Its App-only cases can run
under `FissionCmd.exe` with `FISSION_SPECIALIST_AUTORUN=1`.

The 0.6 build-tree and installed portable suites each passed 45 native GUI cases
and separate restart checks; all 156 presentation/Qt tests and 26 native CTest
executables passed. Canvas acceptance includes native concave selection, linked
paint/escape paths, idle Assembly, actual Fillet tasks, actual Sketcher line clicks,
configuration resets, stationary click guards after popup fitting, and New Design
from Drawing. `scripts/test-gui.ps1 -CanvasOnly` runs four focused canvas groups.
Command search adds actual native Fillet tasks, Sketcher line clicks, readiness,
focus and document-lifetime checks. `scripts/test-gui.ps1 -SearchOnly` runs three
focused search groups. Primary installed reports are in `test-output/move-portable`.
`scripts/test-gui.ps1 -HistoryOnly` runs four focused document-panel keyboard
groups. They exercise real label editors and selection keys, native feature
preview/Cancel/OK, dependency warning rejection, multi-object Delete with one Undo,
task/pending guards, and component-scoped Create Sketch from the shared menu.
`scripts/test-gui.ps1 -MoveOnly` runs four native placement/copy/ownership groups,
including rotated parent frames, real M and Ctrl+Z/Ctrl+Y events, preview Cancel,
mesh movement, linked-copy vertices in both placement modes, source recompute,
FCStd reopen, foreign bookings, and closed documents.

Earlier native acceptance for the 0.2 workspace, Stitch, cube, and navigation-strip
controls was exercised on October 4, 2026. The targeted workspace run passed
native TechDraw page/projection editing with SVG/PDF exports, CAM Job/Profile
editing with generated toolpath preview, workspace keyboard cycling, and native
cube/navigation-strip visibility controls. The actual Stitch dialog passed
Cancel and OK with whole-object and face selections, editable tolerance, six
native source links, closed-shell geometry, Undo/Redo, and FCStd save/reopen.

The App-only specialist cases passed native Surface::Filling boundary edits and
Surface::Sewing recompute/solid conversion, and native mesh tessellation,
mesh-to-shape/solid conversion, open-mesh rejection, and file roundtrips. These
results cover selected workflows. They do not establish GUI completion for
every Surface, Mesh, Drawing, or CAM ribbon tool. The final integrated GUI run
passed all 30 cases, including native Assembly insertion, Fixed/Revolute joint
task panels, J dispatch, solver alignment, Browser reactivation, contextual
solver-panel restoration, and external-link save/reopen. Separate writer and
reader processes passed persisted appearance, shortcuts, navigation, cube/strip
visibility, geometry, and dock layout checks. Current scope and report paths
are recorded in FISSION_STATUS.md.

The final installed portable runtime also passed all 30 native GUI cases and
both restart phases. Its Assembly case recorded 241 real before-change GUI
observer calls through the native derived binding, restored an inactive
insertion task's solver panel, and survived Cancel. Installed-runtime acceptance
passed 13 command-line geometry checks, all nine required native workbenches,
installed module/resource paths, and a rendered native solid. Primary delivery
evidence is in `test-output/iteration-portable` and the verified stage's
`verification` directory.

Packaging refreshes and hashes native DLL/PYD copies in `bin` and `Mod` together
with their installed `lib` aliases. The verified 0.2 stage covers 509 native
paths, including 46 such aliases, and 17,822 matching applied-source files
(17,755 engine and 67 Fission). Final archive generation refreshes the matching
source/documentation, repeats independent command-line geometry checks, tests
both ZIPs, and records their hashes in the package manifest. The prior 0.1
delivery is preserved.

## Source and upstream updates

The independent Fission repository retains origin at pjourney/fission and an
upstream FreeCAD remote. `source-lock.json` pins the recursive engine checkout.
The ignored `upstream-src` has its own upstream remote and codex/fission-engine
branch. `patches/0001-fission-identity-navigation.patch` contains reviewable engine
adaptations across 25 source files, including document-owned TaskView contextual
panels and Assembly's `QPointer` solver-panel lifetime guard. Deterministic
generation, application to fresh pinned source, normalized byte comparison,
and reverse checking passed for all 25 adaptations. The installer
copies the original Fission executable icon separately.
Fission UI changes remain isolated under Mod/Fission. No geometry-kernel changes
are made and no changes are submitted upstream.

To update upstream: establish a fresh pinned baseline, update dependency lock,
review/rebase the patch against that baseline, audit command IDs/APIs, build,
compare native suites, rerun real CAD/UI smoke tests and update status. Do not
silently follow moving main or discard a locally modified engine checkout.
