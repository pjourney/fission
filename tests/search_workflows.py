# SPDX-License-Identifier: LGPL-2.1-or-later
"""Native S toolbox acceptance: actual CAD dispatch, tasks and canvas input."""
from contextlib import contextmanager
import importlib
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
try:
    from PySide import QtTest
except ImportError:
    QtTest = importlib.import_module("PySide6.QtTest")

import cad_workflows as cad
from interactive_workflow import _edited_feature, _finish_task, _set_quantity, _presentation
from marking_workflow import _focus
from fission.shortcuts import DEFAULT_PROFILE


@contextmanager
def _design(controller, settle):
    before = set(App.listDocuments())
    previous = App.ActiveDocument.Name if App.ActiveDocument else None
    profile = controller.shortcuts.profile.export_data()
    history = controller.settings.GetString("CommandSearchHistory", "")
    workspace, tab = controller._workspace_name, controller._tab
    controller.switch_workspace("Design")
    settle(180)
    for index in range(controller.tabs.count()):
        if controller.tabs.tabText(index) == "SOLID":
            controller.tabs.setCurrentIndex(index)
            break
    controller.shortcuts.apply_profile(DEFAULT_PROFILE)
    controller.settings.SetString("CommandSearchHistory", "")
    if hasattr(controller, "search_dialog"):
        controller.search_dialog.close()
    doc = controller.new_design()
    doc.UndoMode = 1
    settle(180)
    try:
        yield doc
    finally:
        if hasattr(controller, "search_dialog"):
            controller.search_dialog.close()
        for name in set(App.listDocuments()) - before:
            gui_doc = Gui.getDocument(name)
            task = Gui.Control.activeTaskDialog(gui_doc)
            if task and gui_doc.getInEdit():
                try:
                    task.reject()
                except Exception:
                    gui_doc.resetEdit()
                    Gui.Control.closeDialog()
            App.closeDocument(name)
        controller.settings.SetString("CommandSearchHistory", history)
        controller.shortcuts.profile.import_data(profile)
        controller.shortcuts.apply_profile(controller.shortcuts.profile.name)
        if previous and previous in App.listDocuments():
            App.setActiveDocument(previous)
            Gui.setActiveDocument(previous)
        if workspace != "Design":
            controller.switch_workspace(workspace)
        else:
            for index in range(controller.tabs.count()):
                if controller.tabs.tabText(index) == tab:
                    controller.tabs.setCurrentIndex(index)
                    break
        settle(150)


def _open(controller, settle, query="", widget=None):
    widget = widget or controller.browser.tree
    _focus(controller, widget, settle)
    QtTest.QTest.keyClick(widget, QtCore.Qt.Key_S)
    settle(90)
    dialog = controller.search_dialog
    cad.require(dialog.isVisible() and QtWidgets.QApplication.focusWidget() is dialog.input,
                "Actual S must open the toolbox and focus its text field: visible={}, focus={}".format(
                    dialog.isVisible(), QtWidgets.QApplication.focusWidget()))
    if query:
        QtTest.QTest.keyClicks(dialog.input, query)
        settle(60)
    return dialog


def _row(dialog, command):
    found = [dialog.results.topLevelItem(index) for index in range(dialog.results.topLevelItemCount())
             if dialog.results.topLevelItem(index).data(0, QtCore.Qt.UserRole) == command]
    cad.require(len(found) == 1, "Toolbox must expose one actual command row: " + command)
    return found[0]


def _run(dialog, command, settle):
    item = _row(dialog, command)
    cad.require(bool(item.flags() & QtCore.Qt.ItemIsEnabled), "Required native toolbox command must be enabled: " + command)
    dialog.results.setCurrentItem(item)
    QtTest.QTest.keyClick(dialog.input, QtCore.Qt.Key_Return)
    settle(160)
    cad.require(not dialog.isVisible(), "Toolbox must close before the native command owns focus")


