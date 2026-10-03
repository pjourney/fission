# SPDX-License-Identifier: MIT
"""Named presentation commands; geometry and task dialogs belong to FreeCAD."""
import importlib
import os
import FreeCAD as App
import FreeCADGui as Gui

ICON = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "fission.svg")

# title, backend, icon, synonyms, context. Core IDs verified against source-lock.
COMMANDS = {
    "NewDesign": ("New Design", None, "Std_New", "new document", "all"),
    "CreateSketch": ("Create Sketch", "PartDesign_NewSketch", "Sketcher_NewSketch", "sketch plane", "model"),
    "FinishSketch": ("Finish Sketch", "Sketcher_LeaveSketch", "Sketcher_LeaveSketch", "close sketch", "sketch"),
    "Extrude": ("Extrude", "PartDesign_Pad", "PartDesign_Pad", "pad extrusion create", "model"),
    "Cut": ("Extrude Cut", "PartDesign_Pocket", "PartDesign_Pocket", "pocket subtract", "model"),
    "Revolve": ("Revolve", "PartDesign_Revolution", "PartDesign_Revolution", "rotation", "model"),
    "Sweep": ("Sweep", "PartDesign_AdditivePipe", "PartDesign_AdditivePipe", "pipe path", "model"),
    "Loft": ("Loft", "PartDesign_AdditiveLoft", "PartDesign_AdditiveLoft", "profiles", "model"),
    "Hole": ("Hole", "PartDesign_Hole", "PartDesign_Hole", "drill bore", "model"),
    "Fillet": ("Fillet", "PartDesign_Fillet", "PartDesign_Fillet", "round edge", "model"),
    "Chamfer": ("Chamfer", "PartDesign_Chamfer", "PartDesign_Chamfer", "bevel", "model"),
    "Shell": ("Shell", "PartDesign_Thickness", "PartDesign_Thickness", "hollow thickness", "model"),
    "Draft": ("Draft", "PartDesign_Draft", "PartDesign_Draft", "taper", "model"),
    "Mirror": ("Mirror", "PartDesign_Mirrored", "PartDesign_Mirrored", "reflect", "model"),
    "RectPattern": ("Rectangular Pattern", "PartDesign_LinearPattern", "PartDesign_LinearPattern", "linear pattern", "model"),
    "CircPattern": ("Circular Pattern", "PartDesign_PolarPattern", "PartDesign_PolarPattern", "polar pattern", "model"),
    "Boolean": ("Combine", "PartDesign_Boolean", "PartDesign_Boolean", "boolean union cut intersect", "model"),
    "Plane": ("Construction Plane", "PartDesign_Plane", "PartDesign_Plane", "datum reference", "model"),
    "Move": ("Move / Copy", None, "Std_Transform", "translate position transform duplicate", "model"),
    "Measure": ("Measure", "Std_Measure", "Std_Measure", "inspect distance angle", "all"),
    "Appearance": ("Appearance", "Std_SetAppearance", "Std_SetAppearance", "material color", "model"),
    "Visibility": ("Toggle Visibility", "Std_ToggleVisibility", "Std_ToggleVisibility", "show hide", "all"),
    "Search": ("Command Search", None, "Std_Search", "toolbox launcher", "all"),
    "Preferences": ("Fission Preferences", None, "preferences-system", "settings shortcuts theme units navigation", "all"),
    "About": ("About Fission", None, ICON, "license attribution", "all"),
    "EditFeature": ("Edit Feature", None, "Std_Edit", "history parameters", "all"),
    "Fit": ("Fit", "Std_ViewFitAll", "Std_ViewFitAll", "zoom all F6", "all"),
    "Compute": ("Compute All", "Std_Refresh", "Std_Refresh", "recompute update", "all"),
    "ToggleBrowser": ("Browser", None, "Std_TreeSelection", "structure panel", "all"),
    "ToggleTimeline": ("Timeline", None, "Std_HistoryBack", "history panel", "all"),
    "ResetLayout": ("Reset Layout", None, "Std_DlgCustomize", "panels default", "all"),
    "AssemblyJoint": ("Joint", "Assembly_CreateJointFixed", "Assembly_CreateJointFixed", "constraint rigid fixed", "assembly"),
    "NewComponent": ("New Component", None, "Std_Part", "part product", "model"),
}

_initialized = False


def initialize():
    global _initialized
    if _initialized:
        return
    for name in ("PartGui", "SketcherGui", "PartDesignGui", "MeasureGui", "MaterialGui", "SurfaceGui", "MeshGui"):
        try:
            importlib.import_module(name)
        except ImportError as err:
            App.Console.PrintWarning("Fission: optional module %s unavailable: %s\n" % (name, err))
    # Assembly registers its Python commands when initialized. No workbench switch.
    try:
        wb = Gui.getWorkbench("AssemblyWorkbench")
        if not Gui.Command.get("Assembly_CreateAssembly"):
            wb.Initialize()
    except Exception as err:
        App.Console.PrintWarning("Fission: Assembly unavailable: %s\n" % err)
    for name in COMMANDS:
        Gui.addCommand("Fission_" + name, FissionCommand(name))
    _initialized = True


class FissionCommand:
    def __init__(self, name):
        self.name = name

    def GetResources(self):
        title, backend, icon, aliases, context = COMMANDS[self.name]
        return {"MenuText": title, "ToolTip": title + " — " + aliases,
                "Pixmap": icon, "CmdType": "ForEdit" if context == "sketch" else ""}

    def Activated(self):
        from .shell import get_controller
        get_controller().perform(self.name)

    def IsActive(self):
        title, backend, icon, aliases, context = COMMANDS[self.name]
        if self.name in ("NewDesign", "Search", "Preferences", "About", "ToggleBrowser", "ToggleTimeline", "ResetLayout"):
            return True
        if not App.ActiveDocument:
            return False
        if backend:
            cmd = Gui.Command.get(backend)
            return bool(cmd and cmd.isActive())
        return True


def catalog():
    result = []
    for name, (title, backend, icon, aliases, context) in COMMANDS.items():
        result.append(dict(id="Fission_" + name, title=title, aliases=aliases,
                           icon=icon, context=context))
    for cmd_id in Gui.Command.listAll():
        if cmd_id.startswith("Fission_"):
            continue
        cmd = Gui.Command.get(cmd_id)
        info = cmd.getInfo()
        result.append(dict(id=cmd_id, title=info.get("MenuText", cmd_id).replace("&", ""),
                           aliases=cmd_id.replace("_", " "), icon=info.get("Pixmap", ""),
                           context="sketch" if cmd_id.startswith("Sketcher_") else "all"))
    return result
