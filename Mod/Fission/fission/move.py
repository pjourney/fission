# SPDX-License-Identifier: MIT
"""Transactional placement editing of native components, bodies and links."""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets


def _derived(obj, kind):
    return bool(obj and obj.isDerivedFrom(kind))


def _ancestors(obj):
    """Actual coordinate-system containment, never generic dependency links."""
    result = []
    current = obj.getParentGeoFeatureGroup()
    while current is not None:
        if current is obj or any(current is item for item in result):
            raise ValueError("The selected object has cyclic component containment.")
        result.append(current)
        current = current.getParentGeoFeatureGroup()
    return result


def _placement_property(obj):
    return "LinkPlacement" if _derived(obj, "App::Link") else "Placement"


def _movable_reason(obj, document):
    if obj is None or obj.Document is not document or document.getObject(obj.Name) is not obj:
        return "Select objects belonging to the active design."
    if not (_derived(obj, "App::Part") or _derived(obj, "PartDesign::Body")
            or _derived(obj, "App::Link") or _derived(obj, "Part::Feature")
            or _derived(obj, "Mesh::Feature")):
        return "Select a component, body, link, or standalone geometry to Move / Copy."
    if _derived(obj, "Sketcher::SketchObject") or _derived(obj, "PartDesign::Feature"):
        return "Move the containing body or component instead of an individual modeling feature."
    ancestors = _ancestors(obj)
    if any(_derived(parent, "PartDesign::Body") for parent in ancestors):
        return "Move the containing body instead of one of its modeling features."
    prop = _placement_property(obj)
    if prop not in obj.PropertiesList:
        return obj.Label + " has no editable placement."
    status = list(obj.getPropertyStatus(prop)) + list(obj.getEditorMode(prop))
    if "ReadOnly" in status or "Immutable" in status:
        return obj.Label + " has a read-only placement."
    if any(path == prop or path.startswith(prop + ".") or path == "Placement"
           or path.startswith("Placement.") for path, _expression in obj.ExpressionEngine):
        return obj.Label + " has a placement controlled by expressions."
    if "MapMode" in obj.PropertiesList and str(obj.MapMode) != "Deactivated":
        return obj.Label + " has a placement controlled by attachment."
    if _derived(obj, "App::Link"):
        if getattr(obj, "ElementCount", 0) or getattr(obj, "ElementList", []):
            return "Move / Copy does not support link arrays; select a single component link."
        source = obj.LinkedObject
        if source is None or isinstance(source, (tuple, list)) or not getattr(source, "Document", None):
            return "Select a whole-object link with an available source."
        scale = getattr(obj, "ScaleVector", App.Vector(1, 1, 1))
        if any(abs(value - 1.0) > 1e-12 for value in (scale.x, scale.y, scale.z)):
            return "Move / Copy does not support scaled links."
    for parent in ancestors:
        if _derived(parent, "Assembly::AssemblyObject"):
            return "Use native assembly dragging or joint tools to move an assembly component."
    return ""


def collect_targets(selected=None, document=None):
    """Validate an entire selection and remove descendants of selected parents."""
    document = App.ActiveDocument if document is None else document
    if document is None:
        raise ValueError("Open a design before Move / Copy.")
    selected = list(Gui.Selection.getSelection() if selected is None else selected)
    unique = []
    for obj in selected:
        if obj is None or obj.Document is not document or document.getObject(obj.Name) is not obj:
            raise ValueError("Select objects belonging to the active design.")
        if not any(obj is item for item in unique):
            unique.append(obj)
    targets = [obj for obj in unique if not any(
        parent is item for parent in _ancestors(obj) for item in unique)]
    if not targets:
        raise ValueError("Select a component, body, link, or standalone geometry to Move / Copy.")
    for obj in targets:
        reason = _movable_reason(obj, document)
        if reason:
            raise ValueError(reason)
    # A linked source can contribute its placement to the link's geometry.
    # Moving both would compound the delta; containment dedup alone cannot
    # resolve a source dependency, especially through links of links.
    for obj in targets:
        if not _derived(obj, "App::Link"):
            continue
        pending = [obj.LinkedObject] + list(getattr(obj, "OutListRecursive", []))
        sources = []
        while pending:
            source = pending.pop()
            if source is None or any(source is old for old in sources):
                continue
            sources.append(source)
            if any(source is target or any(parent is target for parent in _ancestors(source))
                   for target in targets if target is not obj):
                raise ValueError("Move linked sources and their dependent links in separate operations.")
            if _derived(source, "App::Link"):
                pending.append(source.LinkedObject)
            pending.extend(getattr(source, "Group", []))
    return targets


