# SPDX-License-Identifier: LGPL-2.1-or-later
"""Placement math and real Qt ownership/transaction checks for Move / Copy."""
import importlib
import math
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if "fission" not in sys.modules:
    package = types.ModuleType("fission")
    package.__path__ = [str(ROOT / "Mod" / "Fission" / "fission")]
    sys.modules["fission"] = package


class Vector:
    def __init__(self, x=0, y=0, z=0):
        self.x, self.y, self.z = x, y, z

    def __add__(self, other):
        return Vector(self.x + other.x, self.y + other.y, self.z + other.z)

    def __neg__(self):
        return Vector(-self.x, -self.y, -self.z)


class Rotation:
    def __init__(self, axis=None, angle=0):
        self.matrix = [[float(row == column) for column in range(3)] for row in range(3)]
        if axis is not None:
            values = (axis.x, axis.y, axis.z)
            c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
            cross = ((0, -axis.z, axis.y), (axis.z, 0, -axis.x), (-axis.y, axis.x, 0))
            self.matrix = [[c * (row == column) + (1-c) * values[row] * values[column]
                            + s * cross[row][column] for column in range(3)] for row in range(3)]

    def multiply(self, other):
        result = Rotation()
        result.matrix = [[sum(self.matrix[row][k] * other.matrix[k][column] for k in range(3))
                          for column in range(3)] for row in range(3)]
        return result

    def multVec(self, vector):
        values = vector.x, vector.y, vector.z
        return Vector(*(sum(self.matrix[row][k] * values[k] for k in range(3)) for row in range(3)))

    def inverse(self):
        result = Rotation()
        result.matrix = [list(row) for row in zip(*self.matrix)]
        return result


class Placement:
    def __init__(self, base=None, rotation=None):
        if isinstance(base, Placement):
            self.Base, self.Rotation = base.Base, base.Rotation
        else:
            self.Base, self.Rotation = base or Vector(), rotation or Rotation()

    def multiply(self, other):
        return Placement(self.Base + self.Rotation.multVec(other.Base), self.Rotation.multiply(other.Rotation))

    def inverse(self):
        rotation = self.Rotation.inverse()
        return Placement(rotation.multVec(-self.Base), rotation)

    def isSame(self, other, tolerance):
        return (all(abs(a - b) <= tolerance for a, b in zip(
            (self.Base.x, self.Base.y, self.Base.z), (other.Base.x, other.Base.y, other.Base.z)))
            and all(abs(self.Rotation.matrix[row][column] - other.Rotation.matrix[row][column]) <= tolerance
                    for row in range(3) for column in range(3)))


class Document:
    def __init__(self):
        self.Name = "Design"
        self.Objects = []
        self.HasPendingTransaction = False
        self.UndoCount = 0
        self.events = []
        self.transaction_id = 0
        self.snapshot = None

    def getObject(self, name):
        return next((obj for obj in self.Objects if obj.Name == name), None)

    def addObject(self, kind, name):
        name += str(len(self.Objects))
        obj = Object(self, name, kind)
        self.Objects.append(obj)
        return obj

    def removeObject(self, name):
        obj = self.getObject(name)
        self.Objects.remove(obj)
        obj.Document = None

    def openTransaction(self, title):
        self.events.append("open")
        self.HasPendingTransaction = True
        self.transaction_id += 1
        self.snapshot = [(obj, Placement(obj.Placement), obj.parent, list(obj.Group)) for obj in self.Objects]

    def getBookedTransactionID(self):
        return self.transaction_id

    def abortTransaction(self):
        self.events.append("abort")
        self.HasPendingTransaction = False
        self.transaction_id = 0
        self.Objects = [item[0] for item in self.snapshot]
        for obj, placement, parent, group in self.snapshot:
            obj.Document, obj.Placement, obj.parent, obj.Group = self, placement, parent, group

    def commitTransaction(self):
        self.events.append("commit")
        self.HasPendingTransaction = False
        self.transaction_id = 0
        self.UndoCount += 1

    def recompute(self):
        pass


