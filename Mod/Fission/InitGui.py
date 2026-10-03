# SPDX-License-Identifier: MIT
import os
import sys
import FreeCAD as App
import FreeCADGui as Gui

_module_dir = os.path.dirname(__file__)
if _module_dir not in sys.path:
    sys.path.insert(0, _module_dir)

# Factory settings are applied once in the isolated Fission application profile.
_preferences = App.ParamGet("User parameter:BaseApp/Preferences/Fission")
if not _preferences.GetBool("FactoryInitialized", False):
    App.ParamGet("User parameter:BaseApp/Preferences/General").SetString("AutoloadModule", "FissionWorkbench")
    _start = App.ParamGet("User parameter:BaseApp/Preferences/Mod/Start")
    _start.SetBool("Migration2024Complete", True)
    _start.SetBool("ShowOnStartup", False)
    for _dock, _enabled in [("ComboView", False), ("TreeView", False), ("PropertyView", True)]:
        App.ParamGet("User parameter:BaseApp/Preferences/DockWindows/" + _dock).SetBool("Enabled", _enabled)
    App.ParamGet("User parameter:BaseApp/Preferences/View").SetString("NavigationStyle", "Gui::FissionNavigationStyle")
    _preferences.SetBool("FactoryInitialized", True)


class FissionWorkbench(Gui.Workbench):
    MenuText = "Design"
    ToolTip = "Fission unified mechanical design workspace"
    Icon = os.path.join(_module_dir, "resources", "fission.svg")

    def Initialize(self):
        from fission.commands import initialize
        initialize()
        self.appendMenu("&Design", ["Fission_NewDesign", "Fission_CreateSketch",
                                   "Fission_Extrude", "Fission_Fillet", "Fission_Hole",
                                   "Fission_FinishSketch", "Fission_Search"])
        self.appendMenu("&Fission", ["Fission_Preferences", "Fission_About"])

    def Activated(self):
        from fission.shell import get_controller
        get_controller().activate()

    def Deactivated(self):
        from fission.shell import existing_controller
        controller = existing_controller()
        if controller:
            controller.deactivate()

    def ContextMenu(self, recipient):
        self.appendContextMenu("Fission", ["Fission_CreateSketch", "Fission_Extrude",
                                           "Fission_Fillet", "Fission_Measure",
                                           "Fission_EditFeature", "Fission_Visibility"])

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(FissionWorkbench())
