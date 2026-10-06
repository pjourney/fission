# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real native construction tasks, Body creation and modeling ownership guards."""
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets

import cad_workflows as cad
from search_workflows import _design
from ribbon_workflows import _choose
from interactive_workflow import _edited_feature, _finish_task, _set_quantity, _presentation


def _origin_plane(body):
    planes = [obj for obj in body.Origin.OriginFeatures
              if obj.isDerivedFrom("App::Plane")
              and (getattr(obj, "Role", "") == "XY_Plane" or obj.Name.startswith("XY_Plane"))]
    cad.require(len(planes) == 1, "Body must provide one native XY origin plane")
    return planes[0]


def _selection(obj=None):
    Gui.Selection.clearSelection()
    if obj:
        Gui.Selection.addSelection(obj)


def _pose(actual, expected, description):
    cad.require(actual.isSame(expected, 1e-6), description)


def _offset(task, feature, values, settle):
    for field, value in zip(("attachmentOffsetX", "attachmentOffsetY", "attachmentOffsetZ"), values):
        _set_quantity(task, field, value, settle)
    cad.require((feature.AttachmentOffset.Base - App.Vector(*values)).Length < 1e-6,
                "Native attachment controls must update the preview's real offset")
    cad.require(feature.Shape.isValid() and not feature.Shape.isNull(),
                "Native construction preview must contain valid geometry")


def _state(doc):
    view = Gui.getDocument(doc.Name).activeView()
    def name(obj):
        return obj.Name if obj else None
    return {"objects": [(obj.Name, obj.TypeId, obj.Label) for obj in doc.Objects],
            "undo": doc.UndoCount, "pending": doc.HasPendingTransaction,
            "booked": doc.getBookedTransactionID(),
            "part": name(view.getActiveObject("part")),
            "body": name(view.getActiveObject("pdbody")),
            "selection": [(item.DocumentName, item.ObjectName, list(item.SubElementNames))
                          for item in Gui.Selection.getSelectionEx()]}


def _deny(controller, doc, settle, names=("Extrude", "Cut", "RevolveCut", "SweepCut", "LoftCut",
                                        "Plane", "Axis", "Point", "NewBody", "NewComponent")):
    """A direct dispatch must recheck ownership after readiness was queried."""
    before = _state(doc)
    for name in names:
        command = Gui.Command.get("Fission_" + name)
        cad.require(command is not None and not command.isActive(),
                    "Ownership must disable Fission_" + name)
        controller.perform(name)
        settle(40)
        cad.require(_state(doc) == before,
                    "Refused " + name + " must preserve the native graph, active Body, selection and transaction")


