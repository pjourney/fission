# SPDX-License-Identifier: MIT
"""Command icons shared by the ribbon, menus, and command search.

FreeCAD owns its CAD command artwork and icon cache. Resolve those native
symbols through that cache before considering Qt paths or action instances:
some workbenches register commands long before they create their QActions.
Only Fission's own presentation tools receive the original MIT SVG glyphs.
"""
import os

try:
    import FreeCADGui as Gui
except ImportError:  # Resource and offscreen rendering checks do not need CAD.
    Gui = None
try:
    from PySide import QtGui
except ImportError:
    from PySide6 import QtGui


_RESOURCES = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources")
_ICON_DIRECTORY = os.path.join(_RESOURCES, "icons")

_OWNED = {
    "Fission_Move": "move-copy.svg",
    "Fission_NewComponent": "component-new.svg",
    "Fission_Search": "search.svg",
    "Fission_MarkingMenu": "marking-menu.svg",
    "Fission_WindowSelection": "selection-window.svg",
    "Fission_FreeformSelection": "selection-freeform.svg",
    "Fission_PaintSelection": "selection-paint.svg",
    "Fission_EditFeature": "edit-feature.svg",
    "Fission_ToggleBrowser": "browser.svg",
    "Fission_ToggleTimeline": "timeline.svg",
    "Fission_ResetLayout": "layout-reset.svg",
    "Fission_ToggleNavigation": "navigation.svg",
    "Fission_ToggleViewCube": "view-cube.svg",
    "Fission_PreviousWorkspace": "workspace-previous.svg",
    "Fission_NextWorkspace": "workspace-next.svg",
    "Fission_Preferences": "preferences.svg",
}

# Keep this small, explicit map independent of commands.py: GetResources can
# consult owned_resource while commands.py itself is being imported.
_NATIVE_BACKENDS = {
    "Fission_NewDesign": "Std_New",
    "Fission_CreateSketch": "PartDesign_NewSketch",
    "Fission_FinishSketch": "Sketcher_LeaveSketch",
    "Fission_Extrude": "PartDesign_Pad",
    "Fission_Cut": "PartDesign_Pocket",
    "Fission_Revolve": "PartDesign_Revolution",
    "Fission_Sweep": "PartDesign_AdditivePipe",
    "Fission_Loft": "PartDesign_AdditiveLoft",
    "Fission_Hole": "PartDesign_Hole",
    "Fission_Fillet": "PartDesign_Fillet",
    "Fission_Chamfer": "PartDesign_Chamfer",
    "Fission_Shell": "PartDesign_Thickness",
    "Fission_Draft": "PartDesign_Draft",
    "Fission_Mirror": "PartDesign_Mirrored",
    "Fission_RectPattern": "PartDesign_LinearPattern",
    "Fission_CircPattern": "PartDesign_PolarPattern",
    "Fission_Boolean": "PartDesign_Boolean",
    "Fission_Plane": "PartDesign_Plane",
    "Fission_Measure": "Std_Measure",
    "Fission_Appearance": "Std_SetAppearance",
    "Fission_Visibility": "Std_ToggleVisibility",
    "Fission_Fit": "Std_ViewFitAll",
    "Fission_Compute": "Std_Refresh",
    "Fission_Stitch": "Surface_Filling",
    "Fission_AssemblyJoint": "Assembly_CreateJointFixed",
}

_NATIVE_FALLBACKS = {
    "Fission_Measure": "measure.svg",
    "Std_Measure": "measure.svg",
    "Fission_Compute": "recompute.svg",
    "Std_Refresh": "recompute.svg",
}


def owned_resource(command_id):
    """Return an absolute SVG path for a Fission-owned glyph, or None.

    This is suitable for FreeCAD GetResources()['Pixmap'] and needs neither
    command registration nor a QApplication. About retains the project mark.
    """
    if command_id == "Fission_About":
        return os.path.join(_RESOURCES, "fission.svg")
    filename = _OWNED.get(command_id)
    return os.path.join(_ICON_DIRECTORY, filename) if filename else None


def has_pixels(icon):
    """Whether an icon paints visible pixels at the ribbon's 26 px size.

    QIcon.isNull() alone accepts missing SVG resources and fully transparent
    payloads. Check the rendered pixmap and alpha channel as well.
    """
    if icon is None or icon.isNull():
        return False
    pixmap = icon.pixmap(26, 26)
    if pixmap.isNull():
        return False
    image = pixmap.toImage()
    if image.isNull():
        return False
    if not image.hasAlphaChannel():
        return True
    for row in range(image.height()):
        for column in range(image.width()):
            if image.pixelColor(column, row).alpha():
                return True
    return False


def _resource_icon(name):
    if not isinstance(name, str) or not name:
        return None
    # This understands FreeCAD's resource aliases, cached XPMs, icon themes,
    # and icon search paths. Concatenating '.svg' cannot resolve all of them.
    try:
        icon = Gui.getIcon(name)
        if has_pixels(icon):
            return icon
    except (AttributeError, RuntimeError, TypeError):
        pass

    paths = [name]
    if not name.startswith(":") and not os.path.isabs(name):
        paths.append(":/icons/" + name)
        if not os.path.splitext(name)[1]:
            paths.extend(":/icons/" + name + suffix for suffix in (".svg", ".png", ".xpm"))
    for path in paths:
        icon = QtGui.QIcon(path)
        if has_pixels(icon):
            return icon
    icon = QtGui.QIcon.fromTheme(os.path.splitext(os.path.basename(name))[0])
    return icon if has_pixels(icon) else None


def _native_icon(command_id):
    try:
        command = Gui.Command.get(command_id)
    except (AttributeError, RuntimeError, TypeError):
        return None
    if not command:
        return None
    try:
        icon = _resource_icon(command.getInfo().get("pixmap", ""))
        if icon is not None:
            return icon
    except (AttributeError, RuntimeError, TypeError):
        pass
    try:
        for action in command.getAction() or ():
            icon = action.icon()
            if has_pixels(icon):
                return icon
    except (AttributeError, RuntimeError, TypeError):
        pass
    return None


def resolve(command_id):
    """Return a visible QIcon for a registered native or Fission command.

    Resolve on demand so commands loaded by later workbench activation become
    available immediately; do not cache an early missing-command fallback.
    """
    owned = owned_resource(command_id)
    if owned:
        icon = QtGui.QIcon(owned)
        if has_pixels(icon):
            return icon
    backend = _NATIVE_BACKENDS.get(command_id, command_id)
    icon = _native_icon(backend)
    if icon is None and backend != command_id:
        icon = _native_icon(command_id)
    if icon is not None:
        return icon
    filename = _NATIVE_FALLBACKS.get(command_id, "command.svg")
    return QtGui.QIcon(os.path.join(_ICON_DIRECTORY, filename))
