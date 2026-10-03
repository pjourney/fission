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
from fission.shortcuts import (ShortcutProfile, DEFAULT_PROFILE, CLASSIC_PROFILE,
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
        reopened.name = DEFAULT_PROFILE
        self.assertEqual(reopened.resolve("Ctrl+F")["command"], "Fission_Fillet")

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
        for key in ["1", "2", "3", "Shift+N", "Shift+J", "Shift+S", "Ctrl+Alt+V", "Ctrl+["]:
            self.assertEqual(self.profile.resolve(key)["state"], "unsupported")


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
            execute=lambda command: self.called.append(command), notify=self.notifications.append,
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

    def test_reserved_key_cannot_trigger_unrelated_native_action(self):
        action = self.QtGui.QAction("Stock view orientation", self.main)
        action.setShortcut("1")
        action.triggered.connect(lambda: self.native_calls.append("1"))
        self.main.addAction(action)
        self.application.processEvents()
        self.press(self.QtCore.Qt.Key_1)
        self.assertEqual(self.native_calls, [])
        self.assertEqual(self.called, [])
        self.assertIn("reserved", self.notifications[-1])

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
