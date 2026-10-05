# SPDX-License-Identifier: LGPL-2.1-or-later
"""Native compass-menu acceptance case, called by the serial GUI harness.

``run(controller, settle, output)`` sends actual Qt mouse/key events. It never
replaces command dispatch, popup handlers, task dialogs, or CAD geometry with
spies. Only the initial constrained Sketch/Pad fixture is created by Python;
Fillet creation, preview, Cancel, OK and Undo use the real native commands.
"""

import importlib
import json
import math
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

try:
    from PySide import QtTest
except ImportError:
    try:
        QtTest = importlib.import_module("PySide6.QtTest")
    except ImportError:
        QtTest = importlib.import_module("PySide2.QtTest")

import cad_workflows as cad
from interactive_workflow import _edited_feature, _finish_task, _presentation, _set_quantity, _workspace
from fission.marking_config import defaults, normalize_config, write_config
from fission.selection import active_canvas
from fission.shortcuts import CLASSIC_PROFILE, CUSTOM_PROFILE, DEFAULT_PROFILE


def _camera(view):
    node = view.getCameraNode()
    return {"position": list(node.position.getValue().getValue()),
            "orientation": list(view.getCameraOrientation().Q),
            "height": float(node.height.getValue())}


def _different(left, right, tolerance=1e-6):
    return any(abs(a - b) > tolerance for a, b in zip(left, right))


def _same_camera(before, after):
    cad.require(not _different(before["position"], after["position"]), "Menu interaction must preserve camera position")
    cad.require(not _different(before["orientation"], after["orientation"]), "Menu interaction must preserve camera orientation")
    cad.require(abs(before["height"] - after["height"]) < 1e-6, "Menu interaction must preserve camera zoom")


def _snapshot(doc, body, view):
    return {"objects": sorted((obj.Name, obj.TypeId) for obj in doc.Objects),
            "undo": doc.UndoCount, "tip": body.Tip.Name, "shape": cad.shape_signature(body.Shape),
            "camera": _camera(view)}


def _unchanged(before, doc, body, view, camera=True):
    after = _snapshot(doc, body, view)
    cad.require(before["objects"] == after["objects"], "Cancelled/disabled menu operation must preserve the native object graph")
    cad.require(before["undo"] == after["undo"], "Cancelled/disabled menu operation must not add an Undo step")
    cad.require(before["tip"] == after["tip"], "Cancelled/disabled menu operation must preserve Body.Tip")
    cad.compare_shapes(before["shape"], after["shape"])
    cad.require(not doc.HasPendingTransaction and Gui.getDocument(doc.Name).getInEdit() is None,
                "Cancelled/disabled menu operation must leave no native edit or pending transaction")
    cad.require(Gui.Control.activeTaskDialog() is None, "Cancelled/disabled menu operation must leave no feature task")
    if camera:
        _same_camera(before["camera"], after["camera"])
    return after


def _focus(controller, widget, settle):
    # Quarter is a native QGraphicsView with StrongFocus; its GL viewport can
    # delegate keyboard focus to that view. Activate the owning MDI subwindow
    # rather than assuming setFocus on a viewport equals QApplication.focusWidget.
    ancestor = widget
    subwindow = None
    while ancestor is not None:
        if isinstance(ancestor, QtWidgets.QMdiSubWindow):
            subwindow = ancestor
            break
        ancestor = ancestor.parentWidget()
    if subwindow is not None:
        area = subwindow.mdiArea()
        if area is not None:
            area.setActiveSubWindow(subwindow)
        subwindow.show()
        subwindow.raise_()
    controller.main.raise_()
    controller.main.activateWindow()
    settle(60)
    view, viewport = active_canvas()
    target = view.graphicsView() if widget is viewport else widget
    seen = set()
    while target.focusProxy() is not None and id(target) not in seen:
        seen.add(id(target))
        target = target.focusProxy()
    target.setFocus(QtCore.Qt.OtherFocusReason)
    settle(60)
    focus = QtWidgets.QApplication.focusWidget()
    if focus is not target:
        def describe(value):
            if value is None:
                return None
            proxy = value.focusProxy()
            return {"class": value.metaObject().className(), "name": value.objectName(),
                    "visible": value.isVisible(), "enabled": value.isEnabled(),
                    "focus_policy": str(value.focusPolicy()), "window_active": value.window().isActiveWindow(),
                    "proxy_class": proxy.metaObject().className() if proxy is not None else None}
        area = controller.main.findChild(QtWidgets.QMdiArea)
        active_subwindow = area.activeSubWindow() if area is not None else None
        state = {"requested": describe(widget), "focus_target": describe(target), "actual_focus": describe(focus),
                 "active_window": describe(QtWidgets.QApplication.activeWindow()),
                 "native_view": describe(view.graphicsView()) if view is not None else None,
                 "native_viewport": describe(viewport), "active_mdi": describe(active_subwindow),
                 "intended_mdi": describe(subwindow),
                 "app_document": App.ActiveDocument.Name if App.ActiveDocument else None,
                 "gui_document": Gui.activeDocument().Document.Name if Gui.activeDocument() else None}
        raise AssertionError("Actual keyboard focus must belong to the native canvas/editor; state=" + json.dumps(state))