def _idle_reason(document, allow_transaction=False):
    if document is None or App.ActiveDocument is not document:
        return "Return to the design that opened Move / Copy."
    gui_doc = Gui.activeDocument()
    if gui_doc is None or gui_doc.Document is not document:
        return "Return to the design that opened Move / Copy."
    if not allow_transaction and (document.HasPendingTransaction or document.getBookedTransactionID() != 0):
        return "Finish or cancel the active operation before Move / Copy."
    edit = gui_doc.getInEdit()
    if Gui.Control.activeDialog() or (edit and not _derived(edit.Object, "Assembly::AssemblyObject")):
        return "Finish or cancel the active modeling task before Move / Copy."
    view = gui_doc.activeView()
    if view is None or not hasattr(view, "graphicsView"):
        return "Open the design's 3D view before Move / Copy."
    return ""


def can_move():
    try:
        if _idle_reason(App.ActiveDocument):
            return False
        collect_targets()
        return True
    except (AttributeError, ReferenceError, RuntimeError, ValueError):
        return False


def parent_placement(obj):
    """Compose public container poses without traversing private link sources."""
    placement = App.Placement()
    for parent in reversed(_ancestors(obj)):
        placement = placement.multiply(getattr(parent, _placement_property(parent)))
    return placement


def transformed_placement(original, parent, translation, angles):
    """Design axes; X then Y then Z rotation around the object's placement origin."""
    if len(translation) != 3 or len(angles) != 3 or not all(
            math.isfinite(float(value)) for value in (*translation, *angles)):
        raise ValueError("Enter finite translation and rotation values for all three axes.")
    rotation = App.Rotation()
    for axis, angle in zip(((1, 0, 0), (0, 1, 0), (0, 0, 1)), angles):
        rotation = App.Rotation(App.Vector(*axis), float(angle)).multiply(rotation)
    world = parent.multiply(original)
    world = App.Placement(world.Base + App.Vector(*translation), rotation.multiply(world.Rotation))
    return parent.inverse().multiply(world)


