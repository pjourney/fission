# PROJECT: FISSION

You are the principal software architect, senior C++/Qt engineer, CAD application engineer, UX engineer, build engineer, and test engineer responsible for creating a new desktop CAD application named **Fission**.

Fission will be based on the open-source FreeCAD codebase:

https://github.com/FreeCAD/FreeCAD

The interaction model I am most familiar and productive with is Autodesk Fusion:

https://www.autodesk.com/products/fusion-360

Your job is to **actually download, build, modify, rebrand, test, and produce a working application**, not merely write a proposal describing how it could be done.

---

# 1. PRIMARY OBJECTIVE

Transform FreeCAD into **Fission**, a modern parametric mechanical CAD application whose user experience feels immediately familiar to an experienced Autodesk Fusion user.

Fission should retain and exploit FreeCAD's mature CAD engine and functionality while substantially redesigning the application's presentation and workflow.

The goal is:

**FreeCAD's open-source CAD engine + a highly polished Fusion-familiar interaction model = Fission.**

This includes:

- application layout
- modeling workflow
- workspace organization
- feature organization
- sketch workflow
- command placement
- object browser behavior
- parametric history workflow
- selection behavior
- camera/navigation behavior
- contextual editing
- dialog/panel behavior
- terminology where generic CAD terminology allows it
- toolbar organization
- keyboard/mouse efficiency
- **default keyboard shortcuts**
- visual hierarchy
- overall fit and finish

I should be able to open Fission after years of using Fusion and intuitively understand where most important modeling functionality lives **and use the same keyboard shortcuts I already know from Fusion without retraining my muscle memory.**

This is **not** a request to copy Autodesk source code, proprietary assets, icons, trademarks, copyrighted artwork, or private implementation details.

Do not download or redistribute Autodesk application assets.

Create original Fission branding, icons, styling, and implementation.

Behavioral familiarity and standard CAD interaction patterns are desired. Autodesk branding is not.

---

# 2. EXECUTION MODE

Operate as an autonomous engineering agent.

Do not stop after:

- analyzing the repository
- creating an implementation plan
- identifying files to modify
- producing mockups
- writing documentation

Those are intermediate steps.

Continue into implementation.

Your expected end state is:

**a locally buildable, launchable, usable Fission desktop CAD application.**

You have permission to:

- clone public repositories
- inspect source code
- install ordinary development dependencies
- create build environments
- compile software
- modify source code
- add source files
- remove or replace UI code where appropriate
- create original SVG icons and application graphics
- run automated tests
- launch the resulting application
- inspect runtime logs
- diagnose crashes
- iterate on broken implementations
- restructure code where necessary
- create scripts to automate setup/build/package workflows
- use existing FreeCAD functionality instead of unnecessarily reimplementing CAD algorithms

Do not make dangerous or unrelated modifications to the machine.

If something fails, diagnose the failure and attempt to fix it.

Do not abandon an implementation merely because the first build fails.

Do not ask me questions that you can answer through repository inspection, documentation, experimentation, or reasonable engineering judgment.

Ask me only when truly blocked by something requiring human authorization, credentials, subjective product direction that materially affects the architecture, or access you cannot obtain yourself.

---

# 3. BEGIN BY ESTABLISHING THE CODEBASE

Clone FreeCAD using its proper submodule configuration.

Inspect:

- README
- LICENSE files
- CONTRIBUTING
- AI policy
- developer documentation
- CMake configuration
- source tree
- GUI architecture
- workbench architecture
- command architecture
- preferences system
- keyboard shortcut architecture
- document/model architecture
- Python/C++ boundary
- Qt implementation
- selection system
- 3D viewport system
- Part Design
- Part
- Sketcher
- Assembly
- Mesh
- Surface-related functionality
- TechDraw
- CAM/Path functionality
- import/export architecture

Determine the checked-out FreeCAD revision's actual requirements rather than assuming old online tutorials are still correct.

Set up remotes so that:

