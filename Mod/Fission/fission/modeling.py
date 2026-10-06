# SPDX-License-Identifier: MIT
"""Scope and task-ownership guards for native solid and datum commands."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets


MODELED_NAMES = ("Extrude", "Cut", "RevolveCut", "SweepCut", "LoftCut", "Plane", "Axis", "Point",
                 "NewComponent", "NewBody")
_CUTS = frozenset(("Cut", "RevolveCut", "SweepCut", "LoftCut"))
_PROFILES = _CUTS | {"Extrude"}
_DATUM_TYPES = {"Plane": "PartDesign::Plane", "Axis": "PartDesign::Line", "Point": "PartDesign::Point"}
_STALE_ERRORS = (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError)


def _derived(obj, kind):
    return bool(obj is not None and obj.isDerivedFrom(kind))


def _owned(obj, document):
    """Reject detached wrappers and objects from a reopened document namesake."""
    return bool(obj is not None and obj.Document is document
                and document.getObject(obj.Name) is obj)


def _context():
    document = App.ActiveDocument
    gui_document = Gui.activeDocument()
    if document is None or gui_document is None or gui_document.Document is not document:
        return None
    workbench = Gui.activeWorkbench()
    if workbench is None or workbench.name() != "FissionWorkbench":
        return None
    # A command may book its transaction before making any document changes.
    # getActiveTransaction returns None or (name, positive ID), not an ID.
    if (document.HasPendingTransaction or document.getBookedTransactionID() != 0
            or App.getActiveTransaction() is not None):
        return None
    if gui_document.getInEdit() or Gui.Control.activeDialog():
        return None
    application = QtWidgets.QApplication.instance()
    if application is not None and application.activeModalWidget() is not None:
        return None
    view = gui_document.activeView()
    if (view is None or not hasattr(view, "graphicsView")
            or not hasattr(view, "getObjectInfo") or not hasattr(view, "getActiveObject")
            or view.graphicsView() is None):
        return None
    component = view.getActiveObject("part")
    if component is not None and (not _owned(component, document)
                                  or not _derived(component, "App::Part")):
        return None
    return document, gui_document, view, component


def _resolve_body(document, view, component):
    body = view.getActiveObject("pdbody")
    if body is not None:
        if not _owned(body, document) or not _derived(body, "PartDesign::Body"):
            return None
        if body.getParentGeoFeatureGroup() is component:
            return body
    bodies = [obj for obj in document.Objects
              if _owned(obj, document) and _derived(obj, "PartDesign::Body")
              and obj.getParentGeoFeatureGroup() is component]
    return bodies[0] if len(bodies) == 1 else None


def scoped_body():
    """Return an unambiguous Body in the current component without activating it."""
    try:
        context = _context()
        if context is None:
            return None
        document, _gui_document, view, component = context
        return _resolve_body(document, view, component)
    except _STALE_ERRORS:
        return None


def _containing_body(obj):
    seen = []
    while obj is not None:
        if any(obj is previous for previous in seen):
            return None
        if _derived(obj, "PartDesign::Body"):
            return obj
        seen.append(obj)
        obj = obj.getParentGeoFeatureGroup()
    return None


def _checked(name):
    if name not in MODELED_NAMES:
        return None
    context = _context()
    if context is None:
        return None
    document, gui_document, view, component = context
    selected = list(Gui.Selection.getSelection())
    if not all(_owned(obj, document) for obj in selected):
        return None
    if name == "NewComponent":
        return document, gui_document, view, component, None, selected
    if name == "NewBody":
        # Creating an empty body never interprets a selected shape as its base.
        # A selected component must agree with the actual native active scope.
        if any(_derived(obj, "App::Part") and obj is not component for obj in selected):
            return None
        return document, gui_document, view, component, None, selected
    body = _resolve_body(document, view, component)
    if body is None:
        return None
    if name in _CUTS:
        shape = body.Shape
        if shape.isNull() or not shape.Solids:
            return None
    if name in _PROFILES:
        if any(obj is body or not _derived(obj, "Part::Feature") or _containing_body(obj) is not body
               for obj in selected):
            return None
    elif len(selected) == 1 and _derived(selected[0], _DATUM_TYPES[name]):
        # Native datum commands edit an existing selected datum of the same type.
        if _containing_body(selected[0]) is not body:
            return None
    return document, gui_document, view, component, body, selected


def available(name):
    """Read-only readiness; native command availability is checked by the caller."""
    try:
        return _checked(name) is not None
    except _STALE_ERRORS:
        return False


def prepare(name):
    """Revalidate scope, then prepare native activation without opening a task."""
    try:
        checked = _checked(name)
        if checked is None:
            return False
        document, gui_document, view, component, body, selected = checked
        current = _checked(name)
        if current is None or any(a is not b for a, b in zip(checked[:5], current[:5])):
            return False
        if len(selected) != len(current[5]) or any(a is not b for a, b in zip(selected, current[5])):
            return False
        if name == "NewBody":
            Gui.Selection.clearSelection()
        elif body is not None and view.getActiveObject("pdbody") is not body:
            view.setActiveObject("pdbody", body)
        return True
    except _STALE_ERRORS:
        return False
