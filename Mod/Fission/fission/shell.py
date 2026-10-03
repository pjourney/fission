# SPDX-License-Identifier: MIT
"""Native Qt workspace around FreeCAD's MDI canvas and transactional CAD tools."""
import base64
import os
import traceback
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets
from . import theme
from .commands import COMMANDS, ICON, catalog

_controller = None


def existing_controller():
    return _controller


def get_controller():
    global _controller
    if _controller is None:
        _controller = Controller(Gui.getMainWindow())
    return _controller


TABS = {
    "SOLID": [
        ("CREATE", ["CreateSketch", "Extrude", "Revolve", "Sweep", "Loft", "Hole"]),
        ("MODIFY", ["Cut", "Fillet", "Chamfer", "Shell", "Draft", "Move", "Boolean"]),
        ("PATTERN", ["Mirror", "RectPattern", "CircPattern"]),
        ("CONSTRUCT", ["Plane", "NewComponent"]),
        ("INSPECT", ["Measure"]),
    ],
    "SURFACE": [
        ("CREATE", [("Surface_Filling", "Fill"), ("Surface_GeomFillSurface", "Boundary"),
                    ("Surface_Sections", "Loft Sections"), ("Surface_BlendCurve", "Blend Curve")]),
        ("MODIFY", [("Surface_ExtendFace", "Extend"), ("Surface_Cut", "Trim"), ("Part_MakeSolid", "Stitch / Solid")]),
        ("INSPECT", [("Part_CheckGeometry", "Validate"), "Measure"]),
    ],
    "MESH": [
        ("CREATE", [("Mesh_Import", "Import Mesh"), ("Mesh_FromPartShape", "Tessellate")]),
        ("MODIFY", [("Mesh_Smoothing", "Smooth"), ("Mesh_Decimating", "Reduce"),
                    ("Mesh_HarmonizeNormals", "Align Normals"), ("Mesh_FillupHoles", "Fill Holes")]),
        ("CONVERT", [("Part_ShapeFromMesh", "Mesh to Shape"), ("Part_MakeSolid", "Shape to Solid")]),
        ("INSPECT", [("Mesh_Evaluation", "Repair / Analyze"), ("Mesh_Export", "Export Mesh")]),
    ],
    "ASSEMBLE": [
        ("COMPONENTS", ["NewComponent", ("Assembly_CreateAssembly", "New Assembly"), ("Assembly_Insert", "Insert Component")]),
        ("JOINTS", ["AssemblyJoint", ("Assembly_CreateJointRevolute", "Revolute"),
                    ("Assembly_CreateJointSlider", "Slider"), ("Assembly_CreateJointBall", "Ball")]),
        ("POSITION", [("Assembly_ToggleGrounded", "Ground / Unground"), ("Assembly_SolveAssembly", "Solve"), "Move"]),
    ],
    "UTILITIES": [
        ("INSPECT", ["Measure", ("Std_MassProperties", "Mass Properties"), ("Part_CheckGeometry", "Check Geometry")]),
        ("PARAMETERS", [("Spreadsheet_CreateSheet", "Parameter Sheet"), "Compute", ("Std_DlgExpressionInput", "Expression")]),
        ("FILES", [("Std_Import", "Import"), ("Std_Export", "Export"), ("Std_Save", "Save")]),
        ("SETTINGS", ["Search", "Preferences", "About"]),
    ],
    "SKETCH": [
        ("CREATE", [("Sketcher_CreatePolyline", "Line"), ("Sketcher_CreateRectangle", "Rectangle"),
                    ("Sketcher_CreateCircle", "Circle"), ("Sketcher_CreateArc", "Arc"),
                    ("Sketcher_CreateRegularPolygon", "Polygon"), ("Sketcher_CreateSlot", "Slot"),
                    ("Sketcher_CreateBSpline", "Spline")]),
        ("MODIFY", [("Sketcher_Trimming", "Trim"), ("Sketcher_Extend", "Extend"),
                    ("Sketcher_Offset", "Offset"), ("Sketcher_Projection", "Project"),
                    ("Sketcher_ToggleConstruction", "Construction")]),
        ("CONSTRAIN", [("Sketcher_Dimension", "Dimension"), ("Sketcher_ConstrainHorizontal", "Horizontal"),
                       ("Sketcher_ConstrainVertical", "Vertical"), ("Sketcher_ConstrainCoincident", "Coincident"),
                       ("Sketcher_ConstrainTangent", "Tangent"), ("Sketcher_ConstrainParallel", "Parallel"),
                       ("Sketcher_ConstrainPerpendicular", "Perpendicular"), ("Sketcher_ConstrainEqual", "Equal")]),
        ("FINISH", ["FinishSketch"]),
    ],
}


