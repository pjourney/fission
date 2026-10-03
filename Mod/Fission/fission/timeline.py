# SPDX-License-Identifier: LGPL-2.1-or-later
"""Horizontal native feature history, never a synthetic replay/rollback engine."""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

from .browser import _DocumentDock, native_icon, object_tooltip
from .history import chronological_features, derived, feature_state, object_key, reorder_explanation


class Timeline(_DocumentDock):
    def __init__(self, main_window, controller):
        super().__init__("Timeline", main_window, controller)
        self.setObjectName("FissionTimelineDock")
        self.setAllowedAreas(QtCore.Qt.BottomDockWidgetArea | QtCore.Qt.TopDockWidgetArea)
        self.setMinimumHeight(142)
        self._items = {}
        self._features = []
        wrapper = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(wrapper)
        layout.setContentsMargins(10, 3, 10, 5)
        header = QtWidgets.QHBoxLayout()
        self.description = QtWidgets.QLabel("Select a feature to inspect or double-click to edit")
        self.description.setObjectName("FissionTimelineHint")
        header.addWidget(self.description, 1)
        self.recompute_button = QtWidgets.QToolButton()
        self.recompute_button.setText("Recompute")
        self.recompute_button.setToolTip("Recompute the active design using its native dependency graph")
        self.recompute_button.clicked.connect(lambda: controller.execute("Std_Refresh"))
        header.addWidget(self.recompute_button)
        layout.addLayout(header)
        self.list = QtWidgets.QListWidget()
        self.list.setObjectName("FissionTimelineList")
        self.list.setViewMode(QtWidgets.QListView.IconMode)
        self.list.setFlow(QtWidgets.QListView.LeftToRight)
        self.list.setWrapping(False)
        self.list.setResizeMode(QtWidgets.QListView.Adjust)
        self.list.setMovement(QtWidgets.QListView.Static)
        self.list.setDragDropMode(QtWidgets.QAbstractItemView.NoDragDrop)
        self.list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.list.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.list.setIconSize(QtCore.QSize(28, 28))
        self.list.setGridSize(QtCore.QSize(106, 65))
        self.list.setSpacing(3)
        self.list.setTextElideMode(QtCore.Qt.ElideRight)
        self.list.setUniformItemSizes(True)
        self.list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.list.setAccessibleName("Parametric feature history in document creation order")
        self.list.itemSelectionChanged.connect(self._from_list)
        self.list.itemDoubleClicked.connect(self._edit_item)
        self.list.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self.list)
        self.setWidget(wrapper)
        self.refresh()

    def refresh(self):
        if self._closed:
            return
        document = App.ActiveDocument
        name = document.Name if document else None
        switched = self._document_name != name
        self._document_name = name
        self._features = chronological_features(document)
        desired = {object_key(obj) for obj in self._features}
        self._syncing = True
        self.list.blockSignals(True)
        try:
            if switched:
                self.list.clear()
                self._items.clear()
            for key in list(self._items):
                if key not in desired:
                    self.list.takeItem(self.list.row(self._items.pop(key)))
            tips = {object_key(obj.Tip) for obj in document.Objects if derived(obj, "PartDesign::Body") and getattr(obj, "Tip", None)} if document else set()
            edit = None
            if document:
                gui_doc = Gui.getDocument(document.Name)
                view_provider = gui_doc.getInEdit()
                edit = object_key(view_provider.Object) if view_provider else None
            for index, obj in enumerate(self._features):
                key = object_key(obj)
                item = self._items.get(key)
                if item is None:
                    item = QtWidgets.QListWidgetItem()
                    item.setData(QtCore.Qt.UserRole, key)
                    self.list.insertItem(index, item)
                    self._items[key] = item
                elif self.list.row(item) != index:
                    self.list.takeItem(self.list.row(item))
                    self.list.insertItem(index, item)
                state, message = feature_state(obj)
                marker = "▶ " if key == edit else "◆ " if key in tips else ""
                item.setText(marker + obj.Label)
                item.setIcon(native_icon(obj))
                tooltip = object_tooltip(obj) + "\nHistory step {}".format(index + 1)
                if key == edit:
                    tooltip += "\nCurrently editing"
                elif key in tips:
                    tooltip += "\nCurrent body tip (final result)"
                item.setToolTip(tooltip)
                font = item.font()
                font.setBold(key in tips or key == edit)
                font.setStrikeOut(state == "suppressed")
                font.setItalic(not getattr(obj.ViewObject, "Visibility", False))
                item.setFont(font)
                item.setForeground(QtGui.QBrush(QtGui.QColor("#e3656f") if state == "error" else QtGui.QColor("#dda957") if state == "touched" else self.list.palette().color(QtGui.QPalette.Text)))
            self.recompute_button.setEnabled(document is not None)
            self.description.setText(
                "{} feature{} · ◆ Body tip · Double-click to edit".format(len(self._features), "" if len(self._features) == 1 else "s")
                if self._features else "Create a sketch or a modeling feature to begin this design" if document else "Create or open a design to view its feature history"
            )
            self.description.setToolTip("Native document creation order. Body tips are current results; the timeline does not simulate rollback.")
        finally:
            self.list.blockSignals(False)
            self._syncing = False
        self.sync_selection()

    def sync_selection(self):
        if self._closed or self._syncing:
            return
        selected = {object_key(obj) for obj in Gui.Selection.getSelection()}
        self._syncing = True
        self.list.blockSignals(True)
        try:
            for key, item in self._items.items():
                item.setSelected(key in selected)
            for key in selected:
                if key in self._items:
                    self.list.scrollToItem(self._items[key])
                    break
        finally:
            self.list.blockSignals(False)
            self._syncing = False

    def _from_list(self):
        self._select([self._object(item.data(QtCore.Qt.UserRole)) for item in self.list.selectedItems()])

    def _edit_item(self, item):
        obj = self._object(item.data(QtCore.Qt.UserRole))
        if obj:
            self.controller.edit_object(obj)

    def _rename(self, obj):
        label, accepted = QtWidgets.QInputDialog.getText(self, "Rename feature", "Name", QtWidgets.QLineEdit.Normal, obj.Label)
        if accepted and label.strip():
            self._transaction(obj, "Rename feature", lambda: setattr(obj, "Label", label.strip()))

    def _context_menu(self, point):
        item = self.list.itemAt(point)
        obj = self._object(item.data(QtCore.Qt.UserRole)) if item else None
        if obj:
            self._select([obj])
        index = self.list.row(item) if item else -1
        reason = reorder_explanation(self._features, index) if obj else None
        self._menu(obj, self.list.viewport().mapToGlobal(point), lambda: self._rename(obj), reason)