class MoveDialog(QtWidgets.QDialog):
    def __init__(self, controller, targets):
        super().__init__(controller.main)
        self.controller = controller
        self.document = App.ActiveDocument
        self.document_name = self.document.Name
        self.gui_document = Gui.activeDocument()
        self.view = self.gui_document.activeView()
        edit = self.gui_document.getInEdit()
        self.edit_owner = edit.Object if edit else None
        self.context = controller.context()
        self.workbench = Gui.activeWorkbench().name()
        self.targets = list(targets)
        self.original = [App.Placement(getattr(obj, _placement_property(obj))) for obj in self.targets]
        self.expected = [App.Placement(value) for value in self.original]
        self.parents = [_ancestors(obj) for obj in self.targets]
        self.parent_poses = [[App.Placement(getattr(parent, _placement_property(parent)))
                              for parent in chain] for chain in self.parents]
        self.parent_world = [parent_placement(obj) for obj in self.targets]
        self.link_sources = [(obj.LinkedObject, bool(obj.LinkTransform)) if _derived(obj, "App::Link")
                             else None for obj in self.targets]
        self.copies = []
        self.copy_poses = []
        self.transaction = False
        self.transaction_id = None
        self._closed = False
        self._updating = False
        self.setObjectName("FissionMoveDialog")
        self.setWindowTitle("Move / Copy")
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        layout = QtWidgets.QVBoxLayout(self)
        intro = QtWidgets.QLabel("Design axes: translate in X, Y, Z. Rotate X, then Y, then Z around each object's placement origin.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        layout.addWidget(QtWidgets.QLabel("Selected objects: {}".format(len(self.targets))))
        form = QtWidgets.QFormLayout()
        self.translation, self.rotation = [], []
        for group, fields, suffix, limit in (("Translation", self.translation, " mm", 1e6),
                                             ("Rotation", self.rotation, " °", 360.0)):
            for axis in "XYZ":
                field = QtWidgets.QDoubleSpinBox()
                field.setObjectName("Move" + group + axis)
                field.setRange(-limit, limit)
                field.setDecimals(4)
                field.setSuffix(suffix)
                field.setKeyboardTracking(False)
                form.addRow(group + " " + axis, field)
                fields.append(field)
                field.valueChanged.connect(self.preview)
        layout.addLayout(form)
        self.copy = QtWidgets.QCheckBox("Create linked copies in the same component")
        self.copy.setObjectName("MoveCreateCopies")
        self.copy.toggled.connect(self.preview)
        layout.addWidget(self.copy)
        self.message = QtWidgets.QLabel("Preview begins when a value changes. Cancel restores the original design.")
        self.message.setObjectName("MoveMessage")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.buttons.setObjectName("MoveButtons")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(180)
        self.timer.timeout.connect(self.validate_owner)
        self.timer.start()
        self.resize(440, 410)

    def _owns_transaction(self):
        try:
            return bool(self.transaction and self.transaction_id and self.transaction_id > 0
                        and self.document.getBookedTransactionID() == self.transaction_id)
        except (AttributeError, NameError, ReferenceError, RuntimeError):
            return False  # Closing a native document invalidates its Python wrapper.

    def _reason(self):
        if self._closed:
            return "Move / Copy has already closed."
        try:
            if App.getDocument(self.document_name) is not self.document:
                return "The design that opened Move / Copy has closed."
            reason = _idle_reason(self.document, allow_transaction=self.transaction)
            if reason:
                return reason
            if self.transaction and not self._owns_transaction():
                return "The Move / Copy transaction is no longer active."
            edit = self.gui_document.getInEdit()
            if (self.gui_document.activeView() is not self.view
                    or (edit.Object if edit else None) is not self.edit_owner
                    or self.controller.context() != self.context
                    or Gui.activeWorkbench().name() != self.workbench):
                return "The active modeling context changed; Move / Copy was canceled."
            for index, obj in enumerate(self.targets):
                reason = _movable_reason(obj, self.document)
                if reason:
                    return reason
                if not getattr(obj, _placement_property(obj)).isSame(self.expected[index], 1e-9):
                    return "A selected placement changed outside Move / Copy."
                parents = _ancestors(obj)
                if len(parents) != len(self.parents[index]) or any(
                        parent is not old for parent, old in zip(parents, self.parents[index])):
                    return "A selected object changed component containment."
                if any(not getattr(parent, _placement_property(parent)).isSame(pose, 1e-9)
                       for parent, pose in zip(parents, self.parent_poses[index])):
                    return "A containing component moved outside Move / Copy."
                source = self.link_sources[index]
                if source and (obj.LinkedObject is not source[0] or bool(obj.LinkTransform) != source[1]):
                    return "A selected link changed its source or placement mode."
            for index, obj in enumerate(self.copies):
                if (self.document.getObject(obj.Name) is not obj
                        or obj.LinkedObject is not self.targets[index] or bool(obj.LinkTransform)
                        or obj.getParentGeoFeatureGroup() is not (self.parents[index][0] if self.parents[index] else None)
                        or not obj.LinkPlacement.isSame(self.copy_poses[index], 1e-9)
                        or _movable_reason(obj, self.document)):
                    return "A preview copy changed outside Move / Copy."
        except (AttributeError, NameError, ReferenceError, RuntimeError, ValueError):
            return "A selected object or its design is no longer available."
        return ""

    def validate_owner(self):
        if self._closed or self._updating:
            return False
        reason = self._reason()
        if reason:
            self.controller.notify(reason)
            self.reject()
            return False
        return True

    def _abort(self):
        try:
            if self._owns_transaction():
                self.document.abortTransaction()
                self.document.recompute()
        except (AttributeError, NameError, ReferenceError, RuntimeError):
            pass  # A native document may already have been closed.
        self.transaction = False
        self.transaction_id = None
        self.copies = []
        self.copy_poses = []
        self.expected = [App.Placement(value) for value in self.original]

    def preview(self, *_args):
        if self._updating or self._closed or not self.validate_owner():
            return False
        self._updating = True
        try:
            translation = [field.value() for field in self.translation]
            angles = [field.value() for field in self.rotation]
            poses = [transformed_placement(original, parent, translation, angles)
                     for original, parent in zip(self.original, self.parent_world)]
            changed = self.copy.isChecked() or any(not pose.isSame(original, 1e-9)
                                                   for pose, original in zip(poses, self.original))
            if not changed:
                self._abort()
                self.message.setText("No placement change. OK leaves the design unchanged.")
                return True
            if not self.transaction:
                self.document.openTransaction("Move / Copy")
                self.transaction = True
                self.transaction_id = self.document.getBookedTransactionID()
                if not self._owns_transaction():
                    raise ValueError("The native document could not start a Move / Copy transaction.")
            if self.copy.isChecked():
                for obj, original in zip(self.targets, self.original):
                    setattr(obj, _placement_property(obj), App.Placement(original))
                self.expected = [App.Placement(value) for value in self.original]
                if not self.copies:
                    for obj, parents in zip(self.targets, self.parents):
                        copy = self.document.addObject("App::Link", "Copy")
                        self.copies.append(copy)
                        copy.setLink(obj)
                        copy.LinkTransform = False
                        copy.Label = obj.Label + " Copy"
                        if parents:
                            parents[0].addObject(copy)
                for obj, pose in zip(self.copies, poses):
                    obj.LinkPlacement = pose
                self.copy_poses = [App.Placement(value) for value in poses]
            else:
                for obj in self.copies:
                    self.document.removeObject(obj.Name)
                self.copies = []
                self.copy_poses = []
                for obj, pose in zip(self.targets, poses):
                    setattr(obj, _placement_property(obj), pose)
                self.expected = [App.Placement(value) for value in poses]
            self.document.recompute()
            self.message.setText("Preview ready. OK commits one undoable Move / Copy operation.")
            return True
        except Exception as error:
            self._abort()
            self.message.setText("Move / Copy could not preview: " + str(error))
            return False
        finally:
            self._updating = False

    def accept(self):
        if not self.validate_owner() or not self.preview():
            return
        # Native recompute/observers run during preview. Recheck the final pose
        # and booking immediately before committing rather than trusting the
        # ownership established before those callbacks.
        if not self.validate_owner():
            return
        if self.transaction:
            self.document.commitTransaction()
            self.transaction = False
            self.transaction_id = None
        self._closed = True
        self.timer.stop()
        selected = self.copies or self.targets
        Gui.Selection.clearSelection()
        for obj in selected:
            Gui.Selection.addSelection(obj)
        self.controller.refresh_context()
        super().accept()

    def reject(self):
        if self._closed:
            return
        self._closed = True
        self.timer.stop()
        self._abort()
        self.controller.refresh_context()
        super().reject()


def run(controller):
    try:
        reason = _idle_reason(App.ActiveDocument)
        if reason:
            raise ValueError(reason)
        targets = collect_targets()
        existing = getattr(controller, "move_dialog", None)
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return existing
        dialog = MoveDialog(controller, targets)
        controller.move_dialog = dialog
        dialog.open()
        return dialog
    except (AttributeError, ReferenceError, RuntimeError, ValueError) as error:
        controller.notify(str(error))
        return None
