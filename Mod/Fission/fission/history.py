# SPDX-License-Identifier: LGPL-2.1-or-later
"""Read-only presentation of the authoritative FreeCAD document model.

This module deliberately has no FreeCAD or Qt import so its ordering and graph
rules can be tested independently. Objects are never renamed or reordered here.
"""

from dataclasses import dataclass


def derived(obj, type_name):
    try:
        return bool(obj.isDerivedFrom(type_name))
    except (AttributeError, RuntimeError):
        return getattr(obj, "TypeId", "") == type_name


def object_key(obj):
    return (obj.Document.Name, obj.Name)


def category(obj):
    type_id = getattr(obj, "TypeId", "")
    if derived(obj, "PartDesign::Body"):
        return "Bodies"
    if derived(obj, "App::Part") or derived(obj, "App::Link") or "AssemblyObject" in type_id:
        return "Components"
    if derived(obj, "Sketcher::SketchObject"):
        return "Sketches"
    if derived(obj, "App::Origin") or derived(obj, "App::OriginFeature"):
        return "Origin"
    if "Joint" in type_id or hasattr(obj, "JointType"):
        return "Joints"
    if any(token in type_id for token in ("ShapeBinder", "SubShapeBinder", "Datum", "CoordinateSystem")) or type_id in ("PartDesign::Plane", "PartDesign::Line", "PartDesign::Point"):
        return "Reference geometry"
    if derived(obj, "PartDesign::Feature"):
        return "Features"
    if derived(obj, "Part::Feature"):
        return "Geometry"
    if derived(obj, "App::DocumentObjectGroup"):
        return "Groups"
    return "Objects"


def is_history_feature(obj):
    """Include actual model operations; exclude containers and origin helpers."""
    if category(obj) in ("Components", "Bodies", "Origin", "Groups"):
        return False
    return (
        derived(obj, "Sketcher::SketchObject")
        or derived(obj, "PartDesign::Feature")
        or derived(obj, "Part::Feature")
        or category(obj) == "Joints"
    )


def chronological_features(document):
    """Document.Objects is FreeCAD's stored creation sequence, not a replay log.

    The core appends objects to objectArray. Save/restore and native model edits
    remain authoritative; labels and dependency depth must not sort this view.
    """
    return [obj for obj in document.Objects if is_history_feature(obj)] if document else []


@dataclass(frozen=True)
class TreeRecord:
    key: tuple
    parent: tuple | None
    label: str
    obj: object = None


def browser_records(document):
    """Adapt real containment links into product-oriented folders.

    Group/Origin/OriginFeatures are containment. OutList is intentionally *not*
    used: it also contains arbitrary feature dependencies, not child objects.
    An object shared by two groups has one stable display parent.
    """
    if document is None:
        return []
    objects = list(document.Objects)
    known = {object_key(obj): obj for obj in objects}
    parents = {}
    # Bodies own their features ahead of a generic presentation group.
    containers = sorted(objects, key=lambda obj: not derived(obj, "PartDesign::Body"))
    for container in containers:
        if derived(container, "App::Link"):
            continue
        children = list(getattr(container, "Group", ()) or ())
        children += list(getattr(container, "OriginFeatures", ()) or ())
        origin = getattr(container, "Origin", None)
        if origin is not None:
            children.append(origin)
        parent_key = object_key(container)
        for child in children:
            if not hasattr(child, "Document") or child.Document is None:
                continue
            child_key = object_key(child)
            if child_key in known and child_key != parent_key:
                parents.setdefault(child_key, parent_key)
    # Malformed cyclic groups can be loaded; display each object once at root.
    for child_key in list(parents):
        path = {child_key}
        ancestor = parents[child_key]
        while ancestor in parents:
            if ancestor in path:
                parents.pop(child_key, None)
                break
            path.add(ancestor)
            ancestor = parents[ancestor]
    root = ("document", document.Name, "root")
    records = [TreeRecord(root, None, document.Label)]
    folders = set()
    for obj in objects:
        key = object_key(obj)
        parent = parents.get(key, root)
        group = category(obj)
        # Origin already is a real container; display its axes/planes directly.
        if derived(obj, "App::Origin") or (parent in known and derived(known[parent], "App::Origin")):
            display_parent = parent
        else:
            display_parent = ("folder", parent, group)
            if display_parent not in folders:
                folders.add(display_parent)
                records.append(TreeRecord(display_parent, parent, group))
        records.append(TreeRecord(key, display_parent, obj.Label, obj))
    return records


def dependency_move_reason(features, source_index, destination_index):
    """Return the dependency conflict for a proposed visual history move.

    An empty string only means the local directed graph permits this sequence.
    It never authorizes a CAD mutation: body tip/support/group ordering and
    workbench-specific rules still require a native operation.
    """
    count = len(features)
    if not 0 <= source_index < count or not 0 <= destination_index < count:
        return "The requested history position is outside this document."
    candidate = list(features)
    feature = candidate.pop(source_index)
    candidate.insert(destination_index, feature)
    positions = {object_key(obj): index for index, obj in enumerate(candidate)}
    for obj in candidate:
        for dependency in getattr(obj, "OutList", ()):
            dep_key = object_key(dependency)
            if dep_key in positions and positions[dep_key] >= positions[object_key(obj)]:
                return "{} depends on {}; its prerequisite must stay earlier.".format(obj.Label, dependency.Label)
    return ""


def reorder_explanation(features, index):
    conflicts = []
    for destination in (index - 1, index + 1):
        if 0 <= destination < len(features):
            reason = dependency_move_reason(features, index, destination)
            if reason:
                conflicts.append(reason)
    reason = " ".join(dict.fromkeys(conflicts))
    return (reason + " " if reason else "") + (
        "History order follows the native document. Changing it also requires "
        "validated body, tip and support rules; drag reordering is unavailable."
    )


def supports_suppression(obj):
    """Never invent suppression or confuse hiding with removing a feature."""
    try:
        return (
            "Suppressed" in obj.PropertiesList
            and obj.getTypeIdOfProperty("Suppressed") == "App::PropertyBool"
            and "ReadOnly" not in obj.getPropertyStatus("Suppressed")
        )
    except (AttributeError, RuntimeError):
        return False


def feature_state(obj):
    try:
        status = obj.getStatusString()
        if not obj.isValid():
            return "error", status
        if supports_suppression(obj) and obj.Suppressed:
            return "suppressed", "Suppressed"
        if "Touched" in getattr(obj, "State", ()) or status == "Touched":
            return "touched", "Needs recompute"
        return "valid", status
    except (AttributeError, RuntimeError):
        return "valid", ""
