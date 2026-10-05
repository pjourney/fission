# SPDX-License-Identifier: LGPL-2.1-or-later
"""Native Qt acceptance for canvas preferences, called by the serial GUI runner."""

from copy import deepcopy
import importlib
import json
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

try:
    from PySide import QtTest
except ImportError:
    try:
        QtTest = importlib.import_module("PySide6.QtTest")
    except ImportError:
        QtTest = importlib.import_module("PySide2.QtTest")

from cad_workflows import require


def settings(controller, settle, output):
    """Exercise actual preference controls without creating or editing CAD objects.

    ``settle(milliseconds)`` belongs to the native serial GUI harness. All OK,
    Cancel, checkbox, reset, and text-entry actions use real Qt input events.
    The caller must use an isolated test profile. Settings are restored even
    when an assertion fails so this case does not affect subsequent CAD cases.
    """
    from fission import marking
    from fission.preferences import PreferencesDialog

    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    application = QtWidgets.QApplication.instance()
    require(controller.active, "Canvas settings require the active Fission shell")
    controller.marking.close()
    require(application.activeModalWidget() is None,
            "Finish the existing modal operation before testing preferences")
    view_parameters = App.ParamGet("User parameter:BaseApp/Preferences/View")
    invert_entries = [entry for entry in view_parameters.GetContents()
                      if entry[0] == "Boolean" and entry[1] == "InvertZoom"]
    original_invert = invert_entries[0][2] if invert_entries else None
    original_marking = controller.settings.GetString("MarkingMenu", "")
    marking_existed = any(entry[1] == "MarkingMenu" for entry in controller.settings.GetContents())
    original_config = marking.read_config(controller.settings)
    documents_before = {name: tuple(obj.Name for obj in document.Objects)
                        for name, document in App.listDocuments().items()}
    transactions_before = {name: document.HasPendingTransaction
                           for name, document in App.listDocuments().items()}
    selection_before = [(item.Object.Document.Name, item.Object.Name, tuple(item.SubElementNames))
                        for item in Gui.Selection.getSelectionEx()]
    active_before = App.ActiveDocument.Name if App.ActiveDocument else None
    workbench_before = Gui.activeWorkbench().name()
    dialogs = []
    unavailable = "FutureAddon_UnavailableCanvasPreferenceTool"
    require(Gui.Command.get(unavailable) is None,
            "The unavailable assignment fixture must genuinely be unregistered")
    evidence = {"contexts": list(marking.CONTEXTS), "directions": list(marking.DIRECTIONS)}

    def widget(dialog, kind, name):
        matches = [child for child in dialog.findChildren(kind) if child.objectName() == name]
        require(len(matches) == 1, "Expected one preferences control: " + name)
        return matches[0]

    def tab(dialog, title):
        tabs = widget(dialog, QtWidgets.QTabWidget, "FissionPreferencesTabs")
        indices = [index for index in range(tabs.count()) if tabs.tabText(index) == title]
        require(len(indices) == 1, "Expected one preferences tab: " + title)
        QtTest.QTest.mouseClick(tabs.tabBar(), QtCore.Qt.LeftButton,
                               QtCore.Qt.NoModifier, tabs.tabBar().tabRect(indices[0]).center())
        settle(60)
        require(tabs.currentIndex() == indices[0], "Preferences tab click must select " + title)

    def open_dialog(title="Marking Menu"):
        dialog = PreferencesDialog(controller, controller.main)
        dialogs.append(dialog)
        dialog.open()
        settle(120)
        require(dialog.isVisible() and application.activeModalWidget() is dialog,
                "Preferences must expose its actual modal Qt dialog")
        tab(dialog, title)
        return dialog

    def finish(dialog, accept):
        boxes = dialog.findChildren(QtWidgets.QDialogButtonBox)
        require(len(boxes) == 1, "Preferences must expose one native dialog button box")
        button = boxes[0].button(QtWidgets.QDialogButtonBox.Ok if accept
                                 else QtWidgets.QDialogButtonBox.Cancel)
        require(button is not None and button.isVisible() and button.isEnabled(),
                "Preferences OK/Cancel button must be usable")
        QtTest.QTest.mouseClick(button, QtCore.Qt.LeftButton)
        settle(150)
        require(not dialog.isVisible() and dialog.result() == (
                QtWidgets.QDialog.Accepted if accept else QtWidgets.QDialog.Rejected),
                "The actual preferences button must finish the dialog")
        require(application.activeModalWidget() is None,
                "Preferences completion must release modal input")

    def context(dialog, name):
        combo = widget(dialog, QtWidgets.QComboBox, "FissionMarkingContext")
        index = combo.findData(name)
        require(index >= 0, "Marking preferences must expose context " + name)
        # Native combo arrow keys commit each choice directly. Popup geometry
        # can be stale during repeated context rebuilds and screen-edge fitting.
        combo.hidePopup()
        combo.setFocus(QtCore.Qt.OtherFocusReason)
        settle(40)
        QtTest.QTest.keyClick(combo, QtCore.Qt.Key_Home)
        settle(40)
        for _ in range(index):
            QtTest.QTest.keyClick(combo, QtCore.Qt.Key_Down)
            settle(40)
        actual = {"requested": name, "expected_index": index,
                  "actual_index": combo.currentIndex(), "actual_data": combo.currentData(),
                  "actual_text": combo.currentText(), "focused": combo.hasFocus(),
                  "dialog_visible": dialog.isVisible()}
        require(combo.currentData() == name,
                "Native context keyboard choice must select the requested context: " + str(actual))

    def slot(dialog, direction):
        return widget(dialog, QtWidgets.QComboBox, "FissionMarkingSlot" + direction)

    def enter(dialog, direction, command):
        combo = slot(dialog, direction)
        require(combo.isEditable() and combo.isVisible(),
                "Marking slots must accept searchable command text")
        editor = combo.lineEdit()
        QtTest.QTest.mouseClick(editor, QtCore.Qt.LeftButton)
        QtTest.QTest.keyClick(editor, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
        QtTest.QTest.keyClick(editor, QtCore.Qt.Key_Backspace)
        if command:
            QtTest.QTest.keyClicks(editor, command)
        combo.completer().popup().hide()
        settle(40)
        require(combo.currentText() == command, "Typed command IDs must remain intact")

    def enabled(dialog, value):
        checkbox = widget(dialog, QtWidgets.QCheckBox, "FissionMarkingEnabled")
        if checkbox.isChecked() != value:
            QtTest.QTest.mouseClick(checkbox, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier,
                                   QtCore.QPoint(8, checkbox.height() // 2))
            settle(40)
        require(checkbox.isChecked() == value, "Enable marking menu must follow the checkbox")

    def assert_slots(dialog, expected):
        for name in marking.CONTEXTS:
            context(dialog, name)
            actual = [slot(dialog, direction).currentData() for direction in marking.DIRECTIONS]
            require(actual == expected["slots"][name],
                    "Fresh preferences must retain all eight slots for " + name)

    def configure_custom(dialog):
        enabled(dialog, False)
        context(dialog, "model")
        enter(dialog, "N", "Fission_Fit")
        enter(dialog, "NE", "")
        enter(dialog, "E", unavailable)
        context(dialog, "sketch")
        enter(dialog, "N", "Sketcher_CreateCircle")
        context(dialog, "surface")
        require(slot(dialog, "W").findData("Fission_Move") >= 0,
                "Surface preferences must retain useful commands despite model catalog metadata")
        enter(dialog, "W", "Fission_Move")
        context(dialog, "model")
        require([slot(dialog, direction).currentData() for direction in ("N", "NE", "E")]
                == ["Fission_Fit", "", unavailable],
                "Switching contexts must retain custom, Empty, and unavailable staged slots")

    def reset(dialog, all_contexts):
        name = "FissionMarkingResetAll" if all_contexts else "FissionMarkingResetContext"
        button = widget(dialog, QtWidgets.QPushButton, name)
        require(button.isVisible() and button.isEnabled(), "Marking reset must be usable")
        QtTest.QTest.mouseClick(button, QtCore.Qt.LeftButton)
        settle(80)

    try:
        # Exercise the real native fallback, rather than first setting the key.
        view_parameters.RemBool("InvertZoom")
        settle(70)
        require(not any(entry[1] == "InvertZoom" and entry[0] == "Boolean"
                        for entry in view_parameters.GetContents()),
                "Untouched preference acceptance must exercise an unset native wheel preference")
        dialog = open_dialog("Navigation")
        require(dialog.reverse.isChecked(), "The preferences checkbox must match native default InvertZoom=true")
        finish(dialog, True)
        require(view_parameters.GetBool("InvertZoom", False),
                "Untouched Preferences OK must preserve native wheel reversal")
        require(marking.read_config(controller.settings) == original_config,
                "Untouched Preferences OK must preserve marking assignments")
        evidence["untouched_native_wheel_default_preserved"] = True

        baseline = marking.read_config(controller.settings)
        baseline_raw = controller.settings.GetString("MarkingMenu", "")
        dialog = open_dialog()
        configure_custom(dialog)
        require(controller.settings.GetString("MarkingMenu", "") == baseline_raw,
                "Editing marking preferences must not write through before OK")
        finish(dialog, False)
        require(controller.settings.GetString("MarkingMenu", "") == baseline_raw
                and marking.read_config(controller.settings) == baseline
                and controller.marking.config == baseline,
                "Cancel must discard staged edits without changing the active marking menu")
        evidence["cancel_discarded_staged_edits"] = True

        expected = deepcopy(baseline)
        expected["enabled"] = False
        expected["slots"]["model"][0:3] = ["Fission_Fit", "", unavailable]
        expected["slots"]["sketch"][0] = "Sketcher_CreateCircle"
        expected["slots"]["surface"][marking.DIRECTIONS.index("W")] = "Fission_Move"
        dialog = open_dialog()
        configure_custom(dialog)
        finish(dialog, True)
        require(marking.read_config(controller.settings) == expected
                and controller.marking.config == expected,
                "OK must persist the custom slots and refresh the actual marking service")
        require(not controller.marking.available(), "Disabling the marking menu must take effect immediately")
        evidence["persisted_custom_slots"] = deepcopy(expected)

        dialog = open_dialog()
        require(not widget(dialog, QtWidgets.QCheckBox, "FissionMarkingEnabled").isChecked(),
                "A fresh preferences dialog must retain the disabled menu")
        assert_slots(dialog, expected)
        context(dialog, "model")
        require("Unavailable" in slot(dialog, "E").currentText(),
                "The fresh dialog must identify unavailable commands while retaining their IDs")
        require(slot(dialog, "NE").currentText() == "Empty",
                "The fresh dialog must retain an intentionally empty slot")
        capture = output / "fission-marking-preferences.png"
        require(dialog.grab().save(str(capture)), "Marking preferences must produce a real Qt screenshot")
        evidence["fresh_dialog_retained_custom_empty_unavailable"] = True
        evidence["screenshot"] = str(capture)

        context_reset = deepcopy(expected)
        context_reset["slots"]["model"] = list(marking.defaults("model"))
        reset(dialog, False)
        assert_slots(dialog, context_reset)
        require(not widget(dialog, QtWidgets.QCheckBox, "FissionMarkingEnabled").isChecked(),
                "Reset Context must preserve the enable preference")
        require(marking.read_config(controller.settings) == expected,
                "Reset Context must stay staged until OK")
        finish(dialog, True)
        require(marking.read_config(controller.settings) == context_reset,
                "Reset Context OK must reset only the selected context")
        evidence["reset_context_preserved_other_contexts_and_enable"] = True

        factory = {"version": 1, "enabled": True,
                   "slots": {name: list(marking.defaults(name)) for name in marking.CONTEXTS}}
        dialog = open_dialog()
        reset(dialog, True)
        assert_slots(dialog, factory)
        require(widget(dialog, QtWidgets.QCheckBox, "FissionMarkingEnabled").isChecked(),
                "Reset All must restore the factory enable preference")
        finish(dialog, False)
        require(marking.read_config(controller.settings) == context_reset
                and controller.marking.config == context_reset,
                "Cancel after Reset All must preserve the previous active configuration")
        evidence["cancel_discarded_reset_all"] = True

        dialog = open_dialog()
        reset(dialog, True)
        finish(dialog, True)
        require(marking.read_config(controller.settings) == factory and controller.marking.config == factory,
                "Reset All OK must persist all factory choices and refresh the marking service")
        evidence["reset_all_persisted"] = True

        require({name: tuple(obj.Name for obj in document.Objects)
                 for name, document in App.listDocuments().items()} == documents_before,
                "Canvas preferences must not create or delete native CAD objects")
        require({name: document.HasPendingTransaction for name, document in App.listDocuments().items()}
                == transactions_before, "Canvas preferences must not disturb modeling transactions")
        require([(item.Object.Document.Name, item.Object.Name, tuple(item.SubElementNames))
                 for item in Gui.Selection.getSelectionEx()] == selection_before,
                "Canvas preferences must preserve native subelement selection")
        require((App.ActiveDocument.Name if App.ActiveDocument else None) == active_before
                and Gui.activeWorkbench().name() == workbench_before,
                "Choosing menu contexts must not switch the active CAD document or native workbench")
        evidence["native_document_selection_and_transactions_preserved"] = True
        report = output / "canvas-settings-report.json"
        evidence["report"] = str(report)
        report.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        return evidence
    finally:
        for dialog in dialogs:
            if dialog.isVisible():
                dialog.reject()
            dialog.deleteLater()
        if marking_existed:
            controller.settings.SetString("MarkingMenu", original_marking)
        else:
            controller.settings.RemString("MarkingMenu")
        if original_invert is None:
            view_parameters.RemBool("InvertZoom")
        else:
            view_parameters.SetBool("InvertZoom", original_invert)
        controller.marking.refresh_settings()
        App.saveParameter()
        controller.refresh_context()
        settle(80)
