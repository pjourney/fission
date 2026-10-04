# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real parametric test models, executed by Fission's embedded Python runtime."""

import math
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui
import Part
import Sketcher


def require(condition, description):
    if not condition:
        raise AssertionError(description)


def shape_signature(shape):
    require(not shape.isNull(), "Shape must not be null")
    return {
        "valid": bool(shape.isValid()),
        "volume": float(shape.Volume),
        "solids": len(shape.Solids),
        "faces": len(shape.Faces),
        "edges": len(shape.Edges),
        "vertices": len(shape.Vertexes),
        "bounds": [float(getattr(shape.BoundBox, name)) for name in ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax")],
    }


def compare_shapes(before, after, tolerance=1e-6):
    require(before["valid"] and after["valid"], "Both compared shapes must be valid")
    require(abs(before["volume"] - after["volume"]) <= tolerance * max(1.0, before["volume"]), "Shape volume changed unexpectedly")
    for name in ("solids", "faces", "edges", "vertices"):
        require(before[name] == after[name], "Shape topology changed: " + name)
    require(all(abs(left - right) < tolerance for left, right in zip(before["bounds"], after["bounds"])), "Shape bounds changed unexpectedly")


def constrained_rectangle(sketch, width=60.0, height=40.0):
    """A dimensioned closed rectangle, centered with native expressions."""
    corners = [(-width / 2, -height / 2), (width / 2, -height / 2), (width / 2, height / 2), (-width / 2, height / 2)]
    geometry = []
    for index, point in enumerate(corners):
        next_point = corners[(index + 1) % 4]
        geometry.append(Part.LineSegment(App.Vector(point[0], point[1], 0), App.Vector(next_point[0], next_point[1], 0)))
    sketch.addGeometry(geometry, False)
    constraints = [Sketcher.Constraint("Coincident", index, 2, (index + 1) % 4, 1) for index in range(4)]
    constraints.extend([Sketcher.Constraint("Horizontal", 0), Sketcher.Constraint("Vertical", 1), Sketcher.Constraint("Horizontal", 2), Sketcher.Constraint("Vertical", 3)])
    constraints.extend([Sketcher.Constraint("Distance", 0, width), Sketcher.Constraint("Distance", 1, height), Sketcher.Constraint("DistanceX", 0, 1, -width / 2), Sketcher.Constraint("DistanceY", 0, 1, -height / 2)])
    sketch.addConstraint(constraints)
    for index, name in ((8, "Width"), (9, "Height"), (10, "OriginX"), (11, "OriginY")):
        sketch.renameConstraint(index, name)
    sketch.setExpression("Constraints.OriginX", "-Constraints.Width / 2")
    sketch.setExpression("Constraints.OriginY", "-Constraints.Height / 2")
    require(sketch.solve() == 0, "Rectangle solver must succeed")
    return sketch


def create_workflow(name="FissionWorkflow"):
    """Sketch → extrude → fillet → face sketch → hole → rectangular pattern."""
    doc = App.newDocument(name)
    component = doc.addObject("App::Part", "Component")
    component.Label = "Machined plate"
    body = doc.addObject("PartDesign::Body", "Body")
    component.addObject(body)
    sketch = body.newObject("Sketcher::SketchObject", "BaseSketch")
    sketch.Label = "Centered rectangle · 60 × 40"
    constrained_rectangle(sketch)
    doc.recompute()
    require(sketch.DoF == 0, "Base rectangle must be fully constrained")
    pad = body.newObject("PartDesign::Pad", "Extrude")
    pad.Profile = sketch
    pad.Length = 10.0
    doc.recompute()
    require(pad.isValid() and pad.Shape.isValid(), "Extrusion must create valid geometry")
    require(abs(pad.Shape.Volume - 24000.0) < 1e-6, "Extrusion volume must equal 60 × 40 × 10")
    vertical = ["Edge{}".format(index + 1) for index, edge in enumerate(pad.Shape.Edges) if edge.BoundBox.ZLength > 9.9 and edge.BoundBox.XLength < 1e-6 and edge.BoundBox.YLength < 1e-6]
    require(len(vertical) == 4, "Rectangle extrusion must have four vertical edges")
    fillet = body.newObject("PartDesign::Fillet", "CornerFillet")
    fillet.Base = (pad, vertical)
    fillet.Radius = 1.5
    doc.recompute()
    require(fillet.isValid() and fillet.Shape.isValid(), "Corner fillet must be valid")
    require(0 < fillet.Shape.Volume < pad.Shape.Volume, "Fillet must change the extrusion")
    top_faces = ["Face{}".format(index + 1) for index, face in enumerate(fillet.Shape.Faces) if abs(face.BoundBox.ZMin - 10.0) < 1e-6 and abs(face.BoundBox.ZMax - 10.0) < 1e-6]
    require(len(top_faces) == 1, "Fillet must retain one planar top face")
    hole_sketch = body.newObject("Sketcher::SketchObject", "HoleSketch")
    hole_sketch.AttachmentSupport = (fillet, [top_faces[0]])
    hole_sketch.MapMode = "FlatFace"
    doc.recompute()
    local = hole_sketch.Placement.inverse().multVec(App.Vector(-15, 0, 10))
    hole_sketch.addGeometry(Part.Circle(App.Vector(local.x, local.y, 0), App.Vector(0, 0, 1), 2), False)
    # The hole profile is fully constrained in its attached face coordinate frame.
    hole_sketch.addConstraint(Sketcher.Constraint("Diameter", 0, 4.0))
    hole_sketch.addConstraint(Sketcher.Constraint("DistanceX", 0, 3, local.x))
    hole_sketch.addConstraint(Sketcher.Constraint("DistanceY", 0, 3, local.y))
    doc.recompute()
    require(hole_sketch.solve() == 0 and hole_sketch.DoF == 0, "Hole sketch must be fully constrained")
    hole = body.newObject("PartDesign::Hole", "Hole")
    hole.Profile = hole_sketch
    hole.Diameter = 4.0
    hole.DepthType = 1  # Native Through all enumeration.
    hole.ThreadType = 0
    hole.HoleCutType = 0
    hole.DrillPoint = 0
    doc.recompute()
    require(hole.isValid() and hole.Shape.isValid(), "Hole must create valid geometry")
    expected_hole_volume = math.pi * 2**2 * 10
    require(abs(fillet.Shape.Volume - hole.Shape.Volume - expected_hole_volume) < 1e-5, "Hole must remove a 4 mm through cylinder")
    pattern = body.newObject("PartDesign::LinearPattern", "HolePattern")
    pattern.Originals = [hole]
    x_axis = next(feature for feature in body.Origin.OriginFeatures if getattr(feature, "Role", "") == "X_Axis")
    pattern.Direction = (x_axis, [""])
    pattern.Length = 30.0
    pattern.Occurrences = 3
    body.Tip = pattern
    doc.recompute()
    require(pattern.isValid() and pattern.Shape.isValid(), "Linear pattern must create valid geometry")
    require(abs(fillet.Shape.Volume - pattern.Shape.Volume - 3 * expected_hole_volume) < 1e-5, "Pattern must contain three through holes")
    require(len(body.Shape.Solids) == 1, "Machined plate must remain a single solid")
    compare_shapes(shape_signature(pattern.Shape), shape_signature(body.Shape))
    for obj in (sketch, pad, fillet, hole_sketch, hole):
        obj.ViewObject.Visibility = False
    body.ViewObject.Visibility = True
    pattern.ViewObject.Visibility = True
    Gui.activeDocument().activeView().setActiveObject("part", component)
    Gui.activeDocument().activeView().setActiveObject("pdbody", body)
    Gui.activeDocument().activeView().viewAxonometric()
    Gui.activeDocument().activeView().fitAll()
    return doc


def save_and_reopen(doc, path):
    path = Path(path).resolve()
    before = shape_signature(doc.Body.Shape)
    doc.saveAs(str(path))
    App.closeDocument(doc.Name)
    reopened = App.openDocument(str(path))
    reopened.recompute()
    compare_shapes(before, shape_signature(reopened.Body.Shape))
    return reopened


def export_and_reimport(doc, directory):
    import Import
    import Mesh
    directory = Path(directory).resolve()
    step_file = directory / "machined-plate.step"
    stl_file = directory / "machined-plate.stl"
    Import.export([doc.Body], str(step_file))
    Mesh.export([doc.Body], str(stl_file))
    require(step_file.stat().st_size > 1000, "STEP export must contain geometry")
    require(stl_file.stat().st_size > 1000, "STL export must contain geometry")
    step_doc = App.newDocument("StepReimport")
    Import.insert(str(step_file), step_doc.Name)
    step_doc.recompute()
    step_shapes = [obj.Shape for obj in step_doc.Objects if hasattr(obj, "Shape") and not obj.Shape.isNull() and len(obj.Shape.Solids) and not any(hasattr(parent, "Shape") and not parent.Shape.isNull() and len(parent.Shape.Solids) for parent in obj.InList)]
    require(step_shapes, "STEP reimport must contain a root shape")
    step_volume = sum(shape.Volume for shape in step_shapes)
    require(abs(step_volume - doc.Body.Shape.Volume) < 1e-4, "STEP roundtrip must preserve volume")
    require(all(shape.isValid() for shape in step_shapes), "STEP roundtrip geometry must be valid")
    step_doc.saveAs(str(directory / "step-reimport.FCStd"))
    mesh_doc = App.newDocument("StlReimport")
    Mesh.insert(str(stl_file), mesh_doc.Name)
    mesh_objects = [obj for obj in mesh_doc.Objects if hasattr(obj, "Mesh")]
    require(mesh_objects, "STL reimport must contain a mesh")
    require(sum(obj.Mesh.CountFacets for obj in mesh_objects) > 12, "STL mesh must have real tessellated geometry")
    require(all(obj.Mesh.isSolid() for obj in mesh_objects), "STL mesh must be watertight")
    mesh_doc.saveAs(str(directory / "stl-reimport.FCStd"))
    App.closeDocument(step_doc.Name)
    App.closeDocument(mesh_doc.Name)
    App.setActiveDocument(doc.Name)
    return {"step_bytes": step_file.stat().st_size, "stl_bytes": stl_file.stat().st_size, "step_volume": step_volume}


def upstream_compatibility(root, directory):
    source = Path(root) / "upstream-src/data/examples/PartDesignExample.FCStd"
    require(source.is_file(), "Upstream PartDesign example must be available")
    doc = App.openDocument(str(source))
    def signatures(document):
        return {obj.Name: shape_signature(obj.Shape) for obj in document.Objects if hasattr(obj, "Shape") and not obj.Shape.isNull() and len(obj.Shape.Solids)}
    before = signatures(doc)
    require(before, "Upstream fixture must contain solid geometry")
    output = Path(directory) / "upstream-PartDesignExample-roundtrip.FCStd"
    doc.saveAs(str(output))
    App.closeDocument(doc.Name)
    reopened = App.openDocument(str(output))
    after = signatures(reopened)
    require(set(before) == set(after), "Upstream model objects must survive Fission save/reopen")
    for name in before:
        compare_shapes(before[name], after[name])
    App.closeDocument(reopened.Name)
    return {"fixture": str(source.resolve()), "solid_objects": len(before), "objects": list(before)}
