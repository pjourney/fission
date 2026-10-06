# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fission product browser and shared native document UI operations."""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

from .history import browser_records, derived, feature_state, object_key, supports_suppression


def native_icon(obj):
    try:
        icon = obj.ViewObject.Icon
        if isinstance(icon, QtGui.QIcon):
            return icon
        return QtGui.QIcon(icon)
    except (AttributeError, RuntimeError, TypeError):
        return Gui.getIcon(":/icons/PartDesign_Feature.svg")


def object_tooltip(obj):
    state, message = feature_state(obj)
    visible = getattr(getattr(obj, "ViewObject", None), "Visibility", None)
    lines = [obj.Label, "{} · {}".format(obj.Name, obj.TypeId)]
    if visible is not None:
        lines.append("Visible" if visible else "Hidden")
    if message:
        lines.append(message)
    if state == "suppressed":
        lines.append("Native feature suppression is active")
    return "\n".join(lines)


class _LabelDelegate(QtWidgets.QStyledItemDelegate):
    """Edit the authoritative Label, never a Timeline decoration or stale row."""

    def __init__(self, dock, view):
        super().__init__(view)
        self.dock = dock

    def createEditor(self, parent, option, index):
        if index.column() != 0:
            return None
        obj = self.dock._object(index.data(QtCore.Qt.UserRole))
        if obj is None or not self.dock._mutation_allowed([obj], "renaming an object"):
            return None
        editor = QtWidgets.QLineEdit(parent)
        editor._fission_object = obj
        editor._fission_key = object_key(obj)
        editor.setAccessibleName("Rename " + obj.Label)
        return editor

    def setEditorData(self, editor, index):
        editor.setText(editor._fission_object.Label)
        editor.selectAll()

    def setModelData(self, editor, model, index):
        # An editor can survive a document switch or deletion until Qt closes
        # it. Do not resolve the same name to a replacement object at commit.
        obj = editor._fission_object
        if self.dock._object(editor._fission_key) is not obj:
            self.dock.schedule_refresh()
            return
        self.dock._rename_object(obj, editor.text())


