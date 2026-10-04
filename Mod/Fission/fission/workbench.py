# SPDX-License-Identifier: MIT
"""Workbench lives in a real module, independent of FreeCAD's exec loader scope."""
import os
import FreeCAD as App
import FreeCADGui as Gui


class FissionWorkbench(Gui.Workbench):
    MenuText = "Design"
    ToolTip = "Fission unified mechanical design workspace"
    Icon = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "fission.svg")

    def Initialize(self):
        from .commands import initialize
        initialize()
        self.appendMenu("&Design", ["Fission_NewDesign", "Fission_CreateSketch",
                                   "Fission_Extrude", "Fission_Fillet", "Fission_Hole",
                                   "Fission_FinishSketch", "Fission_Search"])
        self.appendMenu("&Fission", ["Fission_Preferences", "Fission_About"])

    def Activated(self):
        from .shell import get_controller
        get_controller().activate()

    def Deactivated(self):
        from .shell import existing_controller
        controller = existing_controller()
        if controller:
            controller.deactivate()

    def ContextMenu(self, recipient):
        self.appendContextMenu("Fission", ["Fission_CreateSketch", "Fission_Extrude",
                                           "Fission_Fillet", "Fission_Measure",
                                           "Fission_EditFeature", "Fission_Visibility"])

    def GetClassName(self):
        return "Gui::PythonWorkbench"
