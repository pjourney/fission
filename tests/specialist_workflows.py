# SPDX-License-Identifier: LGPL-2.1-or-later
"""Native Surface/Mesh acceptance models for Fission's embedded Python.

Set ``FISSION_SPECIALIST_AUTORUN=1`` and run
``FissionCmd.exe tests/specialist_workflows.py``. A GUI harness can
call ``run_all(output_dir)`` and ``audit_gui_catalog(controller)`` separately.
The geometry suite does not import FreeCADGui, activate workbenches, or open
dialogs. Its outputs use real native features and native interchange writers.
"""

import json
import math
import os
from pathlib import Path
import traceback

import FreeCAD as App
import Mesh
import MeshPart
import Part
import Surface  # Registers the native Surface:: document object types.


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "test-output" / "specialist"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def _near(actual, expected, relative=1e-6, absolute=1e-6):
    return abs(actual - expected) <= max(absolute, relative * abs(expected))


def shape_signature(shape):
    require(not shape.isNull(), "Native shape is null")
    return {
        "valid": bool(shape.isValid()),
        "closed": bool(shape.isClosed()),
        "type": shape.ShapeType,
        "volume_mm3": float(shape.Volume),
        "area_mm2": float(shape.Area),
        "solids": len(shape.Solids),
        "shells": len(shape.Shells),
        "faces": len(shape.Faces),
        "edges": len(shape.Edges),
        "vertices": len(shape.Vertexes),
        "bounds_mm": [float(getattr(shape.BoundBox, field)) for field in
                      ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax")],
    }


def mesh_signature(mesh):
    return {
        "facets": mesh.CountFacets,
        "points": mesh.CountPoints,
        "closed": bool(mesh.isSolid()),
        "nonmanifold": bool(mesh.hasNonManifolds()),
        "self_intersections": bool(mesh.hasSelfIntersections()),
        "volume_mm3": float(mesh.Volume),
        "bounds_mm": [float(getattr(mesh.BoundBox, field)) for field in
                      ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax")],
    }


def compare_shapes(before, after):
    require(before["valid"] and after["valid"], "Saved and reopened B-reps must be valid")
    for field in ("type", "closed", "solids", "shells", "faces", "edges", "vertices"):
        require(before[field] == after[field], "FCStd changed B-rep topology: " + field)
    for field in ("volume_mm3", "area_mm2"):
        require(_near(before[field], after[field]), "FCStd changed B-rep geometry: " + field)
    require(all(_near(a, b) for a, b in zip(before["bounds_mm"], after["bounds_mm"])),
            "FCStd changed B-rep bounds")


def _visible(obj, visible):
    # Native headless ViewObjects are absent; this also supports the GUI harness.
    if getattr(obj, "ViewObject", None) is not None:
        obj.ViewObject.Visibility = visible


def _box_contours(width, depth, height):
    # Consistent outward orientations: bottom, top, front, right, back, left.
    vertices = [(0, 0, 0), (width, 0, 0), (width, depth, 0), (0, depth, 0),
                (0, 0, height), (width, 0, height),
                (width, depth, height), (0, depth, height)]
    loops = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    for indices in loops:
        points = [App.Vector(*vertices[index]) for index in indices]
        yield Part.makePolygon(points + points[:1])


def create_surface_workflow(name="SpecialistSurface", dimensions=(20.0, 15.0, 10.0)):
    """Six native Surface::Filling patches -> Surface::Sewing -> Part solid.

    Part_MakeSolid creates a static Part::Feature in upstream FreeCAD. The test
    retains that behavior instead of inventing a parametric solid conversion.
    Boundary and sewing dependencies remain genuine native document links.
    """
    doc = App.newDocument(name)
    surfaces = []
    for index, wire in enumerate(_box_contours(*dimensions), 1):
        boundary = doc.addObject("Part::Feature", "Boundary{}".format(index))
        boundary.Label = "Face {} boundary".format(index)
        boundary.Shape = wire
        filling = doc.addObject("Surface::Filling", "Surface{}".format(index))
        filling.BoundaryEdges = [(boundary, ["Edge1", "Edge2", "Edge3", "Edge4"])]
        filling.BoundaryOrder = [0, 0, 0, 0]
        filling.BoundaryFaces = ["", "", "", ""]
        surfaces.append(filling)
        _visible(boundary, False)
        _visible(filling, False)
    doc.recompute()
    for filling in surfaces:
        require(filling.isValid() and filling.Shape.isValid(), filling.Name + " filling failed")
        require(len(filling.Shape.Faces) == 1 and not filling.Shape.Solids,
                "A surface filling must produce one face, not a solid")
    sewn = doc.addObject("Surface::Sewing", "StitchedShell")
    sewn.ShapeList = [(filling, ["Face1"]) for filling in surfaces]
    sewn.Tolerance = 0.0001
    doc.recompute()
    require(sewn.isValid() and sewn.Shape.isValid(), "Native surface sewing failed")
    require(len(sewn.Shape.Shells) == 1 and sewn.Shape.isClosed(),
            "Six sewn patches must form one closed shell")
    require(not sewn.Shape.Solids, "Sewing must not silently create a solid")
    solid = doc.addObject("Part::Feature", "ConvertedSolid")
    solid.Shape = Part.Solid(sewn.Shape.Shells[0])
    doc.recompute()
    require(solid.Shape.isValid() and len(solid.Shape.Solids) == 1,
            "A closed sewn shell must convert to one valid solid")
    require(_near(solid.Shape.Volume, math.prod(dimensions), relative=1e-5),
            "Surface envelope volume must match its boundaries")
    require(set(sewn.OutList) == set(surfaces), "Sewing must retain all native surface dependencies")
    _visible(sewn, False)
    _visible(solid, True)
    return doc


def surface_case(output):
    doc = create_surface_workflow()
    name = doc.Name
    try:
        original = shape_signature(doc.ConvertedSolid.Shape)
        saved = output / "surface-envelope.FCStd"
        doc.saveAs(str(saved))
        App.closeDocument(name)
        doc = App.openDocument(str(saved))
        name = doc.Name
        # Force native Filling and Sewing execution rather than trusting saved B-reps.
        for obj in doc.Objects:
            if obj.TypeId.startswith("Surface::"):
                obj.touch()
        doc.recompute()
        compare_shapes(original, shape_signature(doc.ConvertedSolid.Shape))
        require(doc.StitchedShell.Shape.isClosed() and doc.StitchedShell.Shape.isValid(),
                "Saved native sewing must recompute as a closed shell")
        require(all(obj.TypeId == "Surface::Filling" for obj in doc.StitchedShell.OutList),
                "FCStd must preserve native sewing link types")
        # Changing real source contours must regenerate the native Surface features.
        for index, wire in enumerate(_box_contours(24.0, 15.0, 10.0), 1):
            doc.getObject("Boundary{}".format(index)).Shape = wire
        doc.recompute()
        require(doc.StitchedShell.Shape.isClosed() and doc.StitchedShell.Shape.isValid(),
                "Boundary edits must regenerate the sewn shell")
        # Repeat the native static conversion after editing its source shell.
        doc.ConvertedSolid.Shape = Part.Solid(doc.StitchedShell.Shape.Shells[0])
        doc.recompute()
        require(_near(doc.ConvertedSolid.Shape.Volume, 3600.0, relative=1e-5),
                "Updated surface boundaries must yield the enlarged envelope")
        doc.save()
        after_edit = shape_signature(doc.ConvertedSolid.Shape)
        step = output / "surface-envelope.step"
        Part.export([doc.ConvertedSolid], str(step))
        restored = Part.Shape()
        restored.read(str(step))
        require(restored.isValid() and len(restored.Solids) == 1,
                "Surface STEP must reimport as one valid solid")
        require(_near(restored.Volume, after_edit["volume_mm3"], relative=1e-5),
                "Surface STEP must preserve volume")
        App.closeDocument(name)
        doc = App.openDocument(str(saved))
        name = doc.Name
        doc.recompute()
        compare_shapes(after_edit, shape_signature(doc.ConvertedSolid.Shape))
        return {"surface_features": 6, "native_sewing": doc.StitchedShell.TypeId,
                "initial": original, "edited": after_edit,
                "artifacts": [str(saved), str(step)]}
    finally:
        if name in App.listDocuments():
            App.closeDocument(name)


def create_mesh_workflow(name="SpecialistMesh"):
    """Native cut solid -> MeshPart tessellation -> sewn B-rep -> valid solid."""
    doc = App.newDocument(name)
    box = doc.addObject("Part::Box", "SourceBox")
    box.Length, box.Width, box.Height = 20.0, 15.0, 10.0
    hole = doc.addObject("Part::Cylinder", "BoreTool")
    hole.Radius, hole.Height = 2.0, 10.0
    hole.Placement.Base = App.Vector(10, 7.5, 0)
    source = doc.addObject("Part::Cut", "SourceSolid")
    source.Base, source.Tool = box, hole
    doc.recompute()
    require(source.Shape.isValid() and len(source.Shape.Solids) == 1,
            "Mesh source must be a valid bored solid")
    mesh_obj = doc.addObject("Mesh::Feature", "TessellatedMesh")
    mesh_obj.Mesh = MeshPart.meshFromShape(Shape=source.Shape, LinearDeflection=0.1,
                                         AngularDeflection=0.2, Relative=False)
    mesh = mesh_obj.Mesh
    require(mesh.CountFacets > 12 and mesh.isSolid(), "Tessellation must create a closed curved mesh")
    require(not mesh.hasNonManifolds() and not mesh.hasSelfIntersections(),
            "Tessellation must be manifold and free of self intersections")
    require(_near(mesh.Volume, source.Shape.Volume, relative=0.002),
            "Tessellated volume must stay within 0.2% of the analytic solid")
    converted = doc.addObject("Part::Feature", "MeshToShape")
    shape = Part.Shape()
    # Same API invoked by native PartGui::ShapeFromMesh with its Sew option checked.
    shape.makeShapeFromMesh(mesh.Topology, 0.0001, True)
    converted.Shape = shape
    require(shape.isValid() and shape.isClosed() and len(shape.Shells) == 1,
            "Mesh to Shape with sewing must yield one closed valid shell")
    solid = doc.addObject("Part::Feature", "ConvertedSolid")
    solid.Shape = Part.Solid(shape.Shells[0])
    doc.recompute()
    require(solid.Shape.isValid() and len(solid.Shape.Solids) == 1,
            "Converted mesh shell must become one valid solid")
    # Mesh.Volume is computed with mesh float precision; OCC accumulates doubles.
    require(_near(solid.Shape.Volume, mesh.Volume, relative=1e-6),
            "Native B-rep conversion must preserve the faceted mesh volume: B-rep={} mesh={}".format(solid.Shape.Volume, mesh.Volume))
    for obj in (box, hole, source, mesh_obj, converted):
        _visible(obj, False)
    _visible(solid, True)
    return doc


def mesh_case(output):
    doc = create_mesh_workflow()
    name = doc.Name
    try:
        before_shape = shape_signature(doc.ConvertedSolid.Shape)
        before_mesh = mesh_signature(doc.TessellatedMesh.Mesh)
        # Missing facets are real open boundaries, not a visual visibility state.
        open_mesh = doc.TessellatedMesh.Mesh.copy()
        open_mesh.removeFacets([0])
        require(not open_mesh.isSolid(), "Removing one facet must expose an open mesh")
        open_shape = Part.Shape()
        open_shape.makeShapeFromMesh(open_mesh.Topology, 0.0001, True)
        require(not open_shape.isClosed(), "Sewing cannot close a genuinely missing mesh facet")
        invalid_solid = Part.Solid(open_shape.Shells[0])
        require(not invalid_solid.isValid(), "An open shell must not be accepted as a valid solid")
        saved = output / "mesh-conversion.FCStd"
        stl, ply = output / "bored-mesh.stl", output / "bored-mesh.ply"
        doc.saveAs(str(saved))
        Mesh.export([doc.TessellatedMesh], str(stl))
        Mesh.export([doc.TessellatedMesh], str(ply))
        for path in (stl, ply):
            require(path.stat().st_size > 1000, "Mesh export must contain real data: " + path.name)
            restored_mesh = Mesh.Mesh(str(path))
            require(restored_mesh.isSolid() and restored_mesh.CountFacets == before_mesh["facets"],
                    path.name + " must reimport with closed topology and the same facet count")
            require(_near(restored_mesh.Volume, before_mesh["volume_mm3"], relative=1e-5),
                    path.name + " must preserve mesh volume")
        App.closeDocument(name)
        doc = App.openDocument(str(saved))
        name = doc.Name
        doc.recompute()
        compare_shapes(before_shape, shape_signature(doc.ConvertedSolid.Shape))
        after_mesh = mesh_signature(doc.TessellatedMesh.Mesh)
        require(before_mesh == after_mesh, "FCStd must preserve exact native mesh data")
        require(doc.SourceSolid.Base == doc.SourceBox and doc.SourceSolid.Tool == doc.BoreTool,
                "FCStd must retain native parametric source cut links")
        step = output / "mesh-converted-solid.step"
        Part.export([doc.ConvertedSolid], str(step))
        step_shape = Part.Shape()
        step_shape.read(str(step))
        require(step_shape.isValid() and len(step_shape.Solids) == 1,
                "Faceted solid STEP must reimport as one valid solid")
        require(_near(step_shape.Volume, before_shape["volume_mm3"], relative=1e-5),
                "Faceted solid STEP must preserve volume")
        return {"mesh": after_mesh, "converted": before_shape,
                "open_mesh_rejected": True,
                "artifacts": [str(saved), str(stl), str(ply), str(step)]}
    finally:
        if name in App.listDocuments():
            App.closeDocument(name)


def audit_gui_catalog(controller):
    """Check current ribbon command IDs with the real loaded GUI registry.

    No tools are invoked; callers must have initialized Fission's command modules.
    Keep unavailable tools visible in the result so they cannot be counted as pass.
    """
    import FreeCADGui as Gui
    from fission.shell import TABS, command_spec
    result = {}
    for tab in ("SURFACE", "MESH"):
        tools = []
        for group, items in TABS[tab]:
            for item in items:
                command_id, label = command_spec(item)
                command = Gui.Command.get(command_id)
                tools.append({"group": group, "id": command_id, "label": label,
                              "registered": bool(command),
                              "actions": len(command.getAction()) if command else 0})
        result[tab] = tools
    return result


def run_stitch(controller, settle, output):
    """Accept the actual Fission Stitch dialog; verify native Undo and restore.

    ``settle(milliseconds)`` is the serial GUI harness's event-processing helper.
    The modal dialog is operated by Qt mouse events while Gui.runCommand enters
    its normal nested event loop. No controller operation is mocked.
    """
    import importlib
    import time
    import FreeCADGui as Gui
    from PySide import QtCore, QtWidgets
    try:
        from PySide import QtTest
    except ImportError:
        try:
            QtTest = importlib.import_module("PySide6.QtTest")
        except ImportError:
            QtTest = importlib.import_module("PySide2.QtTest")

    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    previous = App.ActiveDocument.Name if App.ActiveDocument else None
    previous_tab = getattr(controller, "_design_tab", "SOLID")
    doc = None
    timer = None
    details = {}

    def activate_tab(title):
        indices = [index for index in range(controller.tabs.count())
                   if controller.tabs.tabText(index) == title]
        require(len(indices) == 1, "Expected one Fission ribbon tab: " + title)
        controller.tabs.setCurrentIndex(indices[0])
        settle(120)
        controller.refresh_context()

    def operate_dialog(accept):
        nonlocal timer
        state = {"seen": False, "clicked": False, "errors": []}
        started = time.monotonic()
        timer = QtCore.QTimer(controller.main)
        timer.setInterval(60)

        def finish_dialog():
            modal = QtWidgets.QApplication.activeModalWidget()
            if modal is None:
                if time.monotonic() - started > 6:
                    state["errors"].append("Stitch command did not expose its modal dialog")
                    timer.stop()
                return
            if modal.objectName() != "FissionStitchDialog":
                if time.monotonic() - started > 4:
                    state["errors"].append("Unexpected modal dialog: " + modal.windowTitle())
                    timer.stop()
                    modal.reject()
                return
            try:
                state["seen"] = True
                tolerances = modal.findChildren(QtWidgets.QDoubleSpinBox)
                require(len(tolerances) == 1, "Stitch must expose one native tolerance control")
                tolerance = tolerances[0]
                require(_near(tolerance.value(), 0.0001, absolute=1e-9),
                        "Stitch dialog must default to 0.0001 mm")
                require(_near(tolerance.minimum(), 0.000001, absolute=1e-10),
                        "Stitch tolerance must permit 0.000001 mm")
                state["default_tolerance_mm"] = tolerance.value()
                if accept:
                    tolerance.setValue(0.0002)
                    require(_near(tolerance.value(), 0.0002, absolute=1e-9),
                            "Tolerance control must retain the user-entered precision")
                    state["accepted_tolerance_mm"] = tolerance.value()
                boxes = modal.findChildren(QtWidgets.QDialogButtonBox)
                require(len(boxes) == 1, "Stitch must expose one native dialog button box")
                role = QtWidgets.QDialogButtonBox.Ok if accept else QtWidgets.QDialogButtonBox.Cancel
                button = boxes[0].button(role)
                require(button is not None and button.isVisible() and button.isEnabled(),
                        "Stitch dialog button must be usable")
                timer.stop()
                state["clicked"] = True
                QtTest.QTest.mouseClick(button, QtCore.Qt.LeftButton)
            except Exception:
                state["errors"].append(traceback.format_exc())
                timer.stop()
                modal.reject()

        timer.timeout.connect(finish_dialog)
        timer.start()
        try:
            Gui.runCommand("Fission_Stitch")
            settle(200)
        finally:
            timer.stop()
            timer.deleteLater()
            timer = None
        require(state["seen"] and state["clicked"] and not state["errors"],
                "Actual Stitch dialog must complete: " + str(state))
        require(QtWidgets.QApplication.activeModalWidget() is None,
                "Stitch completion must close its modal dialog")
        return state

    try:
        controller.workspace.setCurrentText("Design")
        settle(250)
        if Gui.activeWorkbench().name() != "FissionWorkbench":
            Gui.activateWorkbench("FissionWorkbench")
            settle(250)
        activate_tab("SURFACE")
        require(controller.context() == "surface", "Surface tab must select its shortcut context")
        require(Gui.Command.get("Fission_Stitch") is not None,
                "Fission Stitch must be registered in the real native command registry")
        doc = create_surface_workflow("GuiStitchWorkflow")
        doc.removeObject("ConvertedSolid")
        doc.removeObject("StitchedShell")
        doc.recompute()
        surfaces = [doc.getObject("Surface{}".format(index)) for index in range(1, 7)]
        source_names = {surface.Name for surface in surfaces}
        for surface in surfaces:
            _visible(surface, True)
        doc.UndoMode = 1
        doc.clearUndos()
        App.setActiveDocument(doc.Name)
        view = Gui.getDocument(doc.Name).activeView()
        view.viewAxonometric()
        view.fitAll()
        Gui.Selection.clearSelection()
        for surface in surfaces:
            Gui.Selection.addSelection(doc.Name, surface.Name, "Face1")
        controller.refresh_context()
        settle(150)
        original_names = {obj.Name for obj in doc.Objects}
        details["cancel_dialog"] = operate_dialog(False)
        require({obj.Name for obj in doc.Objects} == original_names,
                "Cancel Stitch must not create a feature")
        require(not doc.HasPendingTransaction, "Cancel Stitch must leave no modeling transaction")
        require(all(surface.ViewObject.Visibility for surface in surfaces),
                "Cancel Stitch must preserve original surface visibility")
        Gui.Selection.clearSelection()
        for surface in surfaces:
            Gui.Selection.addSelection(doc.Name, surface.Name)
        selected_objects = Gui.Selection.getSelectionEx()
        require(len(selected_objects) == 6 and
                all(not selection.SubElementNames for selection in selected_objects),
                "Whole-object Stitch acceptance must select six complete surface objects")
        controller.refresh_context()
        settle(80)
        details["accept_whole_objects_dialog"] = operate_dialog(True)
        doc.recompute()
        whole_features = [obj for obj in doc.Objects if obj.TypeId == "Surface::Sewing"]
        require(len(whole_features) == 1,
                "Whole-object Stitch must create one actual Surface::Sewing feature")
        whole_sewn = whole_features[0]
        whole_name = whole_sewn.Name
        require(whole_sewn.isValid() and whole_sewn.Shape.isValid() and whole_sewn.Shape.isClosed(),
                "Whole-object Stitch must produce valid closed native geometry")
        require(len(whole_sewn.Shape.Shells) == 1 and not whole_sewn.Shape.Solids,
                "Whole-object Stitch must produce one native shell")
        whole_links = whole_sewn.ShapeList
        require(len(whole_links) == 6 and
                {obj.Name for obj, subnames in whole_links} == source_names and
                all(tuple(subnames) == ("",) for obj, subnames in whole_links),
                "Whole-object Stitch must retain six explicit complete-shape links")
        require({obj.Name for obj in whole_sewn.OutList} == source_names,
                "Whole-object Stitch must depend on all six native fillings")
        require(_near(float(whole_sewn.Tolerance), 0.0002, absolute=1e-9),
                "Whole-object Stitch must use the accepted tolerance")
        require(_near(Part.Solid(whole_sewn.Shape.Shells[0]).Volume, 3000.0, relative=1e-5),
                "Whole-object Stitch must enclose the expected box volume")
        require(not doc.HasPendingTransaction,
                "Whole-object Stitch OK must commit its modeling transaction")
        require(not any(surface.ViewObject.Visibility for surface in surfaces),
                "Whole-object Stitch must hide the original patches")
        details["whole_object_selection"] = {
            "feature": whole_name,
            "type": whole_sewn.TypeId,
            "source_names": sorted(source_names),
            "complete_shape_links": len(whole_links),
            "shape": shape_signature(whole_sewn.Shape),
        }
        Gui.runCommand("Std_Undo")
        settle(220)
        require(doc.getObject(whole_name) is None,
                "One native Undo must remove the whole-object stitched feature")
        require({obj.Name for obj in doc.Objects} == original_names,
                "Whole-object Stitch Undo must restore the source document structure")
        require(all(doc.getObject(name).ViewObject.Visibility for name in source_names),
                "Whole-object Stitch Undo must restore original surface visibility")
        require(not doc.HasPendingTransaction,
                "Whole-object Stitch Undo must leave no modeling transaction")
        Gui.Selection.clearSelection()
        for surface in surfaces:
            Gui.Selection.addSelection(doc.Name, surface.Name, "Face1")
        controller.refresh_context()
        settle(80)
        details["accept_dialog"] = operate_dialog(True)
        doc.recompute()
        sewn_features = [obj for obj in doc.Objects if obj.TypeId == "Surface::Sewing"]
        require(len(sewn_features) == 1, "Stitch wrapper must create one actual Surface::Sewing feature")
        sewn = sewn_features[0]
        sewn_name = sewn.Name
        require(sewn.isValid() and sewn.Shape.isValid() and sewn.Shape.isClosed(),
                "GUI Stitch must create a valid closed native shell")
        require(len(sewn.Shape.Shells) == 1 and not sewn.Shape.Solids,
                "GUI Stitch must sew surfaces into a shell")
        require({obj.Name for obj in sewn.OutList} == source_names,
                "GUI Stitch must retain links to the six selected native fillings")
        require(_near(float(sewn.Tolerance), 0.0002, absolute=1e-9),
                "Created native Sewing must use the dialog tolerance")
        require(_near(Part.Solid(sewn.Shape.Shells[0]).Volume, 3000.0, relative=1e-5),
                "GUI Stitch shell must enclose the expected 20 x 15 x 10 volume")
        require(not doc.HasPendingTransaction, "Stitch OK must commit its transaction")
        require(not any(surface.ViewObject.Visibility for surface in surfaces),
                "Successful Stitch must hide the original patches")
        signature = shape_signature(sewn.Shape)
        Gui.runCommand("Std_Undo")
        settle(220)
        require(doc.getObject(sewn_name) is None, "One native Undo must remove the stitched feature")
        require({obj.Name for obj in doc.Objects} == original_names,
                "One Undo must restore exactly the source document structure")
        require(all(doc.getObject(name).ViewObject.Visibility for name in source_names),
                "Undo Stitch must show the original patches")
        require(not doc.HasPendingTransaction, "Undo Stitch must not leave an open transaction")
        Gui.runCommand("Std_Redo")
        settle(220)
        sewn = doc.getObject(sewn_name)
        require(sewn is not None and sewn.TypeId == "Surface::Sewing",
                "Redo must restore the actual native Sewing feature")
        doc.recompute()
        compare_shapes(signature, shape_signature(sewn.Shape))
        require({obj.Name for obj in sewn.OutList} == source_names,
                "Redo must restore the native surface dependencies")
        require(not any(doc.getObject(name).ViewObject.Visibility for name in source_names),
                "Redo must restore successful Stitch visibility")
        saved = output / "fission-gui-stitch.FCStd"
        doc.saveAs(str(saved))
        require(saved.is_file() and saved.stat().st_size > 1000, "GUI Stitch must write a real FCStd")
        App.closeDocument(doc.Name)
        doc = App.openDocument(str(saved))
        doc.getObject(sewn_name).touch()
        doc.recompute()
        sewn = doc.getObject(sewn_name)
        compare_shapes(signature, shape_signature(sewn.Shape))
        require({obj.Name for obj in sewn.OutList} == source_names,
                "Saved Stitch must retain the native source links")
        details.update({"feature": sewn_name, "type": sewn.TypeId,
                        "source_names": sorted(source_names), "shape": signature,
                        "undo_redo": True, "artifact": str(saved)})
        (output / "gui-stitch-report.json").write_text(json.dumps(details, indent=2), encoding="utf-8")
        return details
    finally:
        if timer is not None:
            timer.stop()
            timer.deleteLater()
        modal = QtWidgets.QApplication.activeModalWidget()
        if modal is not None and modal.objectName() == "FissionStitchDialog":
            modal.reject()
        Gui.Selection.clearSelection()
        if doc is not None and doc.Name in App.listDocuments():
            if doc.HasPendingTransaction:
                doc.abortTransaction()
            App.closeDocument(doc.Name)
        if previous and previous in App.listDocuments():
            App.setActiveDocument(previous)
        controller.workspace.setCurrentText("Design")
        settle(120)
        activate_tab(previous_tab)


def run_all(output_dir=None):
    output = Path(output_dir or os.environ.get("FISSION_SPECIALIST_OUTPUT", DEFAULT_OUTPUT)).resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {"freecad_version": list(App.Version()), "cases": [], "passed": 0, "failed": 0}
    for name, case in (("surface_create_sew_solid_save_reopen", surface_case),
                       ("mesh_tessellate_convert_save_reopen", mesh_case)):
        existing_documents = set(App.listDocuments())
        try:
            details = case(output)
            report["cases"].append({"name": name, "passed": True, "details": details})
            report["passed"] += 1
        except Exception:
            report["cases"].append({"name": name, "passed": False, "error": traceback.format_exc()})
            report["failed"] += 1
        finally:
            for document_name in set(App.listDocuments()) - existing_documents:
                App.closeDocument(document_name)
    (output / "specialist-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    require(report["failed"] == 0, "Specialist workflows failed; see " + str(output / "specialist-report.json"))
    print("FISSION_SPECIALIST_WORKFLOWS_OK", report["passed"], "cases")
    return report


if __name__ == "__main__" or (not App.GuiUp and os.environ.get("FISSION_SPECIALIST_AUTORUN") == "1"):
    run_all()
