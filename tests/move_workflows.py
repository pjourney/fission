# SPDX-License-Identifier: LGPL-2.1-or-later
"""Move native document placements through actual M and Qt dialog controls."""
from contextlib import contextmanager
import importlib
import math
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
try:
    from PySide import QtTest
except ImportError:
    QtTest = importlib.import_module("PySide6.QtTest")

import cad_workflows as cad
from marking_workflow import _focus
from search_workflows import _design


@contextmanager
def _design_move(controller, settle):
    with _design(controller, settle) as doc:
        try:
            yield doc
        finally:
            dialog = getattr(controller, "move_dialog", None)
            if dialog and dialog.isVisible():
                dialog.reject()
                settle(60)


def _part(doc, name="Component", base=(10, 20, 30), angle=90):
    obj = doc.addObject("App::Part", name)
    obj.Placement = App.Placement(App.Vector(*base), App.Rotation(App.Vector(0, 0, 1), angle))
    return obj


def _box(doc, parent=None, name="Box", base=(4, 0, 0), angle=30):
    obj = doc.addObject("Part::Box", name)
    if parent:
        parent.addObject(obj)
    obj.Length, obj.Width, obj.Height = 10, 8, 6
    obj.Placement = App.Placement(App.Vector(*base), App.Rotation(App.Vector(0, 1, 0), angle))
    doc.recompute()
    return obj


def _vector(actual, expected, message):
    expected = App.Vector(*expected) if isinstance(expected, (tuple, list)) else expected
    cad.require((actual - expected).Length < 1e-6, message + ": actual={}, expected={}".format(actual, expected))


def _pose(actual, expected, message):
    cad.require(actual.isSame(expected, 1e-6), message + ": actual={}, expected={}".format(actual, expected))


def _world_vertices(obj):
    parent = obj.getParentGeoFeatureGroup()
    frame = parent.getGlobalPlacement() if parent else App.Placement()
    return [frame.multVec(vertex.Point) for vertex in obj.Shape.Vertexes]


def _shifted_vertices(obj, original, delta, message):
    shift = App.Vector(*delta)
    def points(values):
        return sorted(tuple(round(value, 6) for value in (point.x, point.y, point.z)) for point in values)
    cad.require(points(_world_vertices(obj)) == points([point + shift for point in original]), message)


def _open(controller, objects, settle):
    Gui.Selection.clearSelection()
    for obj in objects:
        Gui.Selection.addSelection(obj)
    settle(180)
    _focus(controller, controller.browser.tree, settle)
    QtTest.QTest.keyClick(controller.browser.tree, QtCore.Qt.Key_M)
    settle(120)
    dialog = getattr(controller, "move_dialog", None)
    cad.require(dialog is not None and dialog.isVisible()
                and QtWidgets.QApplication.activeModalWidget() is dialog,
                "Actual M must open the modal Move / Copy dialog: " + controller.main.statusBar().currentMessage())
    return dialog


def _values(dialog, settle, translation=None, rotation=None):
    for group, values in (("Translation", translation), ("Rotation", rotation)):
        if values is None:
            continue
        for axis, value in zip("XYZ", values):
            field = dialog.findChild(QtWidgets.QDoubleSpinBox, "Move" + group + axis)
            cad.require(field is not None, "Required actual Move control missing: " + group + axis)
            field.setValue(value)
    settle(100)


def _finish(dialog, settle, accept):
    box = dialog.findChild(QtWidgets.QDialogButtonBox, "MoveButtons")
    button = box.button(QtWidgets.QDialogButtonBox.Ok if accept else QtWidgets.QDialogButtonBox.Cancel)
    QtTest.QTest.mouseClick(button, QtCore.Qt.LeftButton)
    settle(140)
    cad.require(not dialog.isVisible(), "Native Move dialog must close after OK/Cancel: " + dialog.message.text())