class Object:
    def __init__(self, document, name, kind="Part::Feature", parent=None):
        self.Document, self.Name, self.Label, self.TypeId = document, name, name, kind
        self.parent, self.Group = parent, []
        self.Placement = Placement()
        self.PropertiesList = ["Placement"]
        self.ExpressionEngine = []
        self.status, self.editor = [], []
        if kind == "App::Link":
            self.PropertiesList.append("LinkPlacement")
            self.LinkedObject = None
            self.LinkTransform = False
            self.ElementCount, self.ElementList = 0, []
            self.ScaleVector = Vector(1, 1, 1)

    @property
    def LinkPlacement(self):
        return self.Placement

    @LinkPlacement.setter
    def LinkPlacement(self, value):
        self.Placement = value

    def isDerivedFrom(self, kind):
        return (kind == self.TypeId or (self.TypeId == "Assembly::AssemblyObject" and kind == "App::Part")
                or (self.TypeId in ("Sketcher::SketchObject", "PartDesign::Pad") and kind == "Part::Feature")
                or (self.TypeId == "PartDesign::Pad" and kind == "PartDesign::Feature"))

    def getParentGeoFeatureGroup(self):
        return self.parent

    def getPropertyStatus(self, prop):
        return self.status

    def getEditorMode(self, prop):
        return self.editor

    def setLink(self, source):
        self.LinkedObject = source

    def addObject(self, obj):
        self.Group.append(obj)
        obj.parent = self


class MoveTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("FISSION_QT_TESTS") == "1":
            from PySide6 import QtCore, QtWidgets, QtTest
            cls.QtCore, cls.QtWidgets, cls.QtTest = QtCore, QtWidgets, QtTest
            cls.application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        else:
            QtCore = types.SimpleNamespace()
            QtWidgets = types.SimpleNamespace(QDialog=object)
        with patch.dict(sys.modules, {"FreeCAD": types.ModuleType("FreeCAD"),
            "FreeCADGui": types.ModuleType("FreeCADGui"),
            "PySide": types.SimpleNamespace(QtCore=QtCore, QtWidgets=QtWidgets)}):
            cls.move = importlib.import_module("fission.move")

    def setUp(self):
        self.document = Document()
        self.parent = Object(self.document, "Component", "App::Part")
        self.body = Object(self.document, "Body", "PartDesign::Body", self.parent)
        self.feature = Object(self.document, "Pad", "PartDesign::Pad", self.body)
        self.free = Object(self.document, "Free")
        self.parent.Group = [self.body]
        self.body.Group = [self.feature]
        self.document.Objects = [self.parent, self.body, self.feature, self.free]
        self.selection = [self.free]
        self.edit = None
        self.task = None
        self.context = "model"
        self.workbench = "FissionWorkbench"
        self.view = types.SimpleNamespace(graphicsView=lambda: None)
        self.gui_document = types.SimpleNamespace(Document=self.document, activeView=lambda: self.view,
                                                 getInEdit=lambda: self.edit)
        self.app = types.SimpleNamespace(ActiveDocument=self.document, Vector=Vector, Placement=Placement,
            Rotation=Rotation, getDocument=lambda name: self.document if name == self.document.Name else None)
        self.gui = types.SimpleNamespace(activeDocument=lambda: self.gui_document,
            activeWorkbench=lambda: types.SimpleNamespace(name=lambda: self.workbench),
            Selection=types.SimpleNamespace(getSelection=lambda: self.selection,
                clearSelection=lambda: self.selection.clear(), addSelection=self.selection.append),
            Control=types.SimpleNamespace(activeDialog=lambda: self.task))
        self.patches = [patch.object(self.move, "App", self.app), patch.object(self.move, "Gui", self.gui)]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()


