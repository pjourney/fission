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
    "RevolveCut": ("Revolve Cut", "PartDesign_Groove", "PartDesign_Groove", "groove subtract revolution turn", "model"),
    "SweepCut": ("Sweep Cut", "PartDesign_SubtractivePipe", "PartDesign_SubtractivePipe", "subtractive pipe path profile", "model"),
    "LoftCut": ("Loft Cut", "PartDesign_SubtractiveLoft", "PartDesign_SubtractiveLoft", "subtractive loft sections profiles", "model"),
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
    "Axis": ("Construction Axis", "PartDesign_Line", "PartDesign_Line", "datum line reference", "model"),
    "Point": ("Construction Point", "PartDesign_Point", "PartDesign_Point", "datum point reference", "model"),
    "Move": ("Move / Copy", None, "Std_Transform", "translate rotate position transform duplicate linked copy", "model"),
    "Measure": ("Measure", "Std_Measure", "Std_Measure", "inspect distance angle", "all"),
    "Appearance": ("Appearance", "Std_SetAppearance", "Std_SetAppearance", "material color", "model"),
    "Visibility": ("Toggle Visibility", "Std_ToggleVisibility", "Std_ToggleVisibility", "show hide", "all"),
    "Search": ("Command Search", None, "Std_Search", "toolbox launcher", "all"),
    "MarkingMenu": ("Marking Menu", None, "Std_Search", "radial compass Alt right-click", "all"),
    "WindowSelection": ("Window Selection", None, "Std_BoxSelection", "rectangle select objects", "all"),
    "FreeformSelection": ("Freeform Selection", None, "Std_BoxSelection", "freehand lasso select objects", "all"),
    "PaintSelection": ("Paint Selection", None, "Std_BoxSelection", "brush frontmost objects", "all"),
    "Preferences": ("Fission Preferences", None, "preferences-system", "settings shortcuts theme units navigation", "all"),
    "About": ("About Fission", None, ICON, "license attribution", "all"),
    "EditFeature": ("Edit Feature", None, "Std_Edit", "history parameters", "all"),
    "Fit": ("Fit", "Std_ViewFitAll", "Std_ViewFitAll", "zoom all F6", "all"),
    "Compute": ("Compute All", "Std_Refresh", "Std_Refresh", "recompute update", "all"),
    "ToggleBrowser": ("Browser", None, "Std_TreeSelection", "structure panel", "all"),
    "ToggleTimeline": ("Timeline", None, "Std_HistoryBack", "history panel", "all"),
    "ResetLayout": ("Reset Layout", None, "Std_DlgCustomize", "panels default", "all"),
    "ToggleViewCube": ("View Cube", None, "Std_ViewIsometric", "orientation cube show hide", "all"),
    "ToggleNavigation": ("Navigation Bar", None, "Std_ViewFitAll", "navigation controls show hide", "all"),
    "PreviousWorkspace": ("Previous Workspace", None, "Std_HistoryBack", "design drawing manufacture previous", "all"),
    "NextWorkspace": ("Next Workspace", None, "Std_HistoryForward", "design drawing manufacture next", "all"),
    "Stitch": ("Stitch", None, "Surface_Filling", "sew join surfaces shell", "surface"),
    "AssemblyJoint": ("Joint", "Assembly_CreateJointFixed", "Assembly_CreateJointFixed", "constraint rigid fixed", "assembly"),
    "NewComponent": ("New Component", None, "Std_Part", "part product", "model"),
    "NewBody": ("New Body", "PartDesign_Body", "PartDesign_Body", "empty body solid component container", "model"),
}

_initialized = False