def nested_placement(controller, settle, output):
    with _design_move(controller, settle) as doc:
        parent = _part(doc)
        box = _box(doc, parent)
        original = App.Placement(box.Placement)
        before = cad.shape_signature(box.Shape)
        _vector(box.getGlobalPlacement().Base, (10, 24, 30), "Rotated-parent fixture must start at the expected design position")
        undo = doc.UndoCount
        for accept in (False, True):
            dialog = _open(controller, [box], settle)
            cad.require(not doc.HasPendingTransaction and doc.getBookedTransactionID() == 0,
                        "Opening unchanged Move must not book a transaction")
            _values(dialog, settle, (5, -2, 3), (90, 0, 90))
            _vector(box.getGlobalPlacement().Base, (15, 22, 33), "Translation must follow design axes through a rotated parent")
            _vector(box.Placement.Base, (2, -5, 3), "Native child local pose must correctly invert its parent frame")
            _vector(box.getGlobalPlacement().Rotation.multVec(App.Vector(1, 0, 0)),
                    (-0.5, 0, math.sqrt(3) / 2), "X then Z rotation must use design axes around the object's own origin")
            # Native UndoCount includes the active, still abortable transaction.
            cad.require(doc.HasPendingTransaction and doc.UndoCount == undo + 1
                        and doc.getBookedTransactionID() == dialog.transaction_id,
                        "Preview must remain inside one uncommitted native transaction")
            cad.require(abs(box.Shape.Volume - before["volume"]) < 1e-6, "Placement preview must preserve native solid volume")
            if accept:
                Gui.activeDocument().activeView().fitAll()
                settle(100)
                controller.main.grab().save(str(Path(output) / "fission-move-preview.png"))
                dialog.grab().save(str(Path(output) / "fission-move-dialog.png"))
            _finish(dialog, settle, accept)
            if not accept:
                _pose(box.Placement, original, "Cancel must restore the native local pose")
                cad.compare_shapes(before, cad.shape_signature(box.Shape))
                cad.require(doc.UndoCount == undo and doc.getBookedTransactionID() == 0,
                            "Cancel must leave no committed or booked transaction")
        cad.require(doc.UndoCount == undo + 1, "OK must commit one Move Undo entry")
        _focus(controller, controller.browser.tree, settle)
        QtTest.QTest.keyClick(controller.browser.tree, QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)
        settle(500)  # Native command actions refresh asynchronously after Undo.
        _pose(box.Placement, original, "Actual Ctrl+Z must restore the original pose")
        cad.require(doc.RedoCount == 1, "Native Undo must retain the accepted Move as one redoable entry")
        _focus(controller, controller.browser.tree, settle)
        QtTest.QTest.keyClick(controller.browser.tree, QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)
        settle(300)
        _vector(box.getGlobalPlacement().Base, (15, 22, 33), "Actual Ctrl+Y must restore the accepted native move")
        controller.main.grab().save(str(Path(output) / "fission-move-result.png"))
        return {"world_translation": [5, -2, 3], "world_position": [15, 22, 33],
                "local_position": [2, -5, 3], "rotation_xyz_degrees": [90, 0, 90],
                "preview_cancel": True, "one_undo_redo": True}


