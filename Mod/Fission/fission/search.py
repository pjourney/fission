"""Searchable native command toolbox. SPDX-License-Identifier: LGPL-2.0-or-later"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from . import shortcuts as _shortcuts
from .shortcuts import QtCore, QtGui, QtWidgets

SEARCH_HISTORY_SCHEMA = 1
SEARCH_RECENT_LIMIT = 12
SEARCH_HISTORY_KEY = "CommandSearchHistory"
_COMMAND_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def normalize_search_text(value):
    """Normalize human text without interpreting arbitrary capitalization."""
    value = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(re.sub(r"[_\W]+", " ", value, flags=re.UNICODE).casefold().split())


def _native_id_words(command_id):
    value = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", command_id)
    return normalize_search_text(re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value))


def normalize_recents(command_ids):
    """Return bounded, unique IDs without interpreting persisted text as code."""
    if not isinstance(command_ids, (list, tuple)):
        return []
    result = []
    for command_id in command_ids:
        if (isinstance(command_id, str) and len(command_id) <= 160
                and _COMMAND_ID.fullmatch(command_id) and command_id not in result):
            result.append(command_id)
            if len(result) == SEARCH_RECENT_LIMIT:
                break
    return result


def read_recents(parameters):
    if parameters is None:
        return []
    try:
        data = json.loads(parameters.GetString(SEARCH_HISTORY_KEY, ""))
        if (not isinstance(data, dict) or type(data.get("schema_version")) is not int
                or data["schema_version"] != SEARCH_HISTORY_SCHEMA):
            return []
        return normalize_recents(data.get("commands"))
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return []


def write_recents(parameters, command_ids):
    commands = normalize_recents(command_ids)
    if parameters is not None:
        parameters.SetString(SEARCH_HISTORY_KEY, json.dumps(
            {"schema_version": SEARCH_HISTORY_SCHEMA, "commands": commands}))
    return commands


def rank_commands(catalog, query="", context="model", recent_ids=()):
    """Rank semantic matches before workspace ties; empty searches favor recents."""
    query = normalize_search_text(query)
    terms = query.split()
    recents = {command_id: index for index, command_id in enumerate(normalize_recents(recent_ids))}
    ranked = []
    for entry in catalog:
        command_id = entry["id"]
        title = normalize_search_text(entry.get("title", command_id))
        aliases = entry.get("aliases", []) or []
        if isinstance(aliases, str):
            aliases = [aliases]
        aliases = [normalize_search_text(alias) for alias in aliases]
        contexts = entry.get("context", "*") or "*"
        if isinstance(contexts, str):
            contexts = [contexts]
        applicable = "*" in contexts or "all" in contexts or context in contexts
        native_id = _native_id_words(command_id)
        literal_id = normalize_search_text(command_id)
        content = " ".join([title, native_id, literal_id] + aliases + list(contexts))
        if not all(term in content for term in terms):
            continue
        if not query:
            relevance = 0
        elif query == title:
            relevance = 0
        elif query in aliases:
            relevance = 1
        elif title.startswith(query):
            relevance = 2
        elif any(alias.startswith(query) for alias in aliases):
            relevance = 3
        elif all(term in title.split() for term in terms):
            relevance = 4
        elif any(all(term in alias.split() for term in terms) for alias in aliases):
            relevance = 5
        elif query in (native_id, literal_id) or native_id.startswith(query):
            relevance = 6
        else:
            relevance = 7
        recent = recents.get(command_id, SEARCH_RECENT_LIMIT)
        wrapper = not command_id.startswith("Fission_")
        key = ((relevance, -int(applicable), recent, wrapper, title, command_id) if query
               else (-int(applicable), recent, wrapper, title, command_id))
        ranked.append((key, entry))
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
        self._available = {}
        self._native_state_ready = True
        self._source_focus = None
        self._owner_token = None
        self._owner_context = None
        self._restore_on_close = True
        self._dispatch_pending = False
        self._generation = 0
        self._selection_service = None
        self._selection_refresh_timer = QtCore.QTimer(self)
        self._selection_refresh_timer.setSingleShot(True)
        # Gui.Command.update schedules native action evaluation after 150 ms.
        # One follow-up reads those cached flags without querying unloaded tools.
        self._selection_refresh_timer.setInterval(180)
        self._selection_refresh_timer.timeout.connect(self.refresh_availability)
        self.destroyed.connect(self._unobserve_selection)
        self._recents = read_recents(getattr(controller, "settings", None))
        self.setObjectName("FissionCommandToolbox")
        self.setWindowTitle("Fission — Command Toolbox")
        self.resize(780, 440)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)
        layout = QtWidgets.QVBoxLayout(self)
        self.input = QtWidgets.QLineEdit()
        self.input.setObjectName("FissionCommandSearchInput")
        self.input.setAccessibleName("Search native CAD commands")
        self.input.setPlaceholderText("Search a command or familiar CAD term…")
        self.input.setClearButtonEnabled(True)
        self.input.textChanged.connect(self._populate)
        layout.addWidget(self.input)
        self.results = QtWidgets.QTreeWidget()
        self.results.setObjectName("FissionCommandSearchResults")
        self.results.setHeaderLabels(["Command", "Shortcut", "Context", "Status"])
        self.results.setRootIsDecorated(False)
        self.results.setUniformRowHeights(True)
        self.results.setAlternatingRowColors(True)
        self.results.itemActivated.connect(self._activate)
        self.input.installEventFilter(self)
        self.results.installEventFilter(self)
        layout.addWidget(self.results, 1)
        self.help = QtWidgets.QLabel("Enter runs the selected command · ↑ / ↓ selects · Esc closes")
        self.help.setWordWrap(True)
        layout.addWidget(self.help)

    def context(self):
        resolver = getattr(self.controller, "context", None)
        return resolver() if callable(resolver) else "model"

    def _token(self):
        resolver = getattr(self.controller, "command_context_token", None)
        return resolver() if callable(resolver) else None

    def _owner_valid(self):
        try:
            return (getattr(self.controller, "active", True)
                    and not getattr(self.controller, "_activation_pending", False)
                    and self.context() == self._owner_context and self._token() == self._owner_token)
        except (AttributeError, RuntimeError, OSError):
            return False

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

    def _refresh_native_state(self):
        refresh = getattr(self.controller, "refresh_command_state", None)
        try:
            if callable(refresh):
                refresh()
            self._native_state_ready = True
        except (AttributeError, RuntimeError, OSError):
            self._native_state_ready = False
        return self._native_state_ready

    def _command_available(self, command_id, entry=None):
        if not self._native_state_ready:
            return False
        checker = getattr(self.controller, "command_available", None)
        try:
            return bool(checker(command_id)) if callable(checker) else bool((entry or {}).get("available", True))
        except (AttributeError, RuntimeError, OSError):
            return False

    def _populate(self, query="", preserve_selection=False):
        if self._owner_context is not None and not self._owner_valid():
            self.close()
            return
        selected = self.results.currentItem()
        selected_id = selected.data(0, QtCore.Qt.UserRole) if selected and preserve_selection else None
        self.results.clear()
        self._available.clear()
        manager = self._manager()
        context = self.context()
        self._refresh_native_state()
        matches = rank_commands(self._catalog, query, context, self._recents)
        first_enabled = retained = None
        unavailable = 0
        self.results.setUpdatesEnabled(False)
        try:
            for entry in matches:
                command_id = entry["id"]
                shortcut = manager.shortcut_for(command_id, context) if manager else entry.get("shortcut", "")
                contexts = entry.get("context", "*") or "*"
                context_label = ", ".join(contexts) if isinstance(contexts, (list, tuple)) else contexts
                enabled = self._command_available(command_id, entry)
                self._available[command_id] = enabled
                item = QtWidgets.QTreeWidgetItem([entry.get("title", command_id), shortcut,
                    "Any workspace" if context_label in ("*", "all") else context_label.title(),
                    "Ready" if enabled else "Unavailable"])
                item.setData(0, QtCore.Qt.UserRole, command_id)
                item.setIcon(0, self._icon(entry.get("icon")))
                aliases = entry.get("aliases", []) or []
                aliases = ", ".join(aliases) if isinstance(aliases, (list, tuple)) else str(aliases)
                hint = command_id + ("\n" + aliases if aliases else "")
                if not enabled:
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEnabled)
                    hint += "\nUnavailable for the current workspace, document, selection, or active operation."
                    unavailable += 1
                elif first_enabled is None:
                    first_enabled = item
                item.setToolTip(0, hint)
                item.setToolTip(3, hint)
                self.results.addTopLevelItem(item)
                if enabled and command_id == selected_id:
                    retained = item
            if retained or first_enabled:
                self.results.setCurrentItem(retained or first_enabled)
            self.results.setColumnWidth(0, 360)
            self.results.resizeColumnToContents(1)
            self.results.resizeColumnToContents(2)
            self.results.resizeColumnToContents(3)
        finally:
            self.results.setUpdatesEnabled(True)
        if not matches:
            self.help.setText("No matching commands. Try a command name, native ID, or familiar CAD term.")
        elif first_enabled is None:
            self.help.setText("{} matching commands · None available for the current selection or operation · Esc closes".format(len(matches)))
        else:
            self.help.setText("{} commands{} · Enter runs · ↑ / ↓ skips unavailable commands · Esc closes".format(
                len(matches), " · {} unavailable".format(unavailable) if unavailable else ""))

    def refresh_availability(self):
        if self.isVisible():
            if not self.validate_owner():
                return
            self._populate(self.input.text(), preserve_selection=True)

    def validate_owner(self):
        """Cheap owner check suitable for the controller's existing refresh."""
        if self.isVisible() and not self._owner_valid():
            self.close()
            return False
        return True

    def _observe_selection(self):
        selection = getattr(_shortcuts.Gui, "Selection", None)
        if self._selection_service is None and callable(getattr(selection, "addObserver", None)):
            selection.addObserver(self)
            self._selection_service = selection

    def _unobserve_selection(self, *_args):
        selection, self._selection_service = self._selection_service, None
        if selection is not None:
            try:
                selection.removeObserver(self)
            except (RuntimeError, ValueError):
                pass

    def _selection_changed(self, *_args):
        if self.isVisible():
            self._refresh_native_state()
            self._selection_refresh_timer.start()

    addSelection = _selection_changed
    removeSelection = _selection_changed
    setSelection = _selection_changed
    clearSelection = _selection_changed

    def show(self):
        self._generation += 1
        if not self.isVisible():
            self._source_focus = QtWidgets.QApplication.focusWidget()
        try:
            self._owner_token = self._token()
            self._owner_context = self.context()
        except (AttributeError, RuntimeError, OSError):
            self.close()
            return
        if not self._owner_valid():
            self.close()
            return
        self._restore_on_close = True
        self._dispatch_pending = False
        self._catalog = list(self.controller.command_catalog())
        self._recents = read_recents(getattr(self.controller, "settings", None))
        self.input.blockSignals(True)
        self.input.clear()
        self.input.blockSignals(False)
        self._populate("")
        super().show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()
        self._observe_selection()
        self._selection_refresh_timer.start()

    def _restore_focus(self, dispatch=False):
        self.main_window.activateWindow()
        QtWidgets.QApplication.setActiveWindow(self.main_window)
        focus = self._source_focus
        if dispatch:
            resolver = getattr(self.controller, "command_focus_widget", None)
            if callable(resolver):
                focus = resolver() or focus
        try:
            if focus is not None and focus.isVisible() and focus.isEnabled():
                focus.setFocus(QtCore.Qt.OtherFocusReason)
        except RuntimeError:
            pass  # The originating document or widget has closed.

    def closeEvent(self, event):
        self._selection_refresh_timer.stop()
        self._unobserve_selection()
        super().closeEvent(event)
        if self._restore_on_close:
            self._restore_focus()

    def _activate(self, item=None, column=0):
        item = item or self.results.currentItem()
        if item is None or self._dispatch_pending:
            return
        command_id = item.data(0, QtCore.Qt.UserRole)
        if not self._available.get(command_id, False):
            return
        if not self._owner_valid():
            self.close()
            self.controller.notify("The active design or workspace changed. Open Command Toolbox again.")
            return
        self._refresh_native_state()
        if not self._command_available(command_id):
            self.refresh_availability()
            return
        self._dispatch_pending = True
        generation = self._generation
        self._restore_on_close = False
        self.close()
        self._restore_focus(dispatch=True)

        def dispatch():
            if generation != self._generation:
                return  # A reopened toolbox owns a new design/focus snapshot.
            self._dispatch_pending = False
            if not self._owner_valid():
                self.controller.notify("The active design or workspace changed. Open Command Toolbox again.")
                return
            application = QtWidgets.QApplication.instance()
            if application.activeModalWidget() or application.activePopupWidget():
                self.controller.notify("Close the open dialog or menu before running a CAD command.")
                return
            self._restore_focus(dispatch=True)
            self._refresh_native_state()
            if not self._command_available(command_id):
                self.controller.notify("This command is no longer available for the current selection or operation.")
                return
            try:
                succeeded = self.controller.execute(command_id)
                if succeeded is True:
                    self._recents = write_recents(getattr(self.controller, "settings", None),
                                                 [command_id] + self._recents)
                    save = getattr(_shortcuts.App, "saveParameter", None)
                    if callable(save):
                        save()
            except Exception as exc:
                self.controller.notify("Could not run command: " + str(exc))

        QtCore.QTimer.singleShot(0, dispatch)

    def eventFilter(self, watched, event):
        if watched in (self.input, self.results) and event.type() == QtCore.QEvent.KeyPress:
            key = event.key()
            if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                if not event.isAutoRepeat():
                    self._activate()
                return True
            if key == QtCore.Qt.Key_Escape:
                self.close()
                return True
            if key in (QtCore.Qt.Key_Down, QtCore.Qt.Key_Up):
                current = self.results.indexOfTopLevelItem(self.results.currentItem())
                direction = 1 if key == QtCore.Qt.Key_Down else -1
                if current < 0:
                    current = -1 if direction > 0 else self.results.topLevelItemCount()
                target = current + direction
                while 0 <= target < self.results.topLevelItemCount():
                    item = self.results.topLevelItem(target)
                    if self._available.get(item.data(0, QtCore.Qt.UserRole), False):
                        self.results.setCurrentItem(item)
                        self.results.scrollToItem(item)
                        break
                    target += direction
                return True
        return super().eventFilter(watched, event)
