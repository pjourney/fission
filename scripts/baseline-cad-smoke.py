"""Repeatable native-engine smoke test for the untouched baseline and Fission.

Run using build/windows-release/bin/FreeCADCmd.exe scripts/baseline-cad-smoke.py.
Produces a real FCStd design plus STEP/STL interchange files and a JSON report.
"""

import json
import math
import os
from pathlib import Path

import FreeCAD as App
import Mesh
import Part
import Sketcher


output = Path(os.environ.get("FISSION_SMOKE_OUTPUT", "build/baseline-smoke")).resolve()
output.mkdir(parents=True, exist_ok=True)
checks = []


def check(condition, description):
    if not condition:
        raise AssertionError(description)
    checks.append(description)
    print("PASS:", description)


doc = App.newDocument("BaselineMechanicalDesign")
body = doc.addObject("PartDesign::Body", "Body")
sketch = body.newObject("Sketcher::SketchObject", "Sketch")
corners = [(-20, -10), (20, -10), (20, 10), (-20, 10)]
for i, point in enumerate(corners):
    end = corners[(i + 1) % 4]
    sketch.addGeometry(Part.LineSegment(App.Vector(*point, 0), App.Vector(*end, 0)), False)
for i in range(4):
    sketch.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
for i in (0, 2):
    sketch.addConstraint(Sketcher.Constraint("Horizontal", i))
for i in (1, 3):
    sketch.addConstraint(Sketcher.Constraint("Vertical", i))
sketch.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, -20.0))
sketch.addConstraint(Sketcher.Constraint("DistanceY", 0, 1, -10.0))
length_constraint = sketch.addConstraint(Sketcher.Constraint("Distance", 0, 40.0))
sketch.addConstraint(Sketcher.Constraint("Distance", 1, 20.0))
doc.recompute()
check(sketch.FullyConstrained, "Rectangle sketch is dimensioned and fully constrained")

extrude = body.newObject("PartDesign::Pad", "Extrude")
extrude.Profile = sketch
extrude.Length = 10
doc.recompute()
check(extrude.Shape.isValid(), "Sketch extrude produces a valid solid")
check(abs(extrude.Shape.Volume - 8000) < 1e-6, "Extruded volume matches the sketch dimensions")

vertical_edge = next(
    i for i, edge in enumerate(extrude.Shape.Edges, 1)
    if abs(edge.Length - 10) < 1e-7 and edge.BoundBox.ZLength > 9.99
)
fillet = body.newObject("PartDesign::Fillet", "Fillet")
fillet.Base = (extrude, [f"Edge{vertical_edge}"])
fillet.Radius = 1
doc.recompute()
check(fillet.Shape.isValid() and fillet.Shape.Volume < extrude.Shape.Volume, "Fillet updates the valid solid")

hole_sketch = body.newObject("Sketcher::SketchObject", "HoleSketch")
hole_sketch.Placement.Base.z = 10
hole_sketch.setExpression("Placement.Base.z", "Extrude.Length")
hole_sketch.addGeometry(Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 2), False)
hole_sketch.addConstraint(Sketcher.Constraint("Coincident", 0, 3, -1, 1))
hole_sketch.addConstraint(Sketcher.Constraint("Diameter", 0, 4.0))
doc.recompute()
hole = body.newObject("PartDesign::Hole", "Hole")
hole.Profile = hole_sketch
hole.Diameter = 4
hole.Depth = 5
hole.DepthType = 0
hole.DrillPoint = 0
body.Tip = hole
doc.recompute()
check(hole.Shape.isValid(), "Hole produces a valid final solid")
check(body.Tip == hole and body.Shape.isValid(), "Body history tip follows the final feature")
check(abs((fillet.Shape.Volume - hole.Shape.Volume) - math.pi * 4 * 5) < 1e-5, "Hole removes the specified cylindrical volume")

model_path = output / "mechanical-design.FCStd"
before_volume = hole.Shape.Volume
doc.saveAs(str(model_path))
App.closeDocument(doc.Name)
doc = App.openDocument(str(model_path))
check(doc.Hole.Shape.isValid() and abs(doc.Hole.Shape.Volume - before_volume) < 1e-6, "FCStd save and reopen preserve geometry")
doc.Sketch.setDatum(length_constraint, App.Units.Quantity("48 mm"))
doc.recompute()
check(doc.Extrude.Shape.isValid() and doc.Fillet.Shape.isValid() and doc.Hole.Shape.isValid(), "Editing the original sketch recomputes all downstream features")
check(doc.Hole.Shape.Volume > before_volume + 1500, "Downstream solid reflects the edited sketch dimension")
doc.save()

step_path = output / "mechanical-design.step"
stl_path = output / "mechanical-design.stl"
Part.export([doc.Hole], str(step_path))
Mesh.export([doc.Hole], str(stl_path))
step_shape = Part.Shape()
step_shape.read(str(step_path))
check(step_shape.isValid() and len(step_shape.Solids) == 1, "STEP export reimports as a valid solid")
check(abs(step_shape.Volume - doc.Hole.Shape.Volume) < 1e-4, "STEP interchange preserves the solid volume")
stl_mesh = Mesh.Mesh(str(stl_path))
check(stl_mesh.CountFacets > 0 and stl_mesh.isSolid(), "STL export reimports as a closed mesh")

report = {
    "passed": len(checks),
    "checks": checks,
    "freecad_version": App.Version(),
    "final_volume_mm3": doc.Hole.Shape.Volume,
    "features": [obj.Name for obj in doc.Body.Group],
    "artifacts": [str(model_path), str(step_path), str(stl_path)],
}
(output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
App.closeDocument(doc.Name)
print("BASELINE_CAD_SMOKE_OK", len(checks), "checks")
