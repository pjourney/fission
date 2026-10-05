# Fission 0.5 Alpha keyboard shortcuts

Fission / Fusion is the default profile. These defaults come from Autodesk's public [Fusion keyboard reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-GetStarted/files/GUID-F0491540-0324-470A-B651-2238D0EFAC30.htm), checked on October 3, 2026. They describe behavior; Fission includes no Autodesk icons, artwork, or application assets.

The table records the implemented dispatcher mapping. Actual operation availability still depends on the active document, selection, and installed FreeCAD modules. The pure profile tests verify dispatch resolution and persistence; the GUI/modeling smoke suite verifies native invocation separately.

In the Browser and Timeline, **Enter** edits one selected feature (**Enter** on a
Browser body/component/assembly activates it), **F2** renames inline, and **Delete**
invokes native deletion for the full selection. These unmodified keys retain their
panel meaning in Fission, Custom, and Classic profiles. Custom assignments still
work elsewhere. Arrow keys and Shift selection remain native Qt navigation.
Inline label editors retain normal text keys; Return commits and Escape cancels.
Active modeling tasks and pending transactions protect their history ownership.
Arrow/Home/End/Page navigation with Ctrl/Shift also belongs to these panels while
focused, taking precedence over camera shortcuts or Custom assignments.

| Fusion command | Default | Fission command | Context | State / difference |
|---|---|---|---|---|
| Toolbox | S | Fission_Search | Any | Complete command search with readiness, shortcut hints and persistent recents |
| Extrude | E | Fission_Extrude | Model / sketch | Finishes the sketch when required; uses FreeCAD feature tools |
| Press Pull | Q | Fission_Extrude | Model / sketch | Partial: sketch extrusion; face offset is not implemented |
| Fillet | F | Fission_Fillet | Model | Mapped |
| Hole | H | Fission_Hole | Model | Mapped |
| Move | M | Fission_Move | Model / assembly / surface / mesh | Mapped to Fission's Move / Copy adapter |
| Visibility | V | Fission_Visibility | Any | Mapped |
| Appearance | A | Fission_Appearance | Model / sketch / assembly / surface / mesh | Native Std_SetAppearance editor |
| Measure | I | Fission_Measure | Model / sketch / assembly / surface / mesh | Mapped |
| Compute All | Ctrl+B | Fission_Compute | Model / sketch / assembly / surface / mesh | Recompute document |
| Joint | J | Fission_AssemblyJoint | Model / assembly | Uses native Assembly joint workflow |
| Line | L | Sketcher_CreateLine | Sketch | Mapped |
| Rectangle | R | Sketcher_CreateRectangle | Sketch | Two-point rectangle |
| Circle | C | Sketcher_CreateCircle | Sketch | Center-radius drawing; diameter dimensions available |
| Trim | T | Sketcher_Trimming | Sketch | Mapped |
| Offset | O | Sketcher_Offset | Sketch | Mapped |
| Project | P | Sketcher_Projection | Sketch | Legacy Sketcher_External fallback |
| Construction | X | Sketcher_ToggleConstruction | Sketch | Mapped |
| Dimension | D | Sketcher_Dimension | Sketch | Native smart dimension tool |
| New Design | Ctrl+N | Fission_NewDesign | Any | Local document |
| Open | Ctrl+O | Std_Open | Any | Local documents / imports |
| Save | Ctrl+S | Std_Save | Any | Local FCStd save; no cloud versions |
| Recovery Save | Ctrl+Shift+S | Std_SaveCopy | Any | Partial: local copy, not Fusion recovery storage |
| Document tabs | Ctrl+Tab | Std_ActivateNextWindow | Any | Next document |
| Undo / redo | Ctrl+Z / Ctrl+Y | Std_Undo / Std_Redo | Any | Native document transactions |
| Copy / paste / cut | Ctrl+C / Ctrl+V / Ctrl+X | Std_Copy / Std_Paste / Std_Cut | Any | Native FreeCAD semantics |
| Delete | Delete | Std_Delete | Any | Native dependency-aware deletion |
| Browser | Ctrl+Alt+B | Fission_ToggleBrowser | Any | Show / hide Browser |
| ViewCube | Ctrl+Alt+V | Fission_ToggleViewCube | Any active document | Show / hide the native orientation cube in open 3D views; preference persists |
| Navigation bar | Ctrl+Alt+N | Fission_ToggleNavigation | Any | Show / hide Fission's navigation strip; preference persists |
| Previous workspace | Ctrl+[ | Fission_PreviousWorkspace | Any | Cycle Design → Manufacture → Drawing → Design |
| Next workspace | Ctrl+] | Fission_NextWorkspace | Any | Cycle Design → Drawing → Manufacture → Design |
| Reset Layout | Ctrl+Alt+R | Fission_ResetLayout | Any | Restore Fission panels |
| Projected View | P | TechDraw_ProjectionGroup | Drawing | Native projection group; different panel details |
| Dimension | D | TechDraw_Dimension | Drawing | Native drawing dimension |
| Text | T | TechDraw_Annotation | Drawing | Native drawing annotation |
| Balloon | B | TechDraw_Balloon | Drawing | Native drawing balloon |
| Window Selection | 1 | Fission_WindowSelection | Idle 3D model / assembly / surface / mesh / CAM | Native rectangle, projected-center and crossing behavior; Ctrl adds |
| Freeform Selection | 2 | Fission_FreeformSelection | Idle 3D model / assembly / surface / mesh / CAM | Native freehand polygon, projected object centers; Ctrl adds |
| Paint Selection | 3 | Fission_PaintSelection | Idle 3D model / assembly / surface / mesh / CAM | One left-drag stroke selects frontmost objects through native ray picking; Ctrl adds, Escape restores |

