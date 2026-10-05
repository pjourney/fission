# SPDX-License-Identifier: LGPL-2.1-or-later
"""Document panel acceptance through actual Qt keys and native CAD commands."""
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
from fission.history import object_key
from interactive_workflow import _edited_feature, _finish_task, _set_quantity
from marking_workflow import _focus
from search_workflows import _design


def _refresh(controller, settle):
    controller.browser.refresh()
    controller.timeline.refresh()
    controller.refresh_context()
    settle(160)


def _select(controller, panel, objects, settle):
    widget = panel.tree if panel is controller.browser else panel.list
    Gui.Selection.clearSelection()
    for obj in objects:
        Gui.Selection.addSelection(obj)
    settle(100)
    panel.sync_selection()
    item = panel._items[object_key(objects[0])]
    if panel is controller.browser:
        widget.setCurrentItem(item, 0, QtCore.QItemSelectionModel.NoUpdate)
    else:
        widget.setCurrentItem(item, QtCore.QItemSelectionModel.NoUpdate)
    _focus(controller, widget, settle)
    return widget


def _boxes(doc, count=3):
    result = []
    for index in range(count):
        obj = doc.addObject("Part::Feature", "HistoryBox")
        obj.Label = "Box {}".format(index + 1)
        obj.Shape = cad.Part.makeBox(8, 6, 4, App.Vector(index * 12, 0, 0))
        result.append(obj)
    doc.recompute()
    return result


def _editor(widget, settle):
    QtTest.QTest.keyClick(widget, QtCore.Qt.Key_F2)
    settle(80)
    editor = QtWidgets.QApplication.focusWidget()
    cad.require(isinstance(editor, QtWidgets.QLineEdit) and widget.isAncestorOf(editor),
                "F2 must open a real inline label editor in the focused panel")
    return editor


def rename_and_selection(controller, settle, output):
    with _design(controller, settle) as doc:
        objects = _boxes(doc)
        _refresh(controller, settle)
        before = [cad.shape_signature(obj.Shape) for obj in objects]
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(objects[2])
        settle(100)
        cad.require(controller.timeline.list.currentItem() is controller.timeline._items[object_key(objects[2])]
                    and controller.browser.tree.currentItem() is controller.browser._items[object_key(objects[2])],
                    "Canvas-driven selection must update both panels' keyboard current row")
        widget = _select(controller, controller.timeline, [objects[0]], settle)
        QtTest.QTest.keyClick(widget, QtCore.Qt.Key_Right)
        settle(90)
        cad.require(Gui.Selection.getSelection() == [objects[1]], "Right must select the next native history object")
        cad.require(controller.browser._items[object_key(objects[1])].isSelected(), "Timeline arrows must synchronize Browser selection")
        camera = list(Gui.activeDocument().activeView().getCameraOrientation().Q)
        QtTest.QTest.keyClick(widget, QtCore.Qt.Key_Right, QtCore.Qt.ShiftModifier)
        settle(90)
        cad.require({obj.Name for obj in Gui.Selection.getSelection()} == {objects[1].Name, objects[2].Name},
                    "Shift+Right must extend actual native object selection: selected={}, current={}".format(
                        [obj.Name for obj in Gui.Selection.getSelection()], widget.currentItem().text()))
        cad.require(camera == list(Gui.activeDocument().activeView().getCameraOrientation().Q),
                    "Panel Shift+Arrow selection must not dispatch native camera rotation")
        widget = _select(controller, controller.browser, [objects[0]], settle)
        QtTest.QTest.keyClick(widget, QtCore.Qt.Key_Down)
        settle(90)
        cad.require(Gui.Selection.getSelection() == [objects[1]], "Browser Down must navigate real object rows")
        cad.require(controller.timeline._items[object_key(objects[1])].isSelected(), "Browser arrows must synchronize Timeline selection")
        undo = doc.UndoCount
        labels = []
        for panel, obj, label in ((controller.browser, objects[0], "Edited Browser label"),
                                  (controller.timeline, objects[1], "Edited Timeline label")):
            widget = _select(controller, panel, [obj], settle)
            editor = _editor(widget, settle)
            cad.require(editor.text() == obj.Label, "Inline editor must contain native Label without presentation markers")
            editor.selectAll()
            QtTest.QTest.keyClicks(editor, label)
            QtTest.QTest.keyClick(editor, QtCore.Qt.Key_Delete)
            cad.require(editor.text() == label and obj.Label != label, "Typing E/Delete must stay in the editor until commit")
            QtTest.QTest.keyClick(editor, QtCore.Qt.Key_Return)
            settle(180)
            cad.require(obj.Label == label, "Return must commit the native object label")
            cad.require(controller.browser._items[object_key(obj)].text(0) == label
                        and label in controller.timeline._items[object_key(obj)].text(),
                        "Committed labels must update both native document panels")
            cad.require(not Gui.Control.activeDialog(), "Editor Return must not start a feature task")
            labels.append(label)
        cad.require(doc.UndoCount == undo + 2, "Each committed rename must create one native Undo entry")
        widget = _select(controller, controller.timeline, [objects[1]], settle)
        editor = _editor(widget, settle)
        editor.selectAll()
        QtTest.QTest.keyClicks(editor, "Cancelled label")
        QtTest.QTest.keyClick(editor, QtCore.Qt.Key_Escape)
        settle(150)
        cad.require(objects[1].Label == labels[1] and doc.UndoCount == undo + 2,
                    "Escape must cancel inline rename without a document transaction")
        doc.undo()
        settle(150)
        cad.require(objects[1].Label == "Box 2", "Native Undo must restore the original Timeline label")
        doc.redo()
        settle(150)
        for obj, shape in zip(objects, before):
            cad.compare_shapes(shape, cad.shape_signature(obj.Shape))
        path = Path(output) / "history-labels.FCStd"
        names = [obj.Name for obj in objects]
        doc.saveAs(str(path))
        App.closeDocument(doc.Name)
        reopened = App.openDocument(str(path))
        _refresh(controller, settle)
        cad.require([reopened.getObject(name).Label for name in names[:2]] == labels,
                    "Inline labels must survive native FCStd reopen")
        return {"arrow_selection_sync": True, "shift_multiselection": True,
                "inline_rename_undo_redo": True, "escape_cancel": True, "file": str(path)}