class MoveAdapterTests(MoveTestBase):
    def test_parent_selection_removes_body_and_feature_before_validation(self):
        self.assertEqual(self.move.collect_targets([self.feature, self.body, self.parent]), [self.parent])
        self.assertEqual(self.move.collect_targets([self.feature, self.body]), [self.body])

    def test_dependency_is_not_containment(self):
        self.free.OutList = [self.body]
        self.assertEqual(self.move.collect_targets([self.free, self.body]), [self.free, self.body])

    def test_rejects_body_feature_sketch_and_mixed_invalid_selection(self):
        sketch = Object(self.document, "Sketch", "Sketcher::SketchObject")
        self.document.Objects.append(sketch)
        for selected in ([self.feature], [sketch], [self.free, self.feature]):
            with self.assertRaisesRegex(ValueError, "body|component"):
                self.move.collect_targets(selected)
        self.assertEqual(self.document.events, [])

    def test_rejects_other_document_and_stale_same_name_object(self):
        for obj in (Object(Document(), "Outside"), Object(self.document, "Free")):
            with self.assertRaisesRegex(ValueError, "active design"):
                self.move.collect_targets([obj])

    def test_standalone_mesh_retains_move_support(self):
        mesh = self.document.addObject("Mesh::Feature", "Mesh")
        self.assertEqual(self.move.collect_targets([mesh]), [mesh])

    def test_rejects_readonly_expression_and_attached_placements(self):
        self.free.status = ["ReadOnly"]
        with self.assertRaisesRegex(ValueError, "read-only"):
            self.move.collect_targets()
        self.free.status = []
        self.free.ExpressionEngine = [("Placement.Base.x", "2 mm")]
        with self.assertRaisesRegex(ValueError, "expressions"):
            self.move.collect_targets()
        self.free.ExpressionEngine = []
        self.free.PropertiesList.append("MapMode")
        self.free.MapMode = "FlatFace"
        with self.assertRaisesRegex(ValueError, "attachment"):
            self.move.collect_targets()

    def test_rejects_link_array_scale_and_missing_source(self):
        link = self.document.addObject("App::Link", "Link")
        link.setLink(self.free)
        link.ElementCount = 2
        with self.assertRaisesRegex(ValueError, "arrays"):
            self.move.collect_targets([link])
        link.ElementCount = 0
        link.ScaleVector = Vector(2, 1, 1)
        with self.assertRaisesRegex(ValueError, "scaled"):
            self.move.collect_targets([link])
        link.ScaleVector = Vector(1, 1, 1)
        link.LinkedObject = None
        with self.assertRaisesRegex(ValueError, "available source"):
            self.move.collect_targets([link])

    def test_assembly_members_rejected_while_whole_assembly_is_supported(self):
        assembly = self.document.addObject("Assembly::AssemblyObject", "Assembly")
        assembly.addObject(self.free)
        with self.assertRaisesRegex(ValueError, "assembly dragging"):
            self.move.collect_targets()
        self.assertEqual(self.move.collect_targets([assembly, self.free]), [assembly])

    def test_link_source_and_transitive_container_selection_reject_atomically(self):
        link = self.document.addObject("App::Link", "Link")
        link.setLink(self.free)
        link.LinkTransform = True
        linked_link = self.document.addObject("App::Link", "LinkOfLink")
        linked_link.setLink(link)
        for selection in ([self.free, link], [self.free, linked_link], [link, linked_link]):
            with self.assertRaisesRegex(ValueError, "separate operations"):
                self.move.collect_targets(selection)
        self.parent.addObject(self.free)
        with self.assertRaisesRegex(ValueError, "separate operations"):
            self.move.collect_targets([self.parent, linked_link])
        link.setLink(self.parent)
        with self.assertRaisesRegex(ValueError, "separate operations"):
            self.move.collect_targets([self.free, link])

    def test_can_move_honors_native_task_pending_transaction_and_idle_assembly(self):
        self.assertTrue(self.move.can_move())
        self.document.HasPendingTransaction = True
        self.assertFalse(self.move.can_move())
        self.document.HasPendingTransaction = False
        self.task = object()
        self.assertFalse(self.move.can_move())
        self.task = None
        self.edit = types.SimpleNamespace(Object=self.feature)
        self.assertFalse(self.move.can_move())
        self.edit = types.SimpleNamespace(Object=Object(self.document, "Assembly", "Assembly::AssemblyObject"))
        self.assertTrue(self.move.can_move())

    def test_nested_translation_uses_design_axes(self):
        parent = Placement(Vector(10, 20, 30), Rotation(Vector(0, 0, 1), 90))
        original = Placement(Vector(4, 0, 0), Rotation(Vector(0, 1, 0), 30))
        actual = self.move.transformed_placement(original, parent, (5, -2, 3), (0, 0, 0))
        self.assertAlmostEqual(actual.Base.x, 2)
        self.assertAlmostEqual(actual.Base.y, -5)
        self.assertAlmostEqual(actual.Base.z, 3)
        world = parent.multiply(actual)
        self.assertAlmostEqual(world.Base.x, 15)
        self.assertAlmostEqual(world.Base.y, 22)
        self.assertAlmostEqual(world.Base.z, 33)

    def test_world_rotation_preserves_pivot_and_uses_x_y_z_order(self):
        original = Placement(Vector(9, 2, -4), Rotation(Vector(0, 1, 0), 30))
        actual = self.move.transformed_placement(original, Placement(), (0, 0, 0), (90, 0, 90))
        expected = Rotation(Vector(0, 0, 1), 90).multiply(Rotation(Vector(1, 0, 0), 90)).multiply(original.Rotation)
        self.assertTrue(actual.isSame(Placement(original.Base, expected), 1e-9))

    def test_transform_rejects_nonfinite_numbers(self):
        for value in (math.inf, -math.inf, math.nan):
            with self.assertRaisesRegex(ValueError, "finite"):
                self.move.transformed_placement(Placement(), Placement(), (value, 0, 0), (0, 0, 0))

    def test_containment_cycle_is_rejected(self):
        self.parent.parent = self.body
        with self.assertRaisesRegex(ValueError, "cyclic"):
            self.move.collect_targets([self.body])