## Marking menu

Alt + right-click opens Fission's original compass menu on a native 3D canvas
with the Fission mouse preset and Fission / Fusion or Custom profile. A right
drag/release chooses a sector; a click opens it for a subsequent left-click.
Escape or a center click closes it. Plain right-click and native modified camera
gestures remain available. FreeCAD Classic leaves the chord to native navigation.
The navigation-strip button and the customizable `Fission_MarkingMenu` command
work with other mouse presets. Drawing sheet views keep their native interaction;
the menu can open on a 3D view beneath the Drawing workspace.

Preferences → Marking Menu configures eight fixed compass slots for each of
seven contexts. Empty and unavailable slots stay in their positions. Availability
follows native commands and the current selection/task; an unavailable command
cannot run. Settings and resets take effect on OK; Cancel discards staged edits.
Stored command IDs survive restart and temporarily missing addons. The menu
closes before dispatch through the normal command controller, so native tools
own their task dialogs and Undo transactions.

Selection modes 1/2/3 yield to Sketcher and active task dialogs. Rectangle/freehand
selection considers projected object centers and may include occluded geometry;
rectangle right-to-left uses native crossing behavior. Paint selects visible
frontmost objects, samples between pointer events, preserves existing selection
gates and link paths, and finishes on release. Escape restores the pre-stroke
selection in that document. Other documents' selections are preserved.

Fit uses **F6**, documented in Autodesk's [preferences reference](https://help.autodesk.com/view/fusion360/ENU/index.html?guid=GUID-878489CD-3A23-4303-8450-C2F4F8E410B1). It dispatches `Fission_Fit` in all contexts. See the navigation preferences for MMB pan, Shift+MMB orbit, wheel zoom, and Ctrl+Shift+MMB drag zoom.

## Context and typing

The active context is `model`, `sketch`, `assembly`, `surface`, `mesh`, `drawing`, or `cam`. In Design, the Solid/Utilities tabs use `model`; Surface, Mesh, and Assemble select their corresponding contexts. Sketch context comes from the actual active Sketcher edit state and takes priority over the selected Design tab. Drawing uses native TechDraw; Manufacture uses native CAM. Sketch and drawing can reuse D/P/T without collisions.