def _close_native_popup(settle):
    popup = QtWidgets.QApplication.activePopupWidget()
    if popup is not None:
        cad.require(isinstance(popup, QtWidgets.QMenu), "Fallback popup must be a native Qt context menu")
        QtTest.QTest.keyClick(popup, QtCore.Qt.Key_Escape)
        settle(80)
    cad.require(QtWidgets.QApplication.activePopupWidget() is None, "Native context menu must close on Escape")


def _open_chord(controller, viewport, settle, release=True):
    _focus(controller, viewport, settle)
    start = viewport.rect().center()
    QtTest.QTest.mousePress(viewport, QtCore.Qt.RightButton, QtCore.Qt.AltModifier, start)
    settle(70)
    popup = controller.marking.popup
    cad.require(popup is not None and popup.isVisible(), "Actual Alt+right-button press must open the compass popup")
    cad.require(popup.objectName() == "FissionMarkingMenu" and QtWidgets.QApplication.activePopupWidget() is popup,
                "Compass popup must own the real native Qt popup grab")
    point = popup.mapFromGlobal(viewport.mapToGlobal(start))
    cad.require(popup.slot(point) is None, "Viewport-center chord must start inside the popup's dead zone")
    if release:
        QtTest.QTest.mouseRelease(popup, QtCore.Qt.RightButton, QtCore.Qt.AltModifier, point)
        settle(70)
        cad.require(controller.marking.popup is popup and popup.isVisible(),
                    "Alt+right-click center release must keep the compass open")
        cad.require(not controller.marking.gesture, "Center release must clear the right-button gesture latch")
    return popup


def _wedge(popup, index):
    angle = math.radians(index * 45)
    return QtCore.QPoint(round(popup.CENTER + 107 * math.sin(angle)),
                        round(popup.CENTER - 107 * math.cos(angle)))


def _drag_command(controller, viewport, command, settle):
    popup = _open_chord(controller, viewport, settle, release=False)
    matches = [index for index, entry in enumerate(popup.entries) if entry["id"] == command]
    cad.require(len(matches) == 1 and popup.entries[matches[0]]["enabled"],
                "Selected geometry must enable one actual compass command: " + command)
    point = _wedge(popup, matches[0])
    move = QtGui.QMouseEvent(QtCore.QEvent.MouseMove, QtCore.QPointF(point),
                            QtCore.QPointF(popup.mapToGlobal(point)), QtCore.Qt.NoButton,
                            QtCore.Qt.RightButton, QtCore.Qt.AltModifier)
    QtWidgets.QApplication.sendEvent(popup, move)
    cad.require(popup.hover == matches[0], "Actual held-button mouse motion must highlight the selected compass wedge")
    QtTest.QTest.mouseRelease(popup, QtCore.Qt.RightButton, QtCore.Qt.AltModifier, point)
    settle(240)
    cad.require(controller.marking.popup is None and not controller.marking.gesture,
                "Wedge release must close the popup before dispatching its native command")


