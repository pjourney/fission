# Fission 0.2 Alpha keyboard shortcuts

Fission / Fusion is the default profile. These defaults come from Autodesk's public [Fusion keyboard reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-GetStarted/files/GUID-F0491540-0324-470A-B651-2238D0EFAC30.htm), checked on October 3, 2026. They describe behavior; Fission includes no Autodesk icons, artwork, or application assets.

The table records the implemented dispatcher mapping. Actual operation availability still depends on the active document, selection, and installed FreeCAD modules. The pure profile tests verify dispatch resolution and persistence; the GUI/modeling smoke suite verifies native invocation separately.

| Fusion command | Default | Fission command | Context | State / difference |
|---|---|---|---|---|
| Toolbox | S | Fission_Search | Any | Native searchable command toolbox |
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

## Explicit gaps

- Shift+N (Component Colors), Shift+J (As-built Joint), Shift+S (Scripts/Add-ins), selection modes 1/2/3, and shell toggles for comments/data panel/text commands remain reserved. Pressing a reserved key shows a status message. Reserved rows are labeled in preferences and can be cleared. Ctrl+Alt+V, Ctrl+Alt+N, and Ctrl+[ / Ctrl+] are implemented as described above.
- Shift for midpoint coincidence is a transient sketch modifier, not a standalone action. Fission preserves FreeCAD's native sketch constraints; exact Fusion inference behavior is not implemented.
- Autodesk's current default reference lists no Create Sketch, Finish Sketch, Revolve, Chamfer, Shell, or Pattern key. These commands and Stitch are available through toolbar/search; their customizable defaults remain blank.
- Ctrl++ and Ctrl+- in that reference belong to Autodesk Assistant, not the CAD canvas. Fission does not claim them as canvas defaults.
- The factory table does not provide specialist Surface, Mesh, or CAM operation keys. Those native commands support custom bindings in their contexts. Form, simulation, generative design, animation, and electronics do not have a Fission workflow in this release.
- Autodesk's current references do not specify wheel sign, drag sensitivity, or the default orbit constraint type precisely enough to claim exact numerical parity. Fission navigation retains configurable zoom reversal and native navigation alternatives. Autodesk documents [reverse zoom preferences](https://help.autodesk.com/view/fusion360/ENU/?caas=caas/sfdcarticles/sfdcarticles/How-to-reverse-the-scroll-direction-for-zoom-in-Fusion-360.html), [free/constrained orbit](https://help.autodesk.com/cloudhelp/ENU/Fusion-GetStarted/files/GS-NAVIGATION-BAR.htm), and [orbit-center controls](https://help.autodesk.com/view/fusion360/ENU/?caas=caas/sfdcarticles/sfdcarticles/How-to-reset-the-orbit-pivot-point-in-Fusion-360.html).

## Source verification and tests

Command IDs were checked against `upstream-src/src/Mod/Sketcher/Gui/CommandCreateGeo.cpp`, `CommandSketcherTools.cpp`, `CommandAlterGeometry.cpp`, `CommandConstraints.cpp`, and TechDraw `Command*.cpp`. Current source names are `Sketcher_Projection` and `Sketcher_Dimension`, rather than guessed legacy names. `upstream-src/src/Gui/CommandPyImp.cpp` exposes native actions; `Action.cpp` and `ShortcutManager.cpp` establish QAction acceleration behavior.

Run `python -m unittest discover -s tests -p test_shortcuts.py -v` for deterministic factory mapping, context reuse, typing-state resolver, collision detection, Classic bypass, save/load, reset, JSON atomicity, custom catalog bindings, and toolbox search tests. Qt focus and modeling invocation require the packaged GUI smoke tests; a pure resolver test alone is not evidence that every native command completed its operation.

For real Qt event tests, set `FISSION_QT_TESTS=1` and `QT_QPA_PLATFORM=offscreen`, then run the same command with the LibPack Python runtime. These cover three-preset selection and persistence, legacy profile migration, dispatch through real Qt key events, stock-action collision/restoration, lazy action registration, typing in native editors, reserved-key handling, preferences rendering, and keyboard command search. The execution spy verifies dispatched IDs; geometry completion requires native CAD workflow tests.

Run `scripts/test-gui.ps1` against the built or staged application for modeling and restart persistence. Use `scripts/test-gui.ps1 -WorkspacesOnly` for the serial Drawing, Manufacture, workspace cycling, and navigation-control suite. The expanded modeling runner also exercises the actual Stitch dialog with whole-object and face selections, tolerance editing, Cancel/OK, Undo/Redo, and FCStd save/reopen.

On October 4, 2026, the integrated native GUI suite passed all 30 cases, including Drawing/CAM operations, Assembly insertion and joints, Stitch, and real Qt events for workspace cycling and cube/navigation-strip controls. Separate processes verified persisted settings after restart. This is selected-tool acceptance; broader catalog commands and custom shortcuts still need native operation coverage. Check FISSION_STATUS.md and the generated JSON reports and completion markers for the tested build.
