# SPDX-License-Identifier: MIT
import os
import sys
import FreeCAD as App
import FreeCADGui as Gui

_module_dir = os.path.join(App.getResourceDir(), "Mod", "Fission")
if _module_dir not in sys.path:
    sys.path.insert(0, _module_dir)

# Factory settings are applied once in the isolated Fission application profile.
_preferences = App.ParamGet("User parameter:BaseApp/Preferences/Fission")
if not _preferences.GetBool("FactoryInitialized", False):
    App.ParamGet("User parameter:BaseApp/Preferences/General").SetString("AutoloadModule", "FissionWorkbench")
    App.ParamGet("User parameter:BaseApp/Preferences/General").SetBool("ShowVersionInTitle", False)
    _start = App.ParamGet("User parameter:BaseApp/Preferences/Mod/Start")
    _start.SetBool("Migration2024Complete", True)
    _start.SetBool("ShowOnStartup", False)
    for _dock, _enabled in [("ComboView", False), ("TreeView", False), ("PropertyView", True)]:
        App.ParamGet("User parameter:BaseApp/Preferences/DockWindows/" + _dock).SetBool("Enabled", _enabled)
    App.ParamGet("User parameter:BaseApp/Preferences/View").SetString("NavigationStyle", "Gui::FissionNavigationStyle")
    _preferences.SetBool("FactoryInitialized", True)


from fission.workbench import FissionWorkbench
Gui.addWorkbench(FissionWorkbench())
