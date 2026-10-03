"""Searchable native command toolbox. SPDX-License-Identifier: LGPL-2.0-or-later"""
from __future__ import annotations

from pathlib import Path

from .shortcuts import QtCore, QtGui, QtWidgets


def rank_commands(catalog, query="", context="model"):
    """Rank all query terms across names, aliases and IDs, prioritizing context."""
    terms = query.casefold().split()
    ranked = []
    for entry in catalog:
        title = entry.get("title", entry["id"])
        aliases = entry.get("aliases", [])
        if isinstance(aliases, str):
            aliases = [aliases]
        contexts = entry.get("context", "*") or "*"
        if isinstance(contexts, str):
            contexts = [contexts]
        applicable = "*" in contexts or "all" in contexts or context in contexts
        content = " ".join([title, entry["id"]] + list(aliases)).casefold()
        if not all(term in content for term in terms):
            continue
        title_lower = title.casefold()
        exact = int(bool(query) and title_lower == query.casefold())
        prefix = int(bool(query) and title_lower.startswith(query.casefold()))
        alias_match = int(bool(query) and query.casefold() in [alias.casefold() for alias in aliases])
        ranked.append(((-int(applicable), -exact, -prefix, -alias_match, title_lower), entry))
    ranked.sort(key=lambda result: result[0])
    return [entry for _, entry in ranked]


_Dialog = QtWidgets.QDialog if QtWidgets else object


class SearchDialog(_Dialog):
    def __init__(self, controller, main_window):
        if QtWidgets is None:
            raise RuntimeError("The command toolbox requires Qt.")
        super().__init__(main_window)
        self.controller = controller
        self.main_window = main_window
        self._catalog = []
        self.setObjectName("FissionCommandToolbox")
        self.setWindowTitle("Fission — Command Toolbox")
        self.resize(680, 440)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)
        layout = QtWidgets.QVBoxLayout(self)
        self.input = QtWidgets.QLineEdit()
        self.input.setObjectName("FissionCommandSearchInput")
        self.input.setPlaceholderText("Search a command or familiar CAD term…")
        self.input.textChanged.connect(self._populate)
        self.input.installEventFilter(self)
        layout.addWidget(self.input)
        self.results = QtWidgets.QTreeWidget()
        self.results.setObjectName("FissionCommandSearchResults")
        self.results.setHeaderLabels(["Command", "Shortcut", "Context"])
        self.results.setRootIsDecorated(False)
        self.results.setUniformRowHeights(True)
        self.results.setAlternatingRowColors(True)
        self.results.itemActivated.connect(self._activate)
        layout.addWidget(self.results, 1)
        self.help = QtWidgets.QLabel("Enter runs the selected command · ↑ / ↓ selects · Esc closes")
        layout.addWidget(self.help)

    def context(self):
        resolver = getattr(self.controller, "context", None)
        return resolver() if callable(resolver) else "model"

    def _manager(self):
        for name in ("shortcuts", "shortcut_manager"):
            manager = getattr(self.controller, name, None)
            if manager is not None and hasattr(manager, "shortcut_for"):
                return manager
        return None

    def _icon(self, name):
        if not name:
            return QtGui.QIcon()
        path = Path(str(name))
        if path.is_file():
            return QtGui.QIcon(str(path))
        resources = Path(__file__).resolve().parents[1] / "resources" / "icons"
        for candidate in (resources / str(name), resources / (str(name) + ".svg")):
            if candidate.is_file():
                return QtGui.QIcon(str(candidate))
        icon = QtGui.QIcon.fromTheme(str(name))
        if icon.isNull():
            resource = str(name) if str(name).startswith(":/") else ":/icons/" + str(name) + ".svg"
            icon = QtGui.QIcon(resource)
        return icon

    def _populate(self, query=""):
        self.results.clear()
        manager = self._manager()
        context = self.context()
        matches = rank_commands(self._catalog, query, context)
        for entry in matches[:100]:
            shortcut = manager.shortcut_for(entry["id"], context) if manager else entry.get("shortcut", "")
            contexts = entry.get("context", "*") or "*"
            context_label = ", ".join(contexts) if isinstance(contexts, (list, tuple)) else contexts
            item = QtWidgets.QTreeWidgetItem([entry.get("title", entry["id"]), shortcut,
                                             "Any workspace" if context_label in ("*", "all") else context_label.title()])
            item.setData(0, QtCore.Qt.UserRole, entry["id"])
            item.setIcon(0, self._icon(entry.get("icon")))
            aliases = entry.get("aliases", [])
            item.setToolTip(0, ", ".join(aliases) if isinstance(aliases, (list, tuple)) else str(aliases))
            self.results.addTopLevelItem(item)
        if self.results.topLevelItemCount():
            self.results.setCurrentItem(self.results.topLevelItem(0))
        self.results.setColumnWidth(0, 400)
        self.results.resizeColumnToContents(1)
        self.help.setText("Enter runs · ↑ / ↓ selects · Esc closes" if matches else "No matching commands")

    def show(self):
        self._catalog = list(self.controller.command_catalog())
        self.input.clear()
        self._populate("")
        super().show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()

    def _activate(self, item=None, column=0):
        item = item or self.results.currentItem()
        if item is None:
            return
        command_id = item.data(0, QtCore.Qt.UserRole)
        # Restore canvas focus before entering a FreeCAD tool or opening its panel.
        self.close()
        self.main_window.activateWindow()
        try:
            self.controller.execute(command_id)
        except Exception as exc:
            self.controller.notify("Could not run command: " + str(exc))

    def eventFilter(self, watched, event):
        if watched is self.input and event.type() == QtCore.QEvent.KeyPress:
            key = event.key()
            if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                self._activate()
                return True
            if key == QtCore.Qt.Key_Escape:
                self.close()
                return True
            if key in (QtCore.Qt.Key_Down, QtCore.Qt.Key_Up):
                current = self.results.indexOfTopLevelItem(self.results.currentItem())
                direction = 1 if key == QtCore.Qt.Key_Down else -1
                target = max(0, min(self.results.topLevelItemCount() - 1, current + direction))
                item = self.results.topLevelItem(target)
                if item is not None:
                    self.results.setCurrentItem(item)
                return True
        return super().eventFilter(watched, event)