def contained_selection(controller, settle, output):
    with _design_move(controller, settle) as doc:
        from fission.move import collect_targets
        parent = _part(doc)
        body = doc.addObject("PartDesign::Body", "Body")
        parent.addObject(body)
        sketch = body.newObject("Sketcher::SketchObject", "Sketch")
        cad.constrained_rectangle(sketch, 12, 8)
        pad = body.newObject("PartDesign::Pad", "Pad")
        pad.Profile, pad.Length = sketch, 6
        doc.recompute()
        child_pose = App.Placement(body.Placement)
        feature_pose = App.Placement(pad.Placement)
        undo = doc.UndoCount
        dialog = _open(controller, [parent, body, pad], settle)
        cad.require(dialog.targets == [parent], "Selected ancestor must deduplicate Body and feature before target validation")
        _values(dialog, settle, (3, 4, 5))
        _finish(dialog, settle, True)
        _vector(parent.Placement.Base, (13, 24, 35), "Selected component must receive one design delta")
        _pose(body.Placement, child_pose, "Contained Body must retain its local pose")
        _pose(pad.Placement, feature_pose, "Contained feature must retain its local pose")
        cad.require(doc.UndoCount == undo + 1, "Deduplicated movement must commit once")
        try:
            collect_targets([pad], doc)
            raise AssertionError("A Body-owned feature alone must not be a numeric Move target")
        except ValueError:
            pass
        standalone = _box(doc, name="Independent", base=(50, 60, 70), angle=0)
        bases = [App.Vector(obj.Placement.Base) for obj in (parent, standalone)]
        dialog = _open(controller, [parent, standalone], settle)
        _values(dialog, settle, rotation=(0, 0, 90))
        _finish(dialog, settle, True)
        for obj, base in zip((parent, standalone), bases):
            _vector(obj.Placement.Base, base, "Each rotation must retain its own native placement origin")
        undo = doc.UndoCount
        dialog = _open(controller, [standalone], settle)
        _values(dialog, settle, (2, 0, 0))
        _values(dialog, settle, (0, 0, 0))
        _finish(dialog, settle, True)
        cad.require(doc.UndoCount == undo and doc.getBookedTransactionID() == 0,
                    "Returning preview to unchanged values must leave no Undo or booking")
        import Mesh
        mesh = doc.addObject("Mesh::Feature", "Mesh")
        mesh.Mesh = Mesh.Mesh(standalone.Shape.tessellate(0.25))
        doc.recompute()
        before_points = mesh.Mesh.CountPoints
        dialog = _open(controller, [mesh], settle)
        _values(dialog, settle, (1, 2, 3))
        _finish(dialog, settle, True)
        _vector(mesh.Placement.Base, (1, 2, 3), "M must retain native mesh placement support")
        cad.require(mesh.Mesh.CountPoints == before_points, "Moving a native mesh must preserve its mesh geometry")
        return {"parent_child_feature_deduplicated": True, "individual_feature_rejected": True,
                "per_object_origin_rotation": True, "no_op_no_undo": True, "native_mesh": True}