def construction_datums(controller, settle, output):
    """Actual Plane split menu -> native Axis/Point attachment tasks."""
    with _design(controller, settle) as doc:
        body = doc.Body
        plane = _origin_plane(body)
        initial_names = sorted(obj.Name for obj in doc.Objects)
        undo = doc.UndoCount
        evidence = []
        for command, type_id, mode, values in (
                ("Fission_Axis", "PartDesign::Line", "ObjectX", (3, 4, 5)),
                ("Fission_Point", "PartDesign::Point", "ObjectOrigin", (7, -2, 11))):
            original_names = sorted(obj.Name for obj in doc.Objects)
            original_undo = doc.UndoCount
            for accept in (False, True):
                _selection(plane)
                settle(80)
                _choose(controller, "Fission_Plane", command, settle)
                feature, task = _edited_feature(doc, type_id, controller)
                cad.require(feature.getParentGeoFeatureGroup() is body and str(feature.MapMode) == mode,
                            "Construction dropdown must infer its native attachment mode inside the active Body")
                cad.require(any(support[0] is plane for support in feature.AttachmentSupport),
                            "Construction task must retain the selected native origin-plane reference")
                _offset(task, feature, values, settle)
                preview = App.Placement(feature.Placement)
                feature_name = feature.Name
                _finish_task(doc, task, settle, accept)
                if not accept:
                    cad.require(sorted(obj.Name for obj in doc.Objects) == original_names
                                and doc.UndoCount == original_undo,
                                "Construction Cancel must restore native features and Undo history")
                else:
                    cad.require(doc.UndoCount == original_undo + 1,
                                "Construction OK must commit one native Undo step")
                    _pose(feature.Placement, preview, "Construction OK must preserve its preview placement")
                    evidence.append({"name": feature_name, "type": type_id, "mode": mode,
                                     "offset": list(values), "placement": preview,
                                     "creation_placement": App.Placement(preview)})
            # Selecting an existing datum and choosing the same native menu
            # command enters its real attachment editor instead of creating
            # another reference object. Exercise both native completion paths.
            record = evidence[-1]
            feature = doc.getObject(record["name"])
            original_offset = App.Placement(feature.AttachmentOffset)
            original_pose = App.Placement(feature.Placement)
            original_names = sorted(obj.Name for obj in doc.Objects)
            original_undo = doc.UndoCount
            updated_values = tuple(value + amount for value, amount in zip(values, (2, -3, 4)))
            for accept in (False, True):
                _selection(feature)
                settle(80)
                _choose(controller, "Fission_Plane", command, settle)
                edited, task = _edited_feature(doc, type_id, controller)
                cad.require(edited is feature,
                            "Construction dropdown on an existing datum must edit that native object")
                _offset(task, edited, updated_values, settle)
                updated_pose = App.Placement(edited.Placement)
                updated_offset = App.Placement(edited.AttachmentOffset)
                _finish_task(doc, task, settle, accept)
                cad.require(sorted(obj.Name for obj in doc.Objects) == original_names,
                            "Editing a datum must preserve its native feature list")
                if not accept:
                    _pose(feature.AttachmentOffset, original_offset,
                          "Cancel existing datum edit must restore its native attachment offset")
                    _pose(feature.Placement, original_pose,
                          "Cancel existing datum edit must restore its previous native placement")
                    cad.require(doc.UndoCount == original_undo,
                                "Cancel existing datum edit must preserve Undo history")
                else:
                    _pose(feature.AttachmentOffset, updated_offset,
                          "OK existing datum edit must retain its native attachment offset")
                    _pose(feature.Placement, updated_pose,
                          "OK existing datum edit must retain its preview placement")
                    cad.require(doc.UndoCount == original_undo + 1,
                                "OK existing datum edit must commit exactly one native Undo step")
                    record["offset"] = list(updated_values)
                    record["placement"] = updated_pose
                    doc.undo()
                    settle(120)
                    _pose(feature.AttachmentOffset, original_offset,
                          "Undo existing datum edit must restore its original attachment offset")
                    _pose(feature.Placement, original_pose,
                          "Undo existing datum edit must restore its original placement")
                    doc.redo()
                    settle(120)
                    _pose(feature.AttachmentOffset, updated_offset,
                          "Redo existing datum edit must restore the changed attachment offset")
                    _pose(feature.Placement, updated_pose,
                          "Redo existing datum edit must restore the changed placement")
        cad.require(doc.UndoCount == undo + 4,
                    "Axis and Point creation and accepted edits must each commit one native transaction")
        point_record = evidence[-1]
        point_name = point_record["name"]
        doc.undo()
        settle(140)
        _pose(doc.getObject(point_name).Placement, point_record["creation_placement"],
              "Undo point edit must retain the completed point at its creation placement")
        doc.undo()
        settle(140)
        cad.require(doc.getObject(point_name) is None,
                    "Native Undo must remove the completed construction point")
        doc.redo()
        settle(140)
        doc.redo()
        settle(140)
        point = doc.getObject(point_name)
        _pose(point.Placement, point_record["placement"], "Native Redo must restore the point's attachment placement")
        _presentation(controller, doc, [doc.getObject(item["name"]) for item in evidence], settle)
        path = Path(output) / "construction-datums.FCStd"
        body_name, plane_name = body.Name, plane.Name
        doc.saveAs(str(path))
        App.closeDocument(doc.Name)
        reopened = App.openDocument(str(path))
        settle(160)
        for record in evidence:
            feature = reopened.getObject(record["name"])
            cad.require(feature.TypeId == record["type"] and str(feature.MapMode) == record["mode"],
                        "Reopened construction geometry must remain native and attached")
            cad.require(feature.getParentGeoFeatureGroup() is reopened.getObject(body_name)
                        and any(item[0] is reopened.getObject(plane_name) for item in feature.AttachmentSupport),
                        "FCStd reopen must preserve construction Body containment and support")
            _pose(feature.Placement, record["placement"], "FCStd reopen must preserve construction placement")
        # Edit only after reopen to verify the saved file retains the actual
        # native attachment engine, rather than a frozen cosmetic shape.
        point = reopened.getObject(point_name)
        old_offset = App.Placement(point.AttachmentOffset)
        changed = App.Placement(old_offset)
        changed.Base = changed.Base + App.Vector(0, 0, 9)
        old_pose = App.Placement(point.Placement)
        point.AttachmentOffset = changed
        reopened.recompute()
        cad.require(point.Shape.isValid() and (point.Placement.Base - old_pose.Base).Length > 8.9,
                    "Reopened construction point must recompute from its parametric attachment offset")
        return {"native_datums": [{key: value for key, value in item.items()
                                   if key not in ("placement", "creation_placement")}
                                  for item in evidence],
                "cancel_undo_redo": True, "existing_native_edit_cancel_ok": True,
                "original_objects": len(initial_names),
                "parametric_reopen": True, "file": str(path)}


