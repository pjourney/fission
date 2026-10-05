# SPDX-License-Identifier: LGPL-2.1-or-later
"""Actual canvas gestures through native rectangle, freehand and ray-pick selection."""
import importlib
import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore, QtGui
try:
    from PySide import QtTest
except ImportError:
    QtTest = importlib.import_module("PySide6.QtTest")
from cad_workflows import require
from fission.history import object_key
from fission.selection import can_select
from fission.shortcuts import DEFAULT_PROFILE


def run(controller, settle, output):
    Gui.activateWorkbench("FissionWorkbench")
    settle()
    controller.shortcuts.apply_profile(DEFAULT_PROFILE)
    doc = App.newDocument("CanvasSelection")
    source = assembly_doc = None
    viewport = None
    try:
        objects = []
        for name, x in (("Left", -30), ("Middle", 0), ("Right", 30)):
            obj = doc.addObject("Part::Feature", name)
            obj.Shape = Part.makeBox(8, 8, 4, App.Vector(x - 4, -4, 0))
            objects.append(obj)
        background = doc.addObject("Part::Feature", "ConcaveRegression")
        background.Shape = Part.makeBox(72, 18, 1, App.Vector(-36, -9, -4))
        doc.recompute()
        view = Gui.activeDocument().activeView()
        view.setCameraType("Orthographic")
        view.viewTop()
        view.fitAll()
        settle()
        viewport = view.graphicsView().viewport()
        ratio = viewport.devicePixelRatioF()
        def screen(vector):
            x, y = view.getPointOnScreen(vector)
            return QtCore.QPoint(round(x / ratio), round((view.getSize()[1] - 1 - y) / ratio))
        points = [screen(obj.Shape.BoundBox.Center) for obj in objects]
        def names():
            return sorted(obj.Name for obj in Gui.Selection.getSelection())
        def key(number):
            controller.main.activateWindow()
            viewport.setFocus()
            QtTest.QTest.keyClick(viewport, getattr(QtCore.Qt, "Key_" + str(number)))
            settle(80)
        def drag(points, modifiers=QtCore.Qt.NoModifier):
            QtTest.QTest.mousePress(viewport, QtCore.Qt.LeftButton, modifiers, points[0])
            for point in points[1:]:
                event = QtGui.QMouseEvent(QtCore.QEvent.MouseMove, QtCore.QPointF(point),
                    QtCore.QPointF(viewport.mapToGlobal(point)), QtCore.Qt.NoButton,
                    QtCore.Qt.LeftButton, modifiers)
                QtCore.QCoreApplication.sendEvent(viewport, event)
                settle(15)
            QtTest.QTest.mouseRelease(viewport, QtCore.Qt.LeftButton, modifiers, points[-1])
            settle(100)
        # Box selection tests engine readiness as well as real keyboard dispatch.
        a, b, c = points
        Gui.Selection.clearSelection()
        key(1)
        require(not Gui.Command.get("Std_BoxSelection").isActive(), "One native handler must own the viewport")
        require(not Gui.Command.get("Std_FreehandSelection").isActive(), "Freehand must not replace a live rectangle handler")
        drag([a - QtCore.QPoint(22, 22), a + QtCore.QPoint(22, 22)])
        require(names() == ["Left"], "Rectangle must select the enclosed object's projected center: " + str(names()))
        require(Gui.Command.get("Std_FreehandSelection").isActive(), "Completed selection must restore native picking")
        key(1)
        drag([c - QtCore.QPoint(22, 22), c + QtCore.QPoint(22, 22)], QtCore.Qt.ControlModifier)
        require(names() == ["Left", "Right"], "Ctrl rectangle must add")
        key(2)
        QtTest.QTest.keyClick(viewport, QtCore.Qt.Key_Escape)
        settle(100)
        require(names() == ["Left", "Right"] and Gui.Command.get("Std_BoxSelection").isActive(),
                "Escape must preserve selection and release the native handler")
        # U-shaped outline: large background's opposite bbox corners are inside,
        # but its center and Middle are outside. This catches the rectangle-only fast path.
        margin = max(24, round((b.x() - a.x()) * 0.35))
        y = a.y()
        outline = [QtCore.QPoint(a.x() - margin, y - margin), QtCore.QPoint(c.x() + margin, y - margin),
                   QtCore.QPoint(c.x() + margin, y + margin), QtCore.QPoint(c.x() - margin, y + margin),
                   QtCore.QPoint(c.x() - margin, y - margin // 3), QtCore.QPoint(a.x() + margin, y - margin // 3),
                   QtCore.QPoint(a.x() + margin, y + margin), QtCore.QPoint(a.x() - margin, y + margin),
                   QtCore.QPoint(a.x() - margin, y - margin)]
        def inside(point):
            result = False
            for left, right in zip(outline, outline[1:]):
                if (left.y() > point.y()) != (right.y() > point.y()):
                    crossing = left.x() + (point.y() - left.y()) * (right.x() - left.x()) / (right.y() - left.y())
                    if point.x() < crossing:
                        result = not result
            return result
        bounds = background.Shape.BoundBox
        corners = [screen(App.Vector(bounds.XMin, bounds.YMin, bounds.ZMin)),
                   screen(App.Vector(bounds.XMax, bounds.YMax, bounds.ZMax))]
        require(all(inside(point) for point in corners) and not inside(b),
                "Concave fixture must contain opposite bbox corners and exclude the center")
        Gui.Selection.clearSelection()
        key(2)
        drag(outline)
        require(names() == ["Left", "Right"], "Concave freeform must exclude centers in the notch: " + str(names()))
        background.Visibility = False
        settle()
        before = [(obj.Name, obj.Shape.Volume, len(obj.Shape.Faces)) for obj in doc.Objects]
        Gui.Selection.clearSelection()
        key(3)
        require(controller.paint.viewport is viewport, "3 must start the real paint adapter")
        drag([a, b])
        require(names() == ["Left", "Middle"], "Paint must sample actual frontmost objects along the stroke: " + str(names()))
        require(controller.paint.viewport is None, "Release must finish one paint stroke")
        key(3)
        drag([c, c + QtCore.QPoint(2, 0)], QtCore.Qt.ControlModifier)
        require(names() == ["Left", "Middle", "Right"], "Ctrl paint must preserve existing selection")
        key(3)
        QtTest.QTest.mousePress(viewport, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, a)
        require(names() == ["Left"], "New paint stroke must replace the previous selection")
        QtTest.QTest.keyClick(viewport, QtCore.Qt.Key_Escape)
        QtTest.QTest.mouseRelease(viewport, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, a)
        settle()
        require(names() == ["Left", "Middle", "Right"], "Escape during a stroke must restore previous selection")
        class Gate:
            def allow(self, document, obj, sub):
                return obj.Name != "Middle"
        Gui.Selection.addSelectionGate(Gate())
        try:
            key(3)
            drag([a, b])
            require(names() == ["Left"], "Paint must honor an existing native selection gate")
        finally:
            Gui.Selection.removeSelectionGate()
        doc.openTransaction("Selection guard probe")
        try:
            placement = App.Placement(objects[0].Placement)
            placement.Base = placement.Base + App.Vector(0, 0, 1)
            objects[0].Placement = placement
            require(doc.HasPendingTransaction, "Selection guard fixture must allocate a real modeling transaction")
            require(not Gui.Command.get("Fission_PaintSelection").isActive(), "Pending modeling transactions must own selection")
            require(not Gui.Command.get("Fission_FreeformSelection").isActive(), "Freeform must yield to modeling transactions")
        finally:
            doc.abortTransaction()
        settle()
        require(before == [(obj.Name, obj.Shape.Volume, len(obj.Shape.Faces)) for obj in doc.Objects],
                "Selection gestures must preserve real geometry and topology")
        controller.browser.refresh()
        controller.timeline.refresh()
        require(controller.browser._items[object_key(objects[0])].isSelected(), "Native paint selection must reach the Browser")
        require(controller.timeline._items[object_key(objects[0])].isSelected(), "Native paint selection must reach the Timeline")

        # Keep a genuine root-relative linked face selection and an independent
        # selection in its external source document. Escape must restore the
        # original parent/subpath without clearing another document's state.
        source = App.newDocument("CanvasSelectionSources")
        source_box = source.addObject("Part::Box", "LinkedSource")
        source_box.Length, source_box.Width, source_box.Height = 8, 8, 4
        source.recompute()
        source.saveAs(str(output / "native-selection-sources.FCStd"))
        Gui.setActiveDocument(doc.Name)
        App.setActiveDocument(doc.Name)
        container = doc.addObject("App::Part", "SelectionContainer")
        link = doc.addObject("App::Link", "SelectionLink")
        doc.saveAs(str(output / "native-selection-owner.FCStd"))
        link.setLink(source_box)
        container.addObject(link)
        link.Placement = App.Placement(App.Vector(56, -4, 0), App.Rotation())
        doc.recompute()
        view.fitAll()
        settle()
        left_point = screen(objects[0].Shape.BoundBox.Center)
        link_point = screen(App.Vector(60, 0, 2))
        def raw_selection():
            return sorted((item.DocumentName, item.ObjectName, tuple(item.SubElementNames))
                          for item in Gui.Selection.getSelectionEx("*", 0))
        Gui.Selection.clearSelection()
        linked_face = link.Name + ".Face1"
        Gui.Selection.addSelection(doc.Name, container.Name, linked_face)
        Gui.Selection.addSelection(source.Name, source_box.Name)
        original = raw_selection()
        require((doc.Name, container.Name, (linked_face,)) in original,
                "Escape fixture must retain a real parent-relative linked face subpath: " + str(original))
        require((source.Name, source_box.Name, ()) in original,
                "Escape fixture must include another document's independent native selection")
        key(3)
        QtTest.QTest.mousePress(viewport, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, left_point)
        require((source.Name, source_box.Name, ()) in raw_selection(),
                "Paint replacement must preserve another document's selection during the stroke")
        QtTest.QTest.keyClick(viewport, QtCore.Qt.Key_Escape)
        QtTest.QTest.mouseRelease(viewport, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, left_point)
        settle()
        require(raw_selection() == original,
                "Paint Escape must restore exact native parent/link subpaths and other-document selection: "
                + str(raw_selection()))
        key(3)
        drag([link_point, link_point + QtCore.QPoint(2, 0)])
        require(Gui.Selection.getSelection(doc.Name) == [link],
                "Native paint ray picking must select the actual visible link rather than its external source")
        linked_pick = [(item.ObjectName, list(item.SubElementNames))
                       for item in Gui.Selection.getSelectionEx(doc.Name, 0)]
        require(all(not sub or sub.endswith(".") for _, subs in linked_pick for sub in subs),
                "Object paint selection must remove the picked face while retaining the link path: " + str(linked_pick))
        require((source.Name, source_box.Name, ()) in raw_selection(),
                "Completed paint must preserve another document's selection")

        # Native Assembly remains in edit mode while its idle solver panel is
        # visible. That edit mode must still permit all three selection tools.
        assembly_doc = App.newDocument("CanvasSelectionAssembly")
        require(controller.execute("Assembly_CreateAssembly"), "Idle Assembly fixture must use native New Assembly")
        settle(180)
        edit = Gui.getDocument(assembly_doc.Name).getInEdit()
        require(edit is not None and edit.Object.isDerivedFrom("Assembly::AssemblyObject"),
                "Idle Assembly fixture must own a real native Assembly edit mode")
        require(not Gui.Control.activeDialog() and not assembly_doc.HasPendingTransaction,
                "Idle Assembly readiness must be tested outside a task or modeling transaction")
        require(can_select(), "Native idle Assembly edit must permit canvas selection")
        for command in ("Fission_WindowSelection", "Fission_FreeformSelection", "Fission_PaintSelection"):
            require(Gui.Command.get(command).isActive(), "Idle native Assembly must enable " + command)
        assembly_viewport = Gui.getDocument(assembly_doc.Name).activeView().graphicsView().viewport()
        for number in (1, 2):
            assembly_viewport.setFocus()
            QtTest.QTest.keyClick(assembly_viewport, getattr(QtCore.Qt, "Key_" + str(number)))
            settle(80)
            require(not Gui.Command.get("Std_BoxSelection").isActive(),
                    "Idle Assembly key " + str(number) + " must start its actual native selection handler")
            QtTest.QTest.keyClick(assembly_viewport, QtCore.Qt.Key_Escape)
            settle(80)
            require(Gui.Command.get("Std_BoxSelection").isActive(),
                    "Idle Assembly Escape must release its native selection handler")
        assembly_viewport.setFocus()
        QtTest.QTest.keyClick(assembly_viewport, QtCore.Qt.Key_3)
        settle(80)
        require(controller.paint.viewport is assembly_viewport,
                "Idle Assembly key 3 must dispatch and arm its actual viewport")
        controller.paint.cancel(False)
        Gui.getDocument(assembly_doc.Name).resetEdit()
        settle()
        for mode in ("WindowSelection", "FreeformSelection"):
            transient = App.newDocument("ArmedSelectionLifetime")
            settle(100)
            require(controller.execute("Fission_" + mode), "Lifecycle probe must arm the native " + mode)
            require(not Gui.Command.get("Std_BoxSelection").isActive(), "Lifecycle probe must own a live native handler")
            App.closeDocument(transient.Name)
            settle(150)
            Gui.setActiveDocument(doc.Name)
            App.setActiveDocument(doc.Name)
            settle(100)
            require(Gui.Command.get("Std_BoxSelection").isActive(),
                    "Closing an armed native viewer must release shared selection ownership: " + mode)
        return {"native_rectangle": True, "native_concave_freehand": True, "paint_ray_picking": True,
                "ctrl_additive": True, "escape_restored": True, "native_gate": True,
                "geometry_unchanged": True, "linked_escape_parent_subpath": True,
                "other_document_selection_preserved": True, "native_link_picking": linked_pick,
                "idle_native_assembly_selection": True,
                "armed_viewer_close_releases_handler": True,
                "screen_points": [[p.x(), p.y()] for p in points], "dpi_ratio": ratio}
    finally:
        controller.paint.cancel(False)
        # Always release a selector if a failed assertion interrupted a stroke.
        if viewport is not None:
            QtTest.QTest.keyClick(viewport, QtCore.Qt.Key_Escape)
        settle(80)
        Gui.Selection.clearSelection()
        for native in (assembly_doc, doc, source):
            if native is not None and native.Name in App.listDocuments():
                gui_doc = Gui.getDocument(native.Name)
                if gui_doc.getInEdit():
                    gui_doc.resetEdit()
                App.closeDocument(native.Name)
        settle()
