# Fission

Fission 0.3 Alpha is native parametric mechanical CAD, built from pinned FreeCAD source with unified
Design, Drawing and Manufacture workspaces, a product Browser, horizontal feature Timeline, and
Fusion-familiar keyboard and mouse controls. Original Fission branding; the
FreeCAD document model, constraint solver and geometry engine remain authoritative.

![Fission 0.3 Alpha native Design workspace](docs/fission-alpha.png)

## Run on Windows

For this development checkout:

```powershell
.\Launch-Fission.ps1
```

The native application is `build/windows-release/bin/Fission.exe`. For the
portable package in `dist/0.3.0-alpha`, extract the complete `Fission-Alpha-Windows-x64.zip` and open
`Fission/bin/Fission.exe`. Keep its companion folders together.

Choose **New**, then **Create Sketch** and a plane. Sketch tools appear in the
contextual toolbar. **Finish Sketch** returns to solids; **E** also finishes a
sketch and opens Extrude. Select a solid edge and press **F** for Fillet. **H**
opens Hole, **M** Move / Copy, **I** Measure, and **S** command search. Drag the
middle mouse button to pan; hold Shift while dragging it to orbit. F6 fits the
design. Double-click a Timeline feature to edit its native parameters.
The portable package includes an editable `examples/machined-plate.FCStd` design.

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
.\scripts\package.ps1 -OutputDirectory dist\0.3.0-alpha
```

Builds require Visual Studio C++ Build Tools and a Windows SDK. Setup downloads
and verifies the official FreeCAD LibPack and recursive pinned engine source.
The runtime has its own Fission preferences and does not require a FreeCAD install.

See [build instructions](FISSION_BUILD.md), [shortcut mappings](FISSION_SHORTCUTS.md),
[architecture](FISSION_ARCHITECTURE.md), and [status and limitations](FISSION_STATUS.md).
This development release retains native feature panels and CAD semantics.
Several Fusion commands and optional specialist modules remain partial.
The October 4 portable build passed 34 GUI cases, restart persistence, 13 CAD
checks, and activation of nine native workbenches. The engine passed 26 native
test suites; Fission's profile/history/marking and Qt suite passed 71 tests.

Fission is based on the FreeCAD open-source project. Source and dependency
copyrights/licenses are preserved in [NOTICE.md](NOTICE.md), the matching source
archive and bundled licenses. Fission is an independent project.
