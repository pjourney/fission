"""Fission shortcuts: deterministic profiles and focus-aware native Qt dispatch.

SPDX-License-Identifier: LGPL-2.0-or-later
The profile model deliberately has no FreeCAD/Qt dependency so its behavior can
be tested before a complete CAD build is available.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

try:
    import FreeCAD as App
    import FreeCADGui as Gui
except ImportError:
    App = Gui = None
try:
    from PySide import QtCore, QtGui, QtWidgets
except ImportError:
    try:
        from PySide2 import QtCore, QtGui, QtWidgets
    except ImportError:
        try:
            from PySide6 import QtCore, QtGui, QtWidgets
        except ImportError:
            QtCore = QtGui = QtWidgets = None

DEFAULT_PROFILE = "Fission / Fusion"
CLASSIC_PROFILE = "FreeCAD Classic"
PARAMETER_PATH = "User parameter:BaseApp/Preferences/Fission/Shortcuts"
RESOURCE_PATH = Path(__file__).resolve().parents[1] / "resources" / "shortcuts.json"


def normalize_shortcut(value):
    """Accept one portable Qt key stroke, avoiding ambiguous multi-key chains."""
    if not isinstance(value, str):
        raise ValueError("A shortcut must be text.")
    value = value.strip()
    if not value:
        return ""
    if "," in value:
        raise ValueError("Use one key with optional Ctrl, Alt, Shift or Meta modifiers.")
    parts = [part.strip() for part in value.split("+")]
    if value.endswith("++"):
        parts = parts[:-2] + ["+"]
    names = {"control": "Ctrl", "ctrl": "Ctrl", "alt": "Alt",
             "shift": "Shift", "meta": "Meta", "cmd": "Meta"}
    modifiers = []
    for part in parts[:-1]:
        modifier = names.get(part.lower())
        if not modifier or modifier in modifiers:
            raise ValueError("Invalid or repeated shortcut modifier.")
        modifiers.append(modifier)
    key = parts[-1]
    aliases = {"esc": "Escape", "escape": "Escape", "del": "Delete",
               "delete": "Delete", "return": "Return", "enter": "Return",
               "tab": "Tab", "backspace": "Backspace", "space": "Space",
               "home": "Home", "end": "End", "insert": "Insert",
               "left": "Left", "right": "Right", "up": "Up", "down": "Down",
               "pgup": "PgUp", "page up": "PgUp", "pgdown": "PgDown",
               "page down": "PgDown"}
    if len(key) == 1 and (key.isascii() and (key.isalnum() or key in "[]-+/?.`=")):
        key = key.upper()
    elif key.lower() in aliases:
        key = aliases[key.lower()]
    elif re.fullmatch(r"[Ff]([1-9]|[12][0-9]|3[0-5])", key):
        key = key.upper()
    else:
        raise ValueError("Use a letter, number, function key, or named navigation key.")
    modifiers.sort(key=["Ctrl", "Alt", "Shift", "Meta"].index)
    return "+".join(modifiers + [key])


def contexts_overlap(left, right):
    return "*" in left or "*" in right or bool(set(left) & set(right))


def _enum_value(value):
    """PySide6 flags use .value; PySide2 flags support int directly."""
    return int(getattr(value, "value", value))


class ShortcutProfile:
    def __init__(self, data=None):
        data = data or json.loads(RESOURCE_PATH.read_text(encoding="utf-8"))
        self.bindings = [dict(row) for row in data["bindings"]]
        self.overrides = {}
        self.name = DEFAULT_PROFILE
        seen = set()
        for row in self.bindings:
            if row["id"] in seen:
                raise ValueError("Duplicate shortcut command: " + row["id"])
            seen.add(row["id"])
            row["shortcut"] = normalize_shortcut(row.get("shortcut", ""))
            row.setdefault("command", row["id"])
            row.setdefault("contexts", ["*"])
        self.validate()

    def add_catalog(self, catalog):
        known = {row["id"] for row in self.bindings}
        for entry in catalog:
            if entry["id"] in known:
                continue
            context = entry.get("context", "*")
            contexts = context if isinstance(context, (list, tuple)) else [context or "*"]
            contexts = ["*" if item == "all" else item for item in contexts]
            self.bindings.append({"id": entry["id"], "command": entry["id"],
                                  "title": entry.get("title", entry["id"]),
                                  "aliases": entry.get("aliases", []),
                                  "shortcut": "", "contexts": contexts,
                                  "category": "Additional Commands"})
            known.add(entry["id"])

    def shortcut(self, row):
        return self.overrides.get(row["id"], row.get("shortcut", ""))

    def conflicts(self, binding_id, shortcut):
        shortcut = normalize_shortcut(shortcut)
        row = next((item for item in self.bindings if item["id"] == binding_id), None)
        if row is None:
            raise ValueError("Unknown command: " + binding_id)
        if not shortcut:
            return []
        return [other for other in self.bindings
                if other["id"] != binding_id and self.shortcut(other) == shortcut
                and contexts_overlap(row["contexts"], other["contexts"])]

    def set_binding(self, binding_id, shortcut):
        shortcut = normalize_shortcut(shortcut)
        conflicts = self.conflicts(binding_id, shortcut)
        if conflicts:
            raise ValueError("Shortcut already assigned in this context: " +
                             ", ".join(row["title"] for row in conflicts))
        self.overrides[binding_id] = shortcut

    def reset_one(self, binding_id):
        row = next((item for item in self.bindings if item["id"] == binding_id), None)
        if row is None:
            raise ValueError("Unknown command: " + binding_id)
        conflicts = self.conflicts(binding_id, row.get("shortcut", ""))
        if conflicts:
            raise ValueError("Default shortcut conflicts with: " +
                             ", ".join(other["title"] for other in conflicts))
        self.overrides.pop(binding_id, None)

    def reset(self):
        self.overrides.clear()
        self.name = DEFAULT_PROFILE

    def validate(self):
        for row in self.bindings:
            shortcut = self.shortcut(row)
            normalize_shortcut(shortcut)
            if self.conflicts(row["id"], shortcut):
                raise ValueError("Conflicting shortcut for " + row["title"])

    def resolve(self, shortcut, context="model", typing=False):
        if typing or self.name == CLASSIC_PROFILE:
            return None
        shortcut = normalize_shortcut(shortcut)
        if not shortcut:
            return None
        for row in self.bindings:
            if self.shortcut(row) == shortcut and ("*" in row["contexts"] or context in row["contexts"]):
                return row
        return None

    def export_data(self):
        return {"schema_version": 1, "profile": self.name, "overrides": dict(self.overrides)}

    def import_data(self, data):
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise ValueError("This is not a version 1 Fission shortcut profile.")
        name = data.get("profile", DEFAULT_PROFILE)
        if name not in (DEFAULT_PROFILE, CLASSIC_PROFILE):
            raise ValueError("Unknown shortcut profile.")
        overrides = data.get("overrides")
        if not isinstance(overrides, dict):
            raise ValueError("The profile needs an overrides object.")
        known = {row["id"] for row in self.bindings}
        unknown = set(overrides) - known
        if unknown:
            raise ValueError("Unknown profile commands: " + ", ".join(sorted(unknown)))
        old_overrides = self.overrides
        self.overrides = {key: normalize_shortcut(value) for key, value in overrides.items()}
        try:
            self.validate()
        except ValueError:
            self.overrides = old_overrides
            raise
        self.name = name

    def load(self, parameters):
        raw = parameters.GetString("Overrides", "{}")
        self.import_data({"schema_version": 1,
                          "profile": parameters.GetString("Profile", DEFAULT_PROFILE),
                          "overrides": json.loads(raw)})

    def save(self, parameters):
        parameters.SetString("Profile", self.name)
        parameters.SetString("Overrides", json.dumps(self.overrides, sort_keys=True))


def is_typing_widget(widget):
    """Include editor ancestors: spin boxes often focus their internal line edit."""
    if QtWidgets is None:
        return False
    kinds = (QtWidgets.QLineEdit, QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit,
             QtWidgets.QAbstractSpinBox, QtWidgets.QKeySequenceEdit)
    while widget is not None:
        if isinstance(widget, kinds):
            return True
        if isinstance(widget, QtWidgets.QComboBox) and widget.isEditable():
            return True
        widget = widget.parentWidget() if hasattr(widget, "parentWidget") else None
    return False


_QObject = QtCore.QObject if QtCore else object


class ShortcutManager(_QObject):
    def __init__(self, controller, main_window):
        if QtCore is None or App is None:
            raise RuntimeError("The shortcut manager requires FreeCAD GUI and Qt.")
        super().__init__(main_window)
        self.controller = controller
        self.main_window = main_window
        self.profile = ShortcutProfile()
        self._original_actions = {}
        self._refresh_pending = False
        self._mutating_actions = False
        self._active = False
        self._dialog = None
        self.parameters = App.ParamGet(PARAMETER_PATH)
        self._update_catalog()
        try:
            self.profile.load(self.parameters)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            controller.notify("Stored shortcuts could not be read; factory defaults loaded. " + str(exc))
            self.profile.reset()

    def context(self):
        resolver = getattr(self.controller, "context", None)
        return resolver() if callable(resolver) else "model"

    def _update_catalog(self):
        catalog = getattr(self.controller, "command_catalog", None)
        if callable(catalog):
            self.profile.add_catalog(catalog())

    def apply_profile(self, name=DEFAULT_PROFILE):
        if name not in (DEFAULT_PROFILE, CLASSIC_PROFILE):
            raise ValueError("Unknown shortcut profile.")
        self._restore_actions()
        if not self._active:
            QtWidgets.QApplication.instance().installEventFilter(self)
            self._active = True
        self.profile.name = name
        self._update_catalog()
        if name != CLASSIC_PROFILE:
            self._suppress_conflicts()
        self.profile.save(self.parameters)
        save_parameters = getattr(App, "saveParameter", None)
        if callable(save_parameters):
            save_parameters()
        return self

    def shortcut_for(self, command_id, context=None):
        if self.profile.name == CLASSIC_PROFILE:
            return ""
        context = context or self.context()
        for row in self.profile.bindings:
            if row["command"] == command_id and ("*" in row["contexts"] or context in row["contexts"]):
                return self.profile.shortcut(row)
        return ""

    def set_binding(self, binding_id, shortcut):
        self.profile.set_binding(binding_id, shortcut)
        self.apply_profile(self.profile.name)

    def reset_binding(self, binding_id):
        self.profile.reset_one(binding_id)
        self.apply_profile(self.profile.name)

    def reset_profile(self):
        self.profile.reset()
        self.apply_profile()

    def export_profile(self, path):
        Path(path).write_text(json.dumps(self.profile.export_data(), indent=2) + "\n", encoding="utf-8")

    def import_profile(self, path):
        self._update_catalog()
        self.profile.import_data(json.loads(Path(path).read_text(encoding="utf-8")))
        self.apply_profile(self.profile.name)

    def _claimed_keys(self):
        return {self.profile.shortcut(row).upper().replace(" ", "")
                for row in self.profile.bindings if self.profile.shortcut(row)}

    def _suppress_conflicts(self):
        self._refresh_pending = False
        if not self._active or self.profile.name == CLASSIC_PROFILE or self._mutating_actions:
            return
        self._mutating_actions = True
        claimed = self._claimed_keys()
        action_type = getattr(QtGui, "QAction", None) or QtWidgets.QAction
        try:
            for action in self.main_window.findChildren(action_type):
                shortcuts = action.shortcuts()
                if any(sequence.toString(QtGui.QKeySequence.PortableText).split(",")[0].upper().replace(" ", "")
                       in claimed for sequence in shortcuts):
                    if action not in self._original_actions:
                        self._original_actions[action] = shortcuts
                    action.setShortcuts([])
        finally:
            self._mutating_actions = False

    def _restore_actions(self):
        self._mutating_actions = True
        try:
            for action, shortcuts in self._original_actions.items():
                try:
                    action.setShortcuts(shortcuts)
                except RuntimeError:
                    pass  # Qt disposed a workbench action since it was captured.
            self._original_actions.clear()
        finally:
            self._mutating_actions = False

    def _event_shortcut(self, event):
        key = _enum_value(event.key())
        if key in (_enum_value(QtCore.Qt.Key_Shift), _enum_value(QtCore.Qt.Key_Control),
                   _enum_value(QtCore.Qt.Key_Alt), _enum_value(QtCore.Qt.Key_Meta)):
            return ""
        modifiers = event.modifiers() & (QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier |
                                         QtCore.Qt.ShiftModifier | QtCore.Qt.MetaModifier)
        sequence = QtGui.QKeySequence(_enum_value(modifiers) | key)
        try:
            return normalize_shortcut(sequence.toString(QtGui.QKeySequence.PortableText))
        except ValueError:
            return ""

    def _resolve_command(self, row):
        command = row["command"]
        if row.get("fallbacks") and Gui is not None:
            available = set(Gui.Command.listAll())
            if command not in available:
                return next((item for item in row["fallbacks"] if item in available), command)
        return command

    def eventFilter(self, watched, event):
        if not self._active:
            return False
        event_type = event.type()
        if event_type in (QtCore.QEvent.ActionAdded, QtCore.QEvent.ActionChanged) and not self._mutating_actions:
            if not self._refresh_pending and self.profile.name != CLASSIC_PROFILE:
                self._refresh_pending = True
                QtCore.QTimer.singleShot(0, self._suppress_conflicts)
            return False
        if event_type not in (QtCore.QEvent.ShortcutOverride, QtCore.QEvent.KeyPress):
            return False
        if self.profile.name == CLASSIC_PROFILE:
            return False
        application = QtWidgets.QApplication.instance()
        focus = application.focusWidget()
        if focus is None or is_typing_widget(focus):
            return False
        if application.activeModalWidget() or application.activePopupWidget():
            return False
        if focus.window() is not self.main_window:
            return False
        shortcut = self._event_shortcut(event)
        if not shortcut:
            return False
        row = self.profile.resolve(shortcut, self.context())
        if row is None:
            return False
        event.accept()
        if event_type == QtCore.QEvent.ShortcutOverride:
            return True
        if not event.isAutoRepeat():
            if row.get("state") == "unsupported":
                self.controller.notify(row["title"] + " is not implemented in Fission Alpha. "
                                       "This Fusion key is reserved in Keyboard Shortcuts.")
                return True
            try:
                self.controller.execute(self._resolve_command(row))
            except Exception as exc:
                self.controller.notify("Could not run " + row["title"] + ": " + str(exc))
        return True

    def show_preferences(self):
        self._update_catalog()
        if self._dialog is None:
            self._dialog = ShortcutPreferences(self, self.main_window)
        self._dialog.refresh()
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()

    def deactivate(self):
        QtWidgets.QApplication.instance().removeEventFilter(self)
        self._active = False
        self._restore_actions()

    def dispose(self):
        self.deactivate()


_Dialog = QtWidgets.QDialog if QtWidgets else object


class ShortcutPreferences(_Dialog):
    def __init__(self, manager, parent):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Fission — Keyboard Shortcuts")
        self.setObjectName("FissionShortcutPreferences")
        self.resize(860, 620)
        self.setModal(True)
        layout = QtWidgets.QVBoxLayout(self)
        self.profile_combo = QtWidgets.QComboBox()
        self.profile_combo.addItems([DEFAULT_PROFILE, CLASSIC_PROFILE])
        self.profile_combo.currentTextChanged.connect(self._profile_changed)
        layout.addWidget(self.profile_combo)
        self.filter_edit = QtWidgets.QLineEdit()
        self.filter_edit.setPlaceholderText("Search commands, contexts, or keys…")
        self.filter_edit.textChanged.connect(self._filter)
        layout.addWidget(self.filter_edit)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Command", "Context", "Shortcut", "Command ID"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.currentItemChanged.connect(self._selected)
        layout.addWidget(self.tree, 1)
        assignment = QtWidgets.QHBoxLayout()
        self.key_edit = QtWidgets.QKeySequenceEdit()
        assignment.addWidget(self.key_edit, 1)
        for title, callback in [("Assign", self._assign), ("Clear", self._clear),
                                ("Reset Selected", self._reset_one)]:
            button = QtWidgets.QPushButton(title)
            button.clicked.connect(callback)
            assignment.addWidget(button)
        layout.addLayout(assignment)
        self.message = QtWidgets.QLabel("Changes are saved immediately. Text entry keeps its normal editing keys.")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        bottom = QtWidgets.QHBoxLayout()
        for title, callback in [("Import JSON…", self._import), ("Export JSON…", self._export),
                                ("Reset Profile", self._reset_all), ("Close", self.close)]:
            button = QtWidgets.QPushButton(title)
            button.clicked.connect(callback)
            bottom.addWidget(button)
        layout.addLayout(bottom)

    def refresh(self):
        selected = self.tree.currentItem()
        selected_id = selected.data(0, QtCore.Qt.UserRole) if selected else None
        self.profile_combo.blockSignals(True)
        self.profile_combo.setCurrentText(self.manager.profile.name)
        self.profile_combo.blockSignals(False)
        self.tree.clear()
        for row in self.manager.profile.bindings:
            contexts = "All" if "*" in row["contexts"] else ", ".join(row["contexts"])
            item = QtWidgets.QTreeWidgetItem([row["title"], contexts,
                                             self.manager.profile.shortcut(row), row["command"]])
            item.setData(0, QtCore.Qt.UserRole, row["id"])
            item.setToolTip(0, row.get("difference", ""))
            if row.get("state") == "unsupported":
                item.setToolTip(0, "Reserved Fusion shortcut. This command is not implemented in Alpha.")
                item.setText(0, row["title"] + " (reserved)")
            self.tree.addTopLevelItem(item)
            if row["id"] == selected_id:
                self.tree.setCurrentItem(item)
        self.tree.resizeColumnToContents(0)
        self.tree.resizeColumnToContents(1)
        self.tree.resizeColumnToContents(2)
        self._filter(self.filter_edit.text())

    def _filter(self, text):
        terms = text.casefold().split()
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            content = " ".join(item.text(column) for column in range(4)).casefold()
            item.setHidden(not all(term in content for term in terms))

    def _selected(self, current, previous=None):
        self.key_edit.setKeySequence(QtGui.QKeySequence(current.text(2) if current else ""))

    def _perform(self, callback):
        try:
            callback()
            self.message.setText("Shortcut profile saved.")
            self.refresh()
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            self.message.setText(str(exc))

    def _profile_changed(self, name):
        self._perform(lambda: self.manager.apply_profile(name))

    def _assign(self):
        current = self.tree.currentItem()
        if current:
            key = self.key_edit.keySequence().toString(QtGui.QKeySequence.PortableText)
            self._perform(lambda: self.manager.set_binding(current.data(0, QtCore.Qt.UserRole), key))

    def _clear(self):
        current = self.tree.currentItem()
        if current:
            self._perform(lambda: self.manager.set_binding(current.data(0, QtCore.Qt.UserRole), ""))

    def _reset_one(self):
        current = self.tree.currentItem()
        if current:
            self._perform(lambda: self.manager.reset_binding(current.data(0, QtCore.Qt.UserRole)))

    def _reset_all(self):
        self._perform(self.manager.reset_profile)

    def _import(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Import Shortcut Profile", "", "JSON profiles (*.json)")
        if path:
            self._perform(lambda: self.manager.import_profile(path))

    def _export(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export Shortcut Profile", "Fission-shortcuts.json", "JSON profiles (*.json)")
        if path:
            self._perform(lambda: self.manager.export_profile(path))