def command_spec(item):
    if isinstance(item, tuple):
        command, title = item
        return command, title
    return "Fission_" + item, COMMANDS[item][0]


def command_icon(command):
    cmd = Gui.Command.get(command)
    if not cmd:
        return QtGui.QIcon(ICON)
    actions = cmd.getAction()
    if actions and not actions[0].icon().isNull():
        return actions[0].icon()
    pixmap = cmd.getInfo().get("Pixmap", "")
    return QtGui.QIcon(pixmap if os.path.isfile(pixmap) else ":/icons/" + pixmap + ".svg")


class DocumentObserver:
    def __init__(self, controller):
        self.controller = controller

    def slotCreatedObject(self, obj):
        if obj.isDerivedFrom("Sketcher::SketchObject"):
            QtCore.QTimer.singleShot(0, lambda: self.controller.prepare_sketch(obj))

    def slotActivateDocument(self, doc):
        QtCore.QTimer.singleShot(0, self.controller.refresh_context)

    def slotDeletedDocument(self, doc):
        QtCore.QTimer.singleShot(0, self.controller.refresh_context)


class Controller(QtCore.QObject):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main = main_window
        self.settings = App.ParamGet("User parameter:BaseApp/Preferences/Fission")
        self.active = False
        self._context = None
        self._tab = "SOLID"
        self.buttons = []
        self._saved_toolbar_visibility = {}
        self._saved_dock_visibility = {}
        self.main.setWindowIcon(QtGui.QIcon(ICON))
        self.create_ribbon()
        from .browser import Browser
        from .timeline import Timeline
        self.browser = Browser(main_window, self)
        self.timeline = Timeline(main_window, self)
        self.main.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.browser)
        self.main.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.timeline)
        self.create_navigation()
        from .shortcuts import ShortcutManager
        self.shortcuts = ShortcutManager(self, main_window)
        self.observer = DocumentObserver(self)
        App.addDocumentObserver(self.observer)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.refresh_context)
        self.main.installEventFilter(self)
        QtWidgets.QApplication.instance().aboutToQuit.connect(self.shutdown)
        self.welcome = None
        self.main.setMinimumSize(1080, 700)

    def eventFilter(self, obj, event):
        if obj is self.main and event.type() == QtCore.QEvent.Close:
            self.save_layout()
        return False

    def activate(self):
        self.active = True
        self.hide_legacy_chrome()
        theme.apply(self.main)
        for widget in (self.ribbon_dock, self.browser, self.timeline, self.nav_dock):
            widget.show()
        self.restore_layout()
        self.shortcuts.apply_profile(self.shortcuts.profile.name)
        self.timer.start()
        self.refresh_context()
        if not App.ActiveDocument:
            self.show_welcome()

    def deactivate(self):
        self.active = False
        self.save_layout()
        self.timer.stop()
        if hasattr(self.shortcuts, "deactivate"):
            self.shortcuts.deactivate()
        for widget in (self.ribbon_dock, self.browser, self.timeline, self.nav_dock):
            widget.hide()
        for toolbar, visible in self._saved_toolbar_visibility.items():
            toolbar.setVisible(visible)
        for dock, visible in self._saved_dock_visibility.items():
            dock.setVisible(visible)
        self.main.setStyleSheet("")

    def hide_legacy_chrome(self):
        for toolbar in self.main.findChildren(QtWidgets.QToolBar):
            if not toolbar.objectName().startswith("Fission"):
                self._saved_toolbar_visibility.setdefault(toolbar, toolbar.isVisible())
                toolbar.hide()
        for dock in self.main.findChildren(QtWidgets.QDockWidget):
            name = dock.objectName()
            if name in ("Model", "Tree view", "Selection view", "Python console", "Report view"):
                self._saved_dock_visibility.setdefault(dock, dock.isVisible())
                dock.hide()
            elif name in ("Combo View", "Tasks", "Task panel", "Property view", "Property editor"):
                self.main.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
                if name == "Combo View":
                    dock.setWindowTitle("Parameters")
                elif "Task" in name:
                    dock.setWindowTitle("Feature Parameters")

    def create_ribbon(self):
        self.ribbon_dock = QtWidgets.QDockWidget("Design", self.main)
        self.ribbon_dock.setObjectName("FissionRibbonDock")
        self.ribbon_dock.setTitleBarWidget(QtWidgets.QWidget())
        self.ribbon_dock.setFeatures(QtWidgets.QDockWidget.NoDockWidgetFeatures)
        self.ribbon_dock.setAllowedAreas(QtCore.Qt.TopDockWidgetArea)
        self.main.addDockWidget(QtCore.Qt.TopDockWidgetArea, self.ribbon_dock)
        self.ribbon = QtWidgets.QWidget()
        self.ribbon.setObjectName("FissionRibbon")
        layout = QtWidgets.QVBoxLayout(self.ribbon)
        layout.setContentsMargins(8, 4, 8, 0)
        layout.setSpacing(1)
        controls = QtWidgets.QHBoxLayout()
        logo = QtWidgets.QLabel()
        logo.setPixmap(QtGui.QIcon(ICON).pixmap(26, 26))
        controls.addWidget(logo)
        brand = QtWidgets.QLabel("FISSION")
        brand.setStyleSheet("font: 600 12pt 'Segoe UI'; letter-spacing: 2px")
        controls.addWidget(brand)
        controls.addSpacing(18)
        self.workspace = QtWidgets.QComboBox()
        self.workspace.addItems(["Design", "Drawing", "Manufacture"])
        self.workspace.setToolTip("Design combines modeling tools. Drawing and Manufacture use native specialist workspaces.")
        self.workspace.currentTextChanged.connect(self.switch_workspace)
        controls.addWidget(self.workspace)
        for cmd, label in [("Fission_NewDesign", "New"), ("Std_Open", "Open"), ("Std_Save", "Save"),
                           ("Std_Undo", "Undo"), ("Std_Redo", "Redo")]:
            controls.addWidget(self.make_button(cmd, label, small=True))
        controls.addStretch()
        self.document_label = QtWidgets.QLabel("Local parametric design")
        controls.addWidget(self.document_label)
        controls.addSpacing(20)
        controls.addWidget(self.make_button("Fission_Search", "Search  S", small=True))
        controls.addWidget(self.make_button("Fission_Preferences", "Settings", small=True))
        layout.addLayout(controls)
        self.tabs = QtWidgets.QTabBar()
        self.tabs.setExpanding(False)
        for tab in TABS:
            if tab == "SKETCH":
                continue
            available = any(Gui.Command.get(command_spec(item)[0]) for _, items in TABS[tab] for item in items)
            if available:
                self.tabs.addTab(tab)
        # Addon tools are exposed only when commands are present, without automatic downloads.
        sheet_tools = [(cmd, title) for cmd, title in [("SheetMetal_AddBase", "Base Flange"),
                       ("SheetMetal_AddWall", "Bend"), ("SheetMetal_Unfold", "Unfold")]
                       if Gui.Command.get(cmd)]
        if sheet_tools:
            TABS["SHEET METAL"] = [("SHEET METAL", sheet_tools)]
            self.tabs.addTab("SHEET METAL")
        self.tabs.currentChanged.connect(self.tab_changed)
        layout.addWidget(self.tabs)
        self.group_area = QtWidgets.QWidget()
        self.group_layout = QtWidgets.QHBoxLayout(self.group_area)
        self.group_layout.setContentsMargins(0, 0, 0, 1)
        self.group_layout.setSpacing(8)
        scroll = QtWidgets.QScrollArea()
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setWidget(self.group_area)
        scroll.setFixedHeight(89)
        layout.addWidget(scroll)
        self.ribbon_dock.setWidget(self.ribbon)
        self.build_groups("SOLID")

    def make_button(self, command, title, small=False):
        button = QtWidgets.QToolButton()
        button.setText(title)
        button.setIcon(command_icon(command))
        button.setIconSize(QtCore.QSize(16, 16) if small else QtCore.QSize(26, 26))
        button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon if small else QtCore.Qt.ToolButtonTextUnderIcon)
        button.setToolTip(title + "\n" + command)
        button.clicked.connect(lambda checked=False, cmd=command: self.execute(cmd))
        button.setProperty("fissionCommand", command)
        self.buttons.append(button)
        return button

    def build_groups(self, tab):
        while self.group_layout.count():
            item = self.group_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.buttons = [b for b in self.buttons if b.toolButtonStyle() == QtCore.Qt.ToolButtonTextBesideIcon]
        for name, items in TABS[tab]:
            group = QtWidgets.QWidget()
            gl = QtWidgets.QVBoxLayout(group)
            gl.setContentsMargins(3, 1, 3, 1)
            gl.setSpacing(0)
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(1)
            for item in items:
                command, title = command_spec(item)
                if Gui.Command.get(command):
                    row.addWidget(self.make_button(command, title))
            gl.addLayout(row)
            label = QtWidgets.QLabel(name)
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setStyleSheet("font: 8pt 'Segoe UI'; padding-top: 3px")
            gl.addWidget(label)
            self.group_layout.addWidget(group)
            divider = QtWidgets.QFrame()
            divider.setFrameShape(QtWidgets.QFrame.VLine)
            self.group_layout.addWidget(divider)
        self.group_layout.addStretch()

    def tab_changed(self, index):
        self._tab = self.tabs.tabText(index)
        if self._tab in TABS:
            self.build_groups(self._tab)
            self.refresh_context()

    def create_navigation(self):
        self.nav_dock = QtWidgets.QDockWidget("Navigation", self.main)
        self.nav_dock.setObjectName("FissionNavigationDock")
        self.nav_dock.setTitleBarWidget(QtWidgets.QWidget())
        self.nav_dock.setFeatures(QtWidgets.QDockWidget.NoDockWidgetFeatures)
        content = QtWidgets.QWidget()
        content.setObjectName("FissionNavigation")
        row = QtWidgets.QHBoxLayout(content)
        row.setContentsMargins(8, 1, 8, 1)
        for cmd, title in [("Std_ViewIsometric", "Home"), ("Std_ViewFront", "Front"),
                           ("Std_ViewTop", "Top"), ("Std_ViewRight", "Right"),
                           ("Std_ViewFitAll", "Fit  F6"), ("Std_ViewFitSelection", "Fit Selection"),
                           ("Std_OrthographicCamera", "Orthographic"), ("Std_PerspectiveCamera", "Perspective")]:
            row.addWidget(self.make_button(cmd, title, small=True))
        row.addStretch()
        row.addWidget(QtWidgets.QLabel("MMB Pan   ·   Shift + MMB Orbit   ·   Wheel Zoom"))
        self.nav_dock.setWidget(content)
        self.main.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.nav_dock)
        self.main.splitDockWidget(self.nav_dock, self.timeline, QtCore.Qt.Vertical)

    def context(self):
        doc = Gui.activeDocument()
        edit = doc.getInEdit() if doc else None
        if edit and edit.Object.isDerivedFrom("Sketcher::SketchObject"):
            return "sketch"
        if self._tab == "ASSEMBLE":
            return "assembly"
        return "model"

    def refresh_context(self):
        if not self.active:
            return
        doc = App.ActiveDocument
        self.document_label.setText((doc.Label + (" *" if doc.UndoCount else "")) if doc else "Local parametric design")
        ctx = self.context()
        if ctx != self._context:
            was_sketch = self._context == "sketch"
            self._context = ctx
            if ctx == "sketch":
                if self.tabs.count() and self.tabs.tabText(self.tabs.count() - 1) != "SKETCH":
                    self.tabs.addTab("SKETCH")
                self.tabs.setCurrentIndex(self.tabs.count() - 1)
                self.build_groups("SKETCH")
                self.notify("Sketch mode — L Line · R Rectangle · C Circle · D Dimension · Finish Sketch to return")
            elif was_sketch:
                for i in range(self.tabs.count()):
                    if self.tabs.tabText(i) == "SKETCH":
                        self.tabs.removeTab(i)
                        break
                self.tabs.setCurrentIndex(0)
                self._tab = "SOLID"
                self.build_groups("SOLID")
        for button in self.buttons:
            try:
                command = Gui.Command.get(button.property("fissionCommand"))
                button.setEnabled(bool(command and command.isActive()))
            except RuntimeError:
                pass  # deferred-deleted group button
        if doc and self.welcome:
            self.welcome.close()
            self.welcome = None
        if doc and Gui.activeDocument():
            view = Gui.activeDocument().activeView()
            if view and hasattr(view, "setNavigationType"):
                desired = self.settings.GetString("Navigation", "Gui::FissionNavigationStyle")
                if hasattr(view, "getNavigationType") and view.getNavigationType() != desired:
                    view.setNavigationType(desired)

    def prepare_sketch(self, obj):
        try:
            if obj.Document and obj.ViewObject and "EditingWorkbench" in obj.ViewObject.PropertiesList:
                obj.ViewObject.EditingWorkbench = "FissionWorkbench"
        except (RuntimeError, ReferenceError):
            pass

    def execute(self, command_id):
        try:
            cmd = Gui.Command.get(command_id)
            if not cmd:
                self.notify("This tool is unavailable in this build: " + command_id)
                return False
            if not cmd.isActive():
                self.notify("Select the required geometry before using " + cmd.getInfo().get("MenuText", command_id))
                return False
            Gui.runCommand(command_id)
            QtCore.QTimer.singleShot(0, self.refresh_context)
            return True
        except Exception as err:
            App.Console.PrintError("Fission command failed: %s\n%s\n" % (command_id, traceback.format_exc()))
            self.notify(str(err))
            return False

    def perform(self, name):
        if name == "NewDesign":
            self.new_design()
        elif name == "NewComponent":
            self.new_component()
        elif name == "CreateSketch":
            self.ensure_body()
            self.execute("PartDesign_NewSketch")
        elif name == "FinishSketch":
            edit = Gui.activeDocument().getInEdit() if Gui.activeDocument() else None
            obj = edit.Object if edit else None
            self.execute("Sketcher_LeaveSketch")
            if obj:
                Gui.Selection.clearSelection()
                Gui.Selection.addSelection(obj)
            self.refresh_context()
        elif name == "Move":
            self.move_copy()
        elif name == "Search":
            from .search import SearchDialog
            if not hasattr(self, "search_dialog"):
                self.search_dialog = SearchDialog(self, self.main)
            self.search_dialog.show()
            self.search_dialog.raise_()
            self.search_dialog.activateWindow()
        elif name == "Preferences":
            from .preferences import PreferencesDialog
            PreferencesDialog(self, self.main).exec()
        elif name == "About":
            QtWidgets.QMessageBox.about(self.main, "About Fission",
                "<h2>Fission 0.1 — Development build</h2><p>Local parametric mechanical design.</p>"
                "<p>Fission is based on the FreeCAD open-source project.</p>"
                "<p>FreeCAD's contributors retain their copyrights. Engine: LGPL 2.1 or later; "
                "Fission presentation: MIT. See the bundled NOTICE and licenses.</p>"
                "<p>Independent project; no endorsement by FreeCAD or Autodesk.</p>")
        elif name == "EditFeature":
            selection = Gui.Selection.getSelection()
            if selection:
                self.edit_object(selection[0])
        elif name == "ToggleBrowser":
            self.browser.setVisible(not self.browser.isVisible())
        elif name == "ToggleTimeline":
            self.timeline.setVisible(not self.timeline.isVisible())
        elif name == "ResetLayout":
            self.reset_layout()
        else:
            backend = COMMANDS[name][1]
            if backend:
                self.execute(backend)

    def new_design(self):
        doc = App.newDocument("Design")
        doc.Label = "Untitled Design"
        component = doc.addObject("App::Part", "Component")
        component.Label = "Component 1"
        body = doc.addObject("PartDesign::Body", "Body")
        body.Label = "Body 1"
        component.addObject(body)
        doc.recompute()
        view = Gui.activeDocument().activeView()
        view.setActiveObject("part", component)
        view.setActiveObject("pdbody", body)
        view.viewAxonometric()
        view.fitAll()
        self.refresh_context()
        return doc

    def new_component(self):
        doc = App.ActiveDocument or self.new_design()
        doc.openTransaction("New component")
        component = doc.addObject("App::Part", "Component")
        component.Label = "Component %d" % len([o for o in doc.Objects if o.TypeId == "App::Part"])
        body = doc.addObject("PartDesign::Body", "Body")
        component.addObject(body)
        doc.recompute()
        doc.commitTransaction()
        view = Gui.activeDocument().activeView()
        view.setActiveObject("part", component)
        view.setActiveObject("pdbody", body)
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(component)

    def ensure_body(self):
        if not App.ActiveDocument:
            self.new_design()
        view = Gui.activeDocument().activeView()
        body = view.getActiveObject("pdbody")
        if not body:
            bodies = [o for o in App.ActiveDocument.Objects if o.isDerivedFrom("PartDesign::Body")]
            if len(bodies) == 1:
                view.setActiveObject("pdbody", bodies[0])

    def edit_object(self, obj):
        if not obj or not obj.Document:
            return False
        Gui.activeDocument().activeView().setActiveObject("pdbody", obj.getParentGeoFeatureGroup()
            if obj.getParentGeoFeatureGroup() and obj.getParentGeoFeatureGroup().isDerivedFrom("PartDesign::Body") else None)
        if obj.isDerivedFrom("Sketcher::SketchObject"):
            self.prepare_sketch(obj)
        doc = Gui.getDocument(obj.Document.Name)
        if doc.getInEdit():
            self.notify("Finish or cancel the current feature before editing history.")
            return False
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(obj)
        result = doc.setEdit(obj.Name)
        self.refresh_context()
        return result

    def move_copy(self):
        selected = Gui.Selection.getSelection()
        if not selected:
            self.notify("Select a component or body to Move / Copy.")
            return
        dialog = QtWidgets.QDialog(self.main)
        dialog.setWindowTitle("Move / Copy")
        layout = QtWidgets.QFormLayout(dialog)
        layout.addRow(QtWidgets.QLabel("Translate selected components or bodies. Use Transform for rotation and canvas handles."))
        axes = []
        for title in ("X (mm)", "Y (mm)", "Z (mm)"):
            field = QtWidgets.QDoubleSpinBox()
            field.setRange(-1e6, 1e6)
            field.setDecimals(4)
            layout.addRow(title, field)
            axes.append(field)
        copy = QtWidgets.QCheckBox("Create linked copies (source geometry remains parametric)")
        layout.addRow(copy)
        manip = QtWidgets.QPushButton("Canvas Transform…")
        manip.clicked.connect(lambda: (dialog.reject(), self.execute("Std_Transform")))
        layout.addRow(manip)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        doc = App.ActiveDocument
        doc.openTransaction("Move / Copy")
        try:
            for obj in selected:
                target = obj
                if copy.isChecked():
                    target = doc.addObject("App::Link", "Copy")
                    target.setLink(obj)
                    target.Label = obj.Label + " Copy"
                if "Placement" not in target.PropertiesList:
                    raise ValueError("%s has no editable placement" % obj.Label)
                placement = App.Placement(target.Placement)
                placement.Base += App.Vector(*(field.value() for field in axes))
                target.Placement = placement
            doc.recompute()
            doc.commitTransaction()
        except Exception:
            doc.abortTransaction()
            raise

    def command_catalog(self):
        return catalog()

    def notify(self, message):
        self.main.statusBar().showMessage(message, 8000)

    def switch_workspace(self, name):
        if name == "Drawing":
            Gui.activateWorkbench("TechDrawWorkbench")
        elif name == "Manufacture":
            Gui.activateWorkbench("CAMWorkbench" if "CAMWorkbench" in Gui.listWorkbenches() else "PathWorkbench")

    def save_layout(self):
        if self.active:
            state = bytes(self.main.saveState(1))
            self.settings.SetString("Layout", base64.b64encode(state).decode("ascii"))
            self.settings.SetString("Geometry", base64.b64encode(bytes(self.main.saveGeometry())).decode("ascii"))
            App.saveParameter()

    def restore_layout(self):
        try:
            geometry = self.settings.GetString("Geometry", "")
            if geometry:
                self.main.restoreGeometry(QtCore.QByteArray(base64.b64decode(geometry)))
            state = self.settings.GetString("Layout", "")
            if state:
                self.main.restoreState(QtCore.QByteArray(base64.b64decode(state)), 1)
            else:
                self.main.resizeDocks([self.browser], [255], QtCore.Qt.Horizontal)
                self.main.resizeDocks([self.timeline], [100], QtCore.Qt.Vertical)
        except (ValueError, RuntimeError):
            self.reset_layout()

    def shutdown(self):
        self.timer.stop()
        self.browser.shutdown()
        self.timeline.shutdown()
        self.shortcuts.deactivate()
        App.removeDocumentObserver(self.observer)

    def reset_layout(self):
        self.main.addDockWidget(QtCore.Qt.TopDockWidgetArea, self.ribbon_dock)
        self.main.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.browser)
        self.main.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.nav_dock)
        self.main.splitDockWidget(self.nav_dock, self.timeline, QtCore.Qt.Vertical)
        for widget in (self.ribbon_dock, self.browser, self.timeline, self.nav_dock):
            widget.show()
        self.main.resizeDocks([self.browser], [255], QtCore.Qt.Horizontal)
        self.main.resizeDocks([self.timeline], [100], QtCore.Qt.Vertical)
        self.save_layout()

    def show_welcome(self):
        mdi = self.main.findChild(QtWidgets.QMdiArea)
        if not mdi or self.welcome:
            return
        widget = QtWidgets.QWidget()
        widget.setObjectName("FissionWelcome")
        outer = QtWidgets.QVBoxLayout(widget)
        outer.setContentsMargins(60, 38, 60, 30)
        title = QtWidgets.QLabel("FISSION")
        title.setStyleSheet("font: 600 28pt 'Segoe UI'; letter-spacing: 5px")
        outer.addWidget(title)
        outer.addWidget(QtWidgets.QLabel("Mechanical design. Local files. Your modeling history."))
        outer.addSpacing(25)
        for cmd, text in [("Fission_NewDesign", "New Design   Ctrl + N"), ("Std_Open", "Open Design   Ctrl + O"),
                          ("Std_Import", "Import STEP / STL / other formats"), ("Fission_Preferences", "Preferences and shortcuts")]:
            button = QtWidgets.QPushButton(text)
            button.setMaximumWidth(480)
            button.clicked.connect(lambda checked=False, command=cmd: self.execute(command))
            outer.addWidget(button)
        outer.addSpacing(22)
        outer.addWidget(QtWidgets.QLabel("RECENT DOCUMENTS"))
        recent = App.ParamGet("User parameter:BaseApp/Preferences/RecentFiles")
        paths = [value for kind, key, value in recent.GetContents() if key.startswith("MRU")]
        for path in paths[:8]:
            button = QtWidgets.QPushButton(os.path.basename(path))
            button.setToolTip(path)
            button.clicked.connect(lambda checked=False, filename=path: Gui.open(filename))
            outer.addWidget(button)
        outer.addStretch()
        outer.addWidget(QtWidgets.QLabel("S Command Search   ·   E Extrude   ·   F Fillet   ·   I Measure   ·   F6 Fit"))
        outer.addWidget(QtWidgets.QLabel("Based on the FreeCAD open-source project. Independent Fission development build."))
        self.welcome = mdi.addSubWindow(widget)
        self.welcome.setWindowTitle("Welcome to Fission")
        self.welcome.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.welcome.showMaximized()