def toolbox(controller, settle, output):
    with _design(controller, settle) as doc:
        Gui.Selection.clearSelection()
        dialog = _open(controller, settle)
        shown = dialog.results.topLevelItemCount()
        cad.require(shown == len(dialog._catalog) and shown > 100,
                    "The unfiltered toolbox must show its complete native catalog without a silent cutoff")
        dialog.input.setText("  eDiT fEaTuRe  ")
        settle(50)
        disabled = _row(dialog, "Fission_EditFeature")
        cad.require(not disabled.flags() & QtCore.Qt.ItemIsEnabled,
                    "Edit Feature without a selected object must be visibly unavailable")
        graph = [(obj.Name, obj.TypeId) for obj in doc.Objects]
        undo = doc.UndoCount
        dialog.results.setCurrentItem(disabled)
        QtTest.QTest.keyClick(dialog.input, QtCore.Qt.Key_Return)
        settle(80)
        cad.require(dialog.isVisible() and not Gui.Control.activeDialog() and not doc.HasPendingTransaction,
                    "Enter on unavailable results must retain search and leave native task ownership untouched")
        cad.require(graph == [(obj.Name, obj.TypeId) for obj in doc.Objects] and undo == doc.UndoCount,
                    "Unavailable toolbox commands must preserve the native graph and Undo history")
        Gui.Selection.addSelection(doc.Body)
        settle(240)
        cad.require(_row(dialog, "Fission_EditFeature").flags() & QtCore.Qt.ItemIsEnabled,
                    "Visible search readiness must follow actual native selection changes")
        Gui.Selection.clearSelection()
        settle(240)
        cad.require(not _row(dialog, "Fission_EditFeature").flags() & QtCore.Qt.ItemIsEnabled,
                    "Clearing native selection must disable the visible edit command again")
        dialog.input.setText("no_such_fission_tool_92847")
        settle(40)
        cad.require(dialog.results.topLevelItemCount() == 0 and "No matching" in dialog.help.text(),
                    "No-match feedback must describe the actual empty result set")
        QtTest.QTest.keyClick(dialog.input, QtCore.Qt.Key_Escape)
        settle(80)
        cad.require(not dialog.isVisible() and QtWidgets.QApplication.focusWidget() is controller.browser.tree,
                    "Escape must restore the Browser that opened search")
        dialog = _open(controller, settle, "new design")
        _run(dialog, "Fission_NewDesign", settle)
        created = App.ActiveDocument
        cad.require(created is not doc and created.getObject("Component") and created.getObject("Body"),
                    "Search must invoke the actual native New Design workflow")
        dialog = _open(controller, settle)
        cad.require(dialog.results.topLevelItem(0).data(0, QtCore.Qt.UserRole) == "Fission_NewDesign",
                    "A successfully launched recent command must appear first on the next empty search")
        history = controller.settings.GetString("CommandSearchHistory", "")
        cad.require("Fission_NewDesign" in history and "Fission_EditFeature" not in history,
                    "Only successful command launches may enter persisted search history")
        screenshot = Path(output) / "fission-command-search.png"
        cad.require(dialog.grab().save(str(screenshot)), "The actual command toolbox must render into a screenshot")
        App.closeDocument(created.Name)
        dialog.input.setText("edit feature")
        settle(100)
        cad.require(not dialog.isVisible() and not Gui.Control.activeDialog(),
                    "Closing the owning native document must invalidate search before another query or command")
        return {"catalog_rows": shown, "no_silent_cutoff": True, "normalized_query": True,
                "disabled_edit_preserves_graph": True, "escape_restores_browser_focus": True,
                "native_new_design": True, "successful_recent": True, "live_selection_readiness": True,
                "closed_document_guard": True, "screenshot": str(screenshot)}


