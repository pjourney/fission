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
WORKSPACES = ("Design", "Drawing", "Manufacture")
WORKBENCH_WORKSPACES = {"FissionWorkbench": "Design", "TechDrawWorkbench": "Drawing",
                        "CAMWorkbench": "Manufacture", "PathWorkbench": "Manufacture"}
WORKSPACE_TABS = {"Design": ("SOLID", "SURFACE", "MESH", "ASSEMBLE", "UTILITIES", "SHEET METAL"),
                  "Drawing": ("VIEWS", "ANNOTATE", "OUTPUT"),
                  "Manufacture": ("SETUP", "MILLING", "TOOLPATH")}


def existing_controller():
    return _controller


def get_controller():
    global _controller
    if _controller is None:
        _controller = Controller(Gui.getMainWindow())
    return _controller


TABS = {
    "SOLID": [
        ("CREATE", ["CreateSketch", "Extrude", "Revolve", "Sweep", "Loft", "Hole",
                    ("PartDesign_CompPrimitiveAdditive", "Primitive")]),
        ("MODIFY", ["Cut", "Fillet", "Chamfer", "Shell", "Draft", "Move", "Boolean",
                    ("PartDesign_CompPrimitiveSubtractive", "Primitive Cut")]),
        ("PATTERN", ["Mirror", "RectPattern", "CircPattern"]),
        ("CONSTRUCT", ["Plane", "NewComponent"]),
        ("INSPECT", ["Measure"]),
    ],
    "SURFACE": [
        ("CREATE", ["CreateSketch", ("Surface_Filling", "Fill"), ("Surface_GeomFillSurface", "Boundary"),
                    ("Surface_Sections", "Loft Sections"), ("Part_RuledSurface", "Ruled Surface")]),
        ("CURVES", [("Surface_BlendCurve", "Blend Curve"), ("Surface_CurveOnMesh", "Curve on Mesh")]),
        ("MODIFY", [("Surface_ExtendFace", "Extend"), ("Part_Cut", "Subtract")]),
        ("CONVERT", ["Stitch", ("Part_Builder", "Build Shell"), ("Part_MakeSolid", "Convert to Solid"), ("Part_RefineShape", "Refine")]),
        ("INSPECT", [("Part_CheckGeometry", "Validate"), "Measure"]),
    ],
    "MESH": [
        ("CREATE", [("Mesh_Import", "Import Mesh"), ("Mesh_FromPartShape", "Tessellate")]),
        ("MODIFY", [("Mesh_Smoothing", "Smooth"), ("Mesh_Decimating", "Reduce")]),
        ("REPAIR", [("Mesh_Evaluation", "Analyze"), ("Mesh_HarmonizeNormals", "Align Normals"),
                    ("Mesh_FlipNormals", "Flip Normals"), ("Mesh_FillupHoles", "Fill Holes")]),
        ("CONVERT", [("Part_ShapeFromMesh", "Mesh to Shape"), ("Part_MakeSolid", "Convert to Solid"), ("Part_RefineShape", "Refine")]),
        ("EXPORT", [("Mesh_Export", "Export Mesh")]),
    ],
    "ASSEMBLE": [
        ("COMPONENTS", [("Assembly_CreateAssembly", "New Assembly"), ("Assembly_ActivateAssembly", "Activate Assembly"),
                       ("Assembly_InsertLink", "Insert Component"), ("Assembly_InsertNewPart", "New Assembly Part")]),
        ("JOINTS", ["AssemblyJoint", ("Assembly_CreateJointRevolute", "Revolute"),
                    ("Assembly_CreateJointSlider", "Slider"), ("Assembly_CreateJointBall", "Ball")]),
        ("POSITION", [("Assembly_ToggleGrounded", "Ground / Unground"), ("Assembly_SolveAssembly", "Solve"), "Move"]),
    ],
    "UTILITIES": [
        ("INSPECT", ["Measure", ("Std_MassProperties", "Mass Properties"), ("Part_CheckGeometry", "Check Geometry")]),
        ("PARAMETERS", [("Spreadsheet_CreateSheet", "Parameter Sheet"), "Compute"]),
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
    "VIEWS": [
        ("SHEET", [("TechDraw_PageDefault", "New Sheet"), ("TechDraw_PageTemplate", "Sheet Template")]),
        ("VIEWS", [("TechDraw_View", "Base View"), ("TechDraw_ProjectionGroup", "Projected Views"),
                   ("TechDraw_SectionView", "Section"), ("TechDraw_DetailView", "Detail")]),
        ("DISPLAY", [("TechDraw_RedrawPage", "Update Sheet"), ("TechDraw_ToggleFrame", "View Frames")]),
    ],
    "ANNOTATE": [
        ("DIMENSION", [("TechDraw_Dimension", "Dimension"), ("TechDraw_LengthDimension", "Length"),
                       ("TechDraw_RadiusDimension", "Radius"), ("TechDraw_AngleDimension", "Angle")]),
        ("NOTES", [("TechDraw_Annotation", "Text"), ("TechDraw_Balloon", "Balloon"), ("TechDraw_Hatch", "Hatch")]),
    ],
    "OUTPUT": [
        ("EXPORT SHEET", [("TechDraw_ExportPagePDF", "PDF"), ("TechDraw_ExportPageSVG", "SVG"), ("TechDraw_ExportPageDXF", "DXF")]),
        ("FILES", [("Std_Save", "Save Drawing")]),
    ],
    "SETUP": [
        ("JOB", [("CAM_Job", "New Setup"), ("CAM_Workplane", "Workplane"), ("CAM_Sanity", "Check Setup")]),
        ("TOOLS", [("CAM_ToolController", "Tool Controller"), ("CAM_ToolBitLibraryOpen", "Tool Library")]),
    ],
    "MILLING": [
        ("2D MILLING", [("CAM_Profile", "Profile"), ("CAM_Pocket_Shape", "Pocket"), ("CAM_MillFacing", "Face"), ("CAM_Drilling", "Drill")]),
        ("3D MILLING", [("CAM_Pocket3D", "3D Pocket"), ("CAM_Surface", "Surface")]),
    ],
    "TOOLPATH": [
        ("VERIFY", [("CAM_SimulatorGL", "Simulate"), ("CAM_Inspect", "Inspect"), ("CAM_Sanity", "Check Setup")]),
        ("OPERATIONS", [("CAM_OpActiveToggle", "Enable / Disable"), ("CAM_OperationCopy", "Copy Operation")]),
        ("OUTPUT", [("CAM_Post", "Post Process"), ("CAM_PostSelected", "Post Selected")]),
    ],
}


def command_spec(item):
    if isinstance(item, tuple):
        command, title = item
        return command, title
    return "Fission_" + item, COMMANDS[item][0]


def command_icon(command):
    from .icons import resolve
    return resolve(command)


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
        self._keep_shortcuts = False
        self._activation_pending = False
        self._tab = "SOLID"
        self._workspace_name = "Design"
        self._shell_workbench = None
        self._workspace_document = None
        self._design_tab = "SOLID"
        self.buttons = []
        self._saved_toolbar_visibility = {}
        self._saved_dock_visibility = {}
        self._properties_before_task = {}
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
        from .selection import PaintSelection
        from .marking import MarkingMenu
        self.paint = PaintSelection(self)
        self.marking = MarkingMenu(self)
        self.observer = DocumentObserver(self)
        App.addDocumentObserver(self.observer)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.refresh_context)
        self.main.installEventFilter(self)
        self.main.workbenchActivated.connect(self.workbench_changed)
        QtWidgets.QApplication.instance().aboutToQuit.connect(self.shutdown)
        self.welcome = None
        self.main.setMinimumSize(1080, 700)

    def eventFilter(self, obj, event):
        if obj is self.main and event.type() == QtCore.QEvent.Close:
            self.save_layout()
        return False

    def activate(self):
        self.activate_workspace("Design")

    def activate_workspace(self, name):
        self.active = True
        self._workspace_name = name
        workbench = Gui.activeWorkbench()
        self._shell_workbench = workbench.name() if workbench else None
        self.workspace.blockSignals(True)
        self.workspace.setCurrentText(name)
        self.workspace.blockSignals(False)
        self.configure_tabs(name)
        self._context = None
        self.hide_legacy_chrome()
        theme.apply(self.main)
        self.ribbon_dock.setWindowTitle(name)
        for widget in (self.ribbon_dock, self.browser):
            widget.show()
        self.nav_dock.setVisible(self.settings.GetBool("ShowNavigation", True))
        self.timeline.setVisible(name == "Design")
        # FreeCAD restores its own main-window state after activating the first
        # workbench. Apply our saved state once that native startup has finished.
        if not self._activation_pending:
            self._activation_pending = True
            QtCore.QTimer.singleShot(0, self.complete_activation)
        self.shortcuts.apply_profile(self.shortcuts.profile.name)
        self.timer.start()

    def configure_tabs(self, workspace):
        self.tabs.blockSignals(True)
        while self.tabs.count():
            self.tabs.removeTab(0)
        keys = [key for key in WORKSPACE_TABS[workspace] if key in TABS
                and any(Gui.Command.get(command_spec(item)[0]) for _, items in TABS[key] for item in items)]
        for key in keys:
            self.tabs.addTab(key)
        desired = self._design_tab if workspace == "Design" else (keys[0] if keys else "")
        self._tab = desired if desired in keys else (keys[0] if keys else "")
        if self._tab:
            self.tabs.setCurrentIndex(keys.index(self._tab))
            self.build_groups(self._tab)
        self.tabs.blockSignals(False)

    def workbench_changed(self, _name):
        # Native workbenches finish creating/removing their Qt chrome first.
        QtCore.QTimer.singleShot(0, self.sync_workbench)

    def sync_workbench(self):
        workbench = Gui.activeWorkbench()
        identifier = workbench.name() if workbench else None
        workspace = WORKBENCH_WORKSPACES.get(identifier)
        if workspace is None:
            if self.active:
                self.deactivate()
            return
        if not self.active or self._shell_workbench != identifier or self._workspace_name != workspace:
            if self.active:
                self.deactivate()
            self.activate_workspace(workspace)
        else:
            self.hide_legacy_chrome()
            self.refresh_context()

    def complete_activation(self):
        self._activation_pending = False
        if not self.active:
            return
        self.hide_legacy_chrome()
        self.restore_layout()
        document = self._workspace_document
        self._workspace_document = None
        if document and document in App.listDocuments():
            Gui.setActiveDocument(document)
            App.setActiveDocument(document)
        if self._workspace_name != "Design":
            self.timeline.hide()
        self.nav_dock.setVisible(self.settings.GetBool("ShowNavigation", True))
        self.refresh_context()
        if self._workspace_name == "Design" and not App.ActiveDocument:
            self.show_welcome()

    def deactivate(self):
        if hasattr(self, "move_dialog"):
            self.move_dialog.reject()
        self.save_layout()
        self.marking.close()
        self.paint.cancel()
        self.active = False
        self.timer.stop()
        if not self._keep_shortcuts and hasattr(self.shortcuts, "deactivate"):
            self.shortcuts.deactivate()
        for widget in (self.ribbon_dock, self.browser, self.timeline, self.nav_dock):
            widget.hide()
        for saved in (self._saved_toolbar_visibility, self._saved_dock_visibility,
                      self._properties_before_task):
            # Native workbenches may delete/recreate docks and toolbars while
            # active. Their Python wrappers can outlive the Qt objects.
            for widget, visible in list(saved.items()):
                try:
                    widget.setVisible(visible)
                except RuntimeError:
                    pass  # native Qt object has already been deleted
            saved.clear()
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
        self.workspace.addItems(list(WORKSPACES))
        self.workspace.setToolTip("Design, technical drawings and manufacturing setups share the Fission workspace.")
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
        for tab in WORKSPACE_TABS["Design"]:
            if tab not in TABS:
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
        native = Gui.Command.get(command)
        description = native.getInfo().get("toolTip", title) if native else title
        button.setToolTip(description)
        button.setProperty("fissionDescription", description)
        button.clicked.connect(lambda checked=False, cmd=command: self.execute(cmd))
        button.setProperty("fissionCommand", command)
        self.add_variants(button, command)
        self.buttons.append(button)
        return button

    def variant_context_token(self):
        gui_document = Gui.activeDocument()
        edit = gui_document.getInEdit() if gui_document else None
        workbench = Gui.activeWorkbench()
        return (self.command_context_token(), self.context(),
                edit.Object if edit else None, workbench.name() if workbench else None)

    def add_variants(self, button, command):
        from .ribbon_tools import variants_for
        variants = [entry for entry in variants_for(command) if Gui.Command.get(entry[0])]
        if not variants:
            return
        menu = QtWidgets.QMenu(button)
        menu.setObjectName("FissionVariants_" + command)
        for identifier, title, index in variants:
            icon = command_icon(identifier)
            if index is not None:
                native_actions = Gui.Command.get(identifier).getAction()
                if 0 <= index < len(native_actions):
                    icon = native_actions[index].icon()
            action = menu.addAction(icon, title)
            action.setProperty("fissionCommand", identifier)
            action.setProperty("fissionCommandIndex", -1 if index is None else index)
            action.triggered.connect(lambda checked=False, item=action: self.execute_variant(menu, item))
        menu.aboutToShow.connect(lambda: self.refresh_variants(menu))
        button.setMenu(menu)
        button.setPopupMode(QtWidgets.QToolButton.MenuButtonPopup)

    def refresh_variants(self, menu):
        menu._fission_owner_token = self.variant_context_token()
        self.refresh_command_state()
        for action in menu.actions():
            identifier = action.property("fissionCommand")
            command = Gui.Command.get(identifier)
            index = action.property("fissionCommandIndex")
            native_actions = command.getAction() if command else []
            enabled = self.command_available(identifier)
            if index >= 0:
                enabled = enabled and index < len(native_actions) and native_actions[index].isEnabled()
            action.setEnabled(enabled)

    def execute_variant(self, menu, action):
        token = getattr(menu, "_fission_owner_token", None)
        identifier = action.property("fissionCommand")
        index = action.property("fissionCommandIndex")
        def dispatch():
            if (not self.active or self._activation_pending or token != self.variant_context_token()):
                self.notify("The design or editing context changed; open the tool menu again.")
                return
            application = QtWidgets.QApplication.instance()
            if application.activeModalWidget() or application.activePopupWidget():
                self.notify("Close the open dialog or menu before running this tool.")
                return
            self.refresh_command_state()
            if not self.command_available(identifier):
                self.notify("This tool is unavailable for the current selection or operation.")
                return
            focus = self.command_focus_widget()
            if focus is not None:
                focus.setFocus(QtCore.Qt.OtherFocusReason)
            self.execute(identifier, None if index < 0 else index)
        # QMenu releases its popup/focus before native CAD handlers start.
        QtCore.QTimer.singleShot(0, dispatch)

    def build_groups(self, tab):
        while self.group_layout.count():
            item = self.group_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        self.buttons = [b for b in self.buttons if b.toolButtonStyle() == QtCore.Qt.ToolButtonTextBesideIcon]
        for name, items in TABS[tab]:
            available = [(command_spec(item)) for item in items if Gui.Command.get(command_spec(item)[0])]
            if not available:
                continue
            group = QtWidgets.QWidget()
            gl = QtWidgets.QVBoxLayout(group)
            gl.setContentsMargins(3, 1, 3, 1)
            gl.setSpacing(0)
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(1)
            for command, title in available:
                row.addWidget(self.make_button(command, title))
            gl.addLayout(row)
            label = QtWidgets.QLabel(name)
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setStyleSheet("font: 8pt 'Segoe UI'; padding-top: 3px")
            gl.addWidget(label)
            self.group_layout.addWidget(group)
            group.show()
            divider = QtWidgets.QFrame()
            divider.setFrameShape(QtWidgets.QFrame.VLine)
            self.group_layout.addWidget(divider)
            divider.show()
        self.group_layout.addStretch()

    def tab_changed(self, index):
        self._tab = self.tabs.tabText(index)
        if self._workspace_name == "Design" and self._tab != "SKETCH":
            self._design_tab = self._tab
        if self._tab in TABS:
            self.build_groups(self._tab)
            self.refresh_context()

    def create_navigation(self):
        self.nav_dock = QtWidgets.QDockWidget("Navigation", self.main)
        self.nav_dock.setObjectName("FissionNavigationDock")
        self.nav_dock.setTitleBarWidget(QtWidgets.QWidget())
        self.nav_dock.setFeatures(QtWidgets.QDockWidget.NoDockWidgetFeatures)
        self.nav_dock.setMaximumHeight(44)
        content = QtWidgets.QWidget()
        content.setObjectName("FissionNavigation")
        row = QtWidgets.QHBoxLayout(content)
        row.setContentsMargins(8, 1, 8, 1)
        for cmd, title in [("Std_ViewIsometric", "Home"), ("Std_ViewFront", "Front"),
                           ("Std_ViewTop", "Top"), ("Std_ViewRight", "Right"),
                           ("Std_ViewFitAll", "Fit  F6"), ("Std_ViewFitSelection", "Fit Selection"),
                           ("Std_OrthographicCamera", "Orthographic"), ("Std_PerspectiveCamera", "Perspective")]:
            row.addWidget(self.make_button(cmd, title, small=True))
        select = QtWidgets.QToolButton()
        select.setText("Select")
        select.setIcon(command_icon("Fission_WindowSelection"))
        select.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        menu = QtWidgets.QMenu(select)
        for command, title in (("WindowSelection", "Window  1"), ("FreeformSelection", "Freeform  2"),
                               ("PaintSelection", "Paint  3")):
            menu.addAction(command_icon("Fission_" + command), title,
                           lambda checked=False, name=command: self.execute("Fission_" + name))
        select.setMenu(menu)
        row.addWidget(select)
        row.addWidget(self.make_button("Fission_MarkingMenu", "Marking Menu", small=True))
        row.addStretch()
        row.addWidget(QtWidgets.QLabel("MMB Pan · Shift + MMB Orbit · Alt + RMB Menu"))
        self.nav_dock.setWidget(content)
        self.main.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.nav_dock)
        self.main.splitDockWidget(self.nav_dock, self.timeline, QtCore.Qt.Vertical)

    def context(self):
        workbench = Gui.activeWorkbench()
        name = workbench.name() if workbench else ""
        if name == "TechDrawWorkbench":
            return "drawing"
        if name in ("CAMWorkbench", "PathWorkbench"):
            return "cam"
        doc = Gui.activeDocument()
        edit = doc.getInEdit() if doc else None
        if edit and edit.Object.isDerivedFrom("Sketcher::SketchObject"):
            return "sketch"
        if self._tab == "SURFACE":
            return "surface"
        if self._tab == "MESH":
            return "mesh"
        if self._tab == "ASSEMBLE":
            return "assembly"
        return "model"

    def refresh_context(self):
        if not self.active or self._activation_pending:
            return
        self.marking.validate()
        if hasattr(self, "search_dialog"):
            self.search_dialog.validate_owner()
        doc = App.ActiveDocument
        gui_doc = Gui.getDocument(doc.Name) if doc else None
        editing = bool(Gui.Control.activeDialog() or (gui_doc and gui_doc.getInEdit()))
        for dock in self.main.findChildren(QtWidgets.QDockWidget):
            if dock.objectName() == "Tasks":
                if editing:
                    if dock.isFloating():
                        dock.setFloating(False)
                    if self.main.dockWidgetArea(dock) != QtCore.Qt.RightDockWidgetArea:
                        self.main.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
                    dock.setWindowTitle("Feature Parameters")
                dock.setVisible(editing)
            elif dock.objectName() in ("Property view", "Property editor"):
                if editing:
                    self._properties_before_task.setdefault(dock, dock.isVisible())
                    dock.hide()
                elif dock in self._properties_before_task:
                    dock.setVisible(self._properties_before_task.pop(dock))
        self.document_label.setText((doc.Label + (" *" if gui_doc and gui_doc.Modified else "")) if doc else "Local parametric design")
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
                for i in range(self.tabs.count()):
                    if self.tabs.tabText(i) == self._design_tab:
                        self.tabs.setCurrentIndex(i)
                        break
                self._tab = self._design_tab
                self.build_groups(self._tab)
        for button in self.buttons:
            try:
                command = Gui.Command.get(button.property("fissionCommand"))
                actions = command.getAction() if command else []
                # Query the native cached action state after activation settles.
                # Calling isActive during native document/workbench teardown can
                # dereference the view that FreeCAD is currently disposing.
                wrapper = button.property("fissionCommand").startswith("Fission_")
                button.setEnabled(bool(command and (command.isActive() if wrapper or not actions
                                                     else any(action.isEnabled() for action in actions))))
                hint = self.shortcuts.shortcut_for(button.property("fissionCommand"), ctx)
                description = button.property("fissionDescription") or button.text()
                button.setToolTip(description + ("\nShortcut: " + hint if hint else ""))
            except RuntimeError:
                pass  # deferred-deleted group button
        if doc and self.welcome:
            welcome = self.welcome
            self.welcome = None
            welcome.close()
        if doc and Gui.activeDocument():
            view = Gui.activeDocument().activeView()
            if view and hasattr(view, "setNavigationType"):
                desired = self.settings.GetString("Navigation", "Gui::FissionNavigationStyle")
                if hasattr(view, "getNavigationType") and view.getNavigationType() != desired:
                    view.setNavigationType(desired)

    def prepare_sketch(self, obj):
        # The native sketch adapter retains Design during setEdit. Never store
        # a Fission-only workbench name in otherwise compatible FCStd files.
        return

    def execute(self, command_id, command_index=None):
        try:
            if self.paint.viewport is not None and command_id not in (
                    "Fission_WindowSelection", "Fission_FreeformSelection", "Fission_PaintSelection"):
                self.paint.cancel()
            cmd = Gui.Command.get(command_id)
            if not cmd:
                self.notify("This tool is unavailable in this build: " + command_id)
                return False
            if not cmd.isActive():
                self.notify("Select the required geometry before using " + cmd.getInfo().get("menuText", command_id))
                return False
            # Native QAction availability includes task-dialog ownership checks
            # that Command.isActive alone omits. Sketch-to-solid is a deliberate
            # transition handled transactionally by the Fission wrapper.
            transitions = command_id in ("Fission_Extrude", "Fission_Cut") and self.context() == "sketch"
            if not transitions and not command_id.startswith("Fission_"):
                Gui.Command.update()
                actions = cmd.getAction()
                if actions and not any(action.isEnabled() for action in actions):
                    self.notify("Finish or cancel the active operation before using this command.")
                    return False
            if command_index is None:
                Gui.runCommand(command_id)
            else:
                actions = cmd.getAction()
                if not (0 <= command_index < len(actions) and actions[command_index].isEnabled()):
                    self.notify("This tool variant is unavailable for the current operation.")
                    return False
                Gui.runCommand(command_id, command_index)
            QtCore.QTimer.singleShot(0, self.refresh_context)
            return True
        except Exception as err:
            App.Console.PrintError("Fission command failed: %s\n%s\n" % (command_id, traceback.format_exc()))
            self.notify(str(err))
            return False

    def perform(self, name):
        if (name in ("RevolveCut", "SweepCut", "LoftCut", "Plane", "Axis", "Point", "NewBody")
                or name in ("Extrude", "Cut") and self.context() != "sketch"):
            from .modeling import prepare
            if not prepare(name):
                self.notify("Finish the current operation and check the active component and selection before using " + COMMANDS[name][0] + ".")
                return False
            return self.execute(COMMANDS[name][1])
        elif name == "NewDesign":
            self.new_design()
        elif name == "NewComponent":
            return self.new_component()
        elif name == "CreateSketch":
            if self.ensure_body():
                self.execute("PartDesign_NewSketch")
        elif name == "FinishSketch":
            edit = Gui.activeDocument().getInEdit() if Gui.activeDocument() else None
            obj = edit.Object if edit else None
            self.execute("Sketcher_LeaveSketch")
            if obj:
                Gui.Selection.clearSelection()
                Gui.Selection.addSelection(obj)
            self.refresh_context()
        elif name in ("Extrude", "Cut") and self.context() == "sketch":
            self.perform("FinishSketch")
            return self.perform(name) if self.context() != "sketch" else False
        elif name == "Move":
            self.move_copy()
        elif name == "Search":
            from .search import SearchDialog
            if not hasattr(self, "search_dialog"):
                self.search_dialog = SearchDialog(self, self.main)
            self.search_dialog.show()
            self.search_dialog.raise_()
            self.search_dialog.activateWindow()
        elif name == "MarkingMenu":
            self.marking.open()
        elif name in ("WindowSelection", "FreeformSelection", "PaintSelection"):
            self.marking.close()
            self.paint.cancel()
            if name == "PaintSelection":
                self.paint.start()
            else:
                self.execute("Std_BoxSelection" if name == "WindowSelection" else "Std_FreehandSelection")
        elif name == "Preferences":
            from .preferences import PreferencesDialog
            PreferencesDialog(self, self.main).exec()
        elif name == "About":
            QtWidgets.QMessageBox.about(self.main, "About Fission",
                "<h2>Fission 0.8 Alpha</h2><p>Local parametric mechanical design.</p>"
                "<p>Fission is based on the FreeCAD open-source project.</p>"
                "<p>FreeCAD's contributors retain their copyrights. Engine: LGPL 2.1 or later; "
                "Fission presentation: MIT and LGPL, as identified in each source file. See the bundled NOTICE and licenses.</p>"
                "<p>Independent project; no endorsement by FreeCAD or Autodesk.</p>")
        elif name == "EditFeature":
            selection = Gui.Selection.getSelection()
            if selection:
                self.edit_object(selection[0])
        elif name == "ToggleBrowser":
            self.browser.setVisible(not self.browser.isVisible())
        elif name == "ToggleTimeline":
            if self._workspace_name == "Design":
                self.timeline.setVisible(not self.timeline.isVisible())
        elif name == "ToggleNavigation":
            visible = not self.nav_dock.isVisible()
            self.settings.SetBool("ShowNavigation", visible)
            self.nav_dock.setVisible(visible)
            self.save_layout()
        elif name == "ToggleViewCube":
            self.toggle_view_cube()
        elif name in ("PreviousWorkspace", "NextWorkspace"):
            offset = -1 if name == "PreviousWorkspace" else 1
            self.switch_workspace(WORKSPACES[(WORKSPACES.index(self._workspace_name) + offset) % len(WORKSPACES)])
        elif name == "Stitch":
            from .surface import StitchDialog
            self.stitch_dialog = StitchDialog(self)
            self.stitch_dialog.open()
        elif name == "ResetLayout":
            self.reset_layout()
        else:
            backend = COMMANDS[name][1]
            if backend:
                self.execute(backend)

    def toggle_view_cube(self):
        preferences = App.ParamGet("User parameter:BaseApp/Preferences/View")
        enabled = not preferences.GetBool("ShowNaviCube", True)
        preferences.SetBool("ShowNaviCube", enabled)
        # Keep existing 3D documents in sync, including the one beneath a drawing.
        for name in App.listDocuments():
            document = Gui.getDocument(name)
            for view in document.mdiViewsOfType("Gui::View3DInventor"):
                view.getViewer().setEnabledNaviCube(enabled)
        App.saveParameter()
        self.notify("Orientation cube " + ("shown" if enabled else "hidden"))

    def new_design(self):
        if self._workspace_name != "Design" and not self.switch_workspace("Design"):
            return None
        doc = App.newDocument("Design")
        # Workspace activation restores its document after native Qt layout
        # setup. A new design requested during that transition must become the
        # restore target instead of the previously active document.
        if self._activation_pending:
            self._workspace_document = doc.Name
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
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) == "SOLID":
                self.tabs.setCurrentIndex(index)
                break
        self.refresh_context()
        return doc

    def new_component(self):
        doc = App.ActiveDocument or self.new_design()
        from .modeling import prepare
        if not prepare("NewComponent"):
            self.notify("Finish or cancel the active feature before creating a component.")
            return False
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
        return component

    def ensure_body(self):
        if not App.ActiveDocument:
            self.new_design()
        doc = App.ActiveDocument
        if doc.HasPendingTransaction or Gui.Control.activeDialog():
            self.notify("Finish or cancel the current operation before creating a sketch.")
            return False
        view = Gui.activeDocument().activeView()
        component = view.getActiveObject("part")
        body = view.getActiveObject("pdbody")
        if body and body.getParentGeoFeatureGroup() is not component:
            view.setActiveObject("pdbody", None)
            body = None
        if not body:
            bodies = [o for o in doc.Objects if o.isDerivedFrom("PartDesign::Body")
                      and o.getParentGeoFeatureGroup() is component]
            if len(bodies) == 1:
                view.setActiveObject("pdbody", bodies[0])
            elif not bodies:
                # The native new-sketch workflow can auto-activate the sole
                # Body anywhere in the document. Establish an actual Body in
                # the selected component first, so it cannot target another.
                doc.openTransaction("New body")
                try:
                    body = doc.addObject("PartDesign::Body", "Body")
                    if component:
                        component.addObject(body)
                    doc.recompute()
                    doc.commitTransaction()
                except Exception:
                    doc.abortTransaction()
                    raise
                view.setActiveObject("pdbody", body)
        return True

    def edit_object(self, obj):
        if not obj or not obj.Document:
            return False
        doc = Gui.getDocument(obj.Document.Name)
        if doc.getInEdit():
            self.notify("Finish or cancel the current feature before editing history.")
            return False
        if obj.Document.HasPendingTransaction:
            self.notify("Finish or cancel the current operation before editing history.")
            return False
        App.setActiveDocument(obj.Document.Name)
        parent = obj.getParentGeoFeatureGroup()
        body = parent if parent and parent.isDerivedFrom("PartDesign::Body") else None
        component = body.getParentGeoFeatureGroup() if body else parent
        view = doc.activeView()
        view.setActiveObject("part", component if component and component.isDerivedFrom("App::Part") else None)
        view.setActiveObject("pdbody", body)
        if obj.isDerivedFrom("Sketcher::SketchObject"):
            self.prepare_sketch(obj)
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(obj)
        # Native PartDesign double-click opens a transaction before showing its
        # task editor. Keep the same commit/cancel semantics from the Timeline.
        opened = not obj.isDerivedFrom("Sketcher::SketchObject")
        if opened:
            obj.Document.openTransaction("Edit " + obj.Label)
        try:
            result = doc.setEdit(obj.Name)
            if result is False and opened:
                obj.Document.abortTransaction()
        except Exception:
            if opened:
                obj.Document.abortTransaction()
            raise
        self.refresh_context()
        return result

    def move_copy(self):
        from .move import run
        return run(self)

    def command_catalog(self):
        return catalog()

    def refresh_command_state(self):
        """Refresh native action ownership once for an explicit toolbox update."""
        if self.active and not self._activation_pending:
            self._search_command_ids = {button.property("fissionCommand") for button in self.buttons}
            for button in self.buttons:
                menu = button.menu()
                if menu:
                    self._search_command_ids.update(action.property("fissionCommand")
                                                    for action in menu.actions())
            if not hasattr(self, "_search_factory_bindings"):
                from .shortcuts import ShortcutProfile
                self._search_factory_bindings = ShortcutProfile().bindings
            context = self.context()
            self._search_command_ids.update(row["command"] for row in self._search_factory_bindings
                if row.get("state") != "unsupported" and ("*" in row["contexts"] or context in row["contexts"]))
            Gui.Command.update()

    def command_available(self, command_id, refresh=False):
        """Use the same native availability gates as command execution."""
        if not self.active or self._activation_pending:
            return False
        if refresh:
            self.refresh_command_state()
        command = Gui.Command.get(command_id)
        if not command:
            return False
        if command_id.startswith("Fission_"):
            if not command.isActive():
                return False
            name = command_id.removeprefix("Fission_")
            backend = COMMANDS.get(name, (None, None))[1]
            # Finishing a sketch before Pad/Pocket is a deliberate transition.
            if name in ("Extrude", "Cut") and self.context() == "sketch":
                return True
            native = Gui.Command.get(backend) if backend else None
            actions = native.getAction() if native else []
            return not actions or any(action.isEnabled() for action in actions)
        # Registered commands from inactive workbenches may assume a native
        # viewer/task that does not exist. Query only instantiated actions;
        # Command.update already applied their native ownership/active checks.
        actions = command.getAction()
        if actions:
            return any(action.isEnabled() for action in actions)
        # Fission's ribbon and factory keys also present native tools without
        # creating stock workbench actions. These context-vetted commands use
        # the same active check as the ribbon; unloaded catalogs stay unavailable.
        if command_id in getattr(self, "_search_command_ids", set()):
            return bool(command.isActive())
        return False

    def command_context_token(self):
        """Retain object identity so closing/reopening a named document is stale."""
        document = App.ActiveDocument
        gui_document = Gui.activeDocument() if document else None
        view = gui_document.activeView() if gui_document else None
        return document, view

    def command_focus_widget(self):
        gui_document = Gui.activeDocument() if App.ActiveDocument else None
        view = gui_document.activeView() if gui_document else None
        return view.graphicsView() if view and hasattr(view, "graphicsView") else None

    def notify(self, message):
        self.main.statusBar().showMessage(message, 8000)

    def switch_workspace(self, name):
        if name not in WORKSPACES:
            return False
        doc = App.ActiveDocument
        if Gui.Control.activeDialog() or (doc and doc.HasPendingTransaction):
            self.workspace.blockSignals(True)
            self.workspace.setCurrentText(self._workspace_name)
            self.workspace.blockSignals(False)
            self.notify("Finish or cancel the current operation before switching workspace.")
            return False
        target = {"Design": "FissionWorkbench", "Drawing": "TechDrawWorkbench",
                  "Manufacture": "CAMWorkbench" if "CAMWorkbench" in Gui.listWorkbenches() else "PathWorkbench"}[name]
        if target not in Gui.listWorkbenches():
            self.notify(name + " is unavailable in this installation.")
            return False
        self._workspace_document = doc.Name if doc else None
        if self.active:
            self.deactivate()
        Gui.activateWorkbench(target)
        self.sync_workbench()
        return True

    def save_layout(self):
        if self.active:
            state = bytes(self.main.saveState(1))
            self.settings.SetString("Layout_" + self._workspace_name, base64.b64encode(state).decode("ascii"))
            if self._workspace_name == "Design":
                self.settings.SetString("Layout", base64.b64encode(state).decode("ascii"))
            self.settings.SetString("Geometry", base64.b64encode(bytes(self.main.saveGeometry())).decode("ascii"))
            App.saveParameter()

    def restore_layout(self):
        try:
            geometry = self.settings.GetString("Geometry", "")
            if geometry:
                self.main.restoreGeometry(QtCore.QByteArray(base64.b64decode(geometry)))
            state = self.settings.GetString("Layout_" + self._workspace_name, "")
            if not state and self._workspace_name == "Design":
                state = self.settings.GetString("Layout", "")
            if state:
                self.main.restoreState(QtCore.QByteArray(base64.b64decode(state)), 1)
            else:
                self.main.resizeDocks([self.browser], [255], QtCore.Qt.Horizontal)
                self.main.resizeDocks([self.timeline], [100], QtCore.Qt.Vertical)
                self.main.resizeDocks([self.nav_dock], [44], QtCore.Qt.Vertical)
        except (ValueError, RuntimeError):
            self.reset_layout()

    def shutdown(self):
        if hasattr(self, "move_dialog"):
            self.move_dialog.reject()
        self.timer.stop()
        if hasattr(self, "search_dialog"):
            self.search_dialog.close()
        self.marking.shutdown()
        self.paint.shutdown()
        self.browser.shutdown()
        self.timeline.shutdown()
        self.shortcuts.deactivate()
        App.removeDocumentObserver(self.observer)

    def reset_layout(self):
        self.main.addDockWidget(QtCore.Qt.TopDockWidgetArea, self.ribbon_dock)
        self.main.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.browser)
        self.main.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.nav_dock)
        self.main.splitDockWidget(self.nav_dock, self.timeline, QtCore.Qt.Vertical)
        for widget in (self.ribbon_dock, self.browser, self.nav_dock):
            widget.show()
        self.timeline.setVisible(self._workspace_name == "Design")
        self.settings.SetBool("ShowNavigation", True)
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
        paths = [value for kind, key, value in (recent.GetContents() or []) if key.startswith("MRU")]
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
        self.welcome.destroyed.connect(self.clear_welcome)
        self.welcome.showMaximized()

    def clear_welcome(self, *_args):
        self.welcome = None
