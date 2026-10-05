# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real Qt panel events with a small document/selection command adapter."""

import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if "fission" not in sys.modules:
    package = types.ModuleType("fission")
    package.__path__ = [str(ROOT / "Mod" / "Fission" / "fission")]
    sys.modules["fission"] = package


@unittest.skipUnless(os.environ.get("FISSION_QT_TESTS") == "1",
                     "Set FISSION_QT_TESTS=1 with a PySide runtime")
class NativeQtDocumentPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6 import QtCore, QtGui, QtWidgets, QtTest
        cls.QtCore, cls.QtGui, cls.QtWidgets, cls.QtTest = QtCore, QtGui, QtWidgets, QtTest
        cls.application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        with patch.dict(sys.modules, {
                "FreeCAD": types.ModuleType("FreeCAD"),
                "FreeCADGui": types.ModuleType("FreeCADGui"),
                "PySide": types.SimpleNamespace(QtCore=QtCore, QtGui=QtGui, QtWidgets=QtWidgets)}):
            from fission import browser, timeline
        cls.browser_module, cls.timeline_module = browser, timeline

    def setUp(self):
        self.main = self.QtWidgets.QMainWindow()
        self.main.resize(900, 520)
        self.document = types.SimpleNamespace(Name="Design", Label="Design", Objects=[], HasPendingTransaction=False)
        self.transactions = []
        self.document.openTransaction = lambda title: self.transactions.append(("open", title))
        self.document.commitTransaction = lambda: self.transactions.append(("commit", None))
        self.document.abortTransaction = lambda: self.transactions.append(("abort", None))
        self.document.getObject = lambda name: next((obj for obj in self.document.Objects if obj.Name == name), None)
        self.objects = [self.make_object("First"), self.make_object("Second")]
        self.document.Objects[:] = self.objects
        self.body = self.make_object("Body", "PartDesign::Body")
        self.body.Tip = self.objects[-1]
        self.body.Group = list(self.objects)
        self.document.Objects.insert(0, self.body)
        self.selection = []
        self.edited = []
        self.commands = []
        self.notifications = []
        self.in_edit = None
        self.dialog = None
        self.view = types.SimpleNamespace(getActiveObject=lambda kind: self.body if kind == "pdbody" else None,
                                          setActiveObject=lambda *args: None)
        self.gui_document = types.SimpleNamespace(activeView=lambda: self.view, getInEdit=lambda: self.in_edit)
        observer = lambda *_args: None
        self.app = types.SimpleNamespace(ActiveDocument=self.document,
                                        getDocument=lambda name: self.document if name == self.document.Name else None,
                                        addDocumentObserver=observer, removeDocumentObserver=observer)
        self.gui = types.SimpleNamespace(
            Selection=types.SimpleNamespace(getSelection=lambda: list(self.selection),
                clearSelection=lambda: self.selection.clear(), addSelection=self.selection.append,
                addObserver=observer, removeObserver=observer),
            getDocument=lambda name: self.gui_document, getIcon=lambda path: self.QtGui.QIcon(),
            Control=types.SimpleNamespace(activeDialog=lambda: self.dialog),
            addDocumentObserver=observer, removeDocumentObserver=observer)
        self.patches = [patch.object(module, attr, value)
                        for module in (self.browser_module, self.timeline_module)
                        for attr, value in (("App", self.app), ("Gui", self.gui))]
        for item in self.patches:
            item.start()
        self.controller = types.SimpleNamespace(notify=self.notifications.append,
            refresh_context=lambda: None, edit_object=lambda obj: self.edited.append(obj),
            execute=lambda command: self.commands.append((command, list(self.selection))) or True)
        self.browser = self.browser_module.Browser(self.main, self.controller)
        self.timeline = self.timeline_module.Timeline(self.main, self.controller)
        self.panels = [(self.browser, self.browser.tree), (self.timeline, self.timeline.list)]
        self.main.addDockWidget(self.QtCore.Qt.LeftDockWidgetArea, self.browser)
        self.main.addDockWidget(self.QtCore.Qt.BottomDockWidgetArea, self.timeline)
        self.main.show()
        self.main.activateWindow()
        self.application.processEvents()

    def tearDown(self):
        self.browser.shutdown()
        self.timeline.shutdown()
        self.main.close()
        self.main.deleteLater()
        self.application.processEvents()
        for item in reversed(self.patches):
            item.stop()

    def make_object(self, name, type_id="PartDesign::Pad"):
        return types.SimpleNamespace(Name=name, Label=name, TypeId=type_id, Document=self.document,
            PropertiesList=[], OutList=[], Group=[], State=[],
            ViewObject=types.SimpleNamespace(Icon=self.QtGui.QIcon(), Visibility=True, PropertiesList=["Visibility"]),
            isDerivedFrom=lambda kind: kind == type_id or (type_id != "PartDesign::Body" and kind in ("PartDesign::Feature", "Part::Feature")),
            getParentGeoFeatureGroup=lambda: None)

    def select(self, panel, *objects):
        self.selection[:] = objects
        panel.sync_selection()
        self.application.processEvents()

    def press(self, view, key, modifiers=None):
        view.setFocus()
        self.application.processEvents()
        self.QtTest.QTest.keyClick(view, key, modifiers or self.QtCore.Qt.NoModifier)
        self.application.processEvents()

    def rename_editor(self, panel, view, obj):
        self.select(panel, obj)
        self.press(view, self.QtCore.Qt.Key_F2)
        editor = self.application.focusWidget()
        self.assertIsInstance(editor, self.QtWidgets.QLineEdit)
        return editor

    def test_enter_uses_one_selected_feature_and_not_stale_current(self):
        for panel, view in self.panels:
            with self.subTest(panel=panel.windowTitle()):
                self.select(panel, self.objects[0])
                self.select(panel, self.objects[1])
                self.assertIs(view.currentItem(), panel._items[("Design", "Second")])
                self.press(view, self.QtCore.Qt.Key_Return)
                self.assertIs(self.edited[-1], self.objects[1])

    def test_enter_does_not_choose_arbitrary_feature_from_multiselection(self):
        for panel, view in self.panels:
            self.select(panel, *self.objects)
            self.press(view, self.QtCore.Qt.Key_Return)
        self.assertEqual(self.edited, [])

    def test_f2_edits_plain_label_and_return_commits_one_transaction(self):
        for panel, view in self.panels:
            with self.subTest(panel=panel.windowTitle()):
                obj = self.objects[1]
                obj.Label = "Second"
                panel.refresh()
                editor = self.rename_editor(panel, view, obj)
                self.assertEqual(editor.text(), "Second")
                self.QtTest.QTest.keyClicks(editor, "Renamed result")
                self.QtTest.QTest.keyClick(editor, self.QtCore.Qt.Key_Return)
                self.application.processEvents()
                self.assertEqual(obj.Label, "Renamed result")
                self.assertEqual(self.transactions[-2:], [("open", "Rename object"), ("commit", None)])
                self.assertEqual(self.commands, [])

    def test_editor_escape_cancel_and_delete_keep_native_text_ownership(self):
        for panel, view in self.panels:
            editor = self.rename_editor(panel, view, self.objects[1])
            self.QtTest.QTest.keyClick(editor, self.QtCore.Qt.Key_Delete)
            self.assertEqual(editor.text(), "")
            self.QtTest.QTest.keyClicks(editor, "Cancelled")
            self.QtTest.QTest.keyClick(editor, self.QtCore.Qt.Key_Escape)
            self.application.processEvents()
            self.assertEqual(self.objects[1].Label, "Second")
        self.assertEqual(self.transactions, [])
        self.assertEqual(self.commands, [])

    def test_blank_and_unchanged_rename_do_not_open_transaction(self):
        for panel, view in self.panels:
            for label in ("", "  ", "Second"):
                editor = self.rename_editor(panel, view, self.objects[1])
                editor.setText(label)
                self.QtTest.QTest.keyClick(editor, self.QtCore.Qt.Key_Return)
                self.application.processEvents()
        self.assertEqual(self.transactions, [])
        self.assertEqual(self.objects[1].Label, "Second")

    def test_delete_dispatches_full_set_once_to_native_command(self):
        for panel, view in self.panels:
            self.select(panel, *self.objects)
            self.press(view, self.QtCore.Qt.Key_Delete)
            self.assertEqual(self.commands[-1], ("Std_Delete", self.objects))
        self.assertEqual(len(self.commands), 2)
        self.assertEqual(self.transactions, [])

    def test_empty_rows_consume_delete_instead_of_native_global_action(self):
        native = self.QtGui.QAction("Native delete", self.main)
        native.setShortcut("Delete")
        native.triggered.connect(lambda: self.commands.append(("native QAction", [])))
        self.main.addAction(native)
        for panel, view in self.panels:
            self.select(panel)
            self.press(view, self.QtCore.Qt.Key_Delete)
        self.assertEqual(self.commands, [])

    def test_pending_edit_and_task_guards_leave_selection_and_transactions(self):
        for guard in ("pending", "edit", "dialog"):
            self.document.HasPendingTransaction = guard == "pending"
            self.in_edit = object() if guard == "edit" else None
            self.dialog = object() if guard == "dialog" else None
            for panel, view in self.panels:
                self.select(panel, self.objects[1])
                for key in (self.QtCore.Qt.Key_Return, self.QtCore.Qt.Key_F2, self.QtCore.Qt.Key_Delete):
                    self.press(view, key)
                self.assertEqual(self.selection, [self.objects[1]])
        self.assertEqual(self.transactions, [])
        self.assertEqual(self.commands, [])
        self.assertEqual(self.edited, [])

    def test_stale_panel_owner_does_not_edit_or_delete_other_document(self):
        for panel, view in self.panels:
            self.app.ActiveDocument = self.document
            self.select(panel, self.objects[1])
            self.app.ActiveDocument = types.SimpleNamespace(Name="Other")
            for key in (self.QtCore.Qt.Key_Return, self.QtCore.Qt.Key_F2, self.QtCore.Qt.Key_Delete):
                self.press(view, key)
        self.assertEqual(self.commands, [])
        self.assertEqual(self.edited, [])
        self.assertEqual(self.transactions, [])

    def test_editor_commit_checks_captured_object_identity(self):
        for panel, view in self.panels:
            editor = self.rename_editor(panel, view, self.objects[1])
            replacement = self.make_object("Second")
            index = self.document.Objects.index(self.objects[1])
            self.document.Objects[index] = replacement
            editor.setText("Must not rename replacement")
            self.QtTest.QTest.keyClick(editor, self.QtCore.Qt.Key_Return)
            self.application.processEvents()
            self.assertEqual(replacement.Label, "Second")
            self.document.Objects[index] = self.objects[1]
        self.assertEqual(self.transactions, [])

    def test_sync_selection_preserves_current_item_in_multiselection(self):
        for panel, view in self.panels:
            self.select(panel, self.objects[1])
            self.select(panel, *self.objects)
            self.assertIs(view.currentItem(), panel._items[("Design", "Second")])
            self.assertEqual(len(view.selectedItems()), 2)

    def test_timeline_arrow_range_keeps_native_qt_selection_anchor(self):
        camera_calls = []
        native = self.QtGui.QAction("Rotate camera", self.main)
        native.setShortcut("Shift+Right")
        native.triggered.connect(lambda: camera_calls.append("rotate"))
        self.main.addAction(native)
        third = self.make_object("Third")
        self.document.Objects.append(third)
        self.timeline.refresh()
        self.select(self.timeline, self.objects[0])
        self.press(self.timeline.list, self.QtCore.Qt.Key_Right)
        self.assertEqual(self.selection, [self.objects[1]])
        self.press(self.timeline.list, self.QtCore.Qt.Key_Right, self.QtCore.Qt.ShiftModifier)
        self.assertEqual(self.selection, [self.objects[1], third])
        self.assertEqual(camera_calls, [])

    def test_idle_assembly_context_allows_mutations_but_not_nested_feature_edit(self):
        assembly = self.make_object("Assembly", "Assembly::AssemblyObject")
        self.in_edit = types.SimpleNamespace(Object=assembly)
        for panel, view in self.panels:
            self.select(panel, self.objects[1])
            self.press(view, self.QtCore.Qt.Key_Delete)
            self.assertEqual(self.commands[-1], ("Std_Delete", [self.objects[1]]))
            self.press(view, self.QtCore.Qt.Key_Return)
            self.assertEqual(self.edited, [])
            editor = self.rename_editor(panel, view, self.objects[1])
            self.QtTest.QTest.keyClick(editor, self.QtCore.Qt.Key_Escape)
            self.application.processEvents()

    def test_filter_text_and_modified_keys_are_not_panel_operations(self):
        self.browser.filter.setFocus()
        self.QtTest.QTest.keyClicks(self.browser.filter, "E")
        self.QtTest.QTest.keyClick(self.browser.filter, self.QtCore.Qt.Key_Delete)
        self.assertEqual(self.browser.filter.text(), "E")
        for panel, view in self.panels:
            self.select(panel, self.objects[1])
            self.press(view, self.QtCore.Qt.Key_Return, self.QtCore.Qt.ControlModifier)
            self.press(view, self.QtCore.Qt.Key_Delete, self.QtCore.Qt.ShiftModifier)
        self.assertEqual(self.commands, [])
        self.assertEqual(self.edited, [])


if __name__ == "__main__":
    unittest.main()