def modeling(controller, settle, output):
    with _design(controller, settle) as doc:
        body = doc.addObject("PartDesign::Body", "Body")
        sketch = body.newObject("Sketcher::SketchObject", "Profile")
        cad.constrained_rectangle(sketch, 20, 10)
        pad = body.newObject("PartDesign::Pad", "Extrude")
        pad.Profile, pad.Length = sketch, 8
        body.Tip = pad
        doc.recompute()
        sketch.ViewObject.Visibility = False
        Gui.activeDocument().activeView().fitAll()
        _refresh(controller, settle)
        before = cad.shape_signature(body.Shape)
        undo = doc.UndoCount
        for panel, accept in ((controller.timeline, False), (controller.browser, True)):
            widget = _select(controller, panel, [pad], settle)
            QtTest.QTest.keyClick(widget, QtCore.Qt.Key_Return if not accept else QtCore.Qt.Key_Enter,
                                 QtCore.Qt.NoModifier if not accept else QtCore.Qt.KeypadModifier)
            settle(220)
            feature, dialog = _edited_feature(doc, "PartDesign::Pad", controller)
            cad.require(feature is pad, "Enter must edit the selected native feature")
            _set_quantity(dialog, "lengthEdit", 12, settle)
            cad.require(abs(pad.Shape.Volume - 2400) < 1e-6, "Native task edit must update preview geometry: pad={}, body={}, length={}".format(
                pad.Shape.Volume, body.Shape.Volume, pad.Length.Value))
            task_graph = [obj.Name for obj in doc.Objects]
            task_undo = doc.UndoCount
            # Panel keys must never resolve the task's open transaction.
            widget = _select(controller, controller.timeline, [pad], settle)
            for key in (QtCore.Qt.Key_F2, QtCore.Qt.Key_Delete, QtCore.Qt.Key_Return):
                QtTest.QTest.keyClick(widget, key)
                settle(50)
            cad.require(Gui.getDocument(doc.Name).getInEdit().Object is pad
                        and doc.HasPendingTransaction and doc.UndoCount == task_undo
                        and [obj.Name for obj in doc.Objects] == task_graph,
                        "History keys must preserve the active native feature task and transaction")
            _finish_task(doc, dialog, settle, accept=accept)
            if not accept:
                cad.compare_shapes(before, cad.shape_signature(body.Shape))
                cad.require(doc.UndoCount == undo, "Cancel of Enter editing must not commit an Undo entry")
            else:
                cad.require(abs(pad.Length.Value - 12) < 1e-6 and doc.UndoCount == undo + 1,
                            "Native OK must commit the Enter edit in one Undo entry")
        doc.undo()
        doc.recompute()
        settle(150)
        cad.compare_shapes(before, cad.shape_signature(body.Shape))
        return {"timeline_enter_cancel": True, "browser_enter_ok": True,
                "native_preview_volume": 2400, "task_key_guard": True, "one_undo": True}