I, Ctrl+B, and A remain available in Surface and Mesh, as does M outside Sketch. Native Surface, Mesh, TechDraw, and CAM commands appear in Keyboard Shortcuts with their workspace contexts and can receive custom bindings. Stitch (`Fission_Stitch`) has no factory key; it sews selected native faces/shapes into a `Surface::Sewing` feature. **Convert to Solid** is a separate operation for a closed shell.

Workspace cycling uses the same native workbench transition as the workspace selector. Finish or cancel the current task before changing workspace. Design keeps Fission's native workbench; Drawing keeps TechDraw; Manufacture keeps CAM. The ribbon and Browser stay available in these workspaces. Timeline is available in Design, and each workspace saves its dock layout separately.

Fission intercepts Qt `ShortcutOverride` and `KeyPress` events. Single-letter commands and application mappings stay inactive while a line edit, spin box, text editor, editable combo box, or shortcut editor has focus. Text input retains normal clipboard and undo behavior. Open modal dialogs and menus also retain their own keyboard handling.

Native FreeCAD QAction shortcuts that collide with a Fission binding are temporarily cleared, including multi-stroke sequences whose first key is claimed. They are restored on switching to **FreeCAD Classic**. This changes live actions, not FreeCAD's persistent shortcut customization group. Newly loaded workbench actions are checked using a coalesced Qt event callback.

## Customize and transfer

Open **Fission Preferences → Keyboard Shortcuts**. Search by command, context, or key; select a row; record a key; choose **Assign**. **Clear**, **Reset Selected**, and **Reset Profile** apply immediately. Conflicts are rejected when command contexts overlap. Additional commands from the active command catalog can receive custom keys even when Fusion provides no factory default.

The preset selector exposes **Fission / Fusion**, **FreeCAD Classic**, and **Custom**. Fission / Fusion applies the factory table. Custom applies that table plus your saved edits. FreeCAD Classic restores native workbench shortcuts. Switching presets retains your Custom edits; assigning, clearing, or resetting an individual binding selects Custom. **Reset Profile** clears custom edits and returns to Fission / Fusion.

The active preset and custom edits persist under `User parameter:BaseApp/Preferences/Fission/Shortcuts` as `Profile`, `SchemaVersion`, and JSON `Overrides`. Restart preserves both the selected preset and the saved Custom keys. **Import JSON** and **Export JSON** transfer version 2 configurations; version 1 configurations remain readable, with active factory-profile edits migrated to Custom. Malformed profiles, unknown commands, invalid keys, and contextual conflicts are rejected before replacing working settings. One key plus optional Ctrl/Alt/Shift/Meta modifiers is supported; multi-stroke custom shortcuts are excluded from the Fission profile dispatcher.

## Command toolbox

**S** opens search from the Browser or canvas. Search names, familiar CAD terms,
or native command IDs. All matching registered tools remain visible with current
shortcut hints and Ready/Unavailable states. **Up/Down** skip unavailable rows;
**Enter** launches a ready command; **Escape** restores the control that opened
search. Native canvas focus returns before a CAD tool starts. Search closes when
its document, view, or editing context changes.

Empty searches prioritize the current context, then recent successful launches.
At most 12 command IDs persist under Fission's versioned `CommandSearchHistory`.
Failed/unavailable invocations are excluded; cancelling a later feature task
does not remove its accepted launch. Inactive workbench tools remain listed as
unavailable until their native actions or supported Fission context are active.

## Explicit gaps

