"""Pure profile and command-search tests, runnable with ordinary Python."""
import json
import os
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "Mod" / "Fission" / "fission"
# Avoid executing the GUI startup package when testing its pure model.
if "fission" not in sys.modules:
    package = types.ModuleType("fission")
    package.__path__ = [str(PACKAGE)]
    sys.modules["fission"] = package
from fission.shortcuts import (ShortcutProfile, DEFAULT_PROFILE, CLASSIC_PROFILE, CUSTOM_PROFILE,
                              PROFILE_NAMES, PROFILE_SCHEMA_VERSION,
                              normalize_shortcut, contexts_overlap)
from fission.search import rank_commands


class Parameters:
    def __init__(self):
        self.data = {}

    def GetString(self, name, default):
        return self.data.get(name, default)

    def SetString(self, name, value):
        self.data[name] = value


class ShortcutTests(unittest.TestCase):
    def setUp(self):
        self.profile = ShortcutProfile()

    def test_major_fusion_keys(self):
        for key, command in [("E", "Fission_Extrude"), ("F", "Fission_Fillet"),
                             ("H", "Fission_Hole"), ("M", "Fission_Move"),
                             ("I", "Fission_Measure"), ("S", "Fission_Search"),
                             ("V", "Fission_Visibility"), ("Q", "Fission_Extrude"),
                             ("A", "Fission_Appearance"),
                             ("F6", "Fission_Fit"), ("Ctrl+B", "Fission_Compute")]:
            with self.subTest(key=key):
                self.assertEqual(self.profile.resolve(key)["command"], command)

    def test_sketch_context(self):
        expected = {"L":"Sketcher_CreateLine", "R":"Sketcher_CreateRectangle",
                    "C":"Sketcher_CreateCircle", "T":"Sketcher_Trimming",
                    "O":"Sketcher_Offset", "P":"Sketcher_Projection",
                    "X":"Sketcher_ToggleConstruction", "D":"Sketcher_Dimension"}
        for key, command in expected.items():
            self.assertEqual(self.profile.resolve(key, "sketch")["command"], command)
            self.assertIsNone(self.profile.resolve(key, "model"))
        self.assertIsNone(self.profile.resolve("F", "sketch"))

    def test_drawing_context_resolves_same_keys(self):
        self.assertEqual(self.profile.resolve("D", "drawing")["command"], "TechDraw_Dimension")
        self.assertEqual(self.profile.resolve("T", "drawing")["command"], "TechDraw_Annotation")
        self.assertEqual(self.profile.resolve("P", "drawing")["command"], "TechDraw_ProjectionGroup")

    def test_typing_and_classic_never_dispatch(self):
        self.assertIsNone(self.profile.resolve("L", "sketch", typing=True))
        self.assertIsNone(self.profile.resolve("Ctrl+C", "model", typing=True))
        self.profile.name = CLASSIC_PROFILE
        self.assertIsNone(self.profile.resolve("S"))

    def test_contextual_conflict_and_global_conflict(self):
        self.profile.set_binding("Sketcher_CreateLine", "H")
        self.assertEqual(self.profile.resolve("H", "sketch")["id"], "Sketcher_CreateLine")
        with self.assertRaises(ValueError):
            self.profile.set_binding("Sketcher_CreateLine", "C")
        with self.assertRaises(ValueError):
            self.profile.set_binding("Sketcher_CreateLine", "S")

    def test_custom_binding_blank_and_reset(self):
        self.profile.set_binding("Fission_Extrude", "Ctrl+E")
        self.assertIsNone(self.profile.resolve("E"))
        self.assertEqual(self.profile.resolve("Ctrl+E")["command"], "Fission_Extrude")
        self.profile.set_binding("Fission_Extrude", "")
        self.assertIsNone(self.profile.resolve("Ctrl+E"))
        self.profile.reset_one("Fission_Extrude")
        self.assertEqual(self.profile.resolve("E")["command"], "Fission_Extrude")

    def test_reset_refuses_new_conflict(self):
        self.profile.set_binding("Sketcher_CreateLine", "Ctrl+L")
        self.profile.set_binding("Sketcher_CreateRectangle", "L")
        with self.assertRaises(ValueError):
            self.profile.reset_one("Sketcher_CreateLine")
        self.profile.reset()
        self.assertEqual(self.profile.name, DEFAULT_PROFILE)
        self.assertEqual(self.profile.overrides, {})
        self.assertEqual(self.profile.resolve("L", "sketch")["command"], "Sketcher_CreateLine")

    def test_round_trip_settings(self):
        parameters = Parameters()
        self.profile.set_binding("Fission_Fillet", "Ctrl+F")
        self.profile.name = CLASSIC_PROFILE
        self.profile.save(parameters)
        reopened = ShortcutProfile()
        reopened.load(parameters)
        self.assertEqual(reopened.name, CLASSIC_PROFILE)
        self.assertEqual(reopened.overrides, {"Fission_Fillet":"Ctrl+F"})
        reopened.name = CUSTOM_PROFILE
        self.assertEqual(reopened.resolve("Ctrl+F")["command"], "Fission_Fillet")

    def test_factory_and_classic_preserve_custom_preset(self):
        self.profile.set_binding("Fission_Extrude", "Ctrl+E")
        self.assertEqual(self.profile.name, CUSTOM_PROFILE)
        self.profile.name = DEFAULT_PROFILE
        self.assertEqual(self.profile.resolve("E")["command"], "Fission_Extrude")
        self.assertIsNone(self.profile.resolve("Ctrl+E"))
        self.profile.name = CLASSIC_PROFILE
        self.assertIsNone(self.profile.resolve("E"))
        self.profile.name = CUSTOM_PROFILE
        self.assertEqual(self.profile.resolve("Ctrl+E")["command"], "Fission_Extrude")
        self.assertIsNone(self.profile.resolve("E"))

    def test_active_custom_preset_survives_restart(self):
        parameters = Parameters()
        self.profile.set_binding("Fission_Fillet", "Ctrl+F")
        self.profile.save(parameters)
        reopened = ShortcutProfile()
        reopened.load(parameters)
        self.assertEqual(reopened.name, CUSTOM_PROFILE)
        self.assertEqual(reopened.resolve("Ctrl+F")["command"], "Fission_Fillet")
        self.assertIsNone(reopened.resolve("F"))
        self.assertEqual(parameters.data["SchemaVersion"], str(PROFILE_SCHEMA_VERSION))

    def test_factory_preset_survives_restart_with_saved_custom_keys(self):
        parameters = Parameters()
        self.profile.set_binding("Fission_Fillet", "Ctrl+F")
        self.profile.name = DEFAULT_PROFILE
        self.profile.save(parameters)
        reopened = ShortcutProfile()
        reopened.load(parameters)
        self.assertEqual(reopened.name, DEFAULT_PROFILE)
        self.assertEqual(reopened.resolve("F")["command"], "Fission_Fillet")
        self.assertIsNone(reopened.resolve("Ctrl+F"))
        reopened.name = CUSTOM_PROFILE
        self.assertEqual(reopened.resolve("Ctrl+F")["command"], "Fission_Fillet")

    def test_legacy_profile_migrates_active_edits_to_custom(self):
        parameters = Parameters()
        parameters.SetString("Profile", DEFAULT_PROFILE)
        parameters.SetString("Overrides", '{"Fission_Fillet":"Ctrl+F"}')
        self.profile.load(parameters)
        self.assertEqual(self.profile.name, CUSTOM_PROFILE)
        self.assertEqual(self.profile.resolve("Ctrl+F")["command"], "Fission_Fillet")
        self.profile.import_data({"schema_version": 1, "profile": CLASSIC_PROFILE,
                                  "overrides": {"Fission_Fillet": "Ctrl+F"}})
        self.assertEqual(self.profile.name, CLASSIC_PROFILE)
        self.assertEqual(self.profile.overrides, {"Fission_Fillet": "Ctrl+F"})

    def test_inactive_custom_keys_still_get_conflict_checks(self):
        self.profile.set_binding("Fission_Extrude", "Ctrl+E")
        self.profile.name = DEFAULT_PROFILE
        with self.assertRaises(ValueError):
            self.profile.set_binding("Fission_Fillet", "Ctrl+E")
        self.assertEqual(self.profile.name, DEFAULT_PROFILE)
        saved = self.profile.export_data()
        with self.assertRaises(ValueError):
            self.profile.import_data({"schema_version": 2, "profile": DEFAULT_PROFILE,
                                      "overrides": {"Fission_Fillet": "H"}})
        self.assertEqual(self.profile.export_data(), saved)

    def test_json_import_is_atomic(self):
        self.profile.set_binding("Fission_Fillet", "Ctrl+F")
        saved = self.profile.export_data()
        bad = {"schema_version":1, "profile":DEFAULT_PROFILE,
               "overrides":{"Fission_Fillet":"H"}}
        with self.assertRaises(ValueError):
            self.profile.import_data(bad)
        self.assertEqual(self.profile.export_data(), saved)
        for bad in [{}, {"schema_version":1,"overrides":{"Missing":"G"}},
                    {"schema_version":1,"overrides":{"Fission_Fillet":1}}]:
            with self.assertRaises(ValueError):
                self.profile.import_data(bad)
            self.assertEqual(self.profile.export_data(), saved)
        reopened = ShortcutProfile()
        reopened.import_data(json.loads(json.dumps(saved)))
        self.assertEqual(reopened.export_data(), saved)

    def test_catalog_commands_can_be_customized(self):
        catalog = [{"id":"Fission_Revolve", "title":"Revolve", "context":"model"}]
        self.profile.add_catalog(catalog)
        self.profile.add_catalog(catalog)
        self.profile.set_binding("Fission_Revolve", "Ctrl+R")
        self.assertEqual(self.profile.resolve("Ctrl+R")["command"], "Fission_Revolve")
        self.assertEqual(sum(row["id"] == "Fission_Revolve" for row in self.profile.bindings), 1)

    def test_normalization_and_invalid_keys(self):
        self.assertEqual(normalize_shortcut(" shift + control + e "), "Ctrl+Shift+E")
        self.assertEqual(normalize_shortcut("Del"), "Delete")
        self.assertEqual(normalize_shortcut("Ctrl++"), "Ctrl++")
        self.assertEqual(normalize_shortcut("Enter"), "Return")
        for invalid in ["G, L", "Ctrl+Ctrl+E", "Ctrl+", "Super+R", "F36"]:
            with self.assertRaises(ValueError):
                normalize_shortcut(invalid)
        self.assertTrue(contexts_overlap(["*"], ["sketch"]))
        self.assertFalse(contexts_overlap(["model"], ["sketch"]))

    def test_new_sketch_commands_have_no_invented_defaults(self):
        for command in ["Fission_FinishSketch", "Fission_Preferences", "Fission_ToggleTimeline"]:
            row = next(item for item in self.profile.bindings if item["id"] == command)
            self.assertEqual(self.profile.shortcut(row), "")

    def test_unsupported_fusion_keys_are_reserved(self):
        for key in ["Shift+N", "Shift+J", "Shift+S", "Ctrl+Alt+A", "Ctrl+Alt+P"]:
            self.assertEqual(self.profile.resolve(key)["state"], "unsupported")

    def test_geometric_selection_keys_resolve_in_supported_contexts(self):
        expected = [("1", "Fission_WindowSelection"),
                    ("2", "Fission_FreeformSelection"),
                    ("3", "Fission_PaintSelection")]
        for context in ("model", "assembly", "surface", "mesh", "cam"):
            for key, command in expected:
                with self.subTest(context=context, key=key):
                    row = self.profile.resolve(key, context)
                    self.assertEqual(row["command"], command)
                    self.assertNotEqual(row.get("state"), "unsupported")

    def test_geometric_selection_keys_leave_sketch_and_drawing_native(self):
        for context in ("sketch", "drawing"):
            for key in ("1", "2", "3"):
                with self.subTest(context=context, key=key):
                    self.assertIsNone(self.profile.resolve(key, context))

    def test_workspace_and_navigation_keys_are_implemented(self):
        for key, command in [("Ctrl+[", "Fission_PreviousWorkspace"), ("Ctrl+]", "Fission_NextWorkspace"),
                             ("Ctrl+Alt+N", "Fission_ToggleNavigation"), ("Ctrl+Alt+V", "Fission_ToggleViewCube")]:
            for context in ("model", "drawing", "cam", "surface", "mesh"):
                row = self.profile.resolve(key, context)
                self.assertEqual(row["command"], command)
                self.assertNotEqual(row.get("state"), "unsupported")

    def test_specialist_contexts_keep_inspection_shortcuts(self):
        for context in ("surface", "mesh"):
            self.assertEqual(self.profile.resolve("I", context)["command"], "Fission_Measure")
            self.assertEqual(self.profile.resolve("Ctrl+B", context)["command"], "Fission_Compute")


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.catalog = [
            {"id":"Fission_Extrude","title":"Extrude","aliases":["pad","push"],"context":"model"},
            {"id":"Sketcher_Dimension","title":"Sketch Dimension","aliases":["constraint"],"context":"sketch"},
            {"id":"TechDraw_Dimension","title":"Drawing Dimension","aliases":["annotation"],"context":"drawing"},
            {"id":"Fission_Search","title":"Command Toolbox","aliases":["search"],"context":"*"}]

    def test_alias_and_multiword_search(self):
        self.assertEqual(rank_commands(self.catalog,"pad")[0]["id"], "Fission_Extrude")
        self.assertEqual(rank_commands(self.catalog,"dimension sketch")[0]["id"], "Sketcher_Dimension")
        self.assertEqual(rank_commands(self.catalog,"TOOLBOX")[0]["id"], "Fission_Search")
        self.assertEqual(rank_commands(self.catalog,"unknown"), [])

    def test_current_context_is_prioritized(self):
        self.assertEqual(rank_commands(self.catalog,"dimension","sketch")[0]["id"], "Sketcher_Dimension")
        self.assertEqual(rank_commands(self.catalog,"dimension","drawing")[0]["id"], "TechDraw_Dimension")


