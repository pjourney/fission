# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real icon rendering and native CAD operations from ribbon dropdowns."""
import importlib
import json
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets
try:
    from PySide import QtTest
except ImportError:
    QtTest = importlib.import_module("PySide6.QtTest")

import cad_workflows as cad
from search_workflows import _design
from interactive_workflow import _edited_feature, _finish_task, _set_quantity
from marking_workflow import _focus


def _pixels(icon, size=26):
    picture = icon.pixmap(size, size)
    cad.require(not picture.isNull(), "Command icon must render at {} pixels".format(size))
    pixels = picture.toImage()
    cad.require(any(pixels.pixelColor(x, y).alpha() for y in range(pixels.height())
                    for x in range(pixels.width())), "Command icon must contain visible pixels")


def _button(controller, command, settle):
    controller.refresh_context()
    settle(70)
    buttons = [button for button in controller.buttons
               if button.property("fissionCommand") == command and button.isVisible()]
    cad.require(len(buttons) == 1 and buttons[0].isEnabled(),
                "Expected one enabled ribbon button: " + command)
    return buttons[0]


def _choose(controller, command, variant, settle, index=None):
    button = _button(controller, command, settle)
    menu = button.menu()
    cad.require(menu is not None and button.popupMode() == QtWidgets.QToolButton.MenuButtonPopup,
                "Native tool family must expose a split button: " + command)
    # Open the actual split-button arrow, then click the real QAction row.
    failures = []
    def click_choice():
        try:
            cad.require(menu.isVisible() and QtWidgets.QApplication.activePopupWidget() is menu,
                        "Actual ribbon arrow must open its native tool menu")
            actions = [action for action in menu.actions() if action.property("fissionCommand") == variant
                       and (index is None or action.property("fissionCommandIndex") == index)]
            cad.require(len(actions) == 1 and actions[0].isEnabled(), "Native menu choice must be ready: " + variant)
            QtTest.QTest.mouseClick(menu, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier,
                                   menu.actionGeometry(actions[0]).center())
        except Exception as error:
            failures.append(error)
            menu.close()
    # QToolButton opens QMenu's nested event loop synchronously. Schedule the
    # actual row click before entering that loop, as a user would do afterward.
    QtCore.QTimer.singleShot(120, click_choice)
    QtTest.QTest.mouseClick(button, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier,
                           QtCore.QPoint(button.width() - 5, button.height() // 2))
    settle(260)
    if failures:
        raise failures[0]
    cad.require(not menu.isVisible(), "Native menu must release popup ownership before CAD starts")


def icons_and_inventory(controller, settle, output):
    from fission.shell import TABS, command_spec, command_icon
    from fission.ribbon_tools import VARIANTS
    from fission import theme
    rows, missing = [], []
    old_theme = controller.settings.GetString("Theme", "Dark")
    with _design(controller, settle):
        try:
            for workspace in ("Design", "Drawing", "Manufacture"):
                controller.switch_workspace(workspace)
                settle(260)
                keys = [controller.tabs.tabText(index) for index in range(controller.tabs.count())]
                if workspace == "Design":
                    keys.append("SKETCH")
                for key in keys:
                    for group, items in TABS[key]:
                        for item in items:
                            command, title = command_spec(item)
                            if not Gui.Command.get(command):
                                missing.append(command)
                                continue
                            icon = command_icon(command)
                            for size in (16, 26):
                                _pixels(icon, size)
                            if command.startswith("Fission_"):
                                for action in Gui.Command.get(command).getAction():
                                    _pixels(action.icon(), 16)
                            rows.append(dict(workspace=workspace, tab=key, command=command, title=title))
            cad.require(set(missing).issubset({"CAM_Surface"}), "Unexpected missing native ribbon commands: " + str(missing))
            for primary, variants in VARIANTS.items():
                for command, title, index in variants:
                    cad.require(Gui.Command.get(command) is not None, "Tool variant must be a registered native command: " + command)
                    icon = command_icon(command)
                    if index is not None:
                        actions = Gui.Command.get(command).getAction()
                        cad.require(index < len(actions), "Primitive variant must have its indexed native QAction")
                        icon = actions[index].icon()
                    for size in (16, 26):
                        _pixels(icon, size)
            controller.switch_workspace("Design")
            settle(260)
            for name in ("Dark", "Light"):
                theme.apply(controller.main, name)
                controller.refresh_context()
                settle(80)
                expected = QtGui.QColor(theme.COLORS[name]["text"])
                for widget, role in ((controller.browser.filter, QtGui.QPalette.Text),
                                     (controller.timeline.description, QtGui.QPalette.WindowText),
                                     (controller.timeline.recompute_button, QtGui.QPalette.ButtonText)):
                    cad.require(widget.palette().color(role) == expected,
                                name + " theme must keep product labels and controls readable")
                cad.require(controller.browser.filter.palette().color(QtGui.QPalette.PlaceholderText)
                            == QtGui.QColor(theme.COLORS[name]["muted"]),
                            name + " browser placeholder must use readable muted text")
                for dock in (controller.browser, controller.timeline):
                    title = dock.titleBarWidget() or dock
                    cad.require(title.palette().color(QtGui.QPalette.WindowText) == expected
                                and title.palette().color(QtGui.QPalette.Text) == expected,
                                name + " native product dock title must be readable")
                    controls = [button for button in title.findChildren(QtWidgets.QAbstractButton)
                                if button.objectName().startswith("qt_dockwidget_") and button.isVisible()]
                    cad.require(len(controls) >= 2, "Native dock must retain its Close and Float controls")
                    glyph = QtGui.QColor("#000000" if name == "Light" else "#ffffff")
                    for control in controls:
                        pixels = control.grab().toImage()
                        cad.require(any(pixels.pixelColor(x, y) == glyph for y in range(pixels.height())
                                        for x in range(pixels.width())),
                                    name + " rendered native dock glyph must contrast with its header")
                    if name == "Light":
                        floating = dock.findChild(QtWidgets.QAbstractButton, "qt_dockwidget_floatbutton")
                        closing = dock.findChild(QtWidgets.QAbstractButton, "qt_dockwidget_closebutton")
                        QtTest.QTest.mouseClick(floating, QtCore.Qt.LeftButton)
                        settle(80)
                        cad.require(dock.isFloating(), "Themed Float control must retain native docking behavior")
                        dock.setFloating(False)
                        settle(80)
                        QtTest.QTest.mouseClick(closing, QtCore.Qt.LeftButton)
                        settle(80)
                        cad.require(not dock.isVisible(), "Themed Close control must hide its native dock")
                        dock.show()
                        settle(80)
                        for control in controls:
                            pixels = control.grab().toImage()
                            cad.require(any(pixels.pixelColor(x, y) == glyph for y in range(pixels.height())
                                            for x in range(pixels.width())),
                                        "Native redocking must preserve Light dock glyph contrast")
                for button in controller.buttons:
                    _pixels(button.icon(), 16 if button.toolButtonStyle() == QtCore.Qt.ToolButtonTextBesideIcon else 26)
                controller.main.grab().save(str(Path(output) / ("fission-ribbon-" + name.lower() + ".png")))
            (Path(output) / "ribbon-inventory.json").write_text(json.dumps(rows, indent=2) + "\n")
        finally:
            theme.apply(controller.main, old_theme)
    return {"registered_slots": len(rows), "native_variants": sum(len(items) for items in VARIANTS.values()),
            "sizes": [16, 26], "themes": ["Dark", "Light"], "native_dock_controls": True,
            "optional_absent": sorted(set(missing))}


def primitives(controller, settle, output):
    with _design(controller, settle) as doc:
        body = doc.Body
        original_names, undo = sorted(obj.Name for obj in doc.Objects), doc.UndoCount
        for accept in (False, True):
            _choose(controller, "PartDesign_CompPrimitiveAdditive", "PartDesign_CompPrimitiveAdditive", settle, 0)
            box, task = _edited_feature(doc, "PartDesign::AdditiveBox", controller)
            for field, value in (("boxLength", 20), ("boxWidth", 12), ("boxHeight", 10)):
                _set_quantity(task, field, value, settle)
            cad.require(box.Shape.isValid() and abs(box.Shape.Volume - 2400) < 1e-6,
                        "Native additive box task must preview requested dimensions")
            _finish_task(doc, task, settle, accept)
            if not accept:
                cad.require(sorted(obj.Name for obj in doc.Objects) == original_names and doc.UndoCount == undo,
                            "Primitive task Cancel must roll back its feature and transaction")
        cad.require(body.Tip is box and doc.UndoCount == undo + 1, "Native primitive OK must commit one feature and Undo")
        before = cad.shape_signature(body.Shape)
        _choose(controller, "PartDesign_CompPrimitiveSubtractive", "PartDesign_CompPrimitiveSubtractive", settle, 1)
        cut, task = _edited_feature(doc, "PartDesign::SubtractiveCylinder", controller)
        _set_quantity(task, "cylinderRadius", 3, settle)
        _set_quantity(task, "cylinderHeight", 10, settle)
        cad.require(cut.Shape.isValid() and 0 < cut.Shape.Volume < before["volume"],
                    "Cylinder menu index must preview a real native subtractive cylinder")
        _finish_task(doc, task, settle, True)
        cad.require(body.Tip is cut and doc.UndoCount == undo + 2, "Primitive cut must commit one native Undo step")
        after = cad.shape_signature(body.Shape)
        doc.undo()
        settle(180)
        cad.compare_shapes(before, cad.shape_signature(body.Shape))
        doc.redo()
        settle(180)
        cad.compare_shapes(after, cad.shape_signature(body.Shape))
        path = Path(output) / "ribbon-primitives.FCStd"
        doc.saveAs(str(path))
        box_name = box.Name
        name = doc.Name
        App.closeDocument(name)
        reopened = App.openDocument(str(path))
        settle(160)
        cad.compare_shapes(after, cad.shape_signature(reopened.Body.Shape))
        reopened.getObject(box_name).Length = 25
        reopened.recompute()
        cad.require(reopened.Body.Shape.isValid() and reopened.Body.Shape.Volume > after["volume"],
                    "Reopened primitives must remain parametric native features")
        return {"additive_box_volume": 2400, "cylinder_cut": after, "native_cancel_undo_redo": True,
                "parametric_reopen": True, "file": str(path)}


def sketch_variants(controller, settle, output):
    with _design(controller, settle) as doc:
        sketch = doc.Body.newObject("Sketcher::SketchObject", "VariantSketch")
        doc.recompute()
        Gui.activeDocument().setEdit(sketch.Name)
        settle(220)
        controller.refresh_context()
        view = Gui.activeDocument().activeView()
        viewport = view.graphicsView().viewport()
        task = Gui.Control.activeTaskDialog()
        _choose(controller, "Sketcher_CreateRectangle", "Sketcher_CreateRectangle_Center", settle)
        for point in (viewport.rect().center() + QtCore.QPoint(-85, -40),
                      viewport.rect().center() + QtCore.QPoint(-30, 10)):
            QtTest.QTest.mouseMove(viewport, point)
            settle(60)
            QtTest.QTest.mouseClick(viewport, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, point)
            settle(100)
        QtTest.QTest.keyClick(view.graphicsView(), QtCore.Qt.Key_Escape)
        settle(100)
        lines = [item for item in sketch.Geometry if item.TypeId == "Part::GeomLineSegment"]
        cad.require(len(lines) == 4 and sketch.solve() == 0,
                    "Center Rectangle menu must create four real solver-valid native edges")
        _choose(controller, "Sketcher_CreateCircle", "Sketcher_Create3PointCircle", settle)
        for point in (viewport.rect().center() + QtCore.QPoint(65, -65),
                      viewport.rect().center() + QtCore.QPoint(130, -20),
                      viewport.rect().center() + QtCore.QPoint(65, 35)):
            QtTest.QTest.mouseMove(viewport, point)
            settle(60)
            QtTest.QTest.mouseClick(viewport, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, point)
            settle(100)
        QtTest.QTest.keyClick(view.graphicsView(), QtCore.Qt.Key_Escape)
        settle(100)
        cad.require(any(item.TypeId == "Part::GeomCircle" for item in sketch.Geometry) and sketch.solve() == 0,
                    "3-Point Circle menu must create real native circle geometry")
        cad.require(Gui.Control.activeTaskDialog().getDialogContent() == task.getDialogContent(),
                    "Sketch dropdowns must preserve the native document-owned task")
        controller.refresh_command_state()
        cad.require(controller.command_available("Sketcher_CreateRectangle_Center"),
                    "Exposed menu variants must also be ready in S command search")
        # A menu from a former edit must not dispatch into a new same-document context.
        button = _button(controller, "Sketcher_CreateRectangle", settle)
        menu, action = button.menu(), button.menu().actions()[1]
        controller.refresh_variants(menu)
        Gui.activeDocument().resetEdit()
        Gui.Control.closeDialog()
        before = sketch.GeometryCount
        controller.execute_variant(menu, action)
        settle(160)
        cad.require(sketch.GeometryCount == before and not Gui.activeDocument().getInEdit(),
                    "Stale native edit menu must refuse dispatch")
        path = Path(output) / "ribbon-sketch-variants.FCStd"
        doc.recompute()
        doc.saveAs(str(path))
        return {"center_rectangle_edges": len(lines), "three_point_circle": True,
                "native_task_preserved": True, "search_readiness": True, "stale_edit_guard": True,
                "file": str(path)}
