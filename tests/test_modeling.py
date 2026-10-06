# SPDX-License-Identifier: MIT
"""Scope and native ownership checks without a CAD kernel or GUI process."""
import importlib
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


class Document:
    def __init__(self, name="Design"):
        self.Name = name
        self.Objects = []
        self.HasPendingTransaction = False
        self.booked = 0

    def getObject(self, name):
        return next((obj for obj in self.Objects if obj.Name == name), None)

    def getBookedTransactionID(self):
        return self.booked


class Object:
    def __init__(self, document, name, kind, parent=None):
        self.Document, self.Name, self.kind, self.parent = document, name, kind, parent
        document.Objects.append(self)

    def isDerivedFrom(self, kind):
        return kind == self.kind or (kind == "Part::Feature" and self.kind in (
            "PartDesign::Body", "PartDesign::Pad", "Sketcher::SketchObject", "PartDesign::Line",
            "PartDesign::Plane", "PartDesign::Point"))

    def getParentGeoFeatureGroup(self):
        return self.parent


class Shape:
    def __init__(self, solid=True):
        self.null, self.valid = False, True
        self.Solids = [object()] if solid else []

    def isNull(self):
        return self.null

    def isValid(self):
        return self.valid


class ModelingGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.dict(sys.modules, {"FreeCAD": types.ModuleType("FreeCAD"),
                "FreeCADGui": types.ModuleType("FreeCADGui"),
                "PySide": types.SimpleNamespace(QtWidgets=types.SimpleNamespace())}):
            cls.modeling = importlib.import_module("fission.modeling")

    def setUp(self):
        self.document = Document()
        self.component = Object(self.document, "Component", "App::Part")
        self.other_component = Object(self.document, "OtherComponent", "App::Part")
        self.body = self.make_body("Body", self.component)
        self.other_body = self.make_body("OtherBody", self.other_component)
        self.profile = Object(self.document, "Profile", "Sketcher::SketchObject", self.body)
        self.spine = Object(self.document, "Spine", "Sketcher::SketchObject", self.body)
        self.section = Object(self.document, "Section", "Sketcher::SketchObject", self.body)
        self.active = {"part": self.component, "pdbody": self.body}
        self.selection = []
        self.activations, self.clears = [], []
        self.edit, self.task, self.modal, self.active_transaction = None, None, None, None
        self.workbench = "FissionWorkbench"
        self.view = types.SimpleNamespace(graphicsView=lambda: object(), getObjectInfo=lambda *_: None,
            getActiveObject=lambda kind: self.active.get(kind), setActiveObject=self.activate)
        self.gui_document = types.SimpleNamespace(Document=self.document, getInEdit=lambda: self.edit,
                                                   activeView=lambda: self.view)
        self.app = types.SimpleNamespace(ActiveDocument=self.document,
                                        getActiveTransaction=lambda: self.active_transaction)
        self.gui = types.SimpleNamespace(activeDocument=lambda: self.gui_document,
            activeWorkbench=lambda: types.SimpleNamespace(name=lambda: self.workbench),
            Control=types.SimpleNamespace(activeDialog=lambda: self.task),
            Selection=types.SimpleNamespace(getSelection=lambda: list(self.selection),
                                            clearSelection=self.clear_selection))
        self.qt = types.SimpleNamespace(QApplication=types.SimpleNamespace(instance=lambda:
            types.SimpleNamespace(activeModalWidget=lambda: self.modal)))
        self.patches = [patch.object(self.modeling, attr, value) for attr, value in
                        (("App", self.app), ("Gui", self.gui), ("QtWidgets", self.qt))]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()

    def make_body(self, name, parent=None, solid=True):
        obj = Object(self.document, name, "PartDesign::Body", parent)
        obj.Shape = Shape(solid)
        return obj

    def activate(self, kind, obj):
        self.activations.append((kind, obj))
        self.active[kind] = obj

    def clear_selection(self):
        self.clears.append(tuple(self.selection))
        self.selection.clear()

    def assert_all_unavailable(self):
        for name in self.modeling.MODELED_NAMES:
            with self.subTest(command=name):
                self.assertFalse(self.modeling.available(name))
                self.assertFalse(self.modeling.prepare(name))
        self.assertEqual(self.activations, [])
        self.assertEqual(self.clears, [])

    def test_readiness_never_changes_selection_scope_or_document(self):
        self.active["pdbody"] = self.other_body
        self.selection[:] = [self.profile, self.spine]
        before = list(self.document.Objects)
        for name in self.modeling.MODELED_NAMES:
            self.assertTrue(self.modeling.available(name))
        self.assertIs(self.modeling.scoped_body(), self.body)
        self.assertEqual(self.selection, [self.profile, self.spine])
        self.assertEqual(self.document.Objects, before)
        self.assertIs(self.active["pdbody"], self.other_body)
        self.assertEqual(self.activations, [])
        self.assertEqual(self.clears, [])

    def test_unique_body_is_activated_only_during_preparation(self):
        self.active["pdbody"] = self.other_body
        self.assertIs(self.modeling.scoped_body(), self.body)
        self.assertEqual(self.activations, [])
        self.assertTrue(self.modeling.prepare("RevolveCut"))
        self.assertEqual(self.activations, [("pdbody", self.body)])

    def test_body_in_another_component_is_never_automatically_reused(self):
        empty = Object(self.document, "EmptyComponent", "App::Part")
        self.active["part"] = empty
        self.active["pdbody"] = self.other_body
        self.assertIsNone(self.modeling.scoped_body())
        for name in ("Extrude", "Cut", "RevolveCut", "SweepCut", "LoftCut", "Plane", "Axis", "Point"):
            self.assertFalse(self.modeling.available(name))
            self.assertFalse(self.modeling.prepare(name))
        self.assertTrue(self.modeling.available("NewBody"))
        self.assertEqual(self.activations, [])

    def test_multiple_inactive_bodies_are_ambiguous_but_an_active_body_is_explicit(self):
        second = self.make_body("SecondBody", self.component)
        self.active["pdbody"] = None
        self.assertIsNone(self.modeling.scoped_body())
        self.assertFalse(self.modeling.available("Axis"))
        self.assertFalse(self.modeling.prepare("SweepCut"))
        self.active["pdbody"] = second
        self.assertIs(self.modeling.scoped_body(), second)
        self.assertTrue(self.modeling.available("LoftCut"))

    def test_root_body_scope_does_not_search_nested_components(self):
        self.active.update(part=None, pdbody=None)
        self.assertIsNone(self.modeling.scoped_body())
        root_body = self.make_body("RootBody")
        self.assertIs(self.modeling.scoped_body(), root_body)
        self.assertTrue(self.modeling.prepare("Point"))
        self.assertEqual(self.activations, [("pdbody", root_body)])
        self.assertIsNone(self.active["part"])

    def test_stale_active_component_and_body_wrappers_are_rejected(self):
        self.document.Objects.remove(self.component)
        self.assert_all_unavailable()
        self.document.Objects.append(self.component)
        self.document.Objects.remove(self.body)
        self.assertIsNone(self.modeling.scoped_body())
        self.assertFalse(self.modeling.prepare("Axis"))
        self.assertEqual(self.activations, [])

    def test_non_component_active_part_is_rejected(self):
        self.active["part"] = self.profile
        self.assert_all_unavailable()

    def test_missing_or_mismatched_gui_document_is_rejected_by_identity(self):
        self.gui_document.Document = Document(self.document.Name)
        self.assert_all_unavailable()
        self.gui_document = None
        self.assert_all_unavailable()
        self.app.ActiveDocument = None
        self.assert_all_unavailable()

    def test_non_3d_and_disposed_views_are_unavailable(self):
        self.view = types.SimpleNamespace(graphicsView=lambda: object())
        self.assert_all_unavailable()
        self.view = types.SimpleNamespace(graphicsView=lambda: None, getObjectInfo=lambda *_: None,
                                         getActiveObject=lambda _: None)
        self.assert_all_unavailable()
        self.gui_document.activeView = lambda: (_ for _ in ()).throw(RuntimeError("deleted native view"))
        self.assert_all_unavailable()

    def test_drawing_and_manufacture_workbenches_do_not_mutate_design_bodies(self):
        for name in ("TechDrawWorkbench", "CAMWorkbench", "PathWorkbench", "PartDesignWorkbench"):
            with self.subTest(workbench=name):
                self.workbench = name
                self.assert_all_unavailable()
        self.workbench = "FissionWorkbench"
        self.assertTrue(self.modeling.available("NewBody"))

    def test_edit_task_and_modal_ownership_blocks_all_modeling(self):
        for field in ("edit", "task", "modal"):
            with self.subTest(owner=field):
                setattr(self, field, object())
                self.assert_all_unavailable()
                setattr(self, field, None)

    def test_pending_and_booked_transactions_block_before_any_geometry_changes(self):
        self.document.HasPendingTransaction = True
        self.assert_all_unavailable()
        self.document.HasPendingTransaction = False
        self.document.booked = 17
        self.assert_all_unavailable()
        self.document.booked = 0
        self.active_transaction = ("Create native feature", 17)
        self.assert_all_unavailable()
        self.active_transaction = None
        self.assertTrue(self.modeling.available("NewBody"))

    def test_cut_requires_an_existing_solid_without_creating_a_body(self):
        before = list(self.document.Objects)
        for field, value in (("Solids", []), ("null", True)):
            old = getattr(self.body.Shape, field)
            setattr(self.body.Shape, field, value)
            for name in ("Cut", "RevolveCut", "SweepCut", "LoftCut"):
                self.assertFalse(self.modeling.available(name))
                self.assertFalse(self.modeling.prepare(name))
            self.assertTrue(self.modeling.available("Axis"))
            setattr(self.body.Shape, field, old)
        self.assertEqual(self.document.Objects, before)
        self.assertEqual(self.activations, [])

    def test_readiness_does_not_run_kernel_shape_validation(self):
        self.body.Shape.isValid = lambda: (_ for _ in ()).throw(AssertionError("expensive kernel check"))
        for name in ("Cut", "RevolveCut", "SweepCut", "LoftCut"):
            self.assertTrue(self.modeling.available(name))

    def test_empty_and_multi_profile_cut_selection_are_left_to_native_pickers(self):
        for selected in ([], [self.profile], [self.profile, self.spine],
                         [self.profile, self.spine, self.section]):
            self.selection[:] = selected
            for name in ("Cut", "RevolveCut", "SweepCut", "LoftCut"):
                self.assertTrue(self.modeling.available(name))
                self.assertTrue(self.modeling.prepare(name))
                self.assertEqual(self.selection, selected)
        self.assertEqual(self.clears, [])

    def test_cut_rejects_other_body_non_geometry_and_stale_selection(self):
        other_profile = Object(self.document, "OtherProfile", "Sketcher::SketchObject", self.other_body)
        stale_profile = Object(self.document, "DeletedProfile", "Sketcher::SketchObject", self.body)
        self.document.Objects.remove(stale_profile)
        for obj in (other_profile, self.component, self.body, stale_profile):
            self.selection[:] = [self.profile, obj]
            for name in ("Extrude", "Cut", "RevolveCut", "SweepCut", "LoftCut"):
                self.assertFalse(self.modeling.available(name))
                self.assertFalse(self.modeling.prepare(name))
        self.assertEqual(self.activations, [])

    def test_foreign_document_selection_blocks_every_command(self):
        foreign = Object(Document(self.document.Name), "Profile", "Sketcher::SketchObject")
        self.selection[:] = [foreign]
        self.assert_all_unavailable()

    def test_native_body_feature_inheritance_does_not_make_it_a_cut_profile(self):
        self.assertTrue(self.body.isDerivedFrom("Part::Feature"))
        self.selection[:] = [self.body]
        for name in ("Extrude", "Cut", "RevolveCut", "SweepCut", "LoftCut"):
            self.assertFalse(self.modeling.available(name))
            self.assertFalse(self.modeling.prepare(name))
        self.assertEqual(self.selection, [self.body])
        self.assertEqual(self.activations, [])

    def test_selected_datum_edit_cannot_target_another_body(self):
        for name, kind in (("Plane", "PartDesign::Plane"), ("Axis", "PartDesign::Line"),
                           ("Point", "PartDesign::Point")):
            current = Object(self.document, name, kind, self.body)
            other = Object(self.document, "Other" + name, kind, self.other_body)
            self.selection[:] = [current]
            self.assertTrue(self.modeling.available(name))
            self.selection[:] = [other]
            self.assertFalse(self.modeling.available(name))
            self.assertFalse(self.modeling.prepare(name))

    def test_datum_accepts_native_origin_planes_without_part_feature_inheritance(self):
        origin = Object(self.document, "Origin", "App::Origin", self.body)
        plane = Object(self.document, "XY_Plane", "App::Plane", origin)
        self.assertFalse(plane.isDerivedFrom("Part::Feature"))
        self.selection[:] = [plane]
        for name in ("Plane", "Axis", "Point"):
            self.assertTrue(self.modeling.available(name))
            self.assertTrue(self.modeling.prepare(name))
            self.assertEqual(self.selection, [plane])

    def test_new_body_clears_geometry_seed_but_preserves_active_component(self):
        self.selection[:] = [self.profile]
        self.assertTrue(self.modeling.available("NewBody"))
        self.assertEqual(self.selection, [self.profile])
        self.assertTrue(self.modeling.prepare("NewBody"))
        self.assertEqual(self.clears, [(self.profile,)])
        self.assertEqual(self.selection, [])
        self.assertIs(self.active["part"], self.component)
        self.assertEqual(self.activations, [])
        self.selection[:] = [self.component]
        self.assertTrue(self.modeling.prepare("NewBody"))

    def test_extrude_accepts_a_scoped_empty_body_while_cut_requires_stock(self):
        self.body.Shape.Solids = []
        self.body.Shape.null = True
        self.selection[:] = [self.profile]
        self.assertTrue(self.modeling.available("Extrude"))
        self.assertTrue(self.modeling.prepare("Extrude"))
        self.assertFalse(self.modeling.available("Cut"))
        self.assertFalse(self.modeling.prepare("Cut"))
        self.assertEqual(self.selection, [self.profile])
        self.assertEqual(self.activations, [])
        self.assertEqual(self.clears, [])

    def test_new_component_needs_no_body_and_preserves_native_selection_and_scope(self):
        empty = Object(self.document, "EmptyNewComponentScope", "App::Part")
        self.active.update(part=empty, pdbody=self.other_body)
        self.selection[:] = [self.component, self.profile]
        before = list(self.document.Objects)
        self.assertTrue(self.modeling.available("NewComponent"))
        self.assertTrue(self.modeling.prepare("NewComponent"))
        self.assertEqual(self.document.Objects, before)
        self.assertIs(self.active["part"], empty)
        self.assertIs(self.active["pdbody"], self.other_body)
        self.assertEqual(self.selection, [self.component, self.profile])
        self.assertEqual(self.activations, [])
        self.assertEqual(self.clears, [])

    def test_new_body_does_not_ignore_a_selected_different_component(self):
        self.selection[:] = [self.other_component]
        self.assertFalse(self.modeling.available("NewBody"))
        self.assertFalse(self.modeling.prepare("NewBody"))
        self.assertEqual(self.selection, [self.other_component])
        self.assertEqual(self.clears, [])

    def test_new_body_clears_standalone_shape_seed_in_component_and_root_scope(self):
        box = Object(self.document, "ImportedBox", "Part::Box")
        for component in (self.component, None):
            self.active["part"] = component
            self.selection[:] = [box]
            self.assertTrue(self.modeling.available("NewBody"))
            self.assertTrue(self.modeling.prepare("NewBody"))
            self.assertIs(self.active["part"], component)
            self.assertEqual(self.selection, [])
        self.assertEqual(self.clears, [(box,), (box,)])
        self.assertEqual(self.activations, [])

    def test_preparation_rechecks_task_ownership_after_readiness(self):
        self.active["pdbody"] = None
        self.assertTrue(self.modeling.available("Axis"))
        self.task = object()
        self.assertFalse(self.modeling.prepare("Axis"))
        self.assertEqual(self.activations, [])

    def test_view_or_selection_changing_during_preparation_causes_no_mutation(self):
        replacement = types.SimpleNamespace(**vars(self.view))
        old_view = self.view
        views = iter((old_view, replacement))
        self.gui_document.activeView = lambda: next(views)
        self.assertFalse(self.modeling.prepare("NewBody"))
        self.gui_document.activeView = lambda: old_view
        selections = iter(([self.profile], [self.spine]))
        self.gui.Selection.getSelection = lambda: next(selections)
        self.assertFalse(self.modeling.prepare("NewBody"))
        self.assertEqual(self.activations, [])
        self.assertEqual(self.clears, [])

    def test_unknown_command_never_prepares_native_state(self):
        self.assertFalse(self.modeling.available("MissingTool"))
        self.assertFalse(self.modeling.prepare("MissingTool"))
        self.assertEqual(self.activations, [])
        self.assertEqual(self.clears, [])


if __name__ == "__main__":
    unittest.main()