- the original FreeCAD repository remains available as `upstream`
- Fission development occurs independently
- future FreeCAD updates can reasonably be merged or rebased into Fission

Create a dedicated Fission development branch.

Do **not** submit changes upstream to FreeCAD unless I explicitly request it.

---

# 4. LICENSING AND PROVENANCE

Before significant modifications, inspect FreeCAD's current LICENSE files and the licenses of relevant bundled components.

FreeCAD currently identifies its application licensing as LGPL 2 or later, but treat the repository's checked-out license files as authoritative.

Fission must remain compliant with all applicable licenses.

Preserve:

- copyright notices
- required attribution
- license texts
- source availability obligations
- notices associated with third-party dependencies

Create an appropriate Fission About dialog containing an attribution similar to:

"Fission is based on the FreeCAD open-source project."

Do not imply that FreeCAD or Autodesk endorses Fission.

Do not use Autodesk trademarks as Fission branding.

Do not use Fusion logos or Autodesk icons.

If an optional FreeCAD addon is considered for integration, verify:

1. license compatibility
2. source provenance
3. maintenance status
4. compatibility with the checked-out FreeCAD version

before incorporating it.

Record important third-party provenance in a NOTICE or equivalent documentation file.

---

# 5. REBRAND THE APPLICATION AS FISSION

Replace the primary end-user FreeCAD identity with Fission.

This includes, where technically appropriate:

- application title
- executable/product naming
- splash screen
- application icon
- About window
- default window title
- installer/package branding
- start screen
- welcome page
- configuration labels
- default application metadata
- desktop shortcut metadata
- application bundle metadata
- Windows executable resources where applicable
- macOS bundle resources where applicable
- Linux desktop metadata where applicable

Retain legally required FreeCAD attribution.

Create an original Fission visual identity.

A restrained engineering-oriented visual style is preferred.

Think:

- precision
- mechanical engineering
- technical instrumentation
- modern manufacturing
- controlled energy
- clean geometry

Do not spend excessive time building elaborate branding before the CAD UX works.

A clean original SVG Fission mark is sufficient initially.

---

# 6. THE MOST IMPORTANT REQUIREMENT: CREATE A FUSION-FAMILIAR UI SHELL

The existing FreeCAD UI should not merely receive a new color theme.

I want a significant UX transformation.

Create a Fission UI mode/shell that reorganizes FreeCAD capabilities into a workflow familiar to a Fusion user.

The principal application layout should approximately follow this mental model:

```text
┌──────────────────────────────────────────────────────────────────┐
│ App / File controls | Workspace Selector | Document controls    │
├──────────────────────────────────────────────────────────────────┤
│ SOLID | SURFACE | MESH | SHEET METAL | ASSEMBLE | UTILITIES    │
│ contextual toolbar / grouped modeling commands                  │
├──────────────┬───────────────────────────────────────┬───────────┤
│              │                                       │           │
│   BROWSER    │                                       │ Optional  │
│              │              3D CANVAS                │ task /    │
│ Components   │                                       │ property  │
│ Bodies       │                              ViewCube │ editor    │
│ Sketches     │                                       │           │
│ Origins      │                                       │           │
│ etc.         │                                       │           │
│              │                                       │           │
├──────────────┴───────────────────────────────────────┴───────────┤
│ navigation controls                                             │
├──────────────────────────────────────────────────────────────────┤
│ FEATURE TIMELINE / PARAMETRIC HISTORY                           │
└──────────────────────────────────────────────────────────────────┘
```

Do not blindly reproduce exact Autodesk pixel measurements.

Reproduce the **interaction hierarchy and muscle-memory model**.

---

# 7. DEFAULT WORKSPACE: DESIGN

Fission should start in a unified **Design** workspace rather than forcing users to understand FreeCAD's traditional Workbench switching model.

Internally, FreeCAD modules/workbenches may continue to provide the functionality.

Externally, expose the functionality through a cohesive Fission workspace.

Create toolbar tabs analogous to:

## SOLID