def deletion(controller, settle, output):
    with _design(controller, settle) as doc:
        objects = _boxes(doc)
        linked = doc.addObject("Part::Feature", "Dependent")
        linked.addProperty("App::PropertyLink", "Source")
        linked.Source = objects[0]
        linked.Shape = objects[0].Shape.copy()
        doc.recompute()
        _refresh(controller, settle)
        widget = _select(controller, controller.timeline, [objects[0]], settle)
        graph = [(obj.Name, obj.TypeId) for obj in doc.Objects]
        undo = doc.UndoCount
        prompts = []
        timer = QtCore.QTimer(controller.main)
        timer.setInterval(20)

        def reject_dependencies():
            modal = QtWidgets.QApplication.activeModalWidget()
            if isinstance(modal, QtWidgets.QMessageBox):
                prompts.append({"title": modal.windowTitle(), "text": modal.text()})
                modal.done(QtWidgets.QMessageBox.No)

        timer.timeout.connect(reject_dependencies)
        timer.start()
        try:
            QtTest.QTest.keyClick(widget, QtCore.Qt.Key_Delete)
            settle(150)
        finally:
            timer.stop()
            timer.deleteLater()
        cad.require(len(prompts) == 1 and "Dependent" in prompts[0]["text"],
                    "Panel Delete must retain the actual native dependency confirmation")
        cad.require(graph == [(obj.Name, obj.TypeId) for obj in doc.Objects] and doc.UndoCount == undo,
                    "Rejecting dependency deletion must preserve graph and Undo history")
        widget = _select(controller, controller.browser, objects[1:], settle)
        names = [obj.Name for obj in objects[1:]]
        signatures = [cad.shape_signature(obj.Shape) for obj in objects[1:]]
        QtTest.QTest.keyClick(widget, QtCore.Qt.Key_Delete)
        settle(180)
        cad.require(all(doc.getObject(name) is None for name in names) and doc.getObject(objects[0].Name),
                    "Delete must remove the full selected set and preserve unselected objects")
        cad.require(doc.UndoCount == undo + 1, "Multi-object native Delete must create one Undo entry")
        doc.undo()
        doc.recompute()
        settle(150)
        for name, shape in zip(names, signatures):
            cad.compare_shapes(shape, cad.shape_signature(doc.getObject(name).Shape))
        doc.openTransaction("Pending history acceptance")
        try:
            doc.getObject(names[0]).Label = "Pending label"
            cad.require(doc.HasPendingTransaction, "Acceptance fixture must establish an actual pending transaction")
            widget = _select(controller, controller.timeline, [doc.getObject(names[0])], settle)
            QtTest.QTest.keyClick(widget, QtCore.Qt.Key_Delete)
            QtTest.QTest.keyClick(widget, QtCore.Qt.Key_F2)
            settle(100)
            cad.require(doc.HasPendingTransaction and doc.getObject(names[0]) is not None,
                        "Panel Delete/F2 must not resolve an externally pending native transaction")
            cad.require(QtWidgets.QApplication.focusWidget() is widget, "Blocked rename must not open an editor")
        finally:
            doc.abortTransaction()
        return {"dependency_prompt_rejected": prompts, "deleted_objects": names,
                "multi_delete_one_undo": True, "pending_transaction_guard": True}


def component_sketch(controller, settle, output):
    with _design(controller, settle) as doc:
        first = doc.addObject("App::Part", "FirstComponent")
        empty = doc.addObject("App::Part", "EmptyComponent")
        old_body = doc.addObject("PartDesign::Body", "ExistingBody")
        first.addObject(old_body)
        doc.recompute()
        controller.browser._activate(empty)
        Gui.Selection.clearSelection()
        _refresh(controller, settle)
        menus = []
        timer = QtCore.QTimer(controller.main)
        timer.setInterval(20)

        def choose_sketch():
            popup = QtWidgets.QApplication.activePopupWidget()
            if isinstance(popup, QtWidgets.QMenu):
                action = next((item for item in popup.actions() if item.text() == "Create sketch"), None)
                if action:
                    menus.append(action.text())
                    popup.close()
                    action.trigger()
                    timer.stop()

        timer.timeout.connect(choose_sketch)
        timer.start()
        try:
            controller.browser._menu(None, controller.browser.tree.mapToGlobal(QtCore.QPoint(30, 30)))
            settle(200)
        finally:
            timer.stop()
            timer.deleteLater()
        cad.require(menus == ["Create sketch"], "Acceptance must invoke the actual document-panel menu action")
        view = Gui.activeDocument().activeView()
        body = view.getActiveObject("pdbody")
        cad.require(body is not None and body is not old_body and body.getParentGeoFeatureGroup() is empty,
                    "Create sketch menu must establish a Body in the active empty component")
        task = Gui.Control.activeTaskDialog(Gui.getDocument(doc.Name))
        cad.require(task is not None, "Menu Create sketch must open the actual native sketch plane task")
        task.reject()
        settle(180)
        cad.require(not Gui.Control.activeDialog() and not doc.HasPendingTransaction,
                    "Native plane Cancel must release its task transaction")
        return {"active_component": empty.Name, "new_body": body.Name,
                "existing_body_retained": doc.getObject(old_body.Name) is old_body, "native_task_cancel": True}
