# Fission architecture

Fission builds the pinned FreeCAD C++ application with a small identity/navigation
patch and installs a native Qt Design workbench. It is a desktop CAD application,
not a web shell or a simulated geometry editor.

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

## Browser and Timeline

`browser.py` presents real containment (`Group`, `Origin`, body children) with
product folders, inline labels, visibility, activation and native selection.
Dependency links do not become fake parents. `timeline.py` displays features in
native Document.Objects creation order, preserving per-object Qt items and
scroll/expansion state. App and Gui observers debounce changes; selection
observers synchronize canvas, Browser and Timeline without feedback loops.

Timeline double-click calls the native document's setEdit, reopening the actual
feature task panel. Visibility and writable native Suppressed properties use
document transactions. Existing pending task transactions are protected.
Native errors/touched states, suppressed features, active edits and body tips
are shown. Origin/container objects are excluded from modeling history.

Creation order is not a Fusion replay timeline. Imported/reordered FreeCAD
documents can differ from their dependency order. `history.py` evaluates local
dependency conflicts, but drag reordering stays disabled because legality also
depends on body topology, feature support and native sequential-model semantics.
The UI explains the limitation and never rewrites the dependency graph.

## Input and navigation

`shortcuts.py` provides a pure profile model and Qt event-filter dispatcher.
Factory Fission / Fusion wins over colliding native QAction shortcuts. Context
switching resolves Sketch, Model, Assembly and configured Drawing bindings.
Typing in line/text/numeric editors keeps standard editing behavior. Classic
restores original actions. Custom edits, conflict checking, individual/all reset,
JSON import/export and disk persistence use Fission's parameter namespace.
`search.py` provides S command search over registered commands, aliases, context,
shortcut hints and recent choices. Unsupported documented Fusion keys are
reserved with a visible explanation instead of launching unrelated native tools.
Exact mappings and differences are in FISSION_SHORTCUTS.md.

The native `Gui::FissionNavigationStyle` adapts the pinned upstream CAD navigation
implementation, retaining camera mathematics, selection, editing and SpaceMouse
paths. MMB pans; Shift+MMB orbits; Ctrl+Shift+MMB drag-zooms; wheel zooms. FreeCAD's
existing orientation cube remains clickable and original. Native presets remain
selectable. Branding uses original SVG assets and a generated Windows icon.

## Source and upstream updates

The independent Fission repository retains origin at pjourney/fission and an
upstream FreeCAD remote. `source-lock.json` pins the recursive engine checkout.
The ignored `upstream-src` has its own upstream remote and codex/fission-engine
branch. `patches/0001-fission-identity-navigation.patch` contains reviewable engine
adaptations; installer copies the original Fission executable icon separately.
Fission UI changes remain isolated under Mod/Fission. No geometry-kernel changes
are made and no changes are submitted upstream.

To update upstream: establish a fresh pinned baseline, update dependency lock,
review/rebase the patch against that baseline, audit command IDs/APIs, build,
compare native suites, rerun real CAD/UI smoke tests and update status. Do not
silently follow moving main or discard a locally modified engine checkout.