Prioritize commands such as:

- Create Sketch
- Extrude / Pad
- Revolve
- Sweep
- Loft
- Hole
- Fillet
- Chamfer
- Shell
- Draft
- Rib where available
- Mirror
- Rectangular Pattern
- Circular Pattern
- Boolean operations
- Move/Copy
- construction/reference geometry

Map these intelligently onto existing FreeCAD operations.

Use Fusion-familiar generic CAD names in the Fission UI where practical while keeping the underlying FreeCAD architecture intact.

For example, users should not need to understand that one operation happens to originate in one historical FreeCAD workbench and another in another workbench.

## SURFACE

Expose relevant FreeCAD surface/Part capabilities through a coherent surface-oriented toolbar.

## MESH

Expose mesh import, conversion, repair, analysis, and editing functionality that exists in the installed codebase.

## SHEET METAL

Audit the actual capabilities available in the FreeCAD version being used.

If appropriate sheet-metal functionality is not part of the core repository, do not pretend that it exists.

Instead:

- investigate mature compatible FreeCAD sheet-metal addons
- verify licensing
- document the dependency
- optionally integrate it through the Fission setup process

Architecture should allow this tab to exist only when the required functionality is available.

## ASSEMBLE

Expose FreeCAD's current assembly capabilities with Fusion-familiar organization:

- components
- insert component
- create component
- joints/constraints
- grounded/fixed components
- component hierarchy
- visibility
- activation/edit-in-context where supported

Do not fake unsupported assembly functionality.

## UTILITIES

Place secondary tools, inspection, measurement, parameters, import/export utilities, repair tools, etc. here.

---

# 8. BROWSER

Create or substantially adapt the left-side model tree into a **Browser**.

It should feel like a product structure rather than an internal application tree.

Desired organization includes concepts such as:

- document/root design
- components
- bodies
- sketches
- origin
- construction/reference geometry
- joints/assembly relationships
- imported geometry

Important interactions:

- expand/collapse hierarchy
- rename inline
- toggle visibility
- activate component/body
- right-click contextual actions
- selection synchronization between Browser and canvas
- canvas selection highlights corresponding Browser object
- Browser selection highlights canvas object
- sensible icons
- drag/reorganization where safely supported
- contextual creation commands

Reduce internal FreeCAD terminology leaking through the UI when a clearer CAD term exists.

Do not break the underlying FreeCAD document model merely to make the tree prettier.

Implement an adapter/presentation layer when appropriate.

---

# 9. PARAMETRIC FEATURE TIMELINE

This is one of the highest-priority pieces of Fission.

Fusion users rely heavily on the horizontal feature Timeline.

FreeCAD already has parametric object dependencies/history, but its normal presentation differs.

Create a **horizontal Fission Timeline** across the bottom of the Design workspace.

The Timeline should represent the chronological modeling sequence as accurately as FreeCAD's document architecture permits.

At minimum support:

- recognizable feature icons
- feature names
- left-to-right modeling history
- selection
- hover tooltip
- synchronization with Browser/canvas selection
- double-click to edit a feature
- right-click contextual menu
- feature suppression/toggle where FreeCAD semantics safely support it
- visibility status where relevant
- current feature/history marker if practical
- scrolling for large models
- clear indication of errors/broken features

Investigate whether safe feature reordering can be supported.

Do **not** implement naive drag-reordering if it can corrupt dependency graphs.

If reordering is unsafe or only valid under certain dependency conditions:

- calculate whether a move is legal
- permit only legal moves
- disable illegal moves
- explain the dependency conflict in the UI

The CAD model must remain authoritative over visual mimicry.

---

# 10. SKETCH EXPERIENCE

Sketching is central to my workflow.

Make Fission's sketch flow significantly closer to Fusion.

Desired workflow:

1. Click **Create Sketch**
2. select a planar face or origin plane
3. automatically orient the camera normal to the sketch
4. enter a dedicated Sketch contextual mode
5. show sketch creation commands
6. show constraint commands
7. clearly differentiate constrained / under-constrained / construction geometry
8. support common dimensions and constraints efficiently
9. provide a clear **Finish Sketch** action
10. return naturally to the Design workspace
11. make the new sketch immediately useful for Extrude/Revolve/etc.

Prioritize tools such as:

- line
- rectangle variants
- circle
- arc
- polygon
- slot if supported
- spline
- trim
- extend
- offset
- mirror
- pattern
- project geometry
- construction geometry
- horizontal/vertical
- coincident
- tangent
- parallel
- perpendicular
- equal
- concentric
- symmetry
- dimensional constraints

Use existing Sketcher functionality rather than rewriting the constraint solver.

Improve the presentation and workflow around it.

---

# 11. FEATURE CREATION PANELS

Many modeling operations should use a consistent Fission parameter interface.

For operations such as Extrude, Revolve, Fillet, Chamfer, Hole, Pattern, Shell, etc.:

create a consistent parameter panel/dialog experience.

A command should generally:

1. begin from toolbar/context action
2. visually preview changes in the canvas
3. display editable parameters
4. validate input interactively
5. allow OK/Apply/Cancel where appropriate
6. commit the resulting parametric feature
7. place that feature into Browser + Timeline
8. allow the same panel to reopen when editing the feature later

Avoid a patchwork where every operation feels like it came from a completely different application.

Re-use underlying FreeCAD task panels where sensible, but create a common Fission presentation layer.

---

# 12. CAMERA AND MOUSE NAVIGATION

Provide a **Fission/Fusion-style navigation preset** and make it the default.

Research current Fusion navigation semantics from public Autodesk documentation where necessary rather than guessing.

Implement familiar behavior for:

- orbit
- pan
- zoom
- zoom-to-fit
- zoom to selection
- standard orthographic views
- perspective/orthographic switching if supported
- face-normal view
- home/isometric view

Retain additional FreeCAD navigation styles in Preferences for users who want them.

Ensure SpaceMouse/3Dconnexion integration remains intact if FreeCAD already supports it.

---

# 13. VIEW CUBE

FreeCAD already has navigation/view concepts that can be used as a foundation.

Implement or adapt a polished clickable orientation widget in the upper-right of the canvas.

It should provide:

- front
- back
- top
- bottom
- left
- right
- isometric corners
- orientation feedback
- smooth orientation changes where practical
- home view

Do not copy Autodesk's ViewCube artwork.

Create an original Fission implementation/iconography.

---

# 14. CONTEXT MENUS AND MARKING MENU

Normal right-click menus should be context aware.

Additionally, investigate implementing a radial/marking menu for common actions.

For example:

- Sketch
- Extrude
- Hole
- Fillet
- Measure
- Move
- Delete
- Edit Feature

Actual contents should depend on selected entity type and editing mode.

This should improve expert speed without preventing conventional right-click interaction.

Make it configurable if practical.

---

# 15. COMMAND SEARCH

Implement a fast command search/launcher accessible from a convenient keyboard shortcut.

It should:

- search commands by name
- search aliases/synonyms
- show icons
- execute the selected command
- optionally show shortcut hints
- rank recently/frequently used commands
- respect current workspace/context

This can act as an escape hatch while the Fission toolbar evolves.

---

# 16. KEYBOARD SHORTCUTS — MATCH AUTODESK FUSION BY DEFAULT

**This is a hard product requirement.**

The default keyboard shortcuts in Fission should match Autodesk Fusion's current default keyboard shortcuts as closely and comprehensively as technically possible.

My existing Fusion keyboard muscle memory should transfer directly to Fission.

Do not merely provide an optional "Fusion-like" shortcut preset.

The **factory-default Fission shortcut configuration must be Fusion-compatible**.

Before implementing this:

1. Research Autodesk's current publicly documented Fusion keyboard shortcuts.
2. Create a complete inventory of relevant Fusion shortcuts.
3. Compare that inventory against FreeCAD's existing commands and shortcut system.
4. Build an explicit mapping between Fusion commands and the corresponding Fission/FreeCAD commands.
5. Identify conflicts where FreeCAD currently uses the same shortcut for something different.
6. Resolve those conflicts in favor of **Fusion behavior for the default Fission profile**.
7. Preserve the ability for users to customize shortcuts afterward.

Create and maintain a machine-readable mapping such as:

```text
Fusion Command        Fusion Shortcut       Fission Command
-----------------------------------------------------------
Line                  L                     Sketch Line
Circle                C                     Sketch Circle
Extrude               E                     Extrude
Fillet                F                     Fillet
Move/Copy             M                     Move/Copy
Measure               I                     Measure / Inspect
...
```

The exact mappings must come from current Fusion documentation rather than assumptions.

Cover shortcuts across relevant contexts, including:

- general application commands
- modeling
- sketching
- assemblies
- inspection
- navigation
- editing
- selections
- visibility
- timeline/history operations
- document operations
- contextual commands where applicable

Where Fusion assigns the same key differently depending on context, reproduce that contextual behavior where technically practical.

For example, Fission's command dispatcher should understand whether the user is:

- editing a sketch
- modeling a solid
- editing an assembly
- working in a drawing
- interacting with the Browser
- interacting with the Timeline

and invoke the appropriate command.

### Shortcut priority

When a conflict exists between:

- FreeCAD's historical shortcut
- Fusion's shortcut

the **Fusion shortcut wins in Fission's default configuration**.

FreeCAD-native shortcuts may remain available through an optional alternate preset.

### Shortcut presets

Provide at least:

**Fission / Fusion**
- default
- matches Fusion's standard shortcuts as closely as possible

**FreeCAD Classic**
- restores FreeCAD-style shortcuts for existing FreeCAD users

**Custom**
- user-edited configuration

### Shortcut customization

Users must be able to:

- inspect shortcuts
- search commands
- change shortcuts
- remove bindings
- detect conflicts
- reset an individual command
- reset the entire profile
- import/export shortcut mappings if reasonably practical

Changes must persist across application launches.

### Shortcut documentation

Create:

`FISSION_SHORTCUTS.md`

It should document:

- Fusion command
- Fusion shortcut
- corresponding Fission command
- implementation status
- known differences
- context-specific behavior
- commands that cannot be mapped exactly and why

Do not silently ignore shortcuts that cannot be reproduced.

Document the difference and choose the closest sensible behavior.

### Shortcut acceptance testing

Add automated or repeatable tests ensuring the major Fusion shortcuts invoke the correct Fission commands.

At minimum verify common operations such as:

- sketch primitives
- Extrude
- Fillet
- Move/Copy
- Measure
- Delete
- undo
- redo
- save
- open
- common view/navigation commands
- sketch contextual shortcuts
- modeling contextual shortcuts

A Fission Alpha build is **not complete** if its primary shortcuts still behave like stock FreeCAD instead of Fusion.

---

# 17. COMPONENT-FIRST WORKFLOW

Fusion users think heavily in terms of:

- components
- bodies
- sketches
- features

Fission should emphasize this conceptual structure.

Where FreeCAD's internal Body/Part/App::Part/document concepts differ, create a presentation model that minimizes confusion without violating FreeCAD's dependency architecture.

A new user should not need to learn FreeCAD implementation vocabulary before modeling a mechanical part.

---

# 18. DOCUMENTS AND FILE COMPATIBILITY

Preserve FreeCAD document compatibility unless there is an exceptionally strong technical reason not to.

Fission should preferably continue reading and writing FreeCAD-compatible FCStd documents.

If additional Fission metadata is needed:

- store it in a backward-tolerant manner when possible
- avoid unnecessarily forking the file format
- document any compatibility implications

Support standard engineering import/export capabilities already available through FreeCAD, including relevant formats such as STEP and STL.

Do not intentionally lock users into Fission.

---

# 19. VISUAL DESIGN