class _DocumentDock(QtWidgets.QDockWidget):
    """Observe App, view providers and selection without polling or rebuilding."""

    def __init__(self, title, main_window, controller):
        super().__init__(title, main_window)
        self.controller = controller
        self._closed = False
        self._syncing = False
        self._document_name = None
        self._document = None
        self._document_view = None
        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(70)
        self._refresh_timer.timeout.connect(self.refresh)
        self._selection_timer = QtCore.QTimer(self)
        self._selection_timer.setSingleShot(True)
        self._selection_timer.setInterval(0)
        self._selection_timer.timeout.connect(self.sync_selection)
        App.addDocumentObserver(self)
        Gui.addDocumentObserver(self)
        Gui.Selection.addObserver(self)
        self.destroyed.connect(self.shutdown)

    def shutdown(self, *_args):
        if self._closed:
            return
        self._closed = True
        for remove in (App.removeDocumentObserver, Gui.removeDocumentObserver, Gui.Selection.removeObserver):
            try:
                remove(self)
            except (RuntimeError, ValueError):
                pass

    def schedule_refresh(self, *_args):
        if not self._closed:
            self._refresh_timer.start()

    slotCreatedDocument = schedule_refresh
    slotDeletedDocument = schedule_refresh
    slotRelabelDocument = schedule_refresh
    slotActivateDocument = schedule_refresh
    slotChangedDocument = schedule_refresh
    slotCreatedObject = schedule_refresh
    slotDeletedObject = schedule_refresh
    slotChangedObject = schedule_refresh
    slotRecomputedObject = schedule_refresh
    slotRecomputedDocument = schedule_refresh
    slotUndoDocument = schedule_refresh
    slotRedoDocument = schedule_refresh
    slotInEdit = schedule_refresh
    slotResetEdit = schedule_refresh
    slotActivatedObject = schedule_refresh

    def selection_changed(self, *_args):
        if not self._closed and not self._syncing:
            self._selection_timer.start()

    addSelection = selection_changed
    removeSelection = selection_changed
    setSelection = selection_changed
    clearSelection = selection_changed

    def _object(self, key):
        if not key or len(key) != 2:
            return None
        try:
            if self._document is None or App.ActiveDocument is not self._document:
                return None
            document = App.getDocument(key[0])
            return document.getObject(key[1]) if document is self._document else None
        except (NameError, RuntimeError):
            return None

    def _install_document_keys(self, view):
        self._document_view = view
        # ShortcutManager defers these panel keys before resolving global
        # bindings; ShortcutOverride also protects against native QActions.
        view.setProperty("fissionDocumentPanelKeys", True)
        view.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self._label_delegate = _LabelDelegate(self, view)
        view.setItemDelegate(self._label_delegate)
        view.installEventFilter(self)

    def _selected_objects(self):
        view = self._document_view
        objects = []
        for item in view.selectedItems():
            if item.isHidden():
                continue
            key = item.data(0, QtCore.Qt.UserRole) if isinstance(item, QtWidgets.QTreeWidgetItem) else item.data(QtCore.Qt.UserRole)
            obj = self._object(key)
            if obj is not None:
                objects.append(obj)
        return objects

    def _single_selected(self):
        objects = self._selected_objects()
        if len(objects) == 1:
            return objects[0]
        if len(objects) > 1:
            self.controller.notify("Select one object to edit or rename.")
        return None

    def eventFilter(self, watched, event):
        if watched is not self._document_view or self._closed:
            return super().eventFilter(watched, event)
        if event.type() not in (QtCore.QEvent.ShortcutOverride, QtCore.QEvent.KeyPress):
            return False
        # Delegate editors own their Return, Escape, Delete and typing. The
        # view can receive a propagated event even while its editor has focus.
        focus = QtWidgets.QApplication.focusWidget()
        if focus not in (watched, watched.viewport()):
            return False
        modifiers = event.modifiers() & (QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier | QtCore.Qt.ShiftModifier | QtCore.Qt.MetaModifier)
        navigation = (QtCore.Qt.Key_Left, QtCore.Qt.Key_Right, QtCore.Qt.Key_Up, QtCore.Qt.Key_Down,
                      QtCore.Qt.Key_Home, QtCore.Qt.Key_End, QtCore.Qt.Key_PageUp, QtCore.Qt.Key_PageDown)
        if event.key() in navigation and not modifiers & (QtCore.Qt.AltModifier | QtCore.Qt.MetaModifier):
            if event.type() == QtCore.QEvent.ShortcutOverride:
                # Native camera rotation uses Shift+Left/Right, and view
                # commands also claim Ctrl+arrows. Here Qt owns navigation
                # and range selection while the panel has keyboard focus.
                event.accept()
                return True
            return False
        if modifiers or event.key() not in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter, QtCore.Qt.Key_F2, QtCore.Qt.Key_Delete):
            return False
        event.accept()
        if event.type() == QtCore.QEvent.ShortcutOverride or event.isAutoRepeat():
            return True
        if event.key() == QtCore.Qt.Key_Delete:
            self._delete_selected()
        else:
            obj = self._single_selected()
            if obj is not None:
                if event.key() == QtCore.Qt.Key_F2:
                    self._rename_selected(obj)
                else:
                    self._enter_object(obj)
        # Empty, synthetic and stale rows also consume these keys. They must
        # not fall through to a native command acting on unrelated selection.
        return True

    def _mutation_allowed(self, objects, action, allow_assembly=True):
        if not objects:
            return False
        try:
            for obj in objects:
                if obj.Document is not self._document or self._object(object_key(obj)) is not obj:
                    self.schedule_refresh()
                    return False
                gui_doc = Gui.getDocument(obj.Document.Name)
                edit = gui_doc.getInEdit() if gui_doc else None
                idle_assembly = allow_assembly and edit and derived(getattr(edit, "Object", None), "Assembly::AssemblyObject")
                if obj.Document.HasPendingTransaction or Gui.Control.activeDialog() or (edit and not idle_assembly):
                    self.controller.notify("Finish or cancel the active modeling operation before {}.".format(action))
                    self.schedule_refresh()
                    return False
        except (AttributeError, RuntimeError):
            self.schedule_refresh()
            return False
        return True

    def _rename_object(self, obj, label):
        label = label.strip()
        if label and label != obj.Label:
            self._transaction(obj, "Rename object", lambda: setattr(obj, "Label", label))
        self.schedule_refresh()

    def _delete_selected(self):
        objects = self._selected_objects()
        if self._mutation_allowed(objects, "deleting objects"):
            self._select(objects)
            # One native invocation preserves the full set, dependency
            # confirmation and a single native Undo transaction.
            self.controller.execute("Std_Delete")

    def _sync_current(self, view, selected):
        current = view.currentItem()
        key = current.data(0, QtCore.Qt.UserRole) if isinstance(current, QtWidgets.QTreeWidgetItem) else current.data(QtCore.Qt.UserRole) if current else None
        if key in selected and not current.isHidden():
            return current
        for selected_key, item in self._items.items():
            if selected_key in selected and not item.isHidden():
                view.selectionModel().setCurrentIndex(view.indexFromItem(item), QtCore.QItemSelectionModel.NoUpdate)
                return item
        return None

    def _edit_object(self, obj):
        if self._mutation_allowed([obj], "editing history", allow_assembly=False):
            self.controller.edit_object(obj)

    def _select(self, objects):
        if self._syncing:
            return
        self._syncing = True
        try:
            Gui.Selection.clearSelection()
            for obj in objects:
                if obj is not None:
                    Gui.Selection.addSelection(obj)
        finally:
            self._syncing = False
        self.controller.refresh_context()

    def _transaction(self, obj, title, operation, recompute=False):
        if not self._mutation_allowed([obj], title.lower()):
            return
        document = obj.Document
        # The guard leaves an active feature task's transaction untouched.
        try:
            document.openTransaction(title)
            operation()
            if recompute:
                document.recompute()
            document.commitTransaction()
        except Exception as exc:
            document.abortTransaction()
            self.controller.notify("{}: {}".format(title, exc))
        self.schedule_refresh()

    def _toggle_visibility(self, obj):
        view = getattr(obj, "ViewObject", None)
        if view is not None and "Visibility" in view.PropertiesList:
            self._transaction(obj, "Toggle visibility", lambda: setattr(view, "Visibility", not view.Visibility))

    def _toggle_suppression(self, obj):
        if supports_suppression(obj):
            self._transaction(obj, "Toggle feature suppression", lambda: setattr(obj, "Suppressed", not obj.Suppressed), True)

    def _activate(self, obj):
        try:
            if self._object(object_key(obj)) is not obj:
                self.schedule_refresh()
                return
        except (AttributeError, RuntimeError):
            self.schedule_refresh()
            return
        if not derived(obj, "Assembly::AssemblyObject") and not self._mutation_allowed([obj], "activating an object"):
            return
        try:
            gui_doc = Gui.getDocument(obj.Document.Name)
            view = gui_doc.activeView()
            if derived(obj, "Assembly::AssemblyObject"):
                if Gui.activeWorkbench().name() != "FissionWorkbench":
                    if not self.controller.switch_workspace("Design"):
                        return
                edit = gui_doc.getInEdit()
                if Gui.Control.activeDialog() or obj.Document.HasPendingTransaction or (edit and not derived(edit.Object, "Assembly::AssemblyObject")):
                    self.controller.notify("Finish or cancel the current operation before activating an assembly.")
                    return
                App.setActiveDocument(obj.Document.Name)
                if edit and edit.Object is not obj:
                    gui_doc.resetEdit()
                if not edit or edit.Object is not obj:
                    assemblies = [item for item in obj.Document.Objects if derived(item, "Assembly::AssemblyObject")]
                    if len(assemblies) == 1:
                        if not self.controller.execute("Assembly_ActivateAssembly"):
                            return
                    else:
                        # The native command shows a chooser for multiple
                        # assemblies. A Browser activation already identifies
                        # the target; use that command's native setEdit API.
                        if gui_doc.setEdit(obj.Name) is False:
                            return
            elif derived(obj, "PartDesign::Body"):
                component = obj.getParentGeoFeatureGroup()
                view.setActiveObject("part", component if component and derived(component, "App::Part") else None)
                view.setActiveObject("pdbody", obj)
            elif derived(obj, "App::Part"):
                view.setActiveObject("part", obj)
                body = view.getActiveObject("pdbody")
                if body and body.getParentGeoFeatureGroup() is not obj:
                    view.setActiveObject("pdbody", None)
            else:
                return
            self._select([obj])
            self.controller.notify("Active: " + obj.Label)
            self.controller.refresh_context()
            self.schedule_refresh()
        except (AttributeError, RuntimeError) as exc:
            self.controller.notify("Could not activate {}: {}".format(obj.Label, exc))

    def _delete(self, obj):
        if not self._selected_objects() and self._mutation_allowed([obj], "deleting objects"):
            self._select([obj])
            self.sync_selection()
        self._delete_selected()

    def _menu(self, obj, position, rename=None, history_explanation=None):
        menu = QtWidgets.QMenu(self)
        if obj is not None:
            menu.addAction("Edit feature", lambda: self._edit_object(obj))
            if rename is not None:
                menu.addAction("Rename", rename)
            if derived(obj, "PartDesign::Body") or derived(obj, "App::Part"):
                menu.addAction("Activate " + ("body" if derived(obj, "PartDesign::Body") else "component"), lambda: self._activate(obj))
            view = getattr(obj, "ViewObject", None)
            if view is not None and "Visibility" in view.PropertiesList:
                menu.addAction("Hide" if view.Visibility else "Show", lambda: self._toggle_visibility(obj))
            if supports_suppression(obj):
                menu.addAction("Unsuppress feature" if obj.Suppressed else "Suppress feature", lambda: self._toggle_suppression(obj))
            menu.addSeparator()
        menu.addAction("Create sketch", lambda: self.controller.execute("Fission_CreateSketch"))
        menu.addAction("Create body", lambda: self.controller.execute("PartDesign_Body"))
        menu.addAction("Create component", lambda: self.controller.execute("Std_Part"))
        if obj is not None:
            menu.addSeparator()
            if history_explanation:
                action = menu.addAction("Why history reordering is unavailable…")
                action.triggered.connect(lambda: self.controller.notify(history_explanation))
                action.setToolTip(history_explanation)
            menu.addAction("Delete…", lambda: self._delete(obj))
        menu.exec_(position)