def _capture(controller, doc, body, view, popup, output):
    """Composite actual Qt chrome/popup with the engine's OpenGL CAD render."""
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    canvas_file = output / "marking-native-canvas.png"
    image_file = output / "marking-native-popup.png"
    viewport = view.graphicsView().viewport()
    saved_camera = view.getCamera()
    try:
        # Native offscreen export needs explicit clip distances. Preserve the
        # focal point and restore the live camera before returning to gestures.
        node = view.getCameraNode()
        span = max(body.Shape.BoundBox.DiagonalLength, 1.0)
        direction = view.getCameraOrientation().multVec(App.Vector(0, 0, 1))
        position = App.Vector(*node.position.getValue().getValue())
        focal = position - direction * float(node.focalDistance.getValue())
        eye = focal + direction * (span * 2)
        node.position = (eye.x, eye.y, eye.z)
        node.focalDistance = span * 2
        node.nearDistance = span * 0.01
        node.farDistance = span * 4
        view.saveImage(str(canvas_file), viewport.width(), viewport.height(), "Current")
        capture = controller.main.grab()
        painter = QtGui.QPainter(capture)
        painter.drawImage(QtCore.QRect(viewport.mapTo(controller.main, QtCore.QPoint(0, 0)), viewport.size()),
                          QtGui.QImage(str(canvas_file)))
        painter.drawPixmap(controller.main.mapFromGlobal(popup.mapToGlobal(QtCore.QPoint(0, 0))), popup.grab())
        painter.end()
        cad.require(not capture.isNull() and capture.save(str(image_file)), "Native CAD/compass composite must be saved")
        cad.require(canvas_file.is_file() and canvas_file.stat().st_size > 1000, "Native CAD render must contain image data")
        return {"file": str(image_file), "canvas": str(canvas_file), "document": doc.Name,
                "width": capture.width(), "height": capture.height()}
    finally:
        view.setCamera(saved_camera)