The application should feel modern and professional.

Avoid:

- excessive gradients
- giant buttons
- toy-like styling
- inconsistent iconography
- excessive rounded-card UI
- excessive whitespace that reduces engineering information density
- obvious web-app styling in a desktop CAD application

Prefer:

- restrained neutral surfaces
- clear separators
- compact engineering-oriented controls
- readable hierarchy
- consistent icon sizing
- predictable hover/active/disabled states
- good high-DPI behavior
- polished dark and light themes where reasonably achievable

Make the 3D viewport the visual focus.

Develop a centralized Qt styling/theme system rather than scattering one-off styles across the application.

Original Fission icons should form a coherent family.

Where existing FreeCAD icons are usable and licensing permits, they may initially be retained while the UX architecture is implemented.

Functionality outranks icon perfection during the first implementation phase.

---

# 20. PREFERENCES

Create a coherent Fission Preferences experience.

Include relevant sections such as:

- General
- Appearance
- Navigation
- Modeling
- Sketch
- Units
- Shortcuts
- Files
- Addons/Extensions where appropriate
- Advanced / FreeCAD compatibility

Important configuration should not require editing configuration files manually.

---

# 21. START EXPERIENCE

Create a clean Fission start screen.

Useful actions:

- New Design
- Open
- Recent Documents
- Import
- Recover document if FreeCAD supports recovery
- Preferences

Avoid building cloud collaboration infrastructure.

Fission should initially be a **local-first desktop CAD application**.

A polished local CAD tool is far more important than attempting to recreate Autodesk's cloud services.

---

# 22. PRIORITIZE CAD — NOT CLOUD FEATURES

Do not try to reproduce Autodesk's proprietary:

- cloud storage
- PLM
- Autodesk account system
- generative cloud services
- Autodesk collaboration infrastructure
- proprietary simulation services

unless an equivalent already exists cleanly in the FreeCAD ecosystem.

The first objective is excellent **mechanical CAD modeling UX**.

Priority order:

**Parametric modeling > sketching > feature history > assemblies > drawings > CAM > advanced specialty functionality.**

---

# 23. MAP FREECAD CAPABILITIES INSTEAD OF REWRITING THEM

Before creating any new geometric algorithm, search the FreeCAD codebase.

Prefer adapting existing functionality.

Examples:

```text
Fission UX concept          Likely FreeCAD foundation
--------------------------------------------------------------
Sketch                      Sketcher
Extrude                     Part Design Pad / Part Extrude
Revolve                     Part Design Revolution / Part Revolve
Fillet                      Part Design / Part fillet functionality
Chamfer                     Part Design / Part
Hole                        Part Design Hole
Patterns                    Part Design patterns
Body                        PartDesign::Body
Surface tools               Part / surface-related modules
Mesh                        Mesh
Assembly                    current FreeCAD Assembly subsystem
Drawing                     TechDraw
CAM                         CAM/Path subsystem
STEP/IGES/BREP              OpenCASCADE-based import/export
Parameters                  FreeCAD property/expression systems
Python automation           FreeCAD Python API
```

Confirm every mapping against the actual checked-out source tree.

Do not assume this table is perfect.

---

# 24. ARCHITECTURE

Avoid producing an unmaintainable giant patch.

Prefer introducing Fission-specific presentation abstractions where appropriate.

Potential architecture may include concepts such as:

```text
src/Gui/Fission/
    FissionMainWindow.*
    FissionWorkspace.*
    FissionToolbar.*
    FissionBrowser.*
    FissionTimeline.*
    FissionCommandSearch.*
    FissionNavigation.*
    FissionMarkingMenu.*
    FissionShortcuts.*
    FissionTheme.*
    FissionPreferences.*
```

This is only a suggestion.

Inspect FreeCAD architecture first and locate functionality where it naturally belongs.

Keep geometry/document logic separated from Fission-specific UI presentation.

We should be able to consume future FreeCAD improvements without every upstream merge becoming catastrophic.

