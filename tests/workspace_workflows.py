# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real TechDraw and CAM workflows inside the cohesive Fission shell.

Called only by an isolated native GUI process. Commands are clicked on the
actual ribbon, native task controls commit their own CAD changes, and exports
use the same native TechDraw printer APIs as its menu commands.
"""

import importlib
import math
import os
from pathlib import Path
import time
import xml.etree.ElementTree as ET

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

try:
    from PySide import QtTest
except ImportError:
    QtTest = importlib.import_module("PySide6.QtTest")

import cad_workflows as cad


def _trace(message):
    directory = Path(os.environ.get("FISSION_TEST_OUTPUT", "test-output"))
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "workspace-progress.log").open("a", encoding="utf-8") as stream:
        stream.write("{:.3f} {}\n".format(time.monotonic(), message))


def _shell(controller, workspace, doc=None):
    native = Gui.activeWorkbench().name()
    expected = {"Design": ("FissionWorkbench",),
                "Drawing": ("TechDrawWorkbench",),
                "Manufacture": ("CAMWorkbench", "PathWorkbench")}[workspace]
    cad.require(native in expected, "{} must keep its native workbench: {}".format(workspace, native))
    cad.require(controller.active, workspace + " must retain the active Fission controller")
    for widget, label in ((controller.ribbon_dock, "ribbon"), (controller.browser, "Browser"),
                          (controller.workspace, "workspace selector")):
        cad.require(widget.isVisible(), workspace + " must retain its visible Fission " + label)
    cad.require(controller.workspace.currentText() == workspace, "Workspace selector must follow the active native workspace")
    cad.require(controller.timeline.isVisible() == (workspace == "Design"),
                "Timeline visibility must follow the selected workspace")
    if controller.nav_dock.isVisible():
        cad.require(controller.nav_dock.height() <= 50,
                    "Navigation controls must remain a compact bar in every workspace")
    context = {"Design": "model", "Drawing": "drawing", "Manufacture": "cam"}[workspace]
    cad.require(controller.context() == context, "Shortcut context must follow " + workspace)
    if doc:
        cad.require(App.ActiveDocument and App.ActiveDocument.Name == doc.Name,
                    workspace + " must retain the intended active CAD document")
        cad.require(Gui.activeDocument() and Gui.activeDocument().Document.Name == doc.Name,
                    workspace + " must retain the intended GUI document")
    return {"native_workbench": native, "context": controller.context(),
            "workspace": controller.workspace.currentText(),
            "browser_visible": controller.browser.isVisible(),
            "timeline_visible": controller.timeline.isVisible(),
            "navigation_height": controller.nav_dock.height() if controller.nav_dock.isVisible() else 0}


def _switch(controller, workspace, settle, doc=None):
    _trace("switch to " + workspace)
    controller.workspace.setCurrentText(workspace)
    settle(350)
    if workspace == "Design":
        # These fixtures exercise modeling commands. Design may legitimately
        # remember a specialist tab, so explicitly select the real SOLID tab.
        indices = [index for index in range(controller.tabs.count()) if controller.tabs.tabText(index) == "SOLID"]
        cad.require(len(indices) == 1, "Design must expose its native SOLID tools")
        controller.tabs.setCurrentIndex(indices[0])
    controller.refresh_context()
    settle(100)
    state = _shell(controller, workspace, doc)
    _trace("switch complete " + str(state))
    return state


def _click(controller, command, settle):
    _trace("click " + command)
    from fission.shell import TABS, command_spec
    # Specialist workspaces expose separate setup/modeling ribbon tabs. Select
    # the real tab containing this tool before looking for its visible button.
    for index in range(controller.tabs.count()):
        key = controller.tabs.tabText(index)
        if key in TABS and any(command_spec(item)[0] == command
                               for _, items in TABS[key] for item in items):
            if controller.tabs.currentIndex() != index:
                QtTest.QTest.mouseClick(controller.tabs, QtCore.Qt.LeftButton,
                                       QtCore.Qt.NoModifier, controller.tabs.tabRect(index).center())
                settle(180)
            break
    controller.refresh_context()
    settle(70)
    buttons = []
    for button in controller.main.findChildren(QtWidgets.QToolButton):
        if button.property("fissionCommand") == command and button.isVisible() and button.isEnabled():
            buttons.append(button)
    cad.require(len(buttons) == 1, "Expected one enabled visible ribbon button {}: {}".format(command, len(buttons)))
    QtTest.QTest.mouseClick(buttons[0], QtCore.Qt.LeftButton)
    settle(220)
    _trace("click completed " + command)


def _task(doc):
    dialog = Gui.Control.activeTaskDialog(Gui.getDocument(doc.Name))
    cad.require(dialog is not None, "Native operation must expose its document-owned task dialog")
    other = [name for name in App.listDocuments() if name != doc.Name
             and Gui.Control.activeTaskDialog(Gui.getDocument(name)) is not None]
    cad.require(not other, "Native task must belong only to its own document: " + str(other))
    return dialog


def _widget(dialog, name):
    matches = []
    for content in dialog.getDialogContent():
        if content.objectName() == name:
            matches.append(content)
        matches.extend(content.findChildren(QtWidgets.QWidget, name))
    usable = [widget for widget in matches if widget.isVisible() and widget.isEnabled()]
    cad.require(len(usable) == 1, "Expected one visible native task control {}: {}".format(name, len(usable)))
    return usable[0]


def _accept(doc, dialog, settle):
    dialog.accept()
    settle(250)
    cad.require(Gui.Control.activeTaskDialog(Gui.getDocument(doc.Name)) is None,
                "Native OK must close its task dialog")
    cad.require(Gui.getDocument(doc.Name).getInEdit() is None, "Native OK must leave edit mode")
    cad.require(not doc.HasPendingTransaction, "Native OK must resolve its transaction")
    doc.recompute()


def _key(controller, key, modifiers, settle):
    controller.main.activateWindow()
    controller.browser.tree.setFocus(QtCore.Qt.OtherFocusReason)
    settle(60)
    cad.require(QtWidgets.QApplication.focusWidget() is controller.browser.tree,
                "Browser must own actual keyboard focus for the workspace shortcut")
    QtTest.QTest.keyClick(controller.browser.tree, key, modifiers)
    settle(260)


def _task_blocks_workspace(controller, doc, workspace, settle):
    native = Gui.activeWorkbench().name()
    _key(controller, QtCore.Qt.Key_BracketRight, QtCore.Qt.ControlModifier, settle)
    cad.require(Gui.activeWorkbench().name() == native and controller.workspace.currentText() == workspace,
                "Workspace cycling must be blocked while a native task owns its operation")
    _task(doc)
    _shell(controller, workspace, doc)


def _fixture(name):
    doc = App.newDocument(name)
    body = doc.addObject("PartDesign::Body", "Body")
    block = body.newObject("PartDesign::AdditiveBox", "Block")
    block.Length = 30
    block.Width = 20
    block.Height = 8
    body.Tip = block
    doc.recompute()
    block.Visibility = True
    cad.require(body.Shape.isValid() and len(body.Shape.Solids) == 1, "Fixture must be a valid native solid")
    Gui.activeDocument().activeView().viewAxonometric()
    Gui.activeDocument().activeView().fitAll()
    return doc, body, block


def _capture_native_view(controller, doc, output, settle):
    """Include the native OpenGL render omitted by QWidget.grab on Windows."""
    view = Gui.getDocument(doc.Name).activeView()
    camera = view.getCameraNode()
    span = max(doc.Body.Shape.BoundBox.DiagonalLength, 1.0)
    direction = view.getCameraOrientation().multVec(App.Vector(0, 0, 1))
    position = App.Vector(*camera.position.getValue().getValue())
    focal = position - direction * float(camera.focalDistance.getValue())
    eye = focal + direction * (span * 2)
    camera.position = (eye.x, eye.y, eye.z)
    camera.focalDistance = span * 2
    camera.nearDistance = span * 0.01
    camera.farDistance = span * 4
    view.redraw()
    controller.main.statusBar().clearMessage()
    settle(150)
    viewport = view.graphicsView().viewport()
    canvas = output.with_name(output.stem + "-canvas.png")
    view.saveImage(str(canvas), viewport.width(), viewport.height(), "Current")
    cad.require(canvas.is_file() and canvas.stat().st_size > 15000,
                "Native CAD preview must render its actual geometry")
    capture = controller.main.grab()
    painter = QtGui.QPainter(capture)
    painter.drawImage(QtCore.QRect(viewport.mapTo(controller.main, QtCore.QPoint(0, 0)), viewport.size()),
                      QtGui.QImage(str(canvas)))
    painter.end()
    cad.require(not capture.isNull() and capture.save(str(output)), "Native workspace screenshot must save")


def _cleanup(controller, doc, previous, settle):
    _trace("cleanup " + (doc.Name if doc else "none"))
    if doc and doc.Name in App.listDocuments():
        try:
            dialog = Gui.Control.activeTaskDialog(Gui.getDocument(doc.Name))
            if dialog:
                dialog.reject()
                settle(80)
        finally:
            Gui.getDocument(doc.Name).resetEdit()
            Gui.Control.closeDialog()
            App.closeDocument(doc.Name)
            _trace("test document closed")
    if previous and previous in App.listDocuments():
        App.setActiveDocument(previous)
        Gui.activeDocument().activeView().viewAxonometric()
    controller.workspace.setCurrentText("Design")
    if Gui.activeWorkbench().name() != "FissionWorkbench":
        Gui.activateWorkbench("FissionWorkbench")
    settle(250)
    Gui.Selection.clearSelection()
    _trace("cleanup complete")


def drawing(controller, settle, output):
    """Click native page/projection commands, accept views and export real files."""
    previous = App.ActiveDocument.Name if App.ActiveDocument else None
    doc = None
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    try:
        doc, body, block = _fixture("FissionDrawingWorkflow")
        state = _switch(controller, "Drawing", settle, doc)
        _click(controller, "TechDraw_PageDefault", settle)
        pages = [obj for obj in doc.Objects if obj.isDerivedFrom("TechDraw::DrawPage")]
        cad.require(len(pages) == 1, "Page ribbon command must create a real native drawing page")
        page = pages[0]
        cad.require(page.Template and Path(page.Template.Template).is_file(), "Drawing page must use an installed SVG template")
        _shell(controller, "Drawing", doc)
        native_views = Gui.getDocument(doc.Name).mdiViewsOfType("Gui::View3DInventor")
        cad.require(native_views, "Drawing source must retain its actual native 3D view")
        native_views[0].viewFront()
        native_views[0].redraw()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(body)
        _click(controller, "TechDraw_ProjectionGroup", settle)
        dialog = _task(doc)
        _shell(controller, "Drawing", doc)
        _task_blocks_workspace(controller, doc, "Drawing", settle)
        groups = [obj for obj in doc.Objects if obj.isDerivedFrom("TechDraw::DrawProjGroup")]
        cad.require(len(groups) == 1 and body in groups[0].Source, "Native projection must reference the original parametric solid")
        group = groups[0]
        convention = _widget(dialog, "projection")
        convention.setCurrentIndex(1)  # Actual native Third angle task control.
        settle(120)
        # A sheet becomes the active MDI view, so the native camera default can
        # still be isometric. Choose the task's real standard Front direction.
        QtTest.QTest.mouseClick(_widget(dialog, "butFront"), QtCore.Qt.LeftButton)
        settle(120)
        checked = []
        for name in ("chkView1", "chkView5"):
            checkbox = _widget(dialog, name)
            if not checkbox.isChecked():
                QtTest.QTest.mouseClick(checkbox, QtCore.Qt.LeftButton)
                settle(130)
            cad.require(checkbox.isChecked(), "Native projection checkbox must be selected: " + name)
            checked.append(checkbox.toolTip())
        _accept(doc, dialog, settle)
        views = [obj for obj in doc.Objects if obj.isDerivedFrom("TechDraw::DrawProjGroupItem")]
        cad.require(len(views) >= 3, "Native projection task must create front and two orthographic views")
        edges = {view.Name: len(view.getVisibleEdges()) for view in views}
        cad.require(all(count >= 4 for count in edges.values()), "Every projection must contain generated CAD edges")
        standard = {name: group.getItemByLabel(name) for name in ("Front", "Top", "Right")}
        cad.require(all(standard.values()), "Native task must create Front, Top and Right orthographic views")
        directions = {name: view.Direction for name, view in standard.items()}
        cad.require((directions["Front"] - App.Vector(0, -1, 0)).Length < 1e-7,
                    "Native Front button must create the standard front projection")
        for first, second in (("Front", "Top"), ("Front", "Right"), ("Top", "Right")):
            cad.require(abs(directions[first].dot(directions[second])) < 1e-7,
                        "Standard drawing projection directions must be mutually orthogonal")
        _shell(controller, "Drawing", doc)
        Gui.Selection.clearSelection()
        page.ViewObject.show()
        settle(200)
        import TechDrawGui
        svg = output / "fission-native-drawing.svg"
        pdf = output / "fission-native-drawing.pdf"
        TechDrawGui.exportPageAsSvg(page, str(svg))
        TechDrawGui.exportPageAsPdf(page, str(pdf))
        cad.require(svg.is_file() and svg.stat().st_size > 1000, "Native SVG printer must create a drawing")
        xml = ET.parse(svg).getroot()
        cad.require(xml.tag.endswith("svg"), "Native SVG export must be valid SVG XML")
        cad.require(any(node.tag.rsplit("}", 1)[-1] in ("path", "polyline", "line") for node in xml.iter()),
                    "Native SVG export must contain drawing geometry")
        cad.require(pdf.is_file() and pdf.stat().st_size > 1000 and pdf.read_bytes().startswith(b"%PDF-"),
                    "Native PDF printer must create a real PDF")
        saved = output / "fission-drawing-workflow.FCStd"
        doc.saveAs(str(saved))
        capture = output / "fission-drawing-workspace.png"
        cad.require(controller.main.grab().save(str(capture)), "Native Drawing workspace screenshot must save")
        _shell(controller, "Drawing", doc)
        return {**state, "page": page.Name, "template": page.Template.Template,
                "projection": group.Name, "additional_views": checked, "projection_edges": edges,
                "projection_directions": {name: list(vector) for name, vector in directions.items()},
                "svg": str(svg), "svg_bytes": svg.stat().st_size,
                "pdf": str(pdf), "pdf_bytes": pdf.stat().st_size, "saved": str(saved), "screenshot": str(capture)}
    except Exception as error:
        _trace("Drawing failed before cleanup: " + repr(error))
        raise
    finally:
        _cleanup(controller, doc, previous, settle)


def _create_job(controller, body, settle):
    """Accept the actual modal Job creation UI while its native command executes."""
    result = {"accepted": False, "errors": []}
    started = time.monotonic()
    timer = QtCore.QTimer(controller.main)
    timer.setInterval(80)

    def finish_modal():
        modal = QtWidgets.QApplication.activeModalWidget()
        if modal is None:
            return
        tree = modal.findChild(QtWidgets.QTreeView, "modelTree")
        if tree is None:
            if time.monotonic() - started > 4:
                result["errors"].append("Unexpected modal dialog: " + modal.windowTitle())
                modal.reject()
            return
        try:
            model = tree.model()
            selected = []
            for row in range(model.rowCount()):
                group = model.item(row, 0)
                for child in range(group.rowCount()):
                    item = group.child(child, 0)
                    if item.checkState() == QtCore.Qt.Checked:
                        selected.append(item.text())
            cad.require(body.Label in selected, "Job dialog must preselect the actual selected body: " + str(selected))
            box = modal.findChild(QtWidgets.QDialogButtonBox, "buttonBox")
            button = box.button(QtWidgets.QDialogButtonBox.Ok)
            cad.require(button.isEnabled(), "Native Job OK must be available")
            result["selected_models"] = selected
            result["accepted"] = True
            timer.stop()
            QtTest.QTest.mouseClick(button, QtCore.Qt.LeftButton)
        except Exception as error:
            result["errors"].append(str(error))
            timer.stop()
            modal.reject()

    timer.timeout.connect(finish_modal)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(body)
    timer.start()
    try:
        _click(controller, "CAM_Job", settle)
    finally:
        timer.stop()
        timer.deleteLater()
    cad.require(result["accepted"] and not result["errors"], "Native Job dialog must complete: " + str(result))
    return result


def manufacture(controller, settle, output):
    """Create a native CAM job/profile through its editors and inspect motion."""
    previous = App.ActiveDocument.Name if App.ActiveDocument else None
    doc = None
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    try:
        doc, body, block = _fixture("FissionManufactureWorkflow")
        state = _switch(controller, "Manufacture", settle, doc)
        modal = _create_job(controller, body, settle)
        jobs = [obj for obj in doc.Objects if obj.Name.startswith("Job") and hasattr(obj, "Operations")]
        cad.require(len(jobs) == 1, "Job ribbon command must create one actual native CAM job")
        job = jobs[0]
        cad.require(job.Model.Group and job.Stock and job.Stock.Shape.isValid(), "CAM Job must own a real model and stock")
        cad.require(job.Tools.Group and job.Tools.Group[0].Tool, "Native Job must initialize its actual tool controller")
        _shell(controller, "Manufacture", doc)
        _accept(doc, _task(doc), settle)
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(job)
        _click(controller, "CAM_Profile", settle)
        dialog = _task(doc)
        _shell(controller, "Manufacture", doc)
        _task_blocks_workspace(controller, doc, "Manufacture", settle)
        operations = list(job.Operations.Group)
        cad.require(len(operations) == 1, "Profile ribbon command must add a real native operation to its Job")
        operation = operations[0]
        offset = _widget(dialog, "extraOffset")
        cad.require(offset.setProperty("rawValue", 1.0), "Native Profile offset control must accept 1 mm")
        # CAM binds quantity updates to editingFinished, whereas PartDesign
        # uses valueChanged. Emit the real control signal before native OK.
        offset.editingFinished.emit()
        settle(120)
        _accept(doc, dialog, settle)
        cad.require(abs(operation.OffsetExtra.Value - 1.0) < 1e-8, "Native Profile OK must commit its actual editor value")
        commands = list(operation.Path.Commands)
        motion = [command for command in commands if command.Name in ("G0", "G00", "G1", "G01", "G2", "G02", "G3", "G03")]
        cutting = [command for command in motion if command.Name in ("G1", "G01", "G2", "G02", "G3", "G03")]
        cad.require(len(cutting) >= 8, "CAM Profile must generate actual cutting motion")
        coordinates = [float(value) for command in motion for key, value in command.Parameters.items() if key in ("X", "Y", "Z")]
        cad.require(coordinates and all(math.isfinite(value) for value in coordinates), "Generated toolpath coordinates must be finite")
        cad.require(operation.ViewObject.Visibility, "Native generated toolpath must remain visible for preview")
        cad.require(operation.ToolController in job.Tools.Group, "Profile must retain the Job's native tool controller")
        _shell(controller, "Manufacture", doc)
        Gui.Selection.clearSelection()
        Gui.activeDocument().activeView().viewAxonometric()
        Gui.activeDocument().activeView().fitAll()
        settle(200)
        preview = output / "fission-native-cam-preview.png"
        _capture_native_view(controller, doc, preview, settle)
        path_file = output / "fission-native-profile-path.txt"
        path_file.write_text(operation.Path.toGCode(), encoding="utf-8")
        saved = output / "fission-manufacture-workflow.FCStd"
        doc.saveAs(str(saved))
        return {**state, "job": job.Name, "selected_models": modal["selected_models"],
                "stock_volume": job.Stock.Shape.Volume, "operation": operation.Name,
                "tool_controller": operation.ToolController.Name, "extra_offset_mm": operation.OffsetExtra.Value,
                "commands": len(commands), "motion_commands": len(motion), "cutting_commands": len(cutting),
                "preview": str(preview), "internal_path_preview": str(path_file), "saved": str(saved)}
    except Exception as error:
        _trace("Manufacture failed before cleanup: " + repr(error))
        raise
    finally:
        _cleanup(controller, doc, previous, settle)


def specialist(controller, settle, output, workspace):
    """Combine live ribbon registration with native Surface/Mesh geometry checks."""
    import specialist_workflows
    previous = App.ActiveDocument.Name if App.ActiveDocument else None
    _switch(controller, "Design", settle)
    tab = "SURFACE" if workspace == "surface" else "MESH"
    indices = [index for index in range(controller.tabs.count()) if controller.tabs.tabText(index) == tab]
    cad.require(len(indices) == 1, "Design must expose its real " + tab + " tab")
    controller.tabs.setCurrentIndex(indices[0])
    settle(150)
    catalog = specialist_workflows.audit_gui_catalog(controller)[tab]
    visible = {button.property("fissionCommand") for button in controller.main.findChildren(QtWidgets.QToolButton)
               if button.isVisible()}
    # Native toolbar QAction instances are created lazily by their own workbench.
    # Fission's actual QToolButtons invoke registered tools directly.
    unavailable = [tool["id"] for tool in catalog if not tool["registered"] or tool["id"] not in visible]
    cad.require(not unavailable, "Specialist ribbon must advertise available native commands: " + str(unavailable))
    try:
        case = specialist_workflows.surface_case if workspace == "surface" else specialist_workflows.mesh_case
        directory = Path(output) / workspace
        directory.mkdir(parents=True, exist_ok=True)
        geometry = case(directory)
        return {"tab": tab, "commands": catalog, "geometry": geometry}
    finally:
        if previous and previous in App.listDocuments():
            App.setActiveDocument(previous)
        controller.tabs.setCurrentIndex(0)
        controller.refresh_context()
        settle(100)


def navigation_controls(controller, settle, output):
    """Send real Qt workspace/cube/bar shortcuts and inspect native viewer state."""
    previous = App.ActiveDocument.Name if App.ActiveDocument else None
    doc = None
    preferences = App.ParamGet("User parameter:BaseApp/Preferences/View")
    initial_cube = preferences.GetBool("ShowNaviCube", True)
    initial_bar = controller.settings.GetBool("ShowNavigation", True)
    sequence = []
    try:
        doc, body, block = _fixture("FissionNavigationControls")
        _switch(controller, "Design", settle, doc)
        viewer = Gui.activeDocument().activeView().getViewer()
        cad.require(viewer.isEnabledNaviCube() == initial_cube, "Native viewer must initially match the cube preference")
        _key(controller, QtCore.Qt.Key_V, QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier, settle)
        cad.require(viewer.isEnabledNaviCube() != initial_cube and preferences.GetBool("ShowNaviCube", True) != initial_cube,
                    "Ctrl+Alt+V must change the actual native orientation cube and stored preference")
        _key(controller, QtCore.Qt.Key_N, QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier, settle)
        cad.require(controller.nav_dock.isVisible() != initial_bar and controller.settings.GetBool("ShowNavigation", True) != initial_bar,
                    "Ctrl+Alt+N must change the actual navigation dock and stored preference")
        for key, expected in ((QtCore.Qt.Key_BracketRight, "Drawing"),
                              (QtCore.Qt.Key_BracketRight, "Manufacture"),
                              (QtCore.Qt.Key_BracketRight, "Design"),
                              (QtCore.Qt.Key_BracketLeft, "Manufacture"),
                              (QtCore.Qt.Key_BracketLeft, "Drawing"),
                              (QtCore.Qt.Key_BracketLeft, "Design")):
            _key(controller, key, QtCore.Qt.ControlModifier, settle)
            if Gui.activeWorkbench().name() == "FissionWorkbench" and expected != "Design":
                App.Console.PrintMessage("WORKSPACE KEY DIAGNOSTICS " + str({
                    "expected": expected, "context": controller.context(), "profile": controller.shortcuts.profile.name,
                    "pending_transaction": doc.HasPendingTransaction, "dialog": repr(Gui.Control.activeDialog()),
                    "status": controller.main.statusBar().currentMessage(),
                    "focus": repr(QtWidgets.QApplication.focusWidget()),
                    "modal": repr(QtWidgets.QApplication.activeModalWidget()),
                    "popup": repr(QtWidgets.QApplication.activePopupWidget())}) + "\n")
            sequence.append(_shell(controller, expected, doc))
            cad.require(controller.nav_dock.isVisible() != initial_bar,
                        "Navigation visibility must survive native workspace changes")
            cad.require(Gui.getDocument(doc.Name).mdiViewsOfType("Gui::View3DInventor")[0].getViewer().isEnabledNaviCube() != initial_cube,
                        "Cube visibility must survive native workspace changes")
        doc.openTransaction("Verify blocked workspace switch")
        try:
            # Native document transactions are allocated lazily when their first
            # change occurs. Hold an actual fixture edit, then abort it below.
            block.Height = 9
            cad.require(doc.HasPendingTransaction, "Guard test must hold a real pending native transaction")
            _key(controller, QtCore.Qt.Key_BracketRight, QtCore.Qt.ControlModifier, settle)
            _shell(controller, "Design", doc)
        finally:
            doc.abortTransaction()
        return {"workspace_sequence": sequence, "actual_qt_keys": ["Ctrl+[", "Ctrl+]", "Ctrl+Alt+V", "Ctrl+Alt+N"],
                "native_cube_changed": True, "navigation_dock_changed": True, "pending_transaction_blocks_switch": True}
    finally:
        preferences.SetBool("ShowNaviCube", initial_cube)
        controller.settings.SetBool("ShowNavigation", initial_bar)
        for name in App.listDocuments():
            for view in Gui.getDocument(name).mdiViewsOfType("Gui::View3DInventor"):
                view.getViewer().setEnabledNaviCube(initial_cube)
        controller.nav_dock.setVisible(initial_bar)
        if doc and doc.Name in App.listDocuments() and doc.HasPendingTransaction:
            doc.abortTransaction()
        _cleanup(controller, doc, previous, settle)
