# SPDX-License-Identifier: LGPL-2.1-or-later
"""Native interactive CAD smoke case; called from the running Fission GUI.

``run(controller, settle)`` returns JSON-compatible evidence and closes only
the document it creates. It never replaces command execution with a spy and
never assigns Pad/Fillet parameters directly to CAD objects. Rectangle input
uses the shared solver helper while the native sketch editor owns the task.

APIs checked against the pinned engine's FreeCADGui._TaskDialog.pyi,
TaskView/TaskDialogPython.cpp, PartDesign/Gui/SketchWorkflow.cpp,
TaskPadPocketParameters.ui, TaskFilletParameters.ui and QuantitySpinBox.h.
"""

import importlib
import json
import re

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

try:
    from PySide import QtTest
except ImportError:
    try:
        QtTest = importlib.import_module("PySide6.QtTest")
    except ImportError:
        QtTest = importlib.import_module("PySide2.QtTest")

import cad_workflows as cad
from fission.history import object_key
from fission.shortcuts import DEFAULT_PROFILE


def _native_state(controller, doc):
    """Describe task/document ownership before failed-case cleanup changes it."""
    def inspect(function):
        try:
            return function()
        except Exception as error:
            return "{}: {}".format(type(error).__name__, error)

    dialog = inspect(Gui.Control.activeTaskDialog)
    gui_doc = Gui.getDocument(doc.Name)
    edit = inspect(gui_doc.getInEdit)
    active_gui = Gui.activeDocument()
    return {"intended_document": doc.Name,
            "active_app_document": App.ActiveDocument.Name if App.ActiveDocument else None,
            "active_gui_document": inspect(lambda: active_gui.Document.Name) if active_gui else None,
            "workbench": inspect(lambda: Gui.activeWorkbench().name()),
            "pending_transaction": doc.HasPendingTransaction,
            "undo_count": doc.UndoCount,
            "objects": [(obj.Name, obj.TypeId) for obj in doc.Objects],
            "edited_object": inspect(lambda: (edit.Object.Name, edit.Object.TypeId)) if edit else None,
            "task_contents": inspect(lambda: [(widget.objectName(), widget.metaObject().className())
                                               for widget in dialog.getDialogContent()]) if dialog else None,
            "document_task_contents": inspect(lambda: [(widget.objectName(), widget.metaObject().className())
                                                        for widget in Gui.Control.activeTaskDialog(gui_doc).getDialogContent()]),
            "all_document_tasks": inspect(lambda: {name: bool(Gui.Control.activeTaskDialog(Gui.getDocument(name)))
                                                    for name in App.listDocuments()}),
            "task_docks": inspect(lambda: [(dock.objectName(), dock.metaObject().className(), dock.isVisible())
                                            for dock in controller.main.findChildren(QtWidgets.QDockWidget)
                                            if "Task" in dock.objectName() or "Task" in dock.windowTitle()]),
            "mdi_active": inspect(lambda: controller.main.findChild(QtWidgets.QMdiArea).activeSubWindow().windowTitle()),
            "status": controller.main.statusBar().currentMessage()}


def _task_widget(dialog, name):
    """Find a control in the active dialog, avoiding stale hidden task forms."""
    matches = []
    for content in dialog.getDialogContent():
        if content.objectName() == name:
            matches.append(content)
        matches.extend(content.findChildren(QtWidgets.QWidget, name))
    usable = [widget for widget in matches if widget.isVisible() and widget.isEnabled()]
    cad.require(len(usable) == 1, "Expected one visible native task control {}; found {}".format(name, len(usable)))
    return usable[0]


def _set_quantity(dialog, name, value, settle):
    widget = _task_widget(dialog, name)
    # QuantitySpinBox's writable double property invokes its native setValue
    # slot and valueChanged signal. The task panel then computes the preview.
    # This avoids changing the CAD feature behind the task dialog's back.
    index = widget.metaObject().indexOfProperty("rawValue")
    cad.require(index >= 0 and widget.metaObject().property(index).isWritable(),
                name + " must expose the native writable quantity property")
    cad.require(widget.setProperty("rawValue", float(value)), "Native task quantity could not be set: " + name)
    settle(160)
    actual = float(widget.property("rawValue"))
    cad.require(abs(actual - value) < 1e-7, "Task control {} expected {}, received {}".format(name, value, actual))
    return widget.metaObject().className()


