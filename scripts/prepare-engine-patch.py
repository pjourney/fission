# SPDX-License-Identifier: MIT
"""Generate a small reviewable source patch without changing the baseline tree.

The navigation implementation is adapted from the pinned upstream CAD preset;
its original license/copyright header is preserved, as are its SpaceMouse hooks.
"""
from pathlib import Path
import difflib

root = Path(__file__).resolve().parents[1]
source = root / "upstream-src"
changes = {}


def replace_file(relative, pairs):
    original = (source / relative).read_text(encoding="utf-8")
    revised = original
    for before, after in pairs:
        if before not in revised:
            raise RuntimeError("Pinned source context changed: " + relative + " / " + before[:70])
        revised = revised.replace(before, after, 1)
    changes[relative] = (original, revised)


replace_file("src/Main/MainGui.cpp", [
    ('Config()["ExeName"] = "FreeCAD"', 'Config()["ExeName"] = "Fission"'),
    ('Config()["ExeVendor"] = "FreeCAD"', 'Config()["ExeVendor"] = "Fission"'),
    ('Config()["AppIcon"] = "freecad"', 'Config()["AppIcon"] = "fission"'),
    ('Config()["SplashScreen"] = "freecadsplash"', 'Config()["SplashScreen"] = "fissionsplash"'),
    ('Config()["StartWorkbench"] = "PartDesignWorkbench"',
     'Config()["StartWorkbench"] = "FissionWorkbench";\n    App::Application::Config()["NavigationStyle"] = "Gui::FissionNavigationStyle"'),
    ('Config()["DesktopFileName"] = "org.freecad.FreeCAD"', 'Config()["DesktopFileName"] = "org.fission.Fission"'),
])
replace_file("src/Main/MainCmd.cpp", [
    ('Config()["ExeName"] = "FreeCAD"', 'Config()["ExeName"] = "Fission"'),
    ('Config()["ExeVendor"] = "FreeCAD"', 'Config()["ExeVendor"] = "Fission"'),
])
replace_file("src/Main/CMakeLists.txt", [
    ('SET_BIN_DIR(FreeCADMain FreeCAD)', 'SET_BIN_DIR(FreeCADMain Fission)'),
    ('SET_BIN_DIR(FreeCADMainCmd FreeCADCmd)', 'SET_BIN_DIR(FreeCADMainCmd FissionCmd)'),
])
for filename, executable in [("freecad.rc.cmake", "Fission.exe"), ("freecadCmd.rc.cmake", "FissionCmd.exe")]:
    replace_file("src/Main/" + filename, [
        ('"${PROJECT_NAME} Team"', '"Fission contributors"'),
        ('"${PROJECT_NAME} main executable"', '"Fission parametric mechanical CAD"') if filename == "freecad.rc.cmake"
        else ('"${PROJECT_NAME} command line executable"', '"Fission CAD command line"'),
        ('"FreeCAD.exe"' if filename == "freecad.rc.cmake" else '"FreeCADCmd.exe"', '"' + executable + '"'),
        ('"FreeCAD.exe"' if filename == "freecad.rc.cmake" else '"FreeCADCmd.exe"', '"' + executable + '"'),
        ('"${PROJECT_NAME}"', '"Fission"'),
    ])
replace_file("src/Gui/Icons/resource.qrc", [
    ('<file>freecadsplash.svg</file>', '<file>freecadsplash.svg</file>\n        <file>fission.svg</file>\n        <file>fissionsplash.svg</file>'),
])
replace_file("src/Gui/CMakeLists.txt", [
    ('Navigation/CADNavigationStyle.cpp', 'Navigation/CADNavigationStyle.cpp\n    Navigation/FissionNavigationStyle.cpp'),
])
replace_file("src/Gui/SoFCDB.cpp", [
    ('CADNavigationStyle::init();', 'CADNavigationStyle::init();\n    FissionNavigationStyle::init();'),
])
declaration = '''class GuiExport FissionNavigationStyle: public UserNavigationStyle
{
    using inherited = UserNavigationStyle;
    TYPESYSTEM_HEADER_WITH_OVERRIDE();
public:
    FissionNavigationStyle();
    ~FissionNavigationStyle() override;
    const char* mouseButtons(ViewerMode) override;
    std::string userFriendlyName() const override { return "Fission / Fusion"; }
protected:
    SbBool processSoEvent(const SoEvent* const ev) override;
private:
    SbBool lockButton1 {false};
};

'''
replace_file("src/Gui/Navigation/NavigationStyle.h", [
    ('class GuiExport RevitNavigationStyle:', declaration + 'class GuiExport RevitNavigationStyle:'),
])
replace_file("src/Mod/Sketcher/Gui/ViewProviderSketch.cpp", [
    ('ADD_PROPERTY_TYPE(EditingWorkbench,\n                      ("SketcherWorkbench")',
     'ADD_PROPERTY_TYPE(EditingWorkbench,\n                      ("FissionWorkbench")'),
])

navigation = (source / "src/Gui/Navigation/CADNavigationStyle.cpp").read_text(encoding="utf-8")
navigation = navigation.replace("CADNavigationStyle", "FissionNavigationStyle")
navigation = navigation.replace('QT_TR_NOOP("Press middle or ctrl+right mouse button")', 'QT_TR_NOOP("Hold middle mouse button and drag")')
navigation = navigation.replace('QT_TR_NOOP("Press middle+left, middle+right or shift+right mouse button")', 'QT_TR_NOOP("Hold Shift and middle mouse button and drag")')
navigation = navigation.replace('"Scroll mouse wheel or keep middle button depressed\\n"\n                "while doing a left or right click and move the mouse up or down"',
                                '"Scroll mouse wheel or hold Ctrl+Shift and middle mouse button and drag"')
anchor = "        case CTRLDOWN | BUTTON2DOWN:\n"
new_cases = '''        // Fission factory preset: Autodesk's public default mouse gestures.
        // Preserve upstream camera math, selection, editing and 3Dconnexion paths.
        case SHIFTDOWN | BUTTON3DOWN:
            if (newmode != NavigationStyle::DRAGGING) {
                saveCursorPosition(ev);
            }
            newmode = NavigationStyle::DRAGGING;
            break;
        case CTRLDOWN | SHIFTDOWN | BUTTON3DOWN:
            newmode = NavigationStyle::ZOOMING;
            break;
'''
assert anchor in navigation
navigation = navigation.replace(anchor, new_cases + anchor, 1)
changes["src/Gui/Navigation/FissionNavigationStyle.cpp"] = ("", navigation)
for filename in ("fission.svg", "fissionsplash.svg"):
    changes["src/Gui/Icons/" + filename] = ("", (root / "Mod/Fission/resources" / filename).read_text(encoding="utf-8"))

patch = []
for filename, (before, after) in changes.items():
    patch.append("diff --git a/%s b/%s\n" % (filename, filename))
    if not before:
        patch.append("new file mode 100644\n")
    patch.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                    fromfile="a/" + filename if before else "/dev/null",
                                    tofile="b/" + filename))
(root / "patches/0001-fission-identity-navigation.patch").write_text("".join(patch), encoding="utf-8", newline="\n")
print("Prepared %d source adaptations; upstream working tree unchanged." % len(changes))
