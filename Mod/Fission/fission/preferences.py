# SPDX-License-Identifier: MIT
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from . import theme


class PreferencesDialog(QtWidgets.QDialog):
    def __init__(self, controller, parent):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Fission Preferences")
        self.resize(580, 400)
        layout = QtWidgets.QVBoxLayout(self)
        tabs = QtWidgets.QTabWidget()
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
        self.reverse.setChecked(view_settings.GetBool("InvertZoom", False))
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

    def accept(self):
        controller = self.controller
        theme.apply(controller.main, self.theme.currentText())
        controller.settings.SetString("Navigation", self.navigation.currentData())
        view = App.ParamGet("User parameter:BaseApp/Preferences/View")
        view.SetString("NavigationStyle", self.navigation.currentData())
        view.SetBool("InvertZoom", self.reverse.isChecked())
        App.saveParameter()
        controller.refresh_context()
        super().accept()