@unittest.skipUnless(os.environ.get("FISSION_QT_TESTS") == "1", "Set FISSION_QT_TESTS=1 with a PySide runtime")
class NativeQtShortcutTests(unittest.TestCase):
    """Real Qt events, with only FreeCAD's command execution replaced by a spy."""
    @classmethod
    def setUpClass(cls):
        import fission.shortcuts as module
        from PySide6 import QtCore, QtGui, QtWidgets, QtTest
        cls.module = module
        cls.QtCore, cls.QtGui, cls.QtWidgets, cls.QtTest = QtCore, QtGui, QtWidgets, QtTest
        cls.application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        cls.original_app, cls.original_gui = module.App, module.Gui

    @classmethod
    def tearDownClass(cls):
        cls.module.App, cls.module.Gui = cls.original_app, cls.original_gui

    def setUp(self):
        parameters = Parameters()
        self.module.App = types.SimpleNamespace(ParamGet=lambda path: parameters)
        self.module.Gui = types.SimpleNamespace(Command=types.SimpleNamespace(
            listAll=lambda: ["Sketcher_External"]))
        self.called = []
        self.notifications = []
        self.native_calls = []
        self.current_context = "model"
        self.main = self.QtWidgets.QMainWindow()
        panel = self.QtWidgets.QWidget()
        layout = self.QtWidgets.QVBoxLayout(panel)
        self.canvas = self.QtWidgets.QWidget()
        self.canvas.setFocusPolicy(self.QtCore.Qt.StrongFocus)
        self.canvas.setMinimumHeight(80)
        layout.addWidget(self.canvas)
        self.editors = [self.QtWidgets.QLineEdit(), self.QtWidgets.QSpinBox(),
                        self.QtWidgets.QTextEdit(), self.QtWidgets.QPlainTextEdit()]
        for editor in self.editors:
            layout.addWidget(editor)
        self.main.setCentralWidget(panel)
        self.native = self.QtGui.QAction("Stock Extrude", self.main)
        self.native.setShortcut("E")
        self.native.triggered.connect(lambda: self.native_calls.append("E"))
        self.main.addAction(self.native)
        controller = types.SimpleNamespace(context=lambda: self.current_context,
            execute=lambda command: self.called.append(command) or True, notify=self.notifications.append,
            command_catalog=lambda: [{"id":"Fission_Extrude", "title":"Extrude",
                                      "aliases":"pad extrude", "context":"model"}])
        self.controller = controller
        self.manager = self.module.ShortcutManager(controller, self.main)
        controller.shortcuts = self.manager
        self.manager.apply_profile()
        self.main.show()
        self.main.activateWindow()
        self.canvas.setFocus()
        self.application.processEvents()

    def tearDown(self):
        self.manager.deactivate()
        self.main.close()
        self.main.deleteLater()
        self.application.processEvents()

    def press(self, key, widget=None, modifiers=None):
        widget = widget or self.canvas
        widget.setFocus()
        self.application.processEvents()
        self.QtTest.QTest.keyClick(widget, key, modifiers or self.QtCore.Qt.NoModifier)
        self.application.processEvents()

    def test_real_key_dispatch_and_native_conflict(self):
        self.assertTrue(self.native.shortcut().isEmpty())
        self.press(self.QtCore.Qt.Key_E)
        self.assertEqual(self.called, ["Fission_Extrude"])
        self.assertEqual(self.native_calls, [])
        self.current_context = "sketch"
        self.press(self.QtCore.Qt.Key_L)
        self.assertEqual(self.called[-1], "Sketcher_CreateLine")
        self.press(self.QtCore.Qt.Key_P)
        self.assertEqual(self.called[-1], "Sketcher_External")

    def test_text_and_numeric_widgets_keep_typing(self):
        for editor in self.editors:
            self.press(self.QtCore.Qt.Key_E, editor)
            self.press(self.QtCore.Qt.Key_C, editor, self.QtCore.Qt.ControlModifier)
        self.assertEqual(self.called, [])
        self.assertEqual(self.editors[0].text(), "e")
        self.assertEqual(self.editors[2].toPlainText(), "e")
        self.assertEqual(self.editors[3].toPlainText(), "e")

    def test_document_panel_keys_defer_custom_dispatch_only_in_panel(self):
        received = []
        QtCore = self.QtCore

        class PanelKeys(QtCore.QObject):
            def eventFilter(self, obj, event):
                if (event.type() in (QtCore.QEvent.ShortcutOverride, QtCore.QEvent.KeyPress)
                        and not event.modifiers() & (QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier |
                                                     QtCore.Qt.ShiftModifier | QtCore.Qt.MetaModifier)
                        and event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter,
                                            QtCore.Qt.Key_F2, QtCore.Qt.Key_Delete)):
                    event.accept()
                    if event.type() == QtCore.QEvent.KeyPress:
                        received.append(event.key())
                    return True
                return False

        observer = PanelKeys(self.canvas)
        self.canvas.setProperty("fissionDocumentPanelKeys", True)
        self.canvas.installEventFilter(observer)
        self.manager.set_binding("Std_Delete", "")
        for key, sequence, modifiers in ((QtCore.Qt.Key_Return, "Return", QtCore.Qt.NoModifier),
                                         (QtCore.Qt.Key_Enter, "Return", QtCore.Qt.NoModifier),
                                         (QtCore.Qt.Key_Enter, "Return", QtCore.Qt.KeypadModifier),
                                         (QtCore.Qt.Key_F2, "F2", QtCore.Qt.NoModifier),
                                         (QtCore.Qt.Key_Delete, "Delete", QtCore.Qt.NoModifier)):
            with self.subTest(sequence=sequence, key=key):
                self.manager.set_binding("Fission_Extrude", sequence)
                self.called.clear()
                self.press(key, modifiers=modifiers)
                self.assertEqual(self.called, [])
                self.assertEqual(received[-1], key)
                self.canvas.setProperty("fissionDocumentPanelKeys", False)
                self.canvas.removeEventFilter(observer)
                self.press(key, modifiers=modifiers)
                self.assertEqual(self.called, ["Fission_Extrude"])
                self.canvas.setProperty("fissionDocumentPanelKeys", True)
                self.canvas.installEventFilter(observer)

    def test_document_panel_navigation_defers_custom_shortcuts(self):
        received = []
        QtCore = self.QtCore

        class Navigation(QtCore.QObject):
            def eventFilter(self, obj, event):
                if event.type() == QtCore.QEvent.KeyPress and event.key() == QtCore.Qt.Key_Right:
                    received.append(event.key())
                return False

        observer = Navigation(self.canvas)
        self.canvas.installEventFilter(observer)
        self.manager.set_binding("Fission_Extrude", "Shift+Right")
        self.canvas.setProperty("fissionDocumentPanelKeys", True)
        self.press(QtCore.Qt.Key_Right, modifiers=QtCore.Qt.ShiftModifier)
        self.assertEqual(received, [QtCore.Qt.Key_Right])
        self.assertEqual(self.called, [])
        self.canvas.setProperty("fissionDocumentPanelKeys", False)
        self.press(QtCore.Qt.Key_Right, modifiers=QtCore.Qt.ShiftModifier)
        self.assertEqual(self.called, ["Fission_Extrude"])

    def test_reserved_key_cannot_trigger_unrelated_native_action(self):
        action = self.QtGui.QAction("Unrelated stock joint command", self.main)
        action.setShortcut("Shift+J")
        action.triggered.connect(lambda: self.native_calls.append("Shift+J"))
        self.main.addAction(action)
        self.application.processEvents()
        self.press(self.QtCore.Qt.Key_J, modifiers=self.QtCore.Qt.ShiftModifier)
        self.assertEqual(self.native_calls, [])
        self.assertEqual(self.called, [])
        self.assertIn("reserved", self.notifications[-1])

    def test_geometric_selection_keys_dispatch_real_qt_events(self):
        expected = [(self.QtCore.Qt.Key_1, "Fission_WindowSelection"),
                    (self.QtCore.Qt.Key_2, "Fission_FreeformSelection"),
                    (self.QtCore.Qt.Key_3, "Fission_PaintSelection")]
        for context in ("model", "assembly", "surface", "mesh", "cam"):
            self.current_context = context
            for key, command in expected:
                with self.subTest(context=context, key=key):
                    before = len(self.called)
                    self.press(key)
                    self.assertEqual(self.called[before:], [command])
        self.assertEqual(self.notifications, [])

    def test_geometric_selection_keys_reach_native_sketch_canvas(self):
        # A widget event filter stands in for the native sketch canvas. It
        # receives key presses only when the application-level Fission filter
        # leaves those events unconsumed.
        received = []
        QtCore = self.QtCore

        class CanvasKeyObserver(QtCore.QObject):
            def eventFilter(self, obj, event):
                if event.type() == QtCore.QEvent.KeyPress:
                    received.append(event.key())
                return False

        observer = CanvasKeyObserver(self.canvas)
        self.canvas.installEventFilter(observer)
        try:
            for context in ("sketch", "drawing"):
                self.current_context = context
                for key in (QtCore.Qt.Key_1, QtCore.Qt.Key_2, QtCore.Qt.Key_3):
                    with self.subTest(context=context, key=key):
                        before = len(received)
                        self.press(key)
                        self.assertEqual(received[before:], [key])
            self.assertEqual(self.called, [])
            self.assertEqual(self.notifications, [])
        finally:
            self.canvas.removeEventFilter(observer)

    def test_classic_and_deactivation_restore_actions(self):
        self.manager.apply_profile(CLASSIC_PROFILE)
        self.assertEqual(self.native.shortcut().toString(), "E")
        self.press(self.QtCore.Qt.Key_E)
        self.assertEqual(self.called, [])
        self.assertEqual(self.native_calls, ["E"])
        self.manager.apply_profile()
        self.manager.deactivate()
        self.assertEqual(self.native.shortcut().toString(), "E")
        self.press(self.QtCore.Qt.Key_E)
        self.assertEqual(self.native_calls, ["E", "E"])
        self.manager.apply_profile()
        self.press(self.QtCore.Qt.Key_E)
        self.assertEqual(self.called, ["Fission_Extrude"])

    def test_lazy_actions_are_suppressed_and_restored(self):
        action = self.QtGui.QAction("Lazy stock command", self.main)
        action.setShortcut("S, L")
        self.main.addAction(action)
        self.application.processEvents()
        self.assertTrue(action.shortcut().isEmpty())
        self.manager.deactivate()
        self.assertEqual(action.shortcut().toString(), "S, L")

    def test_custom_preset_dispatch_and_restart(self):
        self.manager.set_binding("Fission_Extrude", "Ctrl+E")
        self.assertEqual(self.manager.profile.name, CUSTOM_PROFILE)
        self.assertEqual(self.native.shortcut().toString(), "E")
        self.press(self.QtCore.Qt.Key_E, modifiers=self.QtCore.Qt.ControlModifier)
        self.assertEqual(self.called, ["Fission_Extrude"])
        self.manager.apply_profile(DEFAULT_PROFILE)
        self.assertTrue(self.native.shortcut().isEmpty())
        self.manager.deactivate()
        self.manager = self.module.ShortcutManager(self.controller, self.main)
        self.controller.shortcuts = self.manager
        self.manager.apply_profile(self.manager.profile.name)
        self.assertEqual(self.manager.profile.name, DEFAULT_PROFILE)
        self.assertTrue(self.native.shortcut().isEmpty())
        self.press(self.QtCore.Qt.Key_E)
        self.assertEqual(self.called, ["Fission_Extrude", "Fission_Extrude"])
        self.manager.apply_profile(CUSTOM_PROFILE)
        self.assertEqual(self.native.shortcut().toString(), "E")
        self.press(self.QtCore.Qt.Key_E, modifiers=self.QtCore.Qt.ControlModifier)
        self.assertEqual(self.called[-1], "Fission_Extrude")
        self.manager.apply_profile(CLASSIC_PROFILE)
        self.press(self.QtCore.Qt.Key_E)
        self.assertEqual(self.native_calls, ["E"])
        self.manager.apply_profile(CUSTOM_PROFILE)
        self.manager.reset_profile()
        self.assertEqual(self.manager.profile.name, DEFAULT_PROFILE)
        self.assertEqual(self.manager.profile.overrides, {})
        self.assertTrue(self.native.shortcut().isEmpty())

    def test_preferences_expose_three_presets_and_select_custom_on_edit(self):
        self.manager.show_preferences()
        dialog = self.manager._dialog
        self.assertEqual(tuple(dialog.profile_combo.itemText(index)
                               for index in range(dialog.profile_combo.count())), PROFILE_NAMES)
        item = next(dialog.tree.topLevelItem(index)
                    for index in range(dialog.tree.topLevelItemCount())
                    if dialog.tree.topLevelItem(index).data(0, self.QtCore.Qt.UserRole) == "Fission_Extrude")
        dialog.tree.setCurrentItem(item)
        dialog.key_edit.setKeySequence(self.QtGui.QKeySequence("Ctrl+E"))
        dialog._assign()
        self.assertEqual(dialog.profile_combo.currentText(), CUSTOM_PROFILE)
        dialog.profile_combo.setCurrentText(DEFAULT_PROFILE)
        self.assertEqual(self.manager.shortcut_for("Fission_Extrude"), "E")
        dialog.profile_combo.setCurrentText(CUSTOM_PROFILE)
        self.assertEqual(self.manager.shortcut_for("Fission_Extrude"), "Ctrl+E")
        dialog.close()

    def test_preferences_and_toolbox_keyboard(self):
        self.manager.show_preferences()
        self.application.processEvents()
        self.assertGreater(self.manager._dialog.tree.topLevelItemCount(), 25)
        self.manager._dialog.filter_edit.setText("Extrude")
        self.manager._dialog.close()
        self.application.processEvents()
        from fission.search import SearchDialog
        search = SearchDialog(self.controller, self.main)
        search.show()
        self.application.processEvents()
        search.input.setText("pad")
        self.assertEqual(search.results.topLevelItemCount(), 1)
        self.assertEqual(search.results.topLevelItem(0).text(1), "E")
        self.press(self.QtCore.Qt.Key_Return, search.input)
        self.assertEqual(self.called, ["Fission_Extrude"])
        search.deleteLater()


if __name__ == "__main__":
    unittest.main()
