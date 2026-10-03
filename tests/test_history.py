# SPDX-License-Identifier: LGPL-2.1-or-later
"""Graph/order tests run without FreeCAD; integration lives in native smoke tests."""

import importlib.util
import pathlib
import sys
import unittest
from types import SimpleNamespace

source = pathlib.Path(__file__).parents[1] / "Mod/Fission/fission/history.py"
spec = importlib.util.spec_from_file_location("fission_history_tests", source)
history = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = history
spec.loader.exec_module(history)


class Object:
    def __init__(self, name, type_id="PartDesign::Pad", document=None, parents=()):
        self.Name = name
        self.Label = name
        self.TypeId = type_id
        self.Document = document
        self.OutList = list(parents)
        self.Group = []
        self.PropertiesList = []
        self._bases = {type_id}
        if type_id.startswith("PartDesign::") and type_id != "PartDesign::Body":
            self._bases.add("PartDesign::Feature")
        if type_id in ("Sketcher::SketchObject", "PartDesign::Pad", "PartDesign::Pocket"):
            self._bases.add("Part::Feature")

    def isDerivedFrom(self, type_id):
        return type_id in self._bases


def document(*objects):
    doc = SimpleNamespace(Name="Design", Label="Design", Objects=list(objects))
    for obj in objects:
        obj.Document = doc
    return doc


class HistoryTests(unittest.TestCase):
    def test_creation_order_survives_labels_and_dependencies(self):
        sketch = Object("Z", "Sketcher::SketchObject")
        pad = Object("A", parents=[sketch])
        pocket = Object("B", "PartDesign::Pocket", parents=[pad])
        doc = document(Object("Body", "PartDesign::Body"), sketch, pad, pocket, Object("Origin", "App::Origin"))
        self.assertEqual(history.chronological_features(doc), [sketch, pad, pocket])
        pad.Label = "000 Earlier looking label"
        self.assertEqual(history.chronological_features(doc), [sketch, pad, pocket])

    def test_sketch_and_dependency_crossings_rejected(self):
        sketch, pad = Object("Sketch", "Sketcher::SketchObject"), Object("Pad")
        pad.OutList = [sketch]
        document(sketch, pad)
        self.assertIn("Pad depends on Sketch", history.dependency_move_reason([sketch, pad], 1, 0))
        self.assertIn("Pad depends on Sketch", history.dependency_move_reason([sketch, pad], 0, 1))

    def test_independent_features_graph_move_and_bounds(self):
        left, right = Object("Left"), Object("Right")
        document(left, right)
        self.assertEqual(history.dependency_move_reason([left, right], 0, 1), "")
        self.assertIn("outside", history.dependency_move_reason([left, right], 4, 1))
        self.assertIn("tip and support", history.reorder_explanation([left, right], 0))

    def test_external_dependencies_do_not_become_fake_history(self):
        external = Object("External", document=SimpleNamespace(Name="Other"))
        pad = Object("Pad", parents=[external])
        document(pad)
        self.assertEqual(history.dependency_move_reason([pad], 0, 0), "")

    def test_real_containment_is_used_instead_of_dependency_links(self):
        sketch, pad, body = Object("Sketch", "Sketcher::SketchObject"), Object("Pad"), Object("Body", "PartDesign::Body")
        body.Group = [sketch, pad]
        pad.OutList = [sketch]
        doc = document(body, sketch, pad)
        records = {record.key: record for record in history.browser_records(doc)}
        self.assertEqual(records[history.object_key(sketch)].parent, ("folder", history.object_key(body), "Sketches"))
        self.assertEqual(records[history.object_key(pad)].parent, ("folder", history.object_key(body), "Features"))
        self.assertEqual(len([rec for rec in records.values() if rec.obj is not None]), 3)

    def test_origin_features_are_real_children(self):
        body, origin, plane = Object("Body", "PartDesign::Body"), Object("Origin", "App::Origin"), Object("XY", "App::OriginFeature")
        body.Origin = origin
        origin.OriginFeatures = [plane]
        doc = document(body, origin, plane)
        records = {record.key: record for record in history.browser_records(doc)}
        self.assertEqual(records[history.object_key(origin)].parent, history.object_key(body))
        self.assertEqual(records[history.object_key(plane)].parent, history.object_key(origin))

    def test_cyclic_and_shared_groups_display_each_object_once(self):
        a, b, feature = Object("A", "App::Part"), Object("B", "App::Part"), Object("Pad")
        a.Group = [b, feature]
        b.Group = [a, feature]
        doc = document(a, b, feature)
        records = history.browser_records(doc)
        self.assertEqual(len([rec for rec in records if rec.obj is not None]), 3)
        parents = {rec.key: rec.parent for rec in records}
        for key in parents:
            visited = set()
            while key is not None:
                self.assertNotIn(key, visited)
                visited.add(key)
                key = parents[key]

    def test_suppression_requires_true_writable_bool(self):
        pad = Object("Pad")
        pad.Suppressed = False
        pad.getTypeIdOfProperty = lambda _name: "App::PropertyBool"
        pad.getPropertyStatus = lambda _name: []
        self.assertFalse(history.supports_suppression(pad))
        pad.PropertiesList = ["Suppressed"]
        self.assertTrue(history.supports_suppression(pad))
        pad.getPropertyStatus = lambda _name: ["ReadOnly"]
        self.assertFalse(history.supports_suppression(pad))
        pad.getPropertyStatus = lambda _name: []
        pad.getTypeIdOfProperty = lambda _name: "App::PropertyString"
        self.assertFalse(history.supports_suppression(pad))

    def test_error_status_is_not_hidden_by_suppression(self):
        pad = Object("Pad")
        pad.PropertiesList = ["Suppressed"]
        pad.Suppressed = True
        pad.getTypeIdOfProperty = lambda _name: "App::PropertyBool"
        pad.getPropertyStatus = lambda _name: []
        pad.getStatusString = lambda: "Pocket has no valid support"
        pad.isValid = lambda: False
        self.assertEqual(history.feature_state(pad), ("error", "Pocket has no valid support"))


if __name__ == "__main__":
    unittest.main()
