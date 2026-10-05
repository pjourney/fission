# SPDX-License-Identifier: MIT
"""Command-search behavior and real Qt dispatch; no native CAD GUI is started."""
import json
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "Mod" / "Fission" / "fission"
if "fission" not in sys.modules:
    package = types.ModuleType("fission")
    package.__path__ = [str(PACKAGE)]
    sys.modules["fission"] = package

from fission.search import (SEARCH_HISTORY_KEY, SEARCH_HISTORY_SCHEMA,
                           SEARCH_RECENT_LIMIT, normalize_search_text,
                           normalize_recents, rank_commands, read_recents,
                           write_recents)


class Parameters:
    def __init__(self, value=""):
        self.data = {SEARCH_HISTORY_KEY: value} if value else {}
        self.writes = []

    def GetString(self, name, default=""):
        return self.data.get(name, default)

    def SetString(self, name, value):
        self.data[name] = value
        self.writes.append((name, value))


class SearchRankingTests(unittest.TestCase):
    def test_query_normalizes_case_and_whitespace(self):
        self.assertEqual(normalize_search_text("  Create \t SKETCH\n"), "create sketch")
        catalog = [{"id": "A_Plane", "title": "Create Sketch Plane", "context": "model"},
                   {"id": "B_Sketch", "title": "Create Sketch", "context": "model"}]
        self.assertEqual(rank_commands(catalog, "  CREATE   sketch ")[0]["id"], "B_Sketch")

    def test_native_ids_are_searchable_as_words(self):
        entry = {"id": "Sketcher_CreateLine", "title": "Segment", "context": "sketch"}
        self.assertEqual(rank_commands([entry], "sketcher create line"), [entry])
        self.assertEqual(rank_commands([entry], "Sketcher_CreateLine"), [entry])

    def test_mixed_case_query_is_not_split_into_camel_case_words(self):
        entry = {"id": "Fission_Fillet", "title": "Fillet", "context": "model"}
        self.assertEqual(normalize_search_text("fIlLeT"), "fillet")
        self.assertEqual(rank_commands([entry], "fIlLeT"), [entry])

    def test_query_terms_can_cross_title_and_aliases(self):
        entry = {"id": "Fission_Extrude", "title": "Extrude", "aliases": ["pad", "push pull"],
                 "context": "model"}
        self.assertEqual(rank_commands([entry], "PULL extrude"), [entry])
        self.assertEqual(rank_commands([entry], "extrude unavailable"), [])

    def test_exact_name_wins_over_foreign_context(self):
        catalog = [{"id": "Sketcher_Dimension", "title": "Sketch Dimension", "context": "sketch"},
                   {"id": "TechDraw_Dimension", "title": "Dimension", "context": "drawing"}]
        self.assertEqual(rank_commands(catalog, "dimension", "sketch")[0]["id"], "TechDraw_Dimension")

    def test_context_breaks_equal_relevance(self):
        catalog = [{"id": "Drawing_Dimension", "title": "Dimension", "context": "drawing"},
                   {"id": "Sketch_Dimension", "title": "Dimension", "context": "sketch"}]
        self.assertEqual(rank_commands(catalog, "dimension", "sketch")[0]["id"], "Sketch_Dimension")

    def test_empty_query_context_then_recency(self):
        catalog = [{"id": "A_Create", "title": "A Create", "context": "model"},
                   {"id": "Z_Inspect", "title": "Z Inspect", "context": "model"},
                   {"id": "Drawing_New", "title": "Drawing", "context": "drawing"}]
        result = rank_commands(catalog, "", "model", recent_ids=["Z_Inspect", "Drawing_New"])
        self.assertEqual([row["id"] for row in result], ["Z_Inspect", "A_Create", "Drawing_New"])

    def test_recent_command_does_not_override_exact_query(self):
        catalog = [{"id": "A_Extrusion", "title": "Extrude Advanced", "context": "model"},
                   {"id": "B_Extrusion", "title": "Extrude", "context": "model"}]
        self.assertEqual(rank_commands(catalog, "extrude", recent_ids=["A_Extrusion"])[0]["id"],
                         "B_Extrusion")

    def test_fission_wrapper_wins_identical_title(self):
        catalog = [{"id": "PartDesign_Pad", "title": "Extrude", "context": "model"},
                   {"id": "Fission_Extrude", "title": "Extrude", "context": "model"}]
        self.assertEqual(rank_commands(catalog, "extrude")[0]["id"], "Fission_Extrude")

    def test_ranking_keeps_input_entries_and_catalog_unchanged(self):
        catalog = [{"id": "B_Test", "title": "Beta", "aliases": "b test", "context": ["model", "mesh"]},
                   {"id": "A_Test", "title": "Alpha", "aliases": ["a"], "context": "all"}]
        before = json.dumps(catalog, sort_keys=True)
        result = rank_commands(catalog, "", "model")
        self.assertEqual(json.dumps(catalog, sort_keys=True), before)
        self.assertTrue(all(any(entry is original for original in catalog) for entry in result))