def initialize():
    global _initialized
    if _initialized:
        return
    for name in ("PartGui", "SketcherGui", "PartDesignGui", "MeasureGui", "MatGui", "SurfaceGui", "MeshGui", "SpreadsheetGui"):
        try:
            importlib.import_module(name)
        except ImportError as err:
            App.Console.PrintWarning("Fission: optional module %s unavailable: %s\n" % (name, err))
    # Load registration modules, not Workbench.Initialize directly: FreeCAD
    # assigns the native __Workbench__ handle only during workbench activation.
    try:
        importlib.import_module("AssemblyGui")
        for module in ("CommandCreateAssembly", "CommandInsertLink", "CommandInsertNewPart",
                       "CommandCreateJoint", "CommandSolveAssembly"):
            importlib.import_module(module)
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
        from .icons import owned_resource
        owned = owned_resource("Fission_" + self.name)
        if owned:
            icon = owned
        else:
            native = Gui.Command.get(backend or icon)
            if native:
                icon = native.getInfo().get("pixmap", icon) or icon
        return {"MenuText": title, "ToolTip": title + " — " + aliases,
                "Pixmap": icon, "CmdType": "NoTransaction ForEdit" if context in ("sketch", "assembly") or self.name in ("Extrude", "Cut", "ToggleViewCube", "ToggleNavigation", "PreviousWorkspace", "NextWorkspace", "WindowSelection", "FreeformSelection", "PaintSelection", "MarkingMenu") else "NoTransaction"}

    def Activated(self):
        from .shell import get_controller
        get_controller().perform(self.name)

    def IsActive(self):
        title, backend, icon, aliases, context = COMMANDS[self.name]
        if self.name == "MarkingMenu":
            from .shell import existing_controller
            controller = existing_controller()
            return bool(controller and hasattr(controller, "marking") and controller.marking.available())
        if self.name in ("WindowSelection", "FreeformSelection", "PaintSelection"):
            from .selection import can_select
            if not can_select():
                return False
            backend = "Std_FreehandSelection" if self.name == "FreeformSelection" else "Std_BoxSelection"
            command = Gui.Command.get(backend)
            return bool(command and command.isActive())
        if self.name in ("NewDesign", "Search", "Preferences", "About", "ToggleBrowser", "ToggleTimeline", "ResetLayout", "ToggleNavigation", "PreviousWorkspace", "NextWorkspace"):
            return True
        if not App.ActiveDocument:
            return False
        if self.name in ("Extrude", "Cut"):
            doc = Gui.activeDocument()
            edit = doc.getInEdit() if doc else None
            if edit and edit.Object.isDerivedFrom("Sketcher::SketchObject"):
                return True
        if self.name in ("Extrude", "Cut", "RevolveCut", "SweepCut", "LoftCut", "Plane", "Axis", "Point", "NewBody", "NewComponent"):
            from .modeling import available
            return available(self.name) and (backend is None or bool(Gui.Command.get(backend) and Gui.Command.get(backend).isActive()))
        if self.name == "CreateSketch":
            document = Gui.activeDocument()
            return bool(document and not document.getInEdit()
                        and not App.ActiveDocument.HasPendingTransaction and not Gui.Control.activeDialog())
        if self.name == "Move":
            from .move import can_move
            return can_move()
        if self.name == "EditFeature":
            return bool(Gui.Selection.getSelection()) and not Gui.Control.activeDialog()
        if self.name == "Stitch":
            doc = Gui.activeDocument()
            if App.ActiveDocument.HasPendingTransaction or Gui.Control.activeDialog() or (doc and doc.getInEdit()):
                return False
            selected = Gui.Selection.getSelection()
            return bool(selected) and all(obj.Document is App.ActiveDocument and obj.isDerivedFrom("Part::Feature")
                                          and not obj.Shape.isNull() for obj in selected)
        if backend:
            cmd = Gui.Command.get(backend)
            return bool(cmd and cmd.isActive())
        return True


def catalog():
    result = []
    for name, (title, backend, icon, aliases, context) in COMMANDS.items():
        if name in ("Extrude", "Cut"):
            context = ["model", "sketch"]
        elif name in ("WindowSelection", "FreeformSelection", "PaintSelection"):
            context = ["model", "assembly", "surface", "mesh", "cam"]
        result.append(dict(id="Fission_" + name, title=title, aliases=aliases,
                           icon=icon, context=context))
    for cmd_id in Gui.Command.listAll():
        if cmd_id.startswith("Fission_"):
            continue
        cmd = Gui.Command.get(cmd_id)
        info = cmd.getInfo()
        context = "all"
        for prefixes, workspace in (("Sketcher_", "sketch"), ("Assembly_", "assembly"),
                                    ("TechDraw_", "drawing"), (("CAM_", "Path_"), "cam"),
                                    ("Surface_", "surface"), ("Mesh_", "mesh")):
            if cmd_id.startswith(prefixes):
                context = workspace
                break
        result.append(dict(id=cmd_id, title=info.get("menuText", cmd_id).replace("&", ""),
                           aliases=cmd_id.replace("_", " "), icon=info.get("pixmap", ""),
                           context=context))
    return result