- Shift+N (Component Colors), Shift+J (As-built Joint), Shift+S (Scripts/Add-ins), and shell toggles for comments/data panel/text commands remain reserved. Pressing a reserved key shows a status message. Reserved rows are labeled in preferences and can be cleared. Selection modes 1/2/3, Ctrl+Alt+V, Ctrl+Alt+N, and Ctrl+[ / Ctrl+] are implemented as described above.
- Shift for midpoint coincidence is a transient sketch modifier, not a standalone action. Fission preserves FreeCAD's native sketch constraints; exact Fusion inference behavior is not implemented.
- Autodesk's current default reference lists no Create Sketch, Finish Sketch, Revolve, Chamfer, Shell, or Pattern key. These commands and Stitch are available through toolbar/search; their customizable defaults remain blank.
- Ctrl++ and Ctrl+- in that reference belong to Autodesk Assistant, not the CAD canvas. Fission does not claim them as canvas defaults.
- The factory table does not provide specialist Surface, Mesh, or CAM operation keys. Those native commands support custom bindings in their contexts. Form, simulation, generative design, animation, and electronics do not have a Fission workflow in this release.
- Autodesk's current references do not specify wheel sign, drag sensitivity, or the default orbit constraint type precisely enough to claim exact numerical parity. Fission navigation retains configurable zoom reversal and native navigation alternatives. Autodesk documents [reverse zoom preferences](https://help.autodesk.com/view/fusion360/ENU/?caas=caas/sfdcarticles/sfdcarticles/How-to-reverse-the-scroll-direction-for-zoom-in-Fusion-360.html), [free/constrained orbit](https://help.autodesk.com/cloudhelp/ENU/Fusion-GetStarted/files/GS-NAVIGATION-BAR.htm), and [orbit-center controls](https://help.autodesk.com/view/fusion360/ENU/?caas=caas/sfdcarticles/sfdcarticles/How-to-reset-the-orbit-pivot-point-in-Fusion-360.html).

## Source verification and tests

Command IDs were checked against `upstream-src/src/Mod/Sketcher/Gui/CommandCreateGeo.cpp`, `CommandSketcherTools.cpp`, `CommandAlterGeometry.cpp`, `CommandConstraints.cpp`, and TechDraw `Command*.cpp`. Current source names are `Sketcher_Projection` and `Sketcher_Dimension`, rather than guessed legacy names. `upstream-src/src/Gui/CommandPyImp.cpp` exposes native actions; `Action.cpp` and `ShortcutManager.cpp` establish QAction acceleration behavior.

Run `python -m unittest discover -s tests -p test_shortcuts.py -v` for deterministic factory mapping, context reuse, typing-state resolver, collision detection, Classic bypass, save/load, reset, JSON atomicity, custom catalog bindings, and toolbox search tests. Qt focus and modeling invocation require the packaged GUI smoke tests; a pure resolver test alone is not evidence that every native command completed its operation.

For real Qt event tests, set `FISSION_QT_TESTS=1` and `QT_QPA_PLATFORM=offscreen`, then run the same command with the LibPack Python runtime. These cover three-preset selection and persistence, legacy profile migration, dispatch through real Qt key events, stock-action collision/restoration, lazy action registration, typing in native editors, reserved-key handling, preferences rendering, and keyboard command search. The execution spy verifies dispatched IDs; geometry completion requires native CAD workflow tests.

Run `scripts/test-gui.ps1` against the built or staged application for modeling and restart persistence. Use `-HistoryOnly` for four document-panel keyboard groups, `-SearchOnly` for three native toolbox groups, or `-WorkspacesOnly` for Drawing/CAM controls. The full runner also exercises the actual Stitch dialog with whole-object and face selections, tolerance editing, Cancel/OK, Undo/Redo, and FCStd save/reopen.

On October 5, 2026, the integrated native GUI suite passed all 41 cases, including native search-launched Fillet transactions, Sketcher canvas input, Drawing/CAM operations, Assembly, Stitch, selection and marking menus. Separate processes verified persisted search history and settings. The combined unit/Qt suite passed 127 tests. This is selected-tool acceptance; broader catalog commands and custom shortcuts still need native operation coverage. Check FISSION_STATUS.md and the generated JSON reports for the tested build.