def body_ownership(controller, settle, output):
    """Native New Body is empty, component-scoped and rejects busy owners."""
    with _design(controller, settle) as doc:
        component, original_body = doc.Component, doc.Body
        view = Gui.getDocument(doc.Name).activeView()
        base = original_body.newObject("PartDesign::AdditiveBox", "OwnershipBase")
        base.Length, base.Width, base.Height = 10, 10, 10
        solid = doc.addObject("Part::Box", "BodyCreationSelection")
        solid.Length, solid.Width, solid.Height = 6, 8, 10
        component.addObject(solid)
        doc.recompute()
        before_shape = cad.shape_signature(solid.Shape)
        # Before creating additional Bodies, expose the native sole-Body
        # auto-activation hazard: this document has one Body in another Part.
        empty_component = doc.addObject("App::Part", "EmptyModelingComponent")
        doc.recompute()
        view.setActiveObject("part", empty_component)
        view.setActiveObject("pdbody", None)
        _selection(_origin_plane(original_body))
        settle(80)
        _deny(controller, doc, settle, ("Plane", "Axis", "Point"))
        created = []
        for parent in (component, None):
            view.setActiveObject("part", parent)
            view.setActiveObject("pdbody", original_body if parent else None)
            _selection(solid)
            settle(80)
            names, undo = sorted(obj.Name for obj in doc.Objects), doc.UndoCount
            _choose(controller, "Fission_NewComponent", "Fission_NewBody", settle)
            body = view.getActiveObject("pdbody")
            cad.require(body is not None and body.isDerivedFrom("PartDesign::Body")
                        and body.Name not in names,
                        "New Body menu must create and activate a real native Body")
            cad.require(body.getParentGeoFeatureGroup() is parent and body.BaseFeature is None
                        and body.Tip is None and not body.Group,
                        "New Body must be empty in its active Component or document root")
            cad.require(not Gui.Control.activeDialog() and not doc.HasPendingTransaction
                        and doc.getBookedTransactionID() == 0 and doc.UndoCount == undo + 1,
                        "Native New Body must finish one transaction without borrowing task ownership")
            cad.compare_shapes(before_shape, cad.shape_signature(solid.Shape))
            body_name = body.Name
            doc.undo()
            settle(120)
            cad.require(sorted(obj.Name for obj in doc.Objects) == names,
                        "Native New Body Undo must remove the Body and its origin helpers")
            doc.redo()
            settle(120)
            restored = doc.getObject(body_name)
            cad.require(restored is not None and restored.getParentGeoFeatureGroup() is parent
                        and restored.BaseFeature is None and not restored.Group,
                        "Native New Body Redo must restore empty Body containment")
            created.append({"name": body_name, "parent": parent.Name if parent else None})
        view.setActiveObject("part", component)
        view.setActiveObject("pdbody", original_body)
        _selection()
        settle(80)
        for name in ("Extrude", "Cut", "RevolveCut", "SweepCut", "LoftCut",
                     "Plane", "Axis", "Point", "NewBody", "NewComponent"):
            cad.require(Gui.Command.get("Fission_" + name).isActive(),
                        "Idle scoped solid must make the guarded " + name + " tool ready")
        doc.openTransaction("Foreign empty modeling booking")
        try:
            cad.require(not doc.HasPendingTransaction and doc.getBookedTransactionID() > 0,
                        "Ownership fixture must book a native operation before its first mutation")
            _deny(controller, doc, settle)
        finally:
            doc.abortTransaction()
        doc.openTransaction("Foreign pending modeling operation")
        try:
            solid.Label = "Pending native modeling edit"
            cad.require(doc.HasPendingTransaction, "Ownership fixture must hold a real pending native edit")
            _deny(controller, doc, settle)
        finally:
            doc.abortTransaction()
        # A live, document-owned native datum task must keep ownership even
        # when the public perform method is called directly after selection changes.
        _selection(_origin_plane(original_body))
        _choose(controller, "Fission_Plane", "Fission_Axis", settle)
        feature, task = _edited_feature(doc, "PartDesign::Line", controller)
        _deny(controller, doc, settle)
        _finish_task(doc, task, settle, False)
        modal = QtWidgets.QDialog(controller.main)
        modal.setWindowTitle("Modeling ownership acceptance fixture")
        modal.setModal(True)
        try:
            modal.show()
            settle(80)
            cad.require(QtWidgets.QApplication.activeModalWidget() is modal,
                        "Ownership fixture must expose an actual modal Qt owner")
            _deny(controller, doc, settle)
        finally:
            modal.reject()
            modal.deleteLater()
            settle(60)
        view.setActiveObject("part", empty_component)
        view.setActiveObject("pdbody", None)
        _selection(_origin_plane(original_body))
        settle(80)
        _deny(controller, doc, settle, ("Plane", "Axis", "Point"))
        view.setActiveObject("part", component)
        view.setActiveObject("pdbody", None)
        _selection()
        settle(80)
        # The original Body plus the component-scoped New Body are ambiguous.
        _deny(controller, doc, settle, ("Plane", "Axis", "Point"))
        view.setActiveObject("pdbody", original_body)
        _selection(_origin_plane(original_body))
        settle(80)
        cad.require(Gui.Command.get("Fission_Axis").isActive() and Gui.Command.get("Fission_Point").isActive(),
                    "Explicitly activating the scoped Body must restore construction command readiness")
        path = Path(output) / "native-new-bodies.FCStd"
        component_name = component.Name
        doc.saveAs(str(path))
        App.closeDocument(doc.Name)
        reopened = App.openDocument(str(path))
        settle(140)
        for record in created:
            body = reopened.getObject(record["name"])
            parent = reopened.getObject(record["parent"]) if record["parent"] else None
            cad.require(body is not None and body.TypeId == "PartDesign::Body"
                        and body.getParentGeoFeatureGroup() is parent and body.BaseFeature is None and not body.Group,
                        "FCStd reopen must preserve empty native New Bodies and their component ownership")
        return {"created_bodies": created, "active_component": component_name,
                "selected_solid_not_imported": True, "native_undo_redo_reopen": True,
                "guards": ["empty_booking", "pending_edit", "native_task", "modal_owner",
                           "different_component", "sole_body_in_another_component", "ambiguous_body"],
                "file": str(path)}