class Browser(_DocumentDock):
    def __init__(self, main_window, controller):
        super().__init__("Browser", main_window, controller)
        self.setObjectName("FissionBrowserDock")
        self.setMinimumWidth(245)
        self.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
        wrapper = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(wrapper)
        layout.setContentsMargins(8, 6, 8, 8)
        self.filter = QtWidgets.QLineEdit()
        self.filter.setObjectName("FissionBrowserFilter")
        self.filter.setPlaceholderText("Find in design…")
        self.filter.setClearButtonEnabled(True)
        self.filter.setAccessibleName("Filter browser objects")
        layout.addWidget(self.filter)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setObjectName("FissionBrowserTree")
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Design", "Visible"])
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.tree.setIndentation(14)
        self.tree.setAlternatingRowColors(False)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree.setDragDropMode(QtWidgets.QAbstractItemView.NoDragDrop)
        self.tree.setUniformRowHeights(True)
        self.tree.setIconSize(QtCore.QSize(18, 18))
        self._install_document_keys(self.tree)
        self.tree.itemSelectionChanged.connect(self._from_tree)
        self.tree.itemChanged.connect(self._item_changed)
        self.tree.itemDoubleClicked.connect(self._double_clicked)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.filter.textChanged.connect(self._apply_filter)
        layout.addWidget(self.tree)
        self.setWidget(wrapper)
        self._items = {}
        self.refresh()

    def refresh(self):
        if self._closed:
            return
        document = App.ActiveDocument
        name = document.Name if document else None
        switched = document is not self._document
        self._document_name = name
        self._document = document
        records = browser_records(document)
        desired = {record.key for record in records}
        active_keys = set()
        if document:
            view = Gui.getDocument(document.Name).activeView()
            for active_kind in ("pdbody", "part"):
                active = view.getActiveObject(active_kind) if view else None
                if active:
                    active_keys.add(object_key(active))
        self._syncing = True
        self.tree.blockSignals(True)
        try:
            if switched:
                self.tree.clear()
                self._items.clear()
            # Detach all stale children before destroying their parent items.
            retained_items = {id(item) for key, item in self._items.items() if key in desired}
            for key, item in self._items.items():
                if item.parent() is not None:
                    if id(item.parent()) not in retained_items:
                        self._detach(item)
            for key in list(self._items):
                if key not in desired:
                    self._detach(self._items[key])
                    del self._items[key]
            created = set()
            for record in records:
                if record.key not in self._items:
                    item = QtWidgets.QTreeWidgetItem()
                    item.setData(0, QtCore.Qt.UserRole, record.key)
                    self._items[record.key] = item
                    created.add(record.key)
            # Parents may appear later in Document.Objects after restore.
            for record in records:
                item = self._items[record.key]
                parent = self._items.get(record.parent)
                if item.parent() is not parent or (parent is None and self.tree.indexOfTopLevelItem(item) < 0):
                    self._detach(item)
                    (parent.addChild(item) if parent else self.tree.addTopLevelItem(item))
                item.setText(0, record.label)
                if record.obj is None:
                    item.setFlags(QtCore.Qt.ItemIsEnabled)
                    item.setToolTip(0, "Product structure" if record.parent else "Active design")
                    if record.key in created:
                        item.setExpanded(record.parent is None or record.label in ("Bodies", "Components", "Features", "Sketches"))
                    continue
                obj = record.obj
                state, _message = feature_state(obj)
                item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable)
                item.setIcon(0, native_icon(obj))
                item.setToolTip(0, object_tooltip(obj) + ("\nActive modeling context" if record.key in active_keys else ""))
                view = getattr(obj, "ViewObject", None)
                visible = view is not None and "Visibility" in view.PropertiesList
                if visible:
                    item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                    item.setCheckState(1, QtCore.Qt.Checked if view.Visibility else QtCore.Qt.Unchecked)
                    item.setToolTip(1, "Show or hide {}".format(obj.Label))
                font = item.font(0)
                font.setBold(record.key in active_keys)
                font.setStrikeOut(state == "suppressed")
                font.setItalic(visible and not view.Visibility)
                item.setFont(0, font)
                item.setForeground(0, QtGui.QBrush(QtGui.QColor("#e3656f") if state == "error" else QtGui.QColor("#dda957") if state == "touched" else self.tree.palette().color(QtGui.QPalette.Text)))
                if record.key in created and (derived(obj, "PartDesign::Body") or derived(obj, "App::Part")):
                    item.setExpanded(True)
        finally:
            self.tree.blockSignals(False)
            self._syncing = False
        self._apply_filter()
        self.sync_selection()

    def _detach(self, item):
        parent = item.parent()
        if parent is not None:
            parent.takeChild(parent.indexOfChild(item))
        else:
            index = self.tree.indexOfTopLevelItem(item)
            if index >= 0:
                self.tree.takeTopLevelItem(index)

    def _apply_filter(self, *_args):
        query = self.filter.text().strip().casefold()
        def visit(item):
            matches = query in item.text(0).casefold()
            for index in range(item.childCount()):
                matches = visit(item.child(index)) or matches
            item.setHidden(not matches)
            if query and matches:
                item.setExpanded(True)
            return matches
        for index in range(self.tree.topLevelItemCount()):
            visit(self.tree.topLevelItem(index))

    def sync_selection(self):
        if self._closed or self._syncing:
            return
        selected = {object_key(obj) for obj in Gui.Selection.getSelection()}
        self._syncing = True
        self.tree.blockSignals(True)
        try:
            for key, item in self._items.items():
                item.setSelected(key in selected)
                if key in selected:
                    ancestor = item.parent()
                    while ancestor:
                        ancestor.setExpanded(True)
                        ancestor = ancestor.parent()
            current = self._sync_current(self.tree, selected)
            if current is not None:
                self.tree.scrollToItem(current)
        finally:
            self.tree.blockSignals(False)
            self._syncing = False

    def _from_tree(self):
        self._select([self._object(item.data(0, QtCore.Qt.UserRole)) for item in self.tree.selectedItems()])

    def _item_changed(self, item, column):
        if self._syncing:
            return
        obj = self._object(item.data(0, QtCore.Qt.UserRole))
        if obj is None:
            return
        if column == 1:
            view = obj.ViewObject
            visible = item.checkState(1) == QtCore.Qt.Checked
            if visible != view.Visibility:
                self._transaction(obj, "Toggle visibility", lambda: setattr(view, "Visibility", visible))
        elif item.text(0) != obj.Label:
            label = item.text(0).strip()
            if label:
                self._transaction(obj, "Rename object", lambda: setattr(obj, "Label", label))
            else:
                self.schedule_refresh()

    def _double_clicked(self, item, column):
        obj = self._object(item.data(0, QtCore.Qt.UserRole))
        if obj is not None and column == 0:
            self._enter_object(obj)

    def _enter_object(self, obj):
        if derived(obj, "PartDesign::Body") or derived(obj, "App::Part") or derived(obj, "Assembly::AssemblyObject"):
            self._activate(obj)
        else:
            self._edit_object(obj)

    def _rename_selected(self, obj):
        if self._mutation_allowed([obj], "renaming an object"):
            self.tree.editItem(self._items[object_key(obj)], 0)

    def _context_menu(self, point):
        item = self.tree.itemAt(point)
        obj = self._object(item.data(0, QtCore.Qt.UserRole)) if item else None
        if obj and item not in self.tree.selectedItems():
            self._select([obj])
            self.sync_selection()
        self._menu(obj, self.tree.viewport().mapToGlobal(point), lambda: self._rename_selected(obj) if obj else None)