def run(controller, settle, output):
    """Real compass gestures → native Fillet Cancel/OK/Undo, with UI guards."""
    cad.require(not Gui.Control.activeDialog(), "Finish the current native task before the marking-menu case")
    previous_document = App.ActiveDocument.Name if App.ActiveDocument else None
    previous_workspace = controller._workspace_name
    previous_tab = controller._tab
    previous_profile = controller.shortcuts.profile.export_data()
    previous_config = controller.settings.GetString("MarkingMenu", "")
    previous_navigation = controller.settings.GetString("Navigation", "Gui::FissionNavigationStyle")
    previous_filter = controller.browser.filter.text()
    doc = None
    details = {}
    try:
        controller.switch_workspace("Design")
        settle(160)
        for index in range(controller.tabs.count()):
            if controller.tabs.tabText(index) == "SOLID":
                controller.tabs.setCurrentIndex(index)
                break
        controller.settings.SetString("Navigation", "Gui::FissionNavigationStyle")
        controller.shortcuts.apply_profile(DEFAULT_PROFILE)
        controller.browser.filter.clear()
        doc = App.newDocument("FissionMarkingWorkflow")
        doc.UndoMode = 1
        doc.openTransaction("Compass workflow fixture")
        body = doc.addObject("PartDesign::Body", "Body")
        sketch = body.newObject("Sketcher::SketchObject", "BaseSketch")
        cad.constrained_rectangle(sketch, 30.0, 20.0)
        pad = body.newObject("PartDesign::Pad", "Pad")
        pad.Profile = sketch
        pad.Length = 10.0
        doc.recompute()
        body.Tip = pad
        doc.commitTransaction()
        sketch.Visibility = False
        body.Visibility = pad.Visibility = True
        view, viewport = active_canvas()
        cad.require(view is not None and viewport is not None, "Compass workflow must have an actual native CAD canvas")
        view.setActiveObject("part", None)
        view.setActiveObject("pdbody", body)
        view.setCameraType("Orthographic")
        view.viewAxonometric()
        view.fitAll()
        controller.refresh_context()
        settle(180)
        _workspace(controller, doc)
        cad.require(controller.context() == "model" and view.getNavigationType() == "Gui::FissionNavigationStyle",
                    "Compass fixture must use native Fission model navigation")
        cad.require(sketch.DoF == 0 and body.Shape.isValid() and abs(body.Shape.Volume - 6000.0) < 1e-6,
                    "Compass input must be a real constrained, valid native Sketch/Pad solid")
        _presentation(controller, doc, [sketch, pad], settle)

        config = normalize_config({})
        config["slots"]["model"] = defaults("model")
        config["slots"]["model"][0] = "Missing_Marking_Test_Command"
        config["slots"]["model"][1] = ""
        write_config(controller.settings, config)
        controller.marking.refresh_settings()
        Gui.Selection.clearSelection()
        baseline = _snapshot(doc, body, view)
        popup = _open_chord(controller, viewport, settle)
        cad.require(not popup.entries[0]["enabled"] and popup.entries[0]["id"] == "Missing_Marking_Test_Command",
                    "Unavailable safe command IDs must retain their disabled compass positions")
        cad.require(not popup.entries[1]["enabled"] and popup.entries[1]["id"] == "",
                    "Explicit empty compass positions must stay empty and disabled")
        details["screenshot"] = _capture(controller, doc, body, view, popup, output)
        for index in (0, 1):
            QtTest.QTest.mouseClick(popup, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, _wedge(popup, index))
            settle(70)
            cad.require(controller.marking.popup is popup, "Clicking a disabled/empty compass slot must keep the menu open")
            _unchanged(baseline, doc, body, view)
        QtTest.QTest.keyClick(popup, QtCore.Qt.Key_Escape)
        settle(70)
        cad.require(controller.marking.popup is None, "Escape must close the actual compass popup")
        _unchanged(baseline, doc, body, view)
        popup = _open_chord(controller, viewport, settle)
        QtTest.QTest.mouseClick(popup, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(popup.CENTER, popup.CENTER))
        settle(70)
        cad.require(controller.marking.popup is None, "Left-clicking the compass center must close it")
        _unchanged(baseline, doc, body, view)
        details["cancellation"] = {"alt_right_center_keeps_open": True, "disabled_slot": True,
                                   "empty_slot": True, "escape": True, "center_click": True, "cad_unchanged": True}
        popup = _open_chord(controller, viewport, settle, release=False)
        initial_pointer = viewport.mapToGlobal(viewport.rect().center())
        # A window fitted against a screen edge can shift its center. Reproduce
        # that Qt popup movement while leaving the physical pointer stationary.
        popup.move(popup.pos() - QtCore.QPoint(100, 0))
        QtTest.QTest.mouseRelease(popup, QtCore.Qt.RightButton, QtCore.Qt.AltModifier,
                                 popup.mapFromGlobal(initial_pointer))
        settle(80)
        cad.require(controller.marking.popup is popup, "A stationary click must not choose a sector after popup fitting")
        _unchanged(baseline, doc, body, view)
        QtTest.QTest.keyClick(popup, QtCore.Qt.Key_Escape)
        settle(80)
        details["cancellation"]["screen_fitting_click_guard"] = True

        # The binding is assigned through the actual persisted Custom profile.
        shortcut, key = next((value, key) for value, key in (("Ctrl+Alt+M", QtCore.Qt.Key_M),
                                                            ("Ctrl+Alt+F9", QtCore.Qt.Key_F9))
                             if not controller.shortcuts.profile.conflicts("Fission_MarkingMenu", value))
        modifiers = QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier
        controller.shortcuts.set_binding("Fission_MarkingMenu", shortcut)
        _focus(controller, viewport, settle)
        QtTest.QTest.keyClick(viewport, key, modifiers)
        settle(100)
        popup = controller.marking.popup
        cad.require(popup is not None, "Assigned native menu shortcut must open the compass on the canvas")
        QtTest.QTest.keyClick(popup, QtCore.Qt.Key_Escape)
        settle(70)
        field = controller.browser.filter
        _focus(controller, field, settle)
        QtTest.QTest.keyClicks(field, "efsm")
        cad.require(field.text() == "efsm", "CAD letters must remain normal editor text: " + repr(field.text()))
        QtTest.QTest.keyClick(field, key, modifiers)
        settle(100)
        # Ctrl+Alt is also AltGr on some Windows keyboard layouts. Qt may insert
        # native editor text for this chord; the CAD binding must stay inactive.
        cad.require(controller.marking.popup is None,
                    "Custom menu key must preserve native editor handling and suppress CAD commands")
        _unchanged(baseline, doc, body, view)
        field.clear()
        controller.shortcuts.apply_profile(CLASSIC_PROFILE)
        _focus(controller, viewport, settle)
        QtTest.QTest.keyClick(viewport, key, modifiers)
        QtTest.QTest.mouseClick(viewport, QtCore.Qt.RightButton, QtCore.Qt.AltModifier, viewport.rect().center())
        settle(100)
        cad.require(controller.marking.popup is None, "FreeCAD Classic must suppress both the Fission menu key and Alt+RMB chord")
        _close_native_popup(settle)
        _unchanged(baseline, doc, body, view)
        controller.shortcuts.apply_profile(DEFAULT_PROFILE)
        config["enabled"] = False
        write_config(controller.settings, config)
        controller.marking.refresh_settings()
        QtTest.QTest.mouseClick(viewport, QtCore.Qt.RightButton, QtCore.Qt.AltModifier, viewport.rect().center())
        settle(100)
        cad.require(controller.marking.popup is None, "Persisted disabled-menu setting must suppress the Alt+RMB chord")
        _close_native_popup(settle)
        _unchanged(baseline, doc, body, view)
        config["enabled"] = True
        write_config(controller.settings, config)
        controller.marking.refresh_settings()
        controller.shortcuts.apply_profile(CUSTOM_PROFILE)
        details["guards"] = {"custom_shortcut": shortcut, "typing": True, "classic_key_and_chord": True, "disabled_setting": True}

        _focus(controller, viewport, settle)
        QtTest.QTest.mouseClick(viewport, QtCore.Qt.RightButton, QtCore.Qt.NoModifier, viewport.rect().center())
        settle(100)
        native_menu = QtWidgets.QApplication.activePopupWidget()
        cad.require(controller.marking.popup is None and isinstance(native_menu, QtWidgets.QMenu),
                    "Ordinary right-click must open the engine's native Qt context menu")
        actions = [action.text() for action in native_menu.actions() if not action.isSeparator()]
        cad.require(actions, "Native right-click menu must expose actual actions")
        _close_native_popup(settle)
        _unchanged(baseline, doc, body, view)
        before_pan = _camera(view)
        start = viewport.rect().center() + QtCore.QPoint(45, 25)
        QtTest.QTest.mousePress(viewport, QtCore.Qt.MiddleButton, QtCore.Qt.NoModifier, start)
        for delta in (QtCore.QPoint(8, 5), QtCore.QPoint(28, 20), QtCore.QPoint(65, 42)):
            point = start + delta
            move = QtGui.QMouseEvent(QtCore.QEvent.MouseMove, QtCore.QPointF(point),
                                    QtCore.QPointF(viewport.mapToGlobal(point)), QtCore.Qt.NoButton,
                                    QtCore.Qt.MiddleButton, QtCore.Qt.NoModifier)
            QtWidgets.QApplication.sendEvent(viewport, move)
            settle(20)
        QtTest.QTest.mouseRelease(viewport, QtCore.Qt.MiddleButton, QtCore.Qt.NoModifier, start + QtCore.QPoint(65, 42))
        settle(100)
        after_pan = _camera(view)
        cad.require(_different(before_pan["position"], after_pan["position"]), "MMB must still pan after menu cancellation/native RMB")
        cad.require(not _different(before_pan["orientation"], after_pan["orientation"])
                    and abs(before_pan["height"] - after_pan["height"]) < 1e-6,
                    "MMB after a popup must retain native pan orientation/zoom semantics")
        _unchanged(baseline, doc, body, view, camera=False)
        details["navigation"] = {"native_context_actions": actions, "rmb_camera_preserved": True,
                                 "mmb_before": before_pan, "mmb_after": after_pan}

        edges = ["Edge{}".format(index + 1) for index, edge in enumerate(pad.Shape.Edges)
                 if edge.BoundBox.ZLength > 9.9 and edge.BoundBox.XLength < 1e-6 and edge.BoundBox.YLength < 1e-6]
        cad.require(len(edges) == 4, "Native fixture Pad must expose four selectable vertical edges")
        feature_baseline = _snapshot(doc, body, view)
        for accept in (False, True):
            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(doc.Name, pad.Name, edges[0])
            settle(70)
            _drag_command(controller, viewport, "Fission_Fillet", settle)
            fillet, dialog = _edited_feature(doc, "PartDesign::Fillet", controller)
            cad.require(fillet.Base[0] is pad and edges[0] in fillet.Base[1],
                        "Compass Fillet must use the actual selected native Pad edge")
            widget = _set_quantity(dialog, "filletRadius", 1.5, settle)
            preview = cad.shape_signature(fillet.Shape)
            cad.require(preview["valid"] and preview["solids"] == 1 and 0 < preview["volume"] < feature_baseline["shape"]["volume"],
                        "Compass command must create a real valid Fillet preview")
            cad.require(controller.marking.popup is None and not controller.marking.available(),
                        "Native non-sketch feature task must suppress compass invocation")
            _focus(controller, viewport, settle)
            QtTest.QTest.keyClick(viewport, key, modifiers)
            QtTest.QTest.mouseClick(viewport, QtCore.Qt.RightButton, QtCore.Qt.AltModifier, viewport.rect().center())
            settle(80)
            cad.require(controller.marking.popup is None, "Actual menu key and Alt+RMB must stay inactive during a native Fillet task")
            _close_native_popup(settle)
            cad.require(Gui.getDocument(doc.Name).getInEdit().Object is fillet and doc.HasPendingTransaction,
                        "Rejected compass invocation must retain the actual native Fillet task and its transaction")
            cad.compare_shapes(preview, cad.shape_signature(fillet.Shape))
            _finish_task(doc, dialog, settle, accept=accept)
            if not accept:
                _unchanged(feature_baseline, doc, body, view, camera=False)
                details["fillet_cancel"] = {"edge": edges[0], "preview": preview, "graph_and_undo_restored": True}
            else:
                cad.require(body.Tip is fillet and doc.UndoCount == feature_baseline["undo"] + 1,
                            "Compass Fillet OK must commit exactly one native Undo step and advance Body.Tip")
                committed = cad.shape_signature(body.Shape)
                cad.compare_shapes(preview, committed)
                timeline = _presentation(controller, doc, [sketch, pad, fillet], settle)
                details["fillet_ok"] = {"edge": edges[0], "radius_mm": float(fillet.Radius), "widget": widget,
                                        "shape": committed, "timeline": timeline, "one_undo_step": True}
        _focus(controller, viewport, settle)
        QtTest.QTest.keyClick(viewport, QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)
        settle(240)
        doc.recompute()
        _unchanged(feature_baseline, doc, body, view, camera=False)
        _presentation(controller, doc, [sketch, pad], settle)
        details["undo"] = {"key": "Ctrl+Z", "original_pad_restored": True, "fillet_removed": True}
        details["guards"]["native_feature_task_key_and_chord"] = True
        details["document"] = doc.Name
        details["workbench"] = Gui.activeWorkbench().name()
        return details
    finally:
        if controller.marking.gesture:
            # Resolve a physical held-button event even if an assertion failed
            # between the initial press and its release. Do not alter the menu
            # handler's internal state or dispatch any CAD command in cleanup.
            popup = controller.marking.popup
            target = popup if popup is not None else controller.main
            point = QtCore.QPoint(popup.CENTER, popup.CENTER) if popup is not None else QtCore.QPoint(0, 0)
            QtTest.QTest.mouseRelease(target, QtCore.Qt.RightButton, QtCore.Qt.AltModifier, point)
        controller.marking.close()
        _close_native_popup(settle)
        if doc is not None and doc.Name in App.listDocuments():
            try:
                App.setActiveDocument(doc.Name)
                dialog = Gui.Control.activeTaskDialog(Gui.getDocument(doc.Name))
                if dialog is not None:
                    dialog.reject()
                    settle(120)
                gui_doc = Gui.getDocument(doc.Name)
                if gui_doc.getInEdit() is not None:
                    gui_doc.resetEdit()
                if doc.HasPendingTransaction:
                    doc.abortTransaction()
            finally:
                App.closeDocument(doc.Name)
        controller.settings.SetString("MarkingMenu", previous_config)
        controller.settings.SetString("Navigation", previous_navigation)
        controller.marking.refresh_settings()
        controller.shortcuts.profile.import_data(previous_profile)
        controller.shortcuts.apply_profile(controller.shortcuts.profile.name)
        if previous_document and previous_document in App.listDocuments():
            App.setActiveDocument(previous_document)
        controller.switch_workspace(previous_workspace)
        for index in range(controller.tabs.count()):
            if controller.tabs.tabText(index) == previous_tab:
                controller.tabs.setCurrentIndex(index)
                break
        controller.browser.filter.setText(previous_filter)
        controller.refresh_context()
        controller.browser.refresh()
        controller.timeline.refresh()
        settle(120)