@unittest.skipUnless(os.environ.get("FISSION_QT_TESTS") == "1", "Set FISSION_QT_TESTS=1 with PySide")
class MoveDialogQtTests(MoveTestBase):
    def setUp(self):
        super().setUp()
        self.main = self.QtWidgets.QMainWindow()
        self.notifications = []
        self.controller = types.SimpleNamespace(main=self.main, context=lambda: self.context,
            notify=self.notifications.append, refresh_context=lambda: None)
        self.dialog = self.move.MoveDialog(self.controller, [self.free])
        self.main.show()
        self.dialog.show()
        self.application.processEvents()

    def tearDown(self):
        self.dialog.reject()
        self.dialog.deleteLater()
        self.main.close()
        self.main.deleteLater()
        self.application.processEvents()
        super().tearDown()

    def test_preview_cancel_restores_original_placement(self):
        self.dialog.translation[0].setValue(12)
        self.assertEqual(self.free.Placement.Base.x, 12)
        self.dialog.translation[0].setValue(21)
        self.assertEqual(self.free.Placement.Base.x, 21)
        self.assertEqual(self.document.events, ["open"])
        self.dialog.reject()
        self.assertEqual(self.free.Placement.Base.x, 0)
        self.assertEqual(self.document.events, ["open", "abort"])

    def test_actual_ok_button_commits_exactly_one_transaction(self):
        self.dialog.translation[1].setValue(7)
        self.dialog.rotation[2].setValue(90)
        self.QtTest.QTest.mouseClick(self.dialog.buttons.button(self.QtWidgets.QDialogButtonBox.Ok),
                                    self.QtCore.Qt.LeftButton)
        self.assertEqual(self.document.events, ["open", "commit"])
        self.assertEqual(self.document.UndoCount, 1)
        self.assertEqual(self.free.Placement.Base.y, 7)

    def test_unchanged_ok_and_returned_to_zero_do_not_commit_undo(self):
        self.dialog.translation[0].setValue(4)
        self.dialog.translation[0].setValue(0)
        self.dialog.accept()
        self.assertEqual(self.document.events, ["open", "abort"])
        self.assertEqual(self.document.UndoCount, 0)

    def test_untouched_ok_creates_no_transaction(self):
        self.dialog.accept()
        self.assertEqual(self.document.events, [])

    def test_copy_is_deliberate_at_zero_and_preserves_native_source(self):
        self.dialog.copy.setChecked(True)
        self.assertEqual(len(self.dialog.copies), 1)
        copy = self.dialog.copies[0]
        self.assertIs(copy.LinkedObject, self.free)
        self.assertFalse(copy.LinkTransform)
        self.dialog.translation[0].setValue(9)
        self.assertEqual(copy.LinkPlacement.Base.x, 9)
        self.assertEqual(self.free.Placement.Base.x, 0)
        self.dialog.accept()
        self.assertEqual(self.document.events, ["open", "commit"])
        self.assertEqual(self.selection, [copy])

    def test_copy_cancel_removes_preview_link(self):
        self.dialog.copy.setChecked(True)
        self.dialog.reject()
        self.assertEqual(len(self.document.Objects), 4)
        self.assertEqual(self.document.events, ["open", "abort"])

    def test_document_context_change_aborts_owned_preview(self):
        self.dialog.translation[0].setValue(6)
        self.app.ActiveDocument = Document()
        self.assertFalse(self.dialog.validate_owner())
        self.assertEqual(self.document.events, ["open", "abort"])
        self.assertEqual(self.free.Placement.Base.x, 0)

    def test_external_transaction_is_never_committed_or_aborted(self):
        self.dialog.translation[0].setValue(6)
        self.document.transaction_id += 1
        self.assertFalse(self.dialog.validate_owner())
        self.assertEqual(self.document.events, ["open"])
        self.assertTrue(self.document.HasPendingTransaction)

    def test_recompute_changed_booking_cannot_be_committed_by_ok(self):
        self.dialog.translation[0].setValue(6)
        def foreign_booking():
            self.document.transaction_id += 1
        self.document.recompute = foreign_booking
        self.dialog.accept()
        self.assertEqual(self.document.events, ["open"])
        self.assertTrue(self.document.HasPendingTransaction)
        self.assertFalse(self.dialog.isVisible())

    def test_booked_transaction_is_aborted_even_before_first_mutation(self):
        self.document.openTransaction("Move / Copy")
        self.dialog.transaction = True
        self.dialog.transaction_id = self.document.getBookedTransactionID()
        self.document.HasPendingTransaction = False
        self.dialog.reject()
        self.assertEqual(self.document.events, ["open", "abort"])

    def test_modified_preview_link_refuses_accept(self):
        self.dialog.copy.setChecked(True)
        self.dialog.copies[0].setLink(self.parent)
        self.dialog.accept()
        self.assertEqual(self.document.events, ["open", "abort"])
        self.assertEqual(len(self.document.Objects), 4)

    def test_removed_source_and_changed_parent_refuse_accept(self):
        self.dialog.translation[0].setValue(6)
        self.free.parent = self.parent
        self.dialog.accept()
        self.assertEqual(self.document.events, ["open", "abort"])
        self.assertEqual(self.document.UndoCount, 0)

    def test_changed_native_edit_owner_cancels_preview(self):
        self.dialog.translation[0].setValue(6)
        self.edit = types.SimpleNamespace(Object=self.feature)
        self.assertFalse(self.dialog.validate_owner())
        self.assertEqual(self.document.events, ["open", "abort"])

    def test_closed_native_document_nameerror_cancels_without_timer_exception(self):
        def unavailable(name):
            raise NameError("Document not found")
        self.app.getDocument = unavailable
        self.assertFalse(self.dialog.validate_owner())
        self.assertFalse(self.dialog.isVisible())
        self.assertEqual(self.document.events, [])

    def test_closed_native_document_referenceerror_closes_active_preview(self):
        self.dialog.translation[0].setValue(6)
        def unavailable():
            raise ReferenceError("Cannot access deleted native document")
        self.document.getBookedTransactionID = unavailable
        self.app.getDocument = lambda name: None
        self.assertFalse(self.dialog.validate_owner())
        self.assertFalse(self.dialog.isVisible())
        self.assertFalse(self.dialog.transaction)
        self.assertEqual(self.document.events, ["open"])


if __name__ == "__main__":
    unittest.main()