def linked_copies(controller, settle, output):
    with _design_move(controller, settle) as doc:
        parent = _part(doc)
        source = _box(doc, parent)
        original = App.Placement(source.Placement)
        source_vertices = _world_vertices(source)
        undo = doc.UndoCount
        object_count = len(doc.Objects)
        dialog = _open(controller, [source], settle)
        QtTest.QTest.mouseClick(dialog.copy, QtCore.Qt.LeftButton)
        _values(dialog, settle, (5, -2, 3))
        cad.require(len(dialog.copies) == 1, "Preview must create a native linked copy")
        _pose(source.Placement, original, "Linked-copy preview must leave the source pose unchanged")
        _finish(dialog, settle, False)
        cad.require(len(doc.Objects) == object_count and doc.UndoCount == undo,
                    "Cancel must remove preview copies without a committed Undo entry")
        dialog = _open(controller, [source], settle)
        QtTest.QTest.mouseClick(dialog.copy, QtCore.Qt.LeftButton)
        _values(dialog, settle, (5, -2, 3))
        copies = list(dialog.copies)
        cad.require(len(copies) == 1 and copies[0].LinkedObject is source
                    and not copies[0].LinkTransform and copies[0].getParentGeoFeatureGroup() is parent,
                    "Copies must be real native links in the source's component with independent pose")
        _vector(parent.Placement.multiply(copies[0].LinkPlacement).Base, (15, 22, 33), "Copied component must use design-axis delta")
        _shifted_vertices(copies[0], source_vertices, (5, -2, 3),
                          "Native copied vertices must receive exactly the design-axis translation")
        _finish(dialog, settle, True)
        cad.require(doc.UndoCount == undo + 1, "Linked-copy OK must commit one native Undo entry")
        copy_name = copies[0].Name
        doc.undo()
        settle(100)
        cad.require(doc.getObject(copy_name) is None, "Native Undo must remove the accepted linked copy")
        doc.redo()
        settle(100)
        native_copy = doc.getObject(copy_name)
        cad.require(native_copy.LinkedObject is source and native_copy.getParentGeoFeatureGroup() is parent,
                    "Native Redo must restore link source and parent containment")
        _pose(source.Placement, original, "Copy OK/Undo/Redo must preserve the original pose")
        # Both link placement modes, and a copy of a selected link, keep native
        # source dependency rather than baking geometry into independent shapes.
        extra = []
        for mode in (False, True):
            link = doc.addObject("App::Link", "ExistingLink")
            link.setLink(source)
            link.LinkTransform = mode
            parent.addObject(link)
            link.LinkPlacement = App.Placement(App.Vector(20, 0, 0), App.Rotation())
            doc.recompute()
            pose = App.Placement(link.LinkPlacement)
            link_vertices = _world_vertices(link)
            dialog = _open(controller, [link], settle)
            _values(dialog, settle, (2, 0, 0))
            _finish(dialog, settle, True)
            _vector(parent.Placement.multiply(link.LinkPlacement).Base, (12, 40, 30), "Existing link must move in design axes in either mode")
            cad.require(bool(link.LinkTransform) == mode, "Moving an existing link must preserve its placement mode")
            _shifted_vertices(link, link_vertices, (2, 0, 0),
                              "Existing link geometry must move once in either native placement mode")
            moved_vertices = _world_vertices(link)
            dialog = _open(controller, [link], settle)
            QtTest.QTest.mouseClick(dialog.copy, QtCore.Qt.LeftButton)
            _values(dialog, settle, (0, 3, 0))
            cloned = list(dialog.copies)
            _finish(dialog, settle, True)
            cad.require(len(cloned) == 1 and cloned[0].LinkedObject is link and not cloned[0].LinkTransform,
                        "Copy of a link must retain a native link-of-link dependency")
            _vector(parent.Placement.multiply(cloned[0].LinkPlacement).Base, (12, 43, 30), "Link-of-link copy must have the correct native placement origin")
            _shifted_vertices(cloned[0], moved_vertices, (0, 3, 0),
                              "Link-of-link native vertices must match the translated selected geometry")
            cad.require(cloned[0].Shape.isValid() and abs(cloned[0].Shape.Volume - source.Shape.Volume) < 1e-6,
                        "Link-of-link must retain valid source geometry")
            extra.extend((link.Name, cloned[0].Name))
        source.Length = 15
        doc.recompute()
        for name in [copy_name] + extra:
            cad.require(abs(doc.getObject(name).Shape.Volume - 720) < 1e-6,
                        "Native source dimension changes must recompute every linked copy")
        path = Path(output) / "move-linked-copies.FCStd"
        names = [copy_name] + extra
        poses = {name: App.Placement(doc.getObject(name).LinkPlacement) for name in names}
        parent_name, source_name = parent.Name, source.Name
        doc.saveAs(str(path))
        App.closeDocument(doc.Name)
        reopened = App.openDocument(str(path))
        settle(150)
        for name in names:
            link = reopened.getObject(name)
            _pose(link.LinkPlacement, poses[name], "Native linked placement must survive FCStd reopen")
            cad.require(link.getParentGeoFeatureGroup() is reopened.getObject(parent_name),
                        "Native linked-copy containment must survive FCStd reopen")
        reopened.getObject(source_name).Length = 20
        reopened.recompute()
        for name in names:
            cad.require(abs(reopened.getObject(name).Shape.Volume - 960) < 1e-6,
                        "Reopened native links must remain parametric")
        return {"native_copies": names, "same_component": True, "cancel_undo_redo": True,
                "both_link_modes": True, "link_of_link": True, "native_vertex_transforms": True,
                "parametric_reopen": True, "file": str(path)}


