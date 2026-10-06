# SPDX-License-Identifier: LGPL-2.1-or-later
"""Native subtractive modeling through Fission's actual Cut dropdown.

Only fixture geometry is created through the CAD API. Each tested cut starts
with a real Qt menu click, edits the native task, and retains native history.
"""
import math
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui
import Part
import Sketcher
from PySide import QtCore, QtWidgets

import cad_workflows as cad
from search_workflows import _design
from interactive_workflow import _edited_feature, _finish_task, _set_quantity, _task_widget
from ribbon_workflows import _choose, QtTest


def _base(doc):
    body = doc.Body
    base = body.newObject("PartDesign::AdditiveBox", "CutStock")
    base.Length = base.Width = base.Height = 10
    base.Placement = App.Placement(App.Vector(-5, -5, 0), App.Rotation())
    doc.recompute()
    cad.require(base.Shape.isValid() and abs(base.Shape.Volume - 1000) < 1e-7,
                "Native fixture must be a valid 10 mm stock cube")
    return body, base


def _circle(body, name, radius, z=0):
    sketch = body.newObject("Sketcher::SketchObject", name)
    sketch.Placement.Base.z = z
    sketch.addGeometry(Part.Circle(App.Vector(), App.Vector(0, 0, 1), radius), False)
    sketch.addConstraint(Sketcher.Constraint("Coincident", 0, 3, -1, 1))
    radius_index = sketch.addConstraint(Sketcher.Constraint("Radius", 0, radius))
    sketch.renameConstraint(radius_index, "Radius")
    cad.require(sketch.solve() == 0 and sketch.DoF == 0,
                "Circle fixture must retain a fully constrained native radius")
    return sketch, radius_index


def _rectangle(body):
    sketch = body.newObject("Sketcher::SketchObject", "GrooveProfile")
    # The sketch V-axis passes through the stock center, so both halves of the
    # revolved annulus fit in the cube rather than lying below its bottom face.
    sketch.Placement.Base.z = 5
    corners = [(2, -1), (3, -1), (3, 1), (2, 1)]
    sketch.addGeometry([Part.LineSegment(App.Vector(*point, 0),
                                        App.Vector(*corners[(index + 1) % 4], 0))
                        for index, point in enumerate(corners)], False)
    sketch.addConstraint([Sketcher.Constraint("Coincident", index, 2, (index + 1) % 4, 1)
                          for index in range(4)] +
                         [Sketcher.Constraint("Horizontal", 0), Sketcher.Constraint("Vertical", 1),
                          Sketcher.Constraint("Horizontal", 2), Sketcher.Constraint("Vertical", 3),
                          Sketcher.Constraint("Distance", 0, 1), Sketcher.Constraint("Distance", 1, 2),
                          Sketcher.Constraint("DistanceX", 0, 1, 2),
                          Sketcher.Constraint("DistanceY", 0, 1, -1)])
    sketch.renameConstraint(8, "Width")
    cad.require(sketch.solve() == 0 and sketch.DoF == 0,
                "Groove fixture must retain a dimensioned closed native profile")
    return sketch


def _select(controller, doc, base, objects, command, settle):
    doc.Body.Tip = base
    doc.recompute()
    Gui.Selection.clearSelection()
    for obj in objects:
        Gui.Selection.addSelection(obj)
    controller.refresh_command_state()
    cad.require(controller.command_available(command),
                "Cut dropdown command must also be ready in S search: " + command)
    _choose(controller, "Fission_Cut", command, settle)


def _volume(feature, expected, message):
    cad.require(feature.Shape.isValid() and len(feature.Shape.Solids) == 1
                and abs(feature.Shape.Volume - expected) < 1e-6, message)


def _cancel(doc, body, names, before, undo, task, settle):
    _finish_task(doc, task, settle, False)
    cad.require(sorted(obj.Name for obj in doc.Objects) == names and doc.UndoCount == undo,
                "Native cut Cancel must remove the preview without committing an Undo step")
    cad.compare_shapes(before, cad.shape_signature(body.Shape))


