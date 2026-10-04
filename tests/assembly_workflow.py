# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real native Assembly links, grounding, fixed/revolute joints and solver.

``run(controller, settle, output)`` exercises native commands and task panels.
``run_core(output)`` exercises the same C++ solver without a GUI. API names
come from AssemblyObject.pyi, JointObject.py and the pinned Assembly commands.
Every component is a native parametric solid; joints remain native objects.
"""

import importlib
import json
import math
import os
from pathlib import Path

import FreeCAD as App
import Assembly
import Part
import JointObject
import UtilsAssembly


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def _sources(output, name):
    doc = App.newDocument(name)
    base = doc.addObject("Part::Box", "Base")
    base.Length, base.Width, base.Height = 30.0, 20.0, 4.0
    block = doc.addObject("Part::Box", "Bracket")
    block.Length, block.Width, block.Height = 10.0, 8.0, 6.0
    shaft = doc.addObject("Part::Cylinder", "Shaft")
    shaft.Radius, shaft.Height = 3.0, 8.0
    doc.recompute()
    components = [base, block, shaft]
    for obj, volume in zip(components, (2400.0, 480.0, 72.0 * math.pi)):
        require(obj.Shape.isValid() and len(obj.Shape.Solids) == 1,
                "Assembly source must be a real valid native solid: " + obj.Name)
        require(abs(obj.Shape.Volume - volume) < 1e-6,
                "Native source solid must retain its parametric dimensions: " + obj.Name)
    doc.saveAs(str(output / (name + ".FCStd")))
    return doc, components


def _constraint_state(assembly, links, fixed, revolute, anchor):
    require(assembly.isPartGrounded(links[0]), "Base component must be natively grounded")
    require(links[0].Placement.isSame(anchor, 1e-6), "Solver must preserve the grounded component placement")
    for link in links:
        require(assembly.isPartConnected(link), "Every component must have a real joint path to ground")
        require(link.LinkedObject is not None and link.Shape.isValid() and len(link.Shape.Solids) == 1,
                "Assembly components must remain valid dynamic links to native solids")
        require(abs(link.Shape.Volume - link.LinkedObject.Shape.Volume) < 1e-6,
                "Solving placements must preserve linked source geometry")
    first = UtilsAssembly.getJcsGlobalPlc(fixed.Placement1, fixed.Reference1)
    second = UtilsAssembly.getJcsGlobalPlc(fixed.Placement2, fixed.Reference2)
    require(first.isSame(second, 1e-5), "Native fixed joint must align both complete connector placements")
    first = UtilsAssembly.getJcsGlobalPlc(revolute.Placement1, revolute.Reference1)
    second = UtilsAssembly.getJcsGlobalPlc(revolute.Placement2, revolute.Reference2)
    distance = (first.Base - second.Base).Length
    axis1 = first.Rotation.multVec(App.Vector(0, 0, 1))
    axis2 = second.Rotation.multVec(App.Vector(0, 0, 1))
    cross = axis1.cross(axis2).Length
    require(distance < 1e-5 and cross < 1e-5,
            "Native revolute joint must preserve coincident origins and coaxial rotation axes")
    return {"fixed_connectors_aligned": True, "revolute_origin_error_mm": distance,
            "revolute_axis_error": cross, "ground_unchanged": True,
            "linked_volumes": [float(link.Shape.Volume) for link in links]}


def _disturb(links):
    links[1].Placement = App.Placement(App.Vector(17, -9, 6), App.Rotation(20, 35, 45))
    links[2].Placement = App.Placement(App.Vector(-11, 7, 10), App.Rotation(30, 40, 50))


def _core_joint(group, kind, first, second):
    joint = group.newObject("App::FeaturePython", kind + "Joint")
    JointObject.Joint(joint, JointObject.JointTypes.index(kind))
    joint.Proxy.setJointConnectors(joint, [[first, ["", ""]], [second, ["", ""]]])
    return joint


def run_core(output):
    """Create real links/joints, disturb both movable components, solve them."""
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    previous = App.ActiveDocument.Name if App.ActiveDocument else None
    preferences = App.ParamGet("User parameter:BaseApp/Preferences/Mod/Assembly")
    solve_creation = preferences.GetBool("SolveInJointCreation", True)
    solve_recompute = preferences.GetBool("SolveOnRecompute", True)
    source = doc = None
    try:
        preferences.SetBool("SolveInJointCreation", False)
        preferences.SetBool("SolveOnRecompute", False)
        source, components = _sources(output, "AssemblyCoreSources")
        doc = App.newDocument("AssemblyCore")
        assembly = doc.addObject("Assembly::AssemblyObject", "Assembly")
        assembly.Type = "Assembly"
        group = assembly.newObject("Assembly::JointGroup", "Joints")
        doc.saveAs(str(output / "native-assembly-core.FCStd"))
        links = []
        for obj in components:
            link = assembly.newObject("App::Link", obj.Name + "Link")
            link.setLink(obj)
            links.append(link)
        doc.recompute()
        ground = group.newObject("App::FeaturePython", "GroundedJoint")
        JointObject.GroundedJoint(ground, links[0])
        anchor = App.Placement(links[0].Placement)
        fixed = _core_joint(group, "Fixed", links[0], links[1])
        revolute = _core_joint(group, "Revolute", links[0], links[2])
        _disturb(links)
        disturbed = App.Placement(links[1].Placement)
        status = assembly.solve(False)
        require(status == 0, "Native Assembly solver must succeed; received " + str(status))
        require(not links[1].Placement.isSame(disturbed, 1e-6), "Native solver must correct the disturbed fixed component")
        state = _constraint_state(assembly, links, fixed, revolute, anchor)
        doc.saveAs(str(output / "native-assembly-core.FCStd"))
        return dict(state, solver_status=status, component_count=len(links),
                    joint_types=[fixed.JointType, revolute.JointType],
                    external_links=True, feature_file=str(output / "native-assembly-core.FCStd"))
    finally:
        for native in (doc, source):
            if native is not None and native.Name in App.listDocuments():
                App.closeDocument(native.Name)
        preferences.SetBool("SolveInJointCreation", solve_creation)
        preferences.SetBool("SolveOnRecompute", solve_recompute)
        if previous and previous in App.listDocuments():
            App.setActiveDocument(previous)


def _workspace(controller, doc, assembly):
    import FreeCADGui as Gui
    require(App.ActiveDocument is not None and App.ActiveDocument.Name == doc.Name,
            "Native Assembly workflow must retain its document")
    require(Gui.activeWorkbench().name() == "FissionWorkbench" and controller.active,
            "Native Assembly commands must retain the Fission Design shell")
    view = assembly.ViewObject
    provider_state = {"native_type": view.TypeId, "python_type": type(view).__name__,
                      "has_edit_api": callable(getattr(view, "isInEditMode", None)),
                      "has_object_api": hasattr(view, "Object"), "has_document_api": hasattr(view, "Document")}
    require(view.TypeId == "AssemblyGui::ViewProviderAssembly" and all(provider_state[key]
            for key in ("has_edit_api", "has_object_api", "has_document_api")),
            "New Assembly must retain its actual native provider and Python binding: " + json.dumps(provider_state))
    require(view.Object is assembly and view.Document is Gui.getDocument(doc.Name),
            "Native Assembly Python binding must expose its actual object and GUI document")
    edit = Gui.getDocument(doc.Name).getInEdit()
    require(edit is not None and edit.Object is assembly and UtilsAssembly.activeAssembly() is assembly,
            "Native assembly must own actual document edit mode")


def _tree_items(tree):
    def descendants(item):
        yield item
        for index in range(item.childCount()):
            yield from descendants(item.child(index))
    for index in range(tree.topLevelItemCount()):
        yield from descendants(tree.topLevelItem(index))


def _accept_assembly_task(controller, doc, assembly, dialog, settle):
    import FreeCADGui as Gui
    dialog.accept()
    settle(220)
    require(Gui.Control.activeTaskDialog(Gui.getDocument(doc.Name)) is None,
            "Native Assembly task OK must close its document-owned dialog")
    require(not doc.HasPendingTransaction, "Native Assembly OK must commit its transaction")
    _workspace(controller, doc, assembly)


def run(controller, settle, output):
    """Native New Assembly → Insert links → J Fixed/OK → Revolute/OK → Solve."""
    import FreeCADGui as Gui
    from PySide import QtCore, QtWidgets
    try:
        from PySide import QtTest
    except ImportError:
        try:
            QtTest = importlib.import_module("PySide6.QtTest")
        except ImportError:
            QtTest = importlib.import_module("PySide2.QtTest")
    from fission.shortcuts import DEFAULT_PROFILE
    from interactive_workflow import _press

    require(not Gui.Control.activeDialog(), "Finish the current task before the Assembly workflow")
    previous = App.ActiveDocument.Name if App.ActiveDocument else None
    previous_profile = controller.shortcuts.profile.name
    previous_tab = controller.tabs.currentIndex()
    previous_workspace = controller._workspace_name
    preferences = App.ParamGet("User parameter:BaseApp/Preferences/Mod/Assembly")
    saved_preferences = {"GroundFirstPart": preferences.GetInt("GroundFirstPart", 0),
                         "InsertShowOnlyParts": preferences.GetBool("InsertShowOnlyParts", False),
                         "SolveInJointCreation": preferences.GetBool("SolveInJointCreation", True),
                         "SolveOnRecompute": preferences.GetBool("SolveOnRecompute", True)}
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    source = doc = reopened = None

    class BeforeChangeObserver:
        calls = 0

        def slotBeforeChangeObject(self, view, prop):
            self.calls += 1

    observer = BeforeChangeObserver()
    Gui.addDocumentObserver(observer)
    try:
        preferences.SetInt("GroundFirstPart", 1)  # native preference avoids its first-insertion prompt
        preferences.SetBool("InsertShowOnlyParts", False)
        preferences.SetBool("SolveInJointCreation", True)
        preferences.SetBool("SolveOnRecompute", True)
        controller.shortcuts.apply_profile(DEFAULT_PROFILE)
        source, components = _sources(output, "AssemblyGuiSources")
        doc = App.newDocument("FissionAssembly")
        doc.saveAs(str(output / "native-assembly.FCStd"))  # external links require saved documents
        indices = [index for index in range(controller.tabs.count())
                   if controller.tabs.tabText(index) == "ASSEMBLE"]
        require(len(indices) == 1, "Fission must expose its ASSEMBLE ribbon tab")
        controller.tabs.setCurrentIndex(indices[0])
        controller.refresh_context()
        settle(160)
        required_commands = ["Assembly_CreateAssembly", "Assembly_ActivateAssembly", "Assembly_InsertLink",
                             "Assembly_ToggleGrounded", "Assembly_CreateJointFixed",
                             "Assembly_CreateJointRevolute", "Assembly_SolveAssembly", "Fission_AssemblyJoint"]
        require(all(Gui.Command.get(name) for name in required_commands), "Every exposed native Assembly command must be registered")
        require(controller.execute("Assembly_CreateAssembly"), "New Assembly must execute its actual native command")
        settle(220)
        assemblies = [obj for obj in doc.Objects if obj.isDerivedFrom("Assembly::AssemblyObject")]
        require(len(assemblies) == 1, "New Assembly must create one actual native AssemblyObject")
        assembly = assemblies[0]
        _workspace(controller, doc, assembly)
        require(controller.context() == "assembly", "Actual assembly edit must activate Assembly shortcut context")

        require(controller.execute("Assembly_InsertLink"), "Insert Component must open its actual native task")
        settle(160)
        dialog = Gui.Control.activeTaskDialog(Gui.getDocument(doc.Name))
        require(dialog is not None, "Native insertion dialog must belong to the assembly document")
        trees = [child for content in dialog.getDialogContent()
                 for child in content.findChildren(QtWidgets.QTreeWidget, "partList")]
        require(len(trees) == 1 and trees[0].isVisible(), "Native Insert Component must show its component picker")
        tree = trees[0]
        for component in components:
            matches = [item for item in _tree_items(tree) if item.data(0, QtCore.Qt.UserRole) is component]
            require(len(matches) == 1, "Native component picker must list source " + component.Name)
            item = matches[0]
            parent = item.parent()
            while parent is not None:
                parent.setExpanded(True)
                parent = parent.parent()
            tree.scrollToItem(item)
            settle(45)
            point = tree.visualItemRect(item).center()
            require(tree.itemAt(point) is item, "Native insertion source must occupy its clicked picker row")
            QtTest.QTest.mouseClick(tree.viewport(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, point)
            settle(120)
        _accept_assembly_task(controller, doc, assembly, dialog, settle)
        links = []
        for component in components:
            matches = [obj for obj in assembly.Group if obj.isDerivedFrom("App::Link")
                       and obj.LinkedObject is component]
            require(len(matches) == 1, "Native insertion must create one dynamic link to each external source")
            links.append(matches[0])
            require(matches[0].ViewObject.TypeId == "Gui::ViewProviderLink",
                    "Inserted App::Link must retain its native C++ link view provider")
        require(UtilsAssembly.number_of_components_in(assembly) == 3, "Native assembly must contain three linked components")
        require(assembly.isPartGrounded(links[0]), "Native insertion must ground its first component")
        anchor = App.Placement(links[0].Placement)

        def joint_command(first, second, kind):
            Gui.Selection.clearSelection()
            for link in (first, second):
                Gui.Selection.addSelection(doc.Name, assembly.Name, link.Name + ".")
            settle(80)
            if kind == "Fixed":
                buttons = [button for button in controller.buttons
                           if button.property("fissionCommand") == "Fission_AssemblyJoint"
                           and button.isVisible() and button.isEnabled()]
                require(len(buttons) == 1 and Gui.Command.get("Fission_AssemblyJoint").isActive(),
                        "Actual Fission Joint ribbon button must be enabled in native assembly edit mode")
                _press(controller, QtCore.Qt.Key_J, settle)
            else:
                require(controller.execute("Assembly_CreateJointRevolute"), "Revolute must execute its actual native command")
                settle(160)
            native_dialog = Gui.Control.activeTaskDialog(Gui.getDocument(doc.Name))
            require(native_dialog is not None and JointObject.activeTask is not None,
                    kind + " command must open its actual document-owned joint task")
            task = JointObject.activeTask
            joint = task.joint
            require(len(task.refs) == 2 and joint.JointType == kind,
                    kind + " task must consume both real selected components")
            require({joint.Reference1[0], joint.Reference2[0]} == {first, second},
                    kind + " task must reference the actual inserted links")
            _workspace(controller, doc, assembly)
            _accept_assembly_task(controller, doc, assembly, native_dialog, settle)
            return joint

        fixed = joint_command(links[0], links[1], "Fixed")
        revolute = joint_command(links[0], links[2], "Revolute")
        _disturb(links)
        disturbed = App.Placement(links[1].Placement)
        require(controller.execute("Assembly_SolveAssembly"), "Solve must execute its actual native command")
        settle(220)
        require(not links[1].Placement.isSame(disturbed, 1e-6), "Native Solve command must correct disturbed fixed geometry")
        require(assembly.solve(False) == 0, "Native Assembly solver must report success after the command")
        state = _constraint_state(assembly, links, fixed, revolute, anchor)
        _workspace(controller, doc, assembly)

        def solver_panels():
            return [widget for widget in controller.main.findChildren(QtWidgets.QWidget)
                    if widget.metaObject().className().endswith("TaskAssemblyMessages") and widget.isVisible()]

        if len(solver_panels()) != 1:
            widgets = [widget for widget in controller.main.findChildren(QtWidgets.QWidget)
                       if "TaskAssembly" in widget.metaObject().className()]
            debug = [{"class": widget.metaObject().className(), "visible": widget.isVisible(), "hidden": widget.isHidden(),
                      "ancestors": [(parent.objectName(), parent.metaObject().className(), parent.isVisible())
                                    for parent in (widget.parentWidget(), widget.parentWidget().parentWidget()) if parent]}
                     for widget in widgets]
            App.Console.PrintMessage("ASSEMBLY PANEL DIAGNOSTICS " + json.dumps(debug) + "\n")
        require(len(solver_panels()) == 1, "Native Assembly edit must show its contextual solver panel")
        require(controller.switch_workspace("Drawing"), "An idle native assembly must allow switching to Drawing")
        settle(200)
        require(Gui.activeWorkbench().name() == "TechDrawWorkbench", "Drawing must activate its native workbench")
        require(Gui.getDocument(doc.Name).getInEdit().Object is assembly,
                "Workspace changes must preserve actual native assembly edit mode")
        require(not solver_panels(), "Assembly solver panel must hide in the Drawing workspace")
        require(controller.switch_workspace("Design"), "Drawing must return to the Fission Design shell")
        settle(200)
        _workspace(controller, doc, assembly)
        require(len(solver_panels()) == 1,
                "Returning to Fission must restore the native Assembly solver panel")

        # Leave a real insertion task owned by the assembly, activate another
        # document, and recreate its contextual panel through native workbench
        # changes. Its stacked task parent must restore the panel on returning.
        Gui.Selection.clearSelection()
        require(controller.execute("Assembly_InsertLink"), "Insertion must reopen its native task")
        settle(160)
        pending = Gui.Control.activeTaskDialog(Gui.getDocument(doc.Name))
        require(pending is not None, "Assembly must own the pending insertion task")
        pending_content = pending.getDialogContent()
        Gui.setActiveDocument(source.Name)
        App.setActiveDocument(source.Name)
        settle(100)
        Gui.activateWorkbench("TechDrawWorkbench")
        settle(180)
        Gui.activateWorkbench("FissionWorkbench")
        settle(180)
        Gui.setActiveDocument(doc.Name)
        App.setActiveDocument(doc.Name)
        settle(180)
        restored_task = Gui.Control.activeTaskDialog(Gui.getDocument(doc.Name))
        # activeTaskDialog creates a new Python wrapper on every call. Compare
        # its actual native task widgets rather than wrapper identity.
        require(restored_task is not None and restored_task.getDialogContent() == pending_content,
                "Inactive assembly must retain its own native insertion task")
        require(len(solver_panels()) == 1,
                "Reactivating an inactive assembly task must show its recreated solver panel")
        pending.reject()
        settle(200)
        require(Gui.Control.activeTaskDialog(Gui.getDocument(doc.Name)) is None,
                "Native insertion Cancel must close its task")
        _workspace(controller, doc, assembly)
        require(len(solver_panels()) == 1,
                "Cancel must preserve the document-owned solver panel")
        require(observer.calls > 0, "The before-change GUI observer must exercise actual native property signals")

        names = [link.Name for link in links]
        joint_names = [fixed.Name, revolute.Name]
        assembly_name = assembly.Name
        path = output / "native-assembly.FCStd"
        doc.save()
        Gui.getDocument(doc.Name).resetEdit()
        App.closeDocument(doc.Name)
        doc = None
        reopened = App.openDocument(str(path))
        settle(160)
        assembly = reopened.getObject(assembly_name)
        links = [reopened.getObject(name) for name in names]
        fixed, revolute = [reopened.getObject(name) for name in joint_names]
        controller.browser.refresh()
        controller.browser._activate(assembly)
        settle(160)
        _workspace(controller, reopened, assembly)
        require(assembly.solve(False) == 0, "Reopened native assembly must still solve")
        restored = _constraint_state(assembly, links, fixed, revolute, anchor)
        return dict(state, restored=restored, source_file=source.FileName, assembly_file=str(path),
                    native_commands=required_commands, keyboard_joint="J", joint_types=[fixed.JointType, revolute.JointType],
                    component_count=3, external_links=True, native_edit=True, browser_reactivation=True,
                    solver_panel_roundtrip=True,
                    inactive_task_panel_restored=True,
                    before_change_observer_calls=observer.calls,
                    assembly_view_provider=assembly.ViewObject.TypeId,
                    component_view_providers=[link.ViewObject.TypeId for link in links],
                    workbench=Gui.activeWorkbench().name())
    finally:
        Gui.removeDocumentObserver(observer)
        for native in (reopened, doc):
            if native is not None and native.Name in App.listDocuments():
                App.setActiveDocument(native.Name)
                gui_doc = Gui.getDocument(native.Name)
                dialog = Gui.Control.activeTaskDialog(gui_doc)
                if dialog is not None:
                    dialog.reject()
                    settle(100)
                if gui_doc.getInEdit():
                    gui_doc.resetEdit()
                if native.HasPendingTransaction:
                    native.abortTransaction()
                App.closeDocument(native.Name)
        if source is not None and source.Name in App.listDocuments():
            App.closeDocument(source.Name)
        for key, value in saved_preferences.items():
            if isinstance(value, bool):
                preferences.SetBool(key, value)
            else:
                preferences.SetInt(key, value)
        if previous and previous in App.listDocuments():
            App.setActiveDocument(previous)
        if controller._workspace_name != previous_workspace:
            controller.switch_workspace(previous_workspace)
            settle(100)
        controller.shortcuts.apply_profile(previous_profile)
        controller.tabs.setCurrentIndex(previous_tab)
        controller.refresh_context()
        controller.browser.refresh()
        controller.timeline.refresh()
        settle(100)


if __name__ == "__main__" or (not App.GuiUp and os.environ.get("FISSION_ASSEMBLY_RUN_CORE") == "1"):
    target = Path(os.environ.get("FISSION_TEST_OUTPUT", "test-output/assembly-core"))
    result = run_core(target)
    (target / "assembly-core-results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("FISSION_ASSEMBLY_CORE_OK")