def _workspace(controller, doc):
    """Native feature tasks must retain the intended document and Fission UI."""
    active_gui = Gui.activeDocument()
    valid = (App.ActiveDocument is not None and App.ActiveDocument.Name == doc.Name
             and active_gui is not None and active_gui.Document.Name == doc.Name
             and Gui.activeWorkbench().name() == "FissionWorkbench")
    if not valid:
        raise AssertionError("Native CAD workflow must retain its document and FissionWorkbench; state=" +
                             json.dumps(_native_state(controller, doc), default=str))


def _edited_feature(doc, type_id, controller):
    _workspace(controller, doc)
    edit = Gui.getDocument(doc.Name).getInEdit()
    cad.require(edit is not None, "Native {} task must own an edited feature".format(type_id))
    feature = edit.Object
    cad.require(feature.isDerivedFrom(type_id), "Expected {} in native edit, received {}".format(type_id, feature.TypeId))
    dialog = Gui.Control.activeTaskDialog(Gui.getDocument(doc.Name))
    if dialog is None:
        raise AssertionError("Native feature edit must expose its actual task dialog; state=" +
                             json.dumps(_native_state(controller, doc), default=str))
    other_tasks = [name for name in App.listDocuments() if name != doc.Name
                   and Gui.Control.activeTaskDialog(Gui.getDocument(name)) is not None]
    cad.require(not other_tasks, "Native feature task must belong only to {}: other tasks {}".format(doc.Name, other_tasks))
    cad.require(doc.HasPendingTransaction, "Native feature edit must own a transaction so Cancel can roll back")
    return feature, dialog


def _timeline_edit(controller, feature, settle):
    # Prime an actual item click before the double-click event. QTest's
    # mouseDClick alone omits the first click of a physical double-click.
    item = controller.timeline._items[object_key(feature)]
    controller.timeline.list.scrollToItem(item)
    settle(80)
    viewport = controller.timeline.list.viewport()
    point = controller.timeline.list.visualItemRect(item).center()
    cad.require(controller.timeline.list.itemAt(point) is item, "Feature must occupy the clicked timeline position")
    QtTest.QTest.mouseClick(viewport, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, point)
    settle(35)
    QtTest.QTest.mouseDClick(viewport, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, point)
    settle(240)
    edited, dialog = _edited_feature(feature.Document, feature.TypeId, controller)
    cad.require(edited is feature, "Timeline double-click must edit the existing native feature")
    return dialog


def _press(controller, key, settle, modifiers=QtCore.Qt.NoModifier):
    focus = controller.browser.tree
    cad.require(focus.isVisible(), "Fission Browser must be visible for keyboard modeling")
    controller.main.activateWindow()
    focus.setFocus(QtCore.Qt.OtherFocusReason)
    settle(60)
    cad.require(QtWidgets.QApplication.focusWidget() is focus, "Browser must own the actual keyboard focus")
    QtTest.QTest.keyClick(focus, key, modifiers)
    settle(220)


def _presentation(controller, doc, expected, settle):
    controller.refresh_context()
    controller.browser.refresh()
    controller.timeline.refresh()
    settle(120)
    _workspace(controller, doc)
    cad.require(controller.browser.isVisible() and controller.timeline.isVisible(),
                "Fission Browser and Timeline must remain visible after native task completion")
    timeline = [controller.timeline.list.item(index).data(QtCore.Qt.UserRole)
                for index in range(controller.timeline.list.count())]
    for feature in expected:
        key = object_key(feature)
        cad.require(key in controller.browser._items, "Browser must show native feature " + feature.Name)
        cad.require(key in timeline, "Timeline must show native feature " + feature.Name)
    indices = [timeline.index(object_key(feature)) for feature in expected]
    cad.require(indices == sorted(indices), "Timeline must retain native interactive creation order")
    return [key[1] for key in timeline]


def _finish_task(doc, dialog, settle, accept=True):
    # The native wrapper clicks its actual task button; PartDesign's accept
    # commits the transaction and reject aborts it. No manual commit/abort here.
    (dialog.accept if accept else dialog.reject)()
    settle(250)
    cad.require(Gui.Control.activeTaskDialog() is None, "Native task dialog must close after " + ("OK" if accept else "Cancel"))
    cad.require(Gui.getDocument(doc.Name).getInEdit() is None, "Native task completion must leave edit mode")
    cad.require(not doc.HasPendingTransaction, "Native task completion must resolve its transaction")
    doc.recompute()