def _history(doc, body, feature, before, undo, settle):
    cad.require(body.Tip is feature and doc.UndoCount == undo + 1,
                "Native cut OK must commit exactly one feature and one Undo step")
    after = cad.shape_signature(body.Shape)
    doc.undo()
    settle(180)
    doc.recompute()
    cad.compare_shapes(before, cad.shape_signature(body.Shape))
    doc.redo()
    settle(180)
    doc.recompute()
    cad.compare_shapes(after, cad.shape_signature(body.Shape))
    return after


def _reopen(doc, body, feature, sources, after, output, filename, settle):
    path = Path(output) / filename
    # Capture names before closing; native object wrappers become invalid then.
    names = {key: value.Name for key, value in sources.items()}
    names.update(body=body.Name, feature=feature.Name)
    doc.saveAs(str(path))
    App.closeDocument(doc.Name)
    reopened = App.openDocument(str(path))
    settle(180)
    objects = {key: reopened.getObject(name) for key, name in names.items()}
    cad.require(all(value is not None for value in objects.values()),
                "FCStd reopen must retain native stock, sources, and subtractive feature")
    cad.compare_shapes(after, cad.shape_signature(objects["body"].Shape))
    cad.require(objects["body"].Tip is objects["feature"],
                "FCStd reopen must retain the subtractive feature as Body Tip")
    return reopened, objects, path


def revolve_cut(controller, settle, output):
    with _design(controller, settle) as doc:
        body, base = _base(doc)
        profile = _rectangle(body)
        body.Tip = base
        doc.recompute()
        before = cad.shape_signature(body.Shape)
        names, undo = sorted(obj.Name for obj in doc.Objects), doc.UndoCount
        for accept in (False, True):
            _select(controller, doc, base, [profile], "Fission_RevolveCut", settle)
            cut, task = _edited_feature(doc, "PartDesign::Groove", controller)
            cad.require(cut.Profile[0] is profile and cut.ReferenceAxis[0] is profile,
                        "Revolve Cut must retain its native profile and sketch axis")
            _volume(cut, 1000 - 10 * math.pi, "Native Groove must preview the complete annular cut")
            _set_quantity(task, "revolveAngle", 180, settle)
            _volume(cut, 1000 - 5 * math.pi, "Native Groove angle control must preview a half annular cut")
            if not accept:
                _cancel(doc, body, names, before, undo, task, settle)
            else:
                _finish_task(doc, task, settle, True)
        after = _history(doc, body, cut, before, undo, settle)
        reopened, objects, path = _reopen(doc, body, cut, {"profile": profile}, after,
                                           output, "solid-revolve-cut.FCStd", settle)
        objects["profile"].setDatum(8, App.Units.Quantity("1.5 mm"))
        reopened.recompute()
        cad.require(objects["profile"].solve() == 0,
                    "Reopened Groove source dimensions must remain solver valid")
        _volume(objects["feature"], 1000 - 8.25 * math.pi,
                "Reopened Groove must recompute from its edited native profile width")
        return {"feature_type": "PartDesign::Groove", "angle": 180, "cut": after,
                "native_cancel_undo_redo": True, "search_readiness": True,
                "parametric_reopen": True, "file": str(path)}