class SearchHistoryTests(unittest.TestCase):
    def test_ids_are_safe_deduplicated_and_bounded(self):
        valid = ["Native_Command%d" % value for value in range(SEARCH_RECENT_LIMIT + 5)]
        ids = [None, 4, "", "Part Offset", "X;import_os", "../Escape", "9Command",
               valid[0], valid[0]] + valid[1:]
        self.assertEqual(normalize_recents(ids), valid[:SEARCH_RECENT_LIMIT])

    def test_scalar_history_does_not_become_characters(self):
        for value in (None, 5, "Std_New", {"Std_New": 1}):
            with self.subTest(value=value):
                self.assertEqual(normalize_recents(value), [])

    def test_persistence_round_trip_and_exact_schema(self):
        parameters = Parameters()
        write_recents(parameters, ["Fission_Extrude", "Std_New", "Fission_Extrude"])
        self.assertEqual(read_recents(parameters), ["Fission_Extrude", "Std_New"])
        self.assertEqual(json.loads(parameters.data[SEARCH_HISTORY_KEY]),
                         {"schema_version": SEARCH_HISTORY_SCHEMA,
                          "commands": ["Fission_Extrude", "Std_New"]})

    def test_malformed_and_unknown_schemas_start_empty(self):
        for value in ("broken", "[]", "null", '{"schema_version":2,"commands":["Std_New"]}',
                      '{"schema_version":true,"commands":["Std_New"]}',
                      '{"schema_version":1.0,"commands":["Std_New"]}',
                      '{"commands":["Std_New"]}'):
            with self.subTest(value=value):
                parameters = Parameters(value)
                self.assertEqual(read_recents(parameters), [])
                self.assertEqual(parameters.writes, [])

    def test_loaded_history_validates_each_entry(self):
        parameters = Parameters(json.dumps({"schema_version": 1,
                                             "commands": ["Std_New", "bad id", "Std_New", 7, "Std_Save"]}))
        self.assertEqual(read_recents(parameters), ["Std_New", "Std_Save"])


@unittest.skipUnless(os.environ.get("FISSION_QT_TESTS") == "1",
                     "Set FISSION_QT_TESTS=1 with a PySide runtime")
class NativeQtSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6 import QtCore, QtWidgets, QtTest
        from fission.search import SearchDialog
        cls.QtCore, cls.QtWidgets, cls.QtTest = QtCore, QtWidgets, QtTest
        cls.SearchDialog = SearchDialog
        cls.application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.main = self.QtWidgets.QMainWindow()
        panel = self.QtWidgets.QWidget()
        layout = self.QtWidgets.QVBoxLayout(panel)
        self.canvas = self.QtWidgets.QWidget()
        self.canvas.setMinimumHeight(80)
        self.canvas.setFocusPolicy(self.QtCore.Qt.StrongFocus)
        self.editor = self.QtWidgets.QLineEdit()
        layout.addWidget(self.canvas)
        layout.addWidget(self.editor)
        self.main.setCentralWidget(panel)
        self.current_context = "model"
        self.owner_token = ("Design", "View1")
        self.parameters = Parameters()
        self.catalog = [{"id": "A_Ready", "title": "Alpha", "context": "model"},
                        {"id": "B_Blocked", "title": "Beta", "context": "model"},
                        {"id": "C_Ready", "title": "Charlie", "context": "model"}]
        self.available = {"A_Ready": True, "B_Blocked": False, "C_Ready": True}
        self.calls = []
        self.notifications = []
        self.refreshes = 0
        self.execute_result = True
        self.execute_error = None
        self.controller = types.SimpleNamespace(
            context=lambda: self.current_context,
            command_context_token=lambda: self.owner_token,
            command_focus_widget=lambda: self.canvas,
            command_catalog=lambda: list(self.catalog),
            command_available=lambda command, refresh=False: self.available.get(command, True),
            refresh_command_state=self.refresh_state,
            settings=self.parameters,
            execute=self.execute,
            notify=self.notifications.append,
            shortcuts=types.SimpleNamespace(shortcut_for=lambda command, context: "Ctrl+A" if command == "A_Ready" else ""))
        self.main.show()
        self.main.activateWindow()
        self.canvas.setFocus()
        self.application.processEvents()
        self.dialog = self.SearchDialog(self.controller, self.main)

    def tearDown(self):
        self.dialog.close()
        self.dialog.deleteLater()
        self.main.close()
        self.main.deleteLater()
        self.application.processEvents()

    def refresh_state(self):
        self.refreshes += 1

    def execute(self, command):
        self.calls.append({"command": command,
                           "focus": self.application.focusWidget(),
                           "search_visible": self.dialog.isVisible(),
                           "history_before": read_recents(self.parameters)})
        if self.execute_error:
            raise self.execute_error
        return self.execute_result

    def show_search(self, query=""):
        self.dialog.show()
        self.application.processEvents()
        self.dialog.input.setText(query)
        self.application.processEvents()

    def item(self, command):
        for index in range(self.dialog.results.topLevelItemCount()):
            item = self.dialog.results.topLevelItem(index)
            if item.data(0, self.QtCore.Qt.UserRole) == command:
                return item
        self.fail("Missing command result: " + command)

    def selected_id(self):
        return self.dialog.results.currentItem().data(0, self.QtCore.Qt.UserRole)

    def press(self, key, widget=None):
        widget = widget or self.dialog.input
        self.QtTest.QTest.keyClick(widget, key)
        self.application.processEvents()

    def test_all_matching_commands_remain_visible(self):
        self.catalog = [{"id": "Tool_Command%d" % value, "title": "Tool %03d" % value,
                         "context": "model"} for value in range(140)]
        self.show_search("tool")
        self.assertEqual(self.dialog.results.topLevelItemCount(), 140)
        self.assertIsNotNone(self.item("Tool_Command139"))

    def test_availability_and_shortcut_are_visible(self):
        self.show_search()
        self.assertEqual(self.item("A_Ready").text(1), "Ctrl+A")
        self.assertEqual(self.item("A_Ready").text(3), "Ready")
        self.assertEqual(self.item("B_Blocked").text(3), "Unavailable")
        self.assertTrue(self.item("A_Ready").flags() & self.QtCore.Qt.ItemIsEnabled)
        self.assertFalse(self.item("B_Blocked").flags() & self.QtCore.Qt.ItemIsEnabled)
        self.assertLess(self.dialog.results.indexOfTopLevelItem(self.item("A_Ready")),
                        self.dialog.results.indexOfTopLevelItem(self.item("B_Blocked")))
        self.assertGreater(self.refreshes, 0)

    def test_disabled_command_cannot_dispatch_or_change_history(self):
        self.show_search()
        self.dialog._activate(self.item("B_Blocked"))
        self.application.processEvents()
        self.assertEqual(self.calls, [])
        self.assertEqual(read_recents(self.parameters), [])
        self.assertTrue(self.dialog.isVisible())

    def test_unavailable_exact_result_keeps_rank_but_initial_selection_is_ready(self):
        self.catalog = [{"id": "B_Blocked", "title": "Tool", "context": "model"},
                        {"id": "A_Ready", "title": "Tool Advanced", "context": "model"}]
        self.show_search("tool")
        self.assertEqual(self.dialog.results.topLevelItem(0).data(0, self.QtCore.Qt.UserRole), "B_Blocked")
        self.assertEqual(self.selected_id(), "A_Ready")

    def test_keyboard_skips_disabled_results_and_handles_boundaries(self):
        self.show_search()
        self.dialog.results.setCurrentItem(self.item("A_Ready"))
        self.press(self.QtCore.Qt.Key_Down)
        self.assertEqual(self.selected_id(), "C_Ready")
        self.press(self.QtCore.Qt.Key_Down)
        self.assertEqual(self.selected_id(), "C_Ready")
        self.press(self.QtCore.Qt.Key_Up)
        self.assertEqual(self.selected_id(), "A_Ready")
        self.press(self.QtCore.Qt.Key_Up)
        self.assertEqual(self.selected_id(), "A_Ready")

    def test_result_tree_keyboard_can_dispatch_enabled_selection(self):
        self.show_search()
        self.dialog.results.setCurrentItem(self.item("C_Ready"))
        self.dialog.results.setFocus()
        self.application.processEvents()
        self.press(self.QtCore.Qt.Key_Return, self.dialog.results)
        self.assertEqual([call["command"] for call in self.calls], ["C_Ready"])
        self.assertEqual(read_recents(self.parameters), ["C_Ready"])

    def test_queued_dispatch_restores_canvas_focus_before_execution(self):
        self.show_search("alpha")
        self.dialog._activate(self.item("A_Ready"))
        self.assertEqual(self.calls, [])
        self.assertFalse(self.dialog.isVisible())
        self.application.processEvents()
        self.assertEqual([call["command"] for call in self.calls], ["A_Ready"])
        self.assertIs(self.calls[0]["focus"], self.canvas)
        self.assertFalse(self.calls[0]["search_visible"])
        self.assertEqual(self.calls[0]["history_before"], [])
        self.assertEqual(read_recents(self.parameters), ["A_Ready"])

    def test_context_change_between_close_and_dispatch_is_rejected(self):
        self.show_search("alpha")
        self.dialog._activate(self.item("A_Ready"))
        self.current_context = "sketch"
        self.application.processEvents()
        self.assertEqual(self.calls, [])
        self.assertEqual(read_recents(self.parameters), [])

    def test_design_changed_while_search_was_open_is_rejected(self):
        self.show_search("alpha")
        self.owner_token = ("OtherDesign", "View1")
        self.dialog._activate(self.item("A_Ready"))
        self.application.processEvents()
        self.assertEqual(self.calls, [])
        self.assertEqual(read_recents(self.parameters), [])

    def test_query_after_design_change_closes_before_native_refresh(self):
        self.show_search("alpha")
        refreshes = self.refreshes
        self.owner_token = ("OtherDesign", "View1")
        self.dialog.input.setText("charlie")
        self.application.processEvents()
        self.assertFalse(self.dialog.isVisible())
        self.assertEqual(self.refreshes, refreshes)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.parameters.writes, [])

    def test_oserror_from_closed_owner_during_query_is_stale(self):
        self.show_search("alpha")
        refreshes = self.refreshes

        def disposed_owner():
            raise OSError("Document has been disposed")

        self.controller.command_context_token = disposed_owner
        self.dialog.input.setText("charlie")
        self.application.processEvents()
        self.assertFalse(self.dialog.isVisible())
        self.assertEqual(self.refreshes, refreshes)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.parameters.writes, [])

    def test_oserror_from_closed_owner_cancels_queued_dispatch(self):
        self.show_search("alpha")
        self.dialog._activate(self.item("A_Ready"))

        def disposed_owner():
            raise OSError("Document has been disposed")

        self.controller.command_context_token = disposed_owner
        self.application.processEvents()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.parameters.writes, [])

    def test_popup_arriving_before_queued_dispatch_keeps_command_inactive(self):
        self.show_search("alpha")
        self.dialog._activate(self.item("A_Ready"))
        popup = self.QtWidgets.QMenu(self.main)
        popup.addAction("Native context command")
        try:
            popup.popup(self.main.mapToGlobal(self.QtCore.QPoint(20, 20)))
            self.assertIs(self.application.activePopupWidget(), popup)
            self.application.processEvents()
            self.assertEqual(self.calls, [])
            self.assertEqual(self.parameters.writes, [])
            self.assertTrue(popup.isVisible())
        finally:
            popup.close()
            popup.deleteLater()
            self.application.processEvents()
        self.assertEqual(self.calls, [])

    def test_modal_arriving_before_queued_dispatch_keeps_command_inactive(self):
        self.show_search("alpha")
        self.dialog._activate(self.item("A_Ready"))
        modal = self.QtWidgets.QDialog(self.main)
        modal.setWindowModality(self.QtCore.Qt.ApplicationModal)
        try:
            modal.show()
            self.assertIs(self.application.activeModalWidget(), modal)
            self.application.processEvents()
            self.assertEqual(self.calls, [])
            self.assertEqual(self.parameters.writes, [])
            self.assertTrue(modal.isVisible())
        finally:
            modal.close()
            modal.deleteLater()
            self.application.processEvents()
        self.assertEqual(self.calls, [])

    def test_observed_selection_followup_refresh_stops_on_close(self):
        from fission import shortcuts
        observers = []
        selection = types.SimpleNamespace(addObserver=observers.append,
                                          removeObserver=observers.remove)
        checks = []

        def available(command, refresh=False):
            checks.append(command)
            return self.available.get(command, True)

        self.controller.command_available = available
        with patch.object(shortcuts, "Gui", types.SimpleNamespace(Selection=selection)):
            self.show_search()
            self.assertEqual(observers, [self.dialog])
            checks_before = len(checks)
            self.available["A_Ready"] = False
            for observer in list(observers):
                observer.addSelection("Design", "Box", "Face1", (0, 0, 0))
                observer.removeSelection("Design", "Box", "Face1")
                observer.clearSelection("Design")
            self.assertTrue(self.dialog._selection_refresh_timer.isActive())
            self.assertEqual(len(checks), checks_before)
            elapsed = self.QtCore.QElapsedTimer()
            elapsed.start()
            while len(checks) == checks_before and elapsed.elapsed() < 1000:
                self.QtTest.QTest.qWait(10)
            self.assertEqual(len(checks), checks_before + len(self.catalog))
            self.assertEqual(self.item("A_Ready").text(3), "Unavailable")
            self.assertFalse(self.dialog._selection_refresh_timer.isActive())

            self.dialog.addSelection("Design", "Box", "Face1", (0, 0, 0))
            self.assertTrue(self.dialog._selection_refresh_timer.isActive())
            checks_before = len(checks)
            self.dialog.close()
            self.assertEqual(observers, [])
            self.assertFalse(self.dialog._selection_refresh_timer.isActive())
            # A native observer callback already in flight must also stay quiet.
            self.dialog.clearSelection("Design")
            self.QtTest.QTest.qWait(self.dialog._selection_refresh_timer.interval() + 25)
            self.assertEqual(len(checks), checks_before)
            self.assertFalse(self.dialog._selection_refresh_timer.isActive())

    def test_disposed_native_command_becomes_unavailable_and_can_recover(self):
        self.show_search("alpha")

        def disposed_command(command, refresh=False):
            raise OSError("Native command handle has been disposed")

        self.controller.command_available = disposed_command
        self.dialog.refresh_availability()
        self.assertTrue(self.dialog.isVisible())
        self.assertEqual(self.item("A_Ready").text(3), "Unavailable")
        self.press(self.QtCore.Qt.Key_Return)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.parameters.writes, [])
        self.controller.command_available = lambda command, refresh=False: True
        self.dialog.refresh_availability()
        self.assertEqual(self.item("A_Ready").text(3), "Ready")

    def test_disposed_native_state_disables_results_until_healthy_refresh(self):
        self.show_search()

        def disposed_state():
            raise OSError("Native GUI state has been disposed")

        self.controller.refresh_command_state = disposed_state
        self.dialog.refresh_availability()
        self.assertTrue(self.dialog.isVisible())
        for command in self.available:
            self.assertEqual(self.item(command).text(3), "Unavailable")
        self.press(self.QtCore.Qt.Key_Return)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.parameters.writes, [])
        self.controller.refresh_command_state = self.refresh_state
        self.dialog.refresh_availability()
        self.assertEqual(self.item("A_Ready").text(3), "Ready")
        self.assertEqual(self.item("C_Ready").text(3), "Ready")
        self.assertEqual(self.item("B_Blocked").text(3), "Unavailable")

    def test_document_or_view_change_between_close_and_dispatch_is_rejected(self):
        for token in (("OtherDesign", "View1"), ("Design", "View2"), None):
            with self.subTest(token=token):
                self.owner_token = ("Design", "View1")
                self.show_search("alpha")
                self.dialog._activate(self.item("A_Ready"))
                self.owner_token = token
                self.application.processEvents()
                self.assertEqual(self.calls, [])
                self.assertEqual(read_recents(self.parameters), [])

    def test_newly_unavailable_command_is_rechecked_before_dispatch(self):
        self.show_search("alpha")
        self.dialog._activate(self.item("A_Ready"))
        self.available["A_Ready"] = False
        self.application.processEvents()
        self.assertEqual(self.calls, [])
        self.assertEqual(read_recents(self.parameters), [])

    def test_reopening_search_cancels_the_previous_queued_command(self):
        self.show_search("alpha")
        self.dialog._activate(self.item("A_Ready"))
        self.dialog.show()
        self.application.processEvents()
        self.assertEqual(self.calls, [])
        self.assertEqual(read_recents(self.parameters), [])
        self.assertTrue(self.dialog.isVisible())

    def test_failed_and_exceptional_dispatch_are_not_recent(self):
        for result, error in ((False, None), (None, None), (True, ValueError("native failure"))):
            with self.subTest(result=result, error=error):
                self.execute_result, self.execute_error = result, error
                self.show_search("alpha")
                self.dialog._activate(self.item("A_Ready"))
                self.application.processEvents()
                self.assertEqual(read_recents(self.parameters), [])
                self.assertEqual(self.parameters.writes, [])
        self.assertEqual(len(self.calls), 3)
        self.assertTrue(any("native failure" in message for message in self.notifications))

    def test_successful_recents_persist_and_are_most_recent_first(self):
        for command, query in (("A_Ready", "alpha"), ("C_Ready", "charlie"), ("A_Ready", "alpha")):
            self.show_search(query)
            self.dialog._activate(self.item(command))
            self.application.processEvents()
        self.assertEqual(read_recents(self.parameters), ["A_Ready", "C_Ready"])
        reopened = self.SearchDialog(self.controller, self.main)
        try:
            reopened.show()
            self.application.processEvents()
            self.assertEqual(reopened.results.topLevelItem(0).data(0, self.QtCore.Qt.UserRole), "A_Ready")
        finally:
            reopened.close()
            reopened.deleteLater()

    def test_escape_returns_to_source_editor_without_dispatch(self):
        self.editor.setFocus()
        self.application.processEvents()
        self.show_search("alpha")
        self.press(self.QtCore.Qt.Key_Escape)
        self.assertFalse(self.dialog.isVisible())
        self.assertIs(self.application.focusWidget(), self.editor)
        self.assertEqual(self.calls, [])

    def test_refresh_updates_availability_without_clearing_query(self):
        self.show_search("alpha")
        self.available["A_Ready"] = False
        self.dialog.refresh_availability()
        self.assertEqual(self.dialog.input.text(), "alpha")
        self.assertEqual(self.dialog.results.topLevelItemCount(), 1)
        self.assertEqual(self.item("A_Ready").text(3), "Unavailable")
        self.press(self.QtCore.Qt.Key_Return)
        self.assertEqual(self.calls, [])

    def test_no_matches_enter_and_arrows_are_safe(self):
        self.show_search("unfindable")
        for key in (self.QtCore.Qt.Key_Down, self.QtCore.Qt.Key_Up, self.QtCore.Qt.Key_Return):
            self.press(key)
        self.assertEqual(self.dialog.results.topLevelItemCount(), 0)
        self.assertEqual(self.calls, [])
        self.assertTrue(self.dialog.isVisible())


if __name__ == "__main__":
    unittest.main()