Minimize invasive modifications to CAD kernel/model logic when a UI adapter can accomplish the same goal.

---

# 25. DEVELOPMENT DOCUMENTATION

Maintain these files in the repository:

## FISSION_ARCHITECTURE.md

Explain:

- FreeCAD subsystems being reused
- new Fission UI architecture
- important adapters
- Timeline implementation
- Browser implementation
- shortcut architecture
- workspace/command mapping
- upstream merge strategy

## FISSION_BUILD.md

Provide reproducible instructions for:

- clean checkout
- dependencies
- configure
- compile
- run
- test
- package

for the target platform.

## FISSION_SHORTCUTS.md

Document:

- Fusion command
- Fusion default shortcut
- Fission command mapping
- context
- implementation state
- differences or exceptions

## FISSION_STATUS.md

Maintain:

- completed functionality
- partially completed functionality
- known issues
- next priorities

Update it during implementation.

Do not use documentation as a substitute for implementation.

---

# 26. SOURCE CONTROL DISCIPLINE

Commit working stages logically.

Examples:

```text
build: establish reproducible FreeCAD development environment

brand: introduce Fission application identity

ui: add Fission workspace shell

ui: implement unified Design toolbar

ui: add Fission Browser presentation model

ui: add parametric feature Timeline

input: implement Fusion-compatible default shortcuts

ui: implement Fusion-familiar navigation preset

sketch: integrate contextual Fission sketch workflow

modeling: unify solid feature command panels

test: add Fission modeling workflow smoke tests
```

Avoid a single enormous "change everything" commit.

Do not rewrite upstream history.

---

# 27. TESTING

Testing is mandatory.

Run existing FreeCAD tests regularly.

Add Fission-specific tests where feasible.

At minimum perform automated or repeatable smoke testing for these workflows.

### Workflow A — basic parametric part

1. Start Fission.
2. Create New Design.
3. Create a sketch on XY.
4. Draw a centered rectangle.
5. dimension it.
6. Finish Sketch.
7. Extrude it.
8. Add a fillet.
9. Add a hole.
10. Save.
11. Close.
12. Reopen.
13. edit the original sketch dimension.
14. verify downstream geometry updates.

### Workflow B — feature history

Create:

Sketch → Extrude → Fillet → Sketch → Hole → Pattern

Verify:

- Browser objects
- Timeline order
- editing via Timeline
- selection synchronization
- error handling
- recompute behavior

### Workflow C — Fusion shortcut compatibility

Test major modeling workflows **using keyboard shortcuts instead of toolbar clicks wherever Fusion provides a default shortcut**.

Verify:

- the expected Fusion key invokes the corresponding Fission command
- shortcut behavior changes appropriately with context
- sketch-mode shortcuts work
- model-mode shortcuts work
- conflicting FreeCAD defaults do not override Fusion behavior
- shortcut customization persists after restart
- resetting the profile restores Fusion-compatible defaults

### Workflow D — interchange

Create a model and export:

- STEP
- STL

Re-import where appropriate and verify basic geometry validity.

### Workflow E — UI persistence

Change:

- panel sizes
- theme
- navigation preference
- shortcut

Restart Fission and verify preferences remain.

### Workflow F — existing FreeCAD document

Open a representative FCStd file and verify Fission does not damage it merely by opening and saving it.

---

# 28. PERFORMANCE AND STABILITY

Do not sacrifice FreeCAD stability for superficial UI mimicry.

Monitor:

- startup errors
- Qt warnings
- crashes
- memory issues
- recompute problems
- viewport regressions
- document serialization issues

Avoid continuously rebuilding entire UI models when incremental updates are possible.

The Browser and Timeline must remain usable on non-trivial documents.

---

# 29. INITIAL MILESTONE

The first meaningful milestone is **Fission Alpha**.

Fission Alpha is achieved when all of the following are true:

- application builds from source
- launches under Fission branding
- opens existing FCStd files
- new Design starts in the Fission interface
- unified Design workspace exists
- Solid toolbar exists
- Browser exists
- horizontal feature Timeline exists
- Create Sketch workflow functions
- Finish Sketch workflow functions
- Extrude functions
- Fillet functions
- Hole functions
- pattern functionality is accessible
- feature editing from Timeline works
- Fusion-familiar navigation preset works
- **Fusion-compatible keyboard shortcuts are the application defaults**
- **major Fusion modeling and sketch shortcuts have been tested**
- View orientation widget works
- saving/reopening works
- STEP/STL export still works
- existing FreeCAD automated tests have not suffered major regressions
- Fission build/run instructions are reproducible

Do not postpone the Timeline or Fusion shortcut compatibility until some hypothetical later redesign.

They are core to the product.

---

# 30. SECOND MILESTONE

After Alpha is stable, proceed toward **Fission Beta**:

- polished Surface tab
- Mesh tab
- assembly workflow
- sheet metal integration if legitimately available
- drawings workflow
- CAM workspace
- configurable marking menu
- command search refinement
- complete remaining Fusion shortcut mappings
- improved icon family
- light/dark themes
- installer/package
- performance refinement
- improved onboarding

---

# 31. ACCEPTANCE STANDARD

I do not consider this project successful if the result is:

"FreeCAD with Fission written in the title bar."

The result should feel like a deliberately designed CAD application.

When I launch it, the difference should be immediately apparent.

When I create a sketch, extrude it, add features, edit earlier history, create components, navigate the model, **and use keyboard shortcuts**, my existing Fusion habits should transfer naturally.

I should not have to relearn commands merely because Fission is built on FreeCAD.

If I press a standard Fusion shortcut, I expect Fission to perform the corresponding action wherever technically possible.

At the same time, this must remain a real CAD system built on FreeCAD's mature capabilities rather than a fragile visual imitation.

---

# 32. DO NOT OVER-PLAN

Spend enough time understanding FreeCAD to avoid reckless architecture.

Then start changing code.

A good sequence is:

**inspect → build untouched upstream → launch → establish baseline → rebrand → create Fission shell → implement Browser/Timeline → implement Fusion shortcuts → integrate modeling commands → test → iterate**

Do not spend the entire session writing an architecture manifesto.

Working software is the objective.

---

# 33. FIRST ACTIONS

Begin now.

Your first actions should be:

1. inspect the machine/OS/toolchain
2. inspect available disk space and development tools
3. clone FreeCAD recursively
4. inspect the repository and current development documentation
5. verify licensing
6. establish the correct dependency/toolchain configuration
7. build **unmodified FreeCAD**
8. run it and establish a known-good baseline
9. create the Fission development branch
10. research and inventory Fusion's current default keyboard shortcuts
11. map Fusion shortcuts to FreeCAD/Fission commands
12. implement the first Fission branding/UI-shell changes
13. implement the Fusion-compatible default shortcut profile
14. rebuild
15. launch
16. verify shortcut behavior
17. continue iteratively toward Fission Alpha

If dependency installation requires elevated permission that you cannot obtain, prepare the exact installation command, complete every other action you can, and clearly identify the single remaining blocker.

Otherwise, continue autonomously.

---

# 34. IMPORTANT PRODUCT PRINCIPLE

Whenever you must choose between:

A. faithfully reproducing some incidental Fusion visual detail

and

B. creating a robust, intuitive implementation that works naturally with FreeCAD's architecture

choose **B**.

Whenever you must choose between:

A. exposing FreeCAD's historical internal organization

and

B. presenting the same capability through a coherent modern mechanical-CAD workflow

choose **B**, provided doing so does not damage model correctness.

However, when dealing with **keyboard shortcuts and interaction muscle memory**, favor compatibility with Fusion wherever technically reasonable.

The product is not intended to be a screenshot clone.

It is intended to give me **Fusion-level familiarity—including Fusion keyboard muscle memory—on top of FreeCAD's open platform**.

That product is **Fission**.

Start implementation now.