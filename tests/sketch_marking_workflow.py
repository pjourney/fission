# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketch menu commands create real geometry through native canvas clicks."""
import importlib
from pathlib import Path
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
try:
    from PySide import QtTest
except ImportError:
    QtTest = importlib.import_module("PySide6.QtTest")
from cad_workflows import require
from marking_workflow import _open_chord, _wedge
from fission.marking_config import normalize_config, write_config
from fission.shortcuts import DEFAULT_PROFILE


def run(controller, settle, output):
    previous = App.ActiveDocument.Name if App.ActiveDocument else None
    original = controller.settings.GetString("MarkingMenu", "")
    controller.switch_workspace("Drawing")
    settle(180)
    controller.shortcuts.apply_profile(DEFAULT_PROFILE)
    write_config(controller.settings, normalize_config({}))
    controller.marking.refresh_settings()
    doc = controller.new_design()
    require(doc is not None, "New Design from Drawing must create the actual native design")
    settle(220)
    require(App.ActiveDocument is doc and Gui.activeDocument().Document is doc
            and controller._workspace_name == "Design", "Deferred workspace activation must keep the newly created design active")
    try:
        body = doc.Body
        sketch = body.newObject("Sketcher::SketchObject", "Sketch")
        doc.recompute()
        Gui.activeDocument().activeView().setActiveObject("pdbody", body)
        Gui.activeDocument().setEdit(sketch.Name)
        settle(250)
        controller.refresh_context()
        require(controller.context() == "sketch", "Menu context must follow actual native Sketcher edit")
        view = Gui.activeDocument().activeView()
        viewport = view.graphicsView().viewport()
        for name in ("WindowSelection", "FreeformSelection", "PaintSelection"):
            require(not Gui.Command.get("Fission_" + name).isActive(), "Sketcher must retain native selection ownership")
        task = Gui.Control.activeTaskDialog().getDialogContent()
        popup = _open_chord(controller, viewport, settle)
        require(popup.context == "sketch" and popup.entries[0]["id"] == "Sketcher_CreateLine"
                and popup.entries[0]["enabled"], "Sketch menu must expose the actual enabled native line command")
        QtTest.QTest.mouseClick(popup, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, _wedge(popup, 0))
        settle(150)
        require(controller.marking.popup is None, "Sketch draw handler must own the canvas after the menu closes")
        require(Gui.Control.activeTaskDialog().getDialogContent() == task, "Menu dispatch must preserve the native sketch task")
        for point in (viewport.rect().center() + QtCore.QPoint(-75, -45),
                      viewport.rect().center() + QtCore.QPoint(65, 35)):
            QtTest.QTest.mouseMove(viewport, point)
            settle(80)
            QtTest.QTest.mouseClick(viewport, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, point)
            settle(120)
        QtTest.QTest.keyClick(viewport, QtCore.Qt.Key_Escape)
        settle(150)
        require(sketch.GeometryCount == 1 and sketch.Geometry[0].TypeId == "Part::GeomLineSegment",
                "Two actual sketch clicks must create one native line: " + str(sketch.GeometryCount))
        line_length = (sketch.Geometry[0].EndPoint - sketch.Geometry[0].StartPoint).Length
        require(line_length > 0 and sketch.solve() == 0, "Native line geometry and solver must be valid")
        popup = _open_chord(controller, viewport, settle)
        require(popup.entries[4]["id"] == "Fission_FinishSketch" and popup.entries[4]["enabled"],
                "Sketch menu must expose the native Finish Sketch transition")
        QtTest.QTest.mouseClick(popup, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, _wedge(popup, 4))
        settle(220)
        require(not Gui.getDocument(doc.Name).getInEdit() and not Gui.Control.activeDialog()
                and controller.context() == "model", "Finish Sketch menu command must release native task/edit ownership")
        file = Path(output) / "marking-sketch.FCStd"
        doc.recompute()
        doc.saveAs(str(file))
        require(file.is_file(), "Actual sketch geometry must save as FCStd")
        return {"native_sketch_context": True, "native_line_clicks": True, "line_length_mm": line_length,
                "new_design_from_drawing_retained": True,
                "native_task_preserved": True, "selection_wrappers_inactive": True, "finish_sketch": True,
                "saved_document": str(file)}
    finally:
        controller.marking.close()
        gui_doc = Gui.getDocument(doc.Name)
        if gui_doc.getInEdit():
            gui_doc.resetEdit()
            Gui.Control.closeDialog()
        App.closeDocument(doc.Name)
        controller.settings.SetString("MarkingMenu", original)
        controller.marking.refresh_settings()
        if previous and previous in App.listDocuments():
            App.setActiveDocument(previous)
            Gui.setActiveDocument(previous)
        settle(120)