def run(controller, settle):
    """Ctrl+N → Sketch → E Pad → Timeline Cancel/OK/Undo → F Fillet/OK."""
    cad.require(not Gui.Control.activeDialog(), "Finish the current native task before the interactive smoke workflow")
    previous_document = App.ActiveDocument.Name if App.ActiveDocument else None
    previous_documents = set(App.listDocuments())
    previous_task_documents = {name for name in previous_documents
                               if Gui.Control.activeTaskDialog(Gui.getDocument(name)) is not None}
    previous_profile = controller.shortcuts.profile.name
    preferences = App.ParamGet("User parameter:BaseApp/Preferences/Mod/PartDesign")
    attachment_preference = preferences.GetBool("NewSketchUseAttachmentDialog", False)
    doc = None
    details = {}
    try:
        controller.shortcuts.apply_profile(DEFAULT_PROFILE)
        _press(controller, QtCore.Qt.Key_N, settle, QtCore.Qt.ControlModifier)
        created = App.ActiveDocument
        cad.require(created is not None and created.Name not in previous_documents, "Ctrl+N must create an actual new design")
        doc = created
        body = Gui.getDocument(doc.Name).activeView().getActiveObject("pdbody")
        cad.require(body is not None and body.isDerivedFrom("PartDesign::Body"), "New Design must activate its native Body")
        cad.require(body.getParentGeoFeatureGroup() is not None, "New Design must place its Body inside a native component")

        # Native SketchWorkflow fast path: one selected base plane and the
        # attachment-dialog preference off. No scripted Sketch object creation.
        origin_planes = [feature for feature in body.Origin.OriginFeatures
                         if feature.isDerivedFrom("App::Plane")]
        xy_planes = [feature for feature in origin_planes
                     if getattr(feature, "Role", "") == "XY_Plane"]
        if not xy_planes:
            xy_planes = [feature for feature in origin_planes
                         if re.fullmatch(r"XY_Plane\d*", feature.Name)]
        cad.require(len(xy_planes) == 1, "New Body must expose one actual XY origin plane; found {}".format(
            [(feature.Name, getattr(feature, "Role", "")) for feature in origin_planes]))
        plane = xy_planes[0]
        preferences.SetBool("NewSketchUseAttachmentDialog", False)
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(doc.Name, plane.Name)
        controller.refresh_context()
        buttons = [button for button in controller.buttons
                   if button.property("fissionCommand") == "Fission_CreateSketch"
                   and button.isVisible() and button.isEnabled()]
        cad.require(len(buttons) == 1, "The real Create Sketch ribbon command must be enabled")
        QtTest.QTest.mouseClick(buttons[0], QtCore.Qt.LeftButton)
        settle(240)
        edit = Gui.getDocument(doc.Name).getInEdit()
        attachment_panel_used = False
        if edit is None:
            attachment = Gui.Control.activeTaskDialog()
            contents = attachment.getDialogContent() if attachment else []
            if any(widget.metaObject().className() == "PartGui::TaskAttacher" for widget in contents):
                # Native SelectionFilter checks the Body's hierarchical path.
                # A direct base-plane selection can open the attachment panel
                # instead of its fast path. Complete that real native workflow.
                sketches = [obj for obj in body.Group if obj.isDerivedFrom("Sketcher::SketchObject")]
                cad.require(len(sketches) == 1, "Attachment panel must own one newly-created native Sketch")
                attached_sketch = sketches[0]
                if not any(reference[0] is plane for reference in attached_sketch.AttachmentSupport):
                    reference_button = _task_widget(attachment, "buttonRef1")
                    if not reference_button.isChecked():
                        QtTest.QTest.mouseClick(reference_button, QtCore.Qt.LeftButton)
                    Gui.Selection.clearSelection()
                    Gui.Selection.addSelection(doc.Name, plane.Name)
                    settle(100)
                cad.require(any(reference[0] is plane for reference in attached_sketch.AttachmentSupport),
                            "Native attachment panel must select the Body's XY plane")
                cad.require(attached_sketch.MapMode != "Deactivated", "Native attachment panel must enable a plane mapping mode")
                attachment.accept()
                settle(320)
                edit = Gui.getDocument(doc.Name).getInEdit()
                attachment_panel_used = True
        if edit is None or not edit.Object.isDerivedFrom("Sketcher::SketchObject"):
            raise AssertionError("Create Sketch on selected XY plane must open native Sketcher editing; state=" +
                                 json.dumps(_native_state(controller, doc), default=str))
        sketch = edit.Object
        cad.require(controller.context() == "sketch", "Native sketch edit must activate Fission sketch context")
        cad.require(any(reference[0] is plane for reference in sketch.AttachmentSupport),
                    "Native sketch must be attached to the selected XY plane")
        cad.constrained_rectangle(sketch, 60.0, 40.0)
        doc.recompute()
        settle(120)
        cad.require(sketch.DoF == 0 and sketch.solve() == 0, "Rectangle entered during native sketch edit must be fully constrained")

        _press(controller, QtCore.Qt.Key_E, settle)
        pad, dialog = _edited_feature(doc, "PartDesign::Pad", controller)
        cad.require(pad.Profile[0] is sketch, "E must finish the sketch and use it as the actual Pad profile")
        _set_quantity(dialog, "lengthEdit", 7.0, settle)
        cad.require(abs(float(pad.Length) - 7.0) < 1e-7, "Native Pad task widget must update its live Length")
        length_widget = _set_quantity(dialog, "lengthEdit", 10.0, settle)
        preview = cad.shape_signature(pad.Shape)
        cad.require(preview["valid"] and abs(preview["volume"] - 24000.0) < 1e-5,
                    "E must produce a valid native 60 × 40 × 10 Pad preview before OK")
        _finish_task(doc, dialog, settle)
        cad.require(body.Tip is pad, "Pad OK must advance the actual Body tip")
        pad_shape = cad.shape_signature(body.Shape)
        cad.require(pad_shape["valid"] and abs(pad_shape["volume"] - 24000.0) < 1e-5,
                    "Pad OK must commit the expected solid geometry")
        timeline = _presentation(controller, doc, [sketch, pad], settle)
        details["pad"] = {"native_key": "E", "length_mm": float(pad.Length),
                          "widget": length_widget, "preview": preview,
                          "committed": pad_shape, "timeline": timeline}

        before_names = {obj.Name for obj in doc.Objects}
        undo_before = doc.UndoCount
        dialog = _timeline_edit(controller, pad, settle)
        _set_quantity(dialog, "lengthEdit", 16.0, settle)
        cad.require(abs(float(pad.Length) - 16.0) < 1e-7, "History edit must modify the actual preview Length")
        changed = cad.shape_signature(pad.Shape)
        cad.require(changed["valid"] and abs(changed["volume"] - 38400.0) < 1e-5,
                    "History edit must produce changed native geometry before Cancel")
        _finish_task(doc, dialog, settle, accept=False)
        cad.require(abs(float(pad.Length) - 10.0) < 1e-7, "Native Cancel must restore the original Pad Length")
        cad.require({obj.Name for obj in doc.Objects} == before_names, "Cancel must preserve the original native object graph")
        cad.require(doc.UndoCount == undo_before, "Cancel must not add a committed history edit")
        cad.compare_shapes(pad_shape, cad.shape_signature(body.Shape))
        _presentation(controller, doc, [sketch, pad], settle)
        details["cancel"] = {"timeline_double_click": True, "preview_volume": changed["volume"],
                             "restored_length_mm": float(pad.Length), "undo_count_unchanged": True,
                             "geometry_restored": True}

        # Accept an edit to the same existing feature, then undo through a real
        # Ctrl+Z event. This checks commit independently from Cancel rollback.
        body_group = [obj.Name for obj in body.Group]
        dialog = _timeline_edit(controller, pad, settle)
        _set_quantity(dialog, "lengthEdit", 12.0, settle)
        cad.require(abs(float(pad.Length) - 12.0) < 1e-7, "Timeline OK preview must modify the existing Pad Length")
        accepted_preview = cad.shape_signature(pad.Shape)
        cad.require(accepted_preview["valid"] and abs(accepted_preview["volume"] - 28800.0) < 1e-5,
                    "Timeline OK must preview the expected 60 × 40 × 12 solid")
        _finish_task(doc, dialog, settle)
        cad.require(body.Tip is pad and abs(float(pad.Length) - 12.0) < 1e-7,
                    "Timeline OK must retain the existing Body tip with the committed Length")
        cad.require({obj.Name for obj in doc.Objects} == before_names
                    and [obj.Name for obj in body.Group] == body_group,
                    "Timeline OK must preserve the native object graph")
        cad.require(doc.UndoCount == undo_before + 1, "Timeline OK must commit exactly one native undo step")
        cad.compare_shapes(accepted_preview, cad.shape_signature(body.Shape))
        _presentation(controller, doc, [sketch, pad], settle)
        _press(controller, QtCore.Qt.Key_Z, settle, QtCore.Qt.ControlModifier)
        cad.require(abs(float(pad.Length) - 10.0) < 1e-7, "Ctrl+Z must undo the accepted native Pad edit")
        cad.require(doc.UndoCount == undo_before, "Ctrl+Z must restore the previous native undo count")
        cad.require({obj.Name for obj in doc.Objects} == before_names
                    and [obj.Name for obj in body.Group] == body_group and body.Tip is pad,
                    "Ctrl+Z must retain the existing native object graph and Body tip")
        cad.compare_shapes(pad_shape, cad.shape_signature(body.Shape))
        _presentation(controller, doc, [sketch, pad], settle)
        details["edit_ok"] = {"timeline_double_click": True, "committed_length_mm": 12.0,
                              "committed_volume": accepted_preview["volume"], "one_undo_step": True,
                              "undo_key": "Ctrl+Z", "restored_length_mm": float(pad.Length),
                              "graph_preserved": True, "geometry_restored": True,
                              "workbench": Gui.activeWorkbench().name(), "task_document": doc.Name}

        edges = ["Edge{}".format(index + 1) for index, edge in enumerate(pad.Shape.Edges)
                 if edge.BoundBox.ZLength > 9.9 and edge.BoundBox.XLength < 1e-6
                 and edge.BoundBox.YLength < 1e-6]
        cad.require(len(edges) == 4, "Committed Pad must expose four real vertical edges")
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(doc.Name, pad.Name, edges[0])
        settle(70)
        selected = Gui.Selection.getSelectionEx()
        cad.require(len(selected) == 1 and selected[0].Object is pad and list(selected[0].SubElementNames) == [edges[0]],
                    "Fillet input must be a real selected Pad edge")
        _press(controller, QtCore.Qt.Key_F, settle)
        fillet, dialog = _edited_feature(doc, "PartDesign::Fillet", controller)
        cad.require(fillet.Base[0] is pad and edges[0] in fillet.Base[1], "F must use the selected native Pad edge")
        radius_widget = _set_quantity(dialog, "filletRadius", 1.5, settle)
        fillet_preview = cad.shape_signature(fillet.Shape)
        cad.require(fillet_preview["valid"] and 0 < fillet_preview["volume"] < pad_shape["volume"],
                    "F must create a valid edge Fillet preview with changed geometry")
        _finish_task(doc, dialog, settle)
        cad.require(body.Tip is fillet, "Fillet OK must advance the native Body tip")
        final = cad.shape_signature(body.Shape)
        cad.require(final["valid"] and final["solids"] == 1 and 0 < final["volume"] < pad_shape["volume"],
                    "Fillet OK must commit a valid modified solid")
        cad.compare_shapes(fillet_preview, final)
        timeline = _presentation(controller, doc, [sketch, pad, fillet], settle)
        details["fillet"] = {"native_key": "F", "edge": edges[0], "radius_mm": float(fillet.Radius),
                             "widget": radius_widget, "preview": fillet_preview,
                             "committed": final, "timeline": timeline}
        details["document"] = doc.Name
        details["new_design_key"] = "Ctrl+N"
        details["sketch_plane"] = plane.Name
        details["native_attachment_panel"] = attachment_panel_used
        details["sketch_dof"] = sketch.DoF
        return details
    finally:
        preferences.SetBool("NewSketchUseAttachmentDialog", attachment_preference)
        # Resolve only this case's unfinished task. Cleanup does not convert a
        # failed assertion into a successful feature commit.
        if doc is not None and App.getDocument(doc.Name) is not None:
            try:
                App.setActiveDocument(doc.Name)
                # A failed native ownership transition may have attached our
                # newly-opened task to an older document. Resolve tasks created
                # by this serial case before deleting their feature document;
                # preserve every task that already existed when the case began.
                for name in list(App.listDocuments()):
                    if name not in previous_task_documents:
                        dialog = Gui.Control.activeTaskDialog(Gui.getDocument(name))
                        if dialog is not None:
                            dialog.reject()
                            settle(120)
                gui_doc = Gui.getDocument(doc.Name)
                if gui_doc.getInEdit():
                    gui_doc.resetEdit()
                if doc.HasPendingTransaction:
                    doc.abortTransaction()
            finally:
                App.closeDocument(doc.Name)
        if previous_document and previous_document in App.listDocuments():
            App.setActiveDocument(previous_document)
        controller.shortcuts.apply_profile(previous_profile)
        controller.refresh_context()
        controller.browser.refresh()
        controller.timeline.refresh()
        settle(120)