def ownership(controller, settle, output):
    with _design_move(controller, settle) as doc:
        from fission.move import collect_targets, can_move
        source = _box(doc, base=(0, 0, 0), angle=0)
        original = App.Placement(source.Placement)
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(source)
        doc.openTransaction("Other booked operation")
        foreign = doc.getBookedTransactionID()
        cad.require(foreign > 0 and not doc.HasPendingTransaction, "Guard fixture must hold an empty native booked operation")
        cad.require(not can_move(), "Move readiness must reject booked operations before their first mutation")
        cad.require(controller.move_copy() is None and doc.getBookedTransactionID() == foreign,
                    "Refused Move must preserve an unrelated empty booking")
        doc.abortTransaction()
        dialog = _open(controller, [source], settle)
        _finish(dialog, settle, False)
        cad.require(doc.getBookedTransactionID() == 0, "Cancel before preview must leave no booking")
        dialog = _open(controller, [source], settle)
        _values(dialog, settle, (2, 0, 0))
        own = doc.getBookedTransactionID()
        doc.openTransaction("Foreign replacement")
        replacement = doc.getBookedTransactionID()
        cad.require(replacement > 0 and replacement != own, "Native replacement fixture must book a distinct operation")
        dialog.validate_owner()
        cad.require(not dialog.isVisible() and doc.getBookedTransactionID() == replacement,
                    "Invalidated Move must not abort another operation's booked ID")
        doc.abortTransaction()
        # Native external replacement committed the preview; its ordinary Undo
        # remains the safe way to restore it after the foreign booking closes.
        doc.undo()
        _pose(source.Placement, original, "Externally committed preview must retain native Undo")
        dialog = _open(controller, [source], settle)
        _values(dialog, settle, (3, 0, 0))
        other = App.newDocument("MoveOtherDesign")
        other.openTransaction("Other design booking")
        foreign = other.getBookedTransactionID()
        dialog.validate_owner()
        cad.require(not dialog.isVisible() and other.getBookedTransactionID() == foreign,
                    "Document switch must preserve another design's operation")
        _pose(source.Placement, original, "Switching design must cancel the owned preview")
        other.abortTransaction()
        App.closeDocument(other.Name)
        App.setActiveDocument(doc.Name)
        Gui.setActiveDocument(doc.Name)
        settle(100)
        invalid = doc.addObject("App::FeaturePython", "Unsupported")
        try:
            collect_targets([source, invalid], doc)
            raise AssertionError("Mixed unsupported selection must reject atomically")
        except ValueError:
            pass
        dependent = doc.addObject("App::Link", "DependentLink")
        dependent.setLink(source)
        dependent.LinkTransform = True
        dependent.LinkPlacement = App.Placement(App.Vector(20, 0, 0), App.Rotation())
        doc.recompute()
        before_source = cad.shape_signature(source.Shape)
        before_link = cad.shape_signature(dependent.Shape)
        undo = doc.UndoCount
        Gui.Selection.clearSelection()
        for obj in (source, dependent):
            Gui.Selection.addSelection(obj)
        cad.require(controller.move_copy() is None and not can_move(),
                    "Source plus dependent link must reject before a compounded geometric move")
        cad.require(doc.UndoCount == undo and doc.getBookedTransactionID() == 0,
                    "Rejected linked dependency selection must leave no transaction")
        cad.compare_shapes(before_source, cad.shape_signature(source.Shape))
        cad.compare_shapes(before_link, cad.shape_signature(dependent.Shape))
        import Assembly
        assembly = doc.addObject("Assembly::AssemblyObject", "Assembly")
        member = doc.addObject("App::Link", "AssemblyMember")
        member.setLink(source)
        assembly.addObject(member)
        doc.recompute()
        try:
            collect_targets([member], doc)
            raise AssertionError("Assembly members must retain native solver movement ownership")
        except ValueError:
            pass
        dialog = _open(controller, [source], settle)
        _values(dialog, settle, (1, 0, 0))
        name = doc.Name
        App.closeDocument(name)
        dialog.validate_owner()
        cad.require(not dialog.isVisible(), "Closing the source design must safely invalidate Move")
        return {"empty_foreign_booking_preserved": True, "replacement_transaction_preserved": True,
                "document_switch_cancel": True, "mixed_selection_rejected": True,
                "linked_dependency_guard": True,
                "assembly_member_guard": True, "closed_document_guard": True}
