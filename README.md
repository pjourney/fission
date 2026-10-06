# Fission

Fission 0.6 Alpha is native parametric mechanical CAD, built from pinned FreeCAD source with unified
Design, Drawing and Manufacture workspaces, a product Browser, horizontal feature Timeline, and
Fusion-familiar keyboard and mouse controls. Original Fission branding; the
FreeCAD document model, constraint solver and geometry engine remain authoritative.

![Fission native Design workspace](docs/fission-alpha.png)

## Run on Windows

For this development checkout:

```powershell
.\Launch-Fission.ps1
```

The native application is `build/windows-release/bin/Fission.exe`. For the
portable package in `dist/0.6.0-alpha`, extract the complete `Fission-Alpha-Windows-x64.zip` and open
`Fission/bin/Fission.exe`. Keep its companion folders together.

Choose **New**, then **Create Sketch** and a plane. Sketch tools appear in the
contextual toolbar. **Finish Sketch** returns to solids; **E** also finishes a
sketch and opens Extrude. Select a solid edge and press **F** for Fillet. **H**
opens Hole, **M** Move / Copy, **I** Measure, and **S** command search. Drag the
middle mouse button to pan; hold Shift while dragging it to orbit. F6 fits the
design. Select a Browser or Timeline feature and press **Enter** to edit its native
parameters. **F2** renames inline; **Escape** cancels the rename. **Delete** removes
the selected objects through native dependency confirmation and Undo. Arrow keys
navigate, and Shift extends selection between the panels and canvas. In these
panels, Enter/F2/Delete retain their panel meaning even with custom shortcuts.
Finish or cancel the active modeling task before editing history.
The portable package includes an editable `examples/machined-plate.FCStd` design.

**Move / Copy** previews translation in design X/Y/Z axes and rotation in
X, then Y, then Z around each selected object's placement origin. **Cancel**
restores the design; **OK** records one native Undo operation. **Create linked
copies** keeps copies in the source component and preserves parametric source
updates. Select components, bodies, links, or standalone solids/surfaces/meshes;
move individual modeling features through their containing body. Assembly
members use native dragging or joints. Move linked sources and dependent links
in separate operations. See the [native Move / Copy dialog](docs/fission-move.png).

Press **S** to search every registered tool by its name, native ID, or familiar CAD
term. The toolbox displays readiness and current shortcut hints. **Up/Down** skip
unavailable tools; **Enter** launches the selected ready tool; **Escape** returns
to the control that opened search. Recent successful launches appear first when
the query is empty and persist across restarts. Selecting Line from the Browser
returns focus to the sketch canvas before native drawing begins.

**Alt + right-click** opens an original eight-direction marking menu with the
Fission mouse preset. Click a sector, or hold right-click and release over it.
Escape or a center click closes it. Ordinary right-click retains native menus.
Use **Preferences → Marking Menu** to assign commands for each context, leave
slots empty, reset them, or disable the menu. Changes apply with OK. The
navigation-strip button and a custom keyboard binding support other mouse presets.

**1** starts native rectangle selection, **2** starts native freehand selection,
and **3** starts a paint stroke over frontmost objects. Ctrl adds to the selection;
Escape cancels. Sketch editing and active modeling tasks retain native selection.
Rectangle/freehand selection uses projected object centers rather than strict
whole-object containment; paint uses native picking and preserves linked paths.
See the [native marking menu](docs/fission-marking.png).

Use the workspace picker or **Ctrl+[ / Ctrl+]** to switch between Design,
Drawing and Manufacture. Drawing exposes native sheets, projected views,
dimensions and PDF/SVG/DXF exports. Manufacture exposes native CAM setups,
tools, milling operations, preview and post processing. **Ctrl+Alt+V** toggles
the orientation cube; **Ctrl+Alt+N** toggles the navigation strip.
See the native [Drawing workspace](docs/fission-drawing.png) and
[Manufacture toolpath preview](docs/fission-manufacture.png).

Design also includes Surface and Mesh tabs and native assembly tools. **Stitch**
creates a parametric sewn shell from selected surfaces; **Convert to Solid**
converts a closed shell. The Browser can activate a native assembly for inserting
components and creating solver-backed joints.

## Build and verify

```powershell
.\build.ps1 -Jobs 12 -Test
.\scripts\test-gui.ps1
.\scripts\test-gui.ps1 -CanvasOnly
.\scripts\test-gui.ps1 -SearchOnly
.\scripts\test-gui.ps1 -HistoryOnly
.\scripts\test-gui.ps1 -MoveOnly
.\scripts\package.ps1 -OutputDirectory dist\0.6.0-alpha
```

Builds require Visual Studio C++ Build Tools and a Windows SDK. Setup downloads
and verifies the official FreeCAD LibPack and recursive pinned engine source.
The runtime has its own Fission preferences and does not require a FreeCAD install.

See [build instructions](FISSION_BUILD.md), [shortcut mappings](FISSION_SHORTCUTS.md),
[architecture](FISSION_ARCHITECTURE.md), and [status and limitations](FISSION_STATUS.md).
This development release retains native feature panels and CAD semantics.
Several Fusion commands and optional specialist modules remain partial.
The October 5 portable build passed 45 GUI cases, restart persistence, 13 CAD
checks, and activation of nine native workbenches. The engine passed 26 native
test suites; Fission's profile/history/move/marking/search and Qt suite passed 156 tests.

Fission is based on the FreeCAD open-source project. Source and dependency
copyrights/licenses are preserved in [NOTICE.md](NOTICE.md), the matching source
archive and bundled licenses. Fission is an independent project.