def modeling(controller, settle, output):
    with _design(controller, settle) as doc:
        body = doc.Body
        doc.openTransaction("Toolbox fixture")
        sketch = body.newObject("Sketcher::SketchObject", "BaseSketch")
        cad.constrained_rectangle(sketch, 30, 20)
        pad = body.newObject("PartDesign::Pad", "Pad")
        pad.Profile, pad.Length = sketch, 10
        doc.recompute()
        body.Tip = pad
        doc.commitTransaction()
        sketch.Visibility = False
        pad.Visibility = body.Visibility = True
        view = Gui.activeDocument().activeView()
        view.setActiveObject("pdbody", body)
        view.viewAxonometric()
        view.fitAll()
        settle(120)
        initial = cad.shape_signature(body.Shape)
        original_graph = sorted(obj.Name for obj in doc.Objects)
        undo = doc.UndoCount
        edges = ["Edge{}".format(index + 1) for index, edge in enumerate(pad.Shape.Edges)
                 if edge.BoundBox.ZLength > 9.9 and edge.BoundBox.XLength < 1e-6 and edge.BoundBox.YLength < 1e-6]
        cad.require(len(edges) == 4, "Toolbox fixture must expose four real vertical edges")
        for accept in (False, True):
            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(doc.Name, pad.Name, edges[0])
            settle(70)
            dialog = _open(controller, settle, "fillet")
            _run(dialog, "Fission_Fillet", settle)
            feature, task = _edited_feature(doc, "PartDesign::Fillet", controller)
            cad.require(feature.Base[0] is pad and edges[0] in feature.Base[1],
                        "Search must pass the actual selected native edge to Fillet")
            _set_quantity(task, "filletRadius", 1.5, settle)
            preview = cad.shape_signature(feature.Shape)
            cad.require(preview["valid"] and preview["solids"] == 1 and 0 < preview["volume"] < initial["volume"],
                        "Toolbox Fillet must preview a real valid modified solid")
            # Search remains available during a task, but task ownership disables
            # unrelated native tools through their QAction state.
            toolbox_dialog = _open(controller, settle, "create sketch", view.graphicsView())
            cad.require(not _row(toolbox_dialog, "Fission_CreateSketch").flags() & QtCore.Qt.ItemIsEnabled,
                        "Search must reflect the native task's unavailable Create Sketch command")
            QtTest.QTest.keyClick(toolbox_dialog.input, QtCore.Qt.Key_Escape)
            settle(60)
            cad.require(Gui.getDocument(doc.Name).getInEdit().Object is feature and doc.HasPendingTransaction,
                        "Search cancellation must retain the native Fillet transaction")
            _finish_task(doc, task, settle, accept)
            if not accept:
                cad.require(sorted(obj.Name for obj in doc.Objects) == original_graph and doc.UndoCount == undo,
                            "Native Fillet Cancel must restore graph and Undo history")
                cad.compare_shapes(initial, cad.shape_signature(body.Shape))
            else:
                cad.require(body.Tip is feature and doc.UndoCount == undo + 1,
                            "Native Fillet OK must commit one Undo step from search")
                cad.compare_shapes(preview, cad.shape_signature(body.Shape))
                _presentation(controller, doc, [sketch, pad, feature], settle)
        _focus(controller, view.graphicsView(), settle)
        QtTest.QTest.keyClick(view.graphicsView(), QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)
        settle(220)
        cad.require(sorted(obj.Name for obj in doc.Objects) == original_graph and body.Tip is pad,
                    "Ctrl+Z after search-launched Fillet must restore the original body")
        cad.compare_shapes(initial, cad.shape_signature(body.Shape))
        return {"edge": edges[0], "native_fillet_preview": preview, "cancel_rollback": True,
                "task_availability": True, "one_undo_step": True, "ctrl_z_restores_pad": True}


def sketch(controller, settle, output):
    with _design(controller, settle) as doc:
        obj = doc.Body.newObject("Sketcher::SketchObject", "ToolboxSketch")
        doc.recompute()
        Gui.activeDocument().setEdit(obj.Name)
        settle(240)
        controller.refresh_context()
        cad.require(controller.context() == "sketch", "Search must run inside the actual native Sketcher edit")
        view = Gui.activeDocument().activeView()
        viewport = view.graphicsView().viewport()
        task = Gui.Control.activeTaskDialog().getDialogContent()
        dialog = _open(controller, settle, "line")
        _run(dialog, "Sketcher_CreateLine", settle)
        cad.require(Gui.Control.activeTaskDialog().getDialogContent() == task,
                    "Search must preserve the document-owned Sketcher task")
        focus = QtWidgets.QApplication.focusWidget()
        cad.require(focus is view.graphicsView() or focus is view.graphicsView().focusProxy(),
                    "Search opened from Browser must return keyboard focus to the actual native sketch canvas")
        for point in (viewport.rect().center() + QtCore.QPoint(-75, -40),
                      viewport.rect().center() + QtCore.QPoint(70, 35)):
            QtTest.QTest.mouseMove(viewport, point)
            settle(70)
            QtTest.QTest.mouseClick(viewport, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, point)
            settle(100)
        QtTest.QTest.keyClick(view.graphicsView(), QtCore.Qt.Key_Escape)
        settle(100)
        cad.require(obj.GeometryCount == 1 and obj.Geometry[0].TypeId == "Part::GeomLineSegment" and obj.solve() == 0,
                    "Search-launched Line must create real native sketch geometry through canvas clicks")
        dialog = _open(controller, settle, "finish sketch", view.graphicsView())
        _run(dialog, "Fission_FinishSketch", settle)
        cad.require(not Gui.getDocument(doc.Name).getInEdit() and not Gui.Control.activeDialog(),
                    "Search-launched Finish Sketch must release native editing ownership")
        path = Path(output) / "toolbox-sketch.FCStd"
        doc.recompute()
        doc.saveAs(str(path))
        cad.require(path.is_file(), "Toolbox-created native sketch must save as FCStd")
        return {"browser_to_canvas_focus": True, "native_task_preserved": True,
                "native_line_canvas_clicks": True, "solver_valid": True, "finish_sketch": True,
                "document": str(path)}