def sweep_cut(controller, settle, output):
    with _design(controller, settle) as doc:
        body, base = _base(doc)
        profile, radius_index = _circle(body, "SweepProfile", 1)
        spine = body.newObject("Sketcher::SketchObject", "SweepPath")
        spine.Placement.Rotation = App.Rotation(App.Vector(1, 0, 0), 90)
        spine.addGeometry(Part.LineSegment(App.Vector(), App.Vector(0, 10, 0)), False)
        spine.addConstraint(Sketcher.Constraint("Block", 0))
        body.Tip = base
        doc.recompute()
        before = cad.shape_signature(body.Shape)
        names, undo = sorted(obj.Name for obj in doc.Objects), doc.UndoCount
        for accept in (False, True):
            _select(controller, doc, base, [profile, spine], "Fission_SweepCut", settle)
            cut, task = _edited_feature(doc, "PartDesign::SubtractivePipe", controller)
            cad.require(cut.Profile[0] is profile and cut.Spine[0] is spine,
                        "Sweep Cut must initialize the selected native profile and path")
            _volume(cut, 1000 - 10 * math.pi, "Native Sweep Cut must preview the cylindrical channel")
            transition = _task_widget(task, "comboBoxTransition")
            cad.require(isinstance(transition, QtWidgets.QComboBox) and transition.count() == 3,
                        "Native sweep task must expose its actual path transition choices")
            transition.setFocus(QtCore.Qt.OtherFocusReason)
            QtTest.QTest.keyClick(transition, QtCore.Qt.Key_End)
            settle(160)
            cad.require(transition.currentIndex() == 2 and str(cut.Transition) == "Round corner",
                        "Native transition control must update the parametric sweep feature")
            _volume(cut, 1000 - 10 * math.pi,
                    "Straight sweep must remain valid after its native transition changes")
            if not accept:
                _cancel(doc, body, names, before, undo, task, settle)
            else:
                _finish_task(doc, task, settle, True)
        after = _history(doc, body, cut, before, undo, settle)
        reopened, objects, path = _reopen(doc, body, cut, {"profile": profile, "spine": spine}, after,
                                           output, "solid-sweep-cut.FCStd", settle)
        cad.require(objects["feature"].Spine[0] is objects["spine"],
                    "Reopened sweep must retain its source path link")
        objects["profile"].setDatum(radius_index, App.Units.Quantity("1.5 mm"))
        reopened.recompute()
        _volume(objects["feature"], 1000 - 22.5 * math.pi,
                "Reopened Sweep Cut must recompute from its edited native profile radius")
        return {"feature_type": "PartDesign::SubtractivePipe", "cut": after,
                "transition": "Round corner", "native_cancel_undo_redo": True,
                "search_readiness": True, "parametric_reopen": True, "file": str(path)}


def loft_cut(controller, settle, output):
    with _design(controller, settle) as doc:
        body, base = _base(doc)
        profile, _ = _circle(body, "LoftProfile", 2)
        section, radius_index = _circle(body, "LoftSection", 1, 10)
        body.Tip = base
        doc.recompute()
        before = cad.shape_signature(body.Shape)
        names, undo = sorted(obj.Name for obj in doc.Objects), doc.UndoCount
        for accept in (False, True):
            _select(controller, doc, base, [profile, section], "Fission_LoftCut", settle)
            cut, task = _edited_feature(doc, "PartDesign::SubtractiveLoft", controller)
            cad.require(cut.Profile[0] is profile and len(cut.Sections) == 1
                        and cut.Sections[0][0] is section,
                        "Loft Cut must initialize both selected native profile sections")
            _volume(cut, 1000 - 70 * math.pi / 3,
                    "Native Loft Cut must preview the analytic conical-frustum channel")
            ruled = _task_widget(task, "checkBoxRuled")
            cad.require(isinstance(ruled, QtWidgets.QCheckBox) and not ruled.isChecked(),
                        "Native loft task must expose its actual ruled control")
            QtTest.QTest.mouseClick(ruled, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier,
                                   QtCore.QPoint(8, ruled.height() // 2))
            settle(160)
            cad.require(ruled.isChecked() and cut.Ruled,
                        "Native ruled checkbox must update the parametric loft feature")
            _volume(cut, 1000 - 70 * math.pi / 3,
                    "Native ruled loft must retain the conical-frustum channel")
            if not accept:
                _cancel(doc, body, names, before, undo, task, settle)
            else:
                _finish_task(doc, task, settle, True)
        after = _history(doc, body, cut, before, undo, settle)
        reopened, objects, path = _reopen(doc, body, cut, {"profile": profile, "section": section}, after,
                                           output, "solid-loft-cut.FCStd", settle)
        cad.require(objects["feature"].Sections[0][0] is objects["section"]
                    and objects["feature"].Ruled,
                    "Reopened loft must retain its section link and task option")
        objects["section"].setDatum(radius_index, App.Units.Quantity("1.5 mm"))
        reopened.recompute()
        _volume(objects["feature"], 1000 - 92.5 * math.pi / 3,
                "Reopened Loft Cut must recompute from its edited native section radius")
        return {"feature_type": "PartDesign::SubtractiveLoft", "cut": after, "ruled": True,
                "native_cancel_undo_redo": True, "search_readiness": True,
                "parametric_reopen": True, "file": str(path)}
