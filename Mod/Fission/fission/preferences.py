# SPDX-License-Identifier: MIT
from copy import deepcopy

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from . import commands, marking, theme


class PreferencesDialog(QtWidgets.QDialog):
    def __init__(self, controller, parent):
        super().__init__(parent)
        self.controller = controller
        self.setObjectName("FissionPreferencesDialog")
        self.setWindowTitle("Fission Preferences")
        self.resize(680, 560)
        layout = QtWidgets.QVBoxLayout(self)
        tabs = QtWidgets.QTabWidget()
        tabs.setObjectName("FissionPreferencesTabs")
        layout.addWidget(tabs)
        appearance = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(appearance)
        self.theme = QtWidgets.QComboBox()
        self.theme.addItems(["Dark", "Light"])
        self.theme.setCurrentText(controller.settings.GetString("Theme", "Dark"))
        form.addRow("Theme", self.theme)
        form.addRow(QtWidgets.QLabel("Panel sizes and layout are saved when Fission closes."))
        reset = QtWidgets.QPushButton("Reset Layout")
        reset.clicked.connect(controller.reset_layout)
        form.addRow(reset)
        tabs.addTab(appearance, "Appearance")
        navigation = QtWidgets.QWidget()
        navform = QtWidgets.QFormLayout(navigation)
        self.navigation = QtWidgets.QComboBox()
        for label, name in [("Fission / Fusion", "Gui::FissionNavigationStyle"),
                            ("FreeCAD CAD", "Gui::CADNavigationStyle"),
                            ("Blender", "Gui::BlenderNavigationStyle"),
                            ("Touchpad", "Gui::TouchpadNavigationStyle"),
                            ("Inventor", "Gui::InventorNavigationStyle")]:
            self.navigation.addItem(label, name)
        current = controller.settings.GetString("Navigation", "Gui::FissionNavigationStyle")
        self.navigation.setCurrentIndex(max(0, self.navigation.findData(current)))
        navform.addRow("Mouse preset", self.navigation)
        navform.addRow(QtWidgets.QLabel("Fission: MMB Pan; Shift + MMB Orbit; Ctrl + Shift + MMB Zoom."))
        view_settings = App.ParamGet("User parameter:BaseApp/Preferences/View")
        self.reverse = QtWidgets.QCheckBox("Reverse mouse-wheel zoom")
        self.reverse.setChecked(view_settings.GetBool("InvertZoom", True))
        navform.addRow(self.reverse)
        tabs.addTab(navigation, "Navigation")
        shortcuts = QtWidgets.QWidget()
        sl = QtWidgets.QVBoxLayout(shortcuts)
        sl.addWidget(QtWidgets.QLabel("Fusion defaults are active in Fission. Custom bindings and presets persist."))
        shortcut_button = QtWidgets.QPushButton("Inspect / Customize Shortcuts…")
        shortcut_button.clicked.connect(controller.shortcuts.show_preferences)
        sl.addWidget(shortcut_button)
        sl.addStretch()
        tabs.addTab(shortcuts, "Shortcuts")
        tabs.addTab(self._create_marking_tab(), "Marking Menu")
        advanced = QtWidgets.QWidget()
        al = QtWidgets.QVBoxLayout(advanced)
        al.addWidget(QtWidgets.QLabel("FreeCAD provides units, sketch solver, files/recovery and extension settings."))
        native = QtWidgets.QPushButton("Units, Modeling, Sketch, Files and Advanced…")
        native.clicked.connect(lambda: Gui.runCommand("Std_DlgPreferences"))
        al.addWidget(native)
        addons = QtWidgets.QPushButton("Extensions / Addon Manager…")
        addons.clicked.connect(lambda: Gui.runCommand("Std_AddonMgr"))
        al.addWidget(addons)
        al.addStretch()
        tabs.addTab(advanced, "General / Advanced")
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _create_marking_tab(self):
        self._marking_config = deepcopy(marking.read_config(self.controller.settings))
        choices = {entry["id"]: entry.get("title") or entry["id"]
                   for entry in commands.catalog()}
        self._marking_choices = sorted(choices.items(),
                                       key=lambda choice: (choice[1].casefold(), choice[0].casefold()))
        tab = QtWidgets.QWidget()
        tab.setObjectName("FissionMarkingPreferences")
        layout = QtWidgets.QVBoxLayout(tab)
        self.marking_enabled = QtWidgets.QCheckBox("Enable marking menu")
        self.marking_enabled.setObjectName("FissionMarkingEnabled")
        self.marking_enabled.setChecked(self._marking_config["enabled"])
        layout.addWidget(self.marking_enabled)
        help_text = QtWidgets.QLabel("Alt + right-click opens the menu with the Fission mouse preset. "
                                    "The Marking Menu button or a custom shortcut works with other presets. "
                                    "Native right-click remains available.")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        form = QtWidgets.QFormLayout()
        layout.addLayout(form)
        self.marking_context = QtWidgets.QComboBox()
        self.marking_context.setObjectName("FissionMarkingContext")
        for context in marking.CONTEXTS:
            self.marking_context.addItem(context.title(), context)
        current = self.controller.context()
        self._marking_context = current if current in marking.CONTEXTS else marking.CONTEXTS[0]
        self.marking_context.setCurrentIndex(self.marking_context.findData(self._marking_context))
        form.addRow("Context", self.marking_context)
        labels = {"N": "North", "NE": "North-east", "E": "East", "SE": "South-east",
                  "S": "South", "SW": "South-west", "W": "West", "NW": "North-west"}
        self.marking_slots = {}
        for direction in marking.DIRECTIONS:
            combo = QtWidgets.QComboBox()
            combo.setObjectName("FissionMarkingSlot" + direction)
            combo.setEditable(True)
            combo.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
            combo.setMaxVisibleItems(14)
            combo.lineEdit().setPlaceholderText("Search a command or enter its ID")
            completer = combo.completer()
            completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
            completer.setFilterMode(QtCore.Qt.MatchContains)
            completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
            self.marking_slots[direction] = combo
            form.addRow(labels.get(direction, direction) + " (" + direction + ")", combo)
        actions = QtWidgets.QHBoxLayout()
        reset_context = QtWidgets.QPushButton("Reset Context")
        reset_context.setObjectName("FissionMarkingResetContext")
        reset_context.clicked.connect(self._reset_marking_context)
        actions.addWidget(reset_context)
        reset_all = QtWidgets.QPushButton("Reset All")
        reset_all.setObjectName("FissionMarkingResetAll")
        reset_all.clicked.connect(self._reset_marking_all)
        actions.addWidget(reset_all)
        actions.addStretch()
        layout.addLayout(actions)
        note = QtWidgets.QLabel("Empty leaves a direction unused. Unavailable assignments are retained. "
                               "Changes and resets apply when you click OK.")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        self._show_marking_context()
        self.marking_context.currentIndexChanged.connect(self._change_marking_context)
        return tab

    @staticmethod
    def _marking_command(combo):
        text = combo.currentText().strip()
        index = combo.currentIndex()
        if index >= 0 and text == combo.itemText(index):
            return combo.itemData(index) or ""
        if not text or text.casefold() == "empty":
            return ""
        for item in range(combo.count()):
            if text == combo.itemText(item):
                return combo.itemData(item) or ""
        return text

    def _store_marking_context(self):
        self._marking_config["slots"][self._marking_context] = [
            self._marking_command(self.marking_slots[direction]) for direction in marking.DIRECTIONS]

    def _show_marking_context(self):
        slots = self._marking_config["slots"][self._marking_context]
        for direction, command_id in zip(marking.DIRECTIONS, slots):
            combo = self.marking_slots[direction]
            blocked = combo.blockSignals(True)
            try:
                combo.clear()
                combo.addItem("Empty", "")
                for native_id, title in self._marking_choices:
                    combo.addItem(title + " · " + native_id, native_id)
                index = combo.findData(command_id)
                if index < 0:
                    combo.addItem("Unavailable · " + command_id, command_id)
                    index = combo.count() - 1
                combo.setCurrentIndex(index)
            finally:
                combo.blockSignals(blocked)

    def _change_marking_context(self, index):
        self._store_marking_context()
        self._marking_context = self.marking_context.itemData(index)
        self._show_marking_context()

    def _reset_marking_context(self):
        self._marking_config["slots"][self._marking_context] = list(marking.defaults(self._marking_context))
        self._show_marking_context()

    def _reset_marking_all(self):
        self._marking_config = {"version": 1, "enabled": True,
                                "slots": {context: list(marking.defaults(context))
                                          for context in marking.CONTEXTS}}
        self.marking_enabled.setChecked(True)
        self._show_marking_context()

    def accept(self):
        controller = self.controller
        self._store_marking_context()
        self._marking_config["enabled"] = self.marking_enabled.isChecked()
        marking.write_config(controller.settings, self._marking_config)
        theme.apply(controller.main, self.theme.currentText())
        controller.settings.SetString("Navigation", self.navigation.currentData())
        view = App.ParamGet("User parameter:BaseApp/Preferences/View")
        view.SetString("NavigationStyle", self.navigation.currentData())
        view.SetBool("InvertZoom", self.reverse.isChecked())
        App.saveParameter()
        controller.marking.refresh_settings()
        controller.refresh_context()
        super().accept()
