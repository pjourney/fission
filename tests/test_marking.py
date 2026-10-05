# SPDX-License-Identifier: MIT
"""Pure marking-menu configuration and geometry tests; no CAD or Qt imports."""

import copy
import json
import math
from pathlib import Path
import re
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "Mod" / "Fission" / "fission"
if "fission" not in sys.modules:
    package = types.ModuleType("fission")
    package.__path__ = [str(PACKAGE)]
    sys.modules["fission"] = package

from fission.marking_config import (CONTEXTS, DIRECTIONS, defaults, normalize_config,
                                   read_config, write_config, wedge_at)


class Parameters:
    def __init__(self, value=""):
        self.data = {"MarkingMenu": value} if value else {}
        self.reads = []
        self.writes = []

    def GetString(self, name, default):
        self.reads.append((name, default))
        return self.data.get(name, default)

    def SetString(self, name, value):
        self.writes.append((name, value))
        self.data[name] = value


class ConfigurationTests(unittest.TestCase):
    def assertFactorySlots(self, config):
        self.assertEqual(config["version"], 1)
        self.assertIs(type(config["enabled"]), bool)
        self.assertEqual(set(config["slots"]), set(CONTEXTS))
        for context in CONTEXTS:
            self.assertEqual(config["slots"][context], defaults(context))

    def test_contexts_and_compass_order_are_stable(self):
        self.assertEqual(CONTEXTS, ("model", "sketch", "assembly", "surface", "mesh", "drawing", "cam"))
        self.assertEqual(DIRECTIONS, ("N", "NE", "E", "SE", "S", "SW", "W", "NW"))

    def test_each_factory_context_has_eight_safe_command_slots(self):
        identifier = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
        for context in CONTEXTS:
            with self.subTest(context=context):
                slots = defaults(context)
                self.assertIsInstance(slots, list)
                self.assertEqual(len(slots), 8)
                self.assertTrue(all(isinstance(value, str) and identifier.fullmatch(value) for value in slots))

    def test_factory_lists_are_independent_and_cannot_be_mutated_globally(self):
        for context in CONTEXTS:
            with self.subTest(context=context):
                expected = defaults(context)
                changed = defaults(context)
                self.assertIsNot(changed, expected)
                changed[0] = "User_CustomCommand"
                changed.append("Another_Command")
                self.assertEqual(defaults(context), expected)

    def test_unknown_context_uses_model_defaults_without_changing_known_contexts(self):
        fallback = defaults("future_workspace")
        self.assertEqual(fallback, defaults("model"))
        fallback[0] = "Custom_FutureCommand"
        self.assertNotEqual(defaults("model")[0], "Custom_FutureCommand")

    def test_missing_and_non_object_config_use_complete_factory_slots(self):
        for value in (None, [], 0, 1, True, False, "", "{}"):
            with self.subTest(value=value):
                self.assertFactorySlots(normalize_config(value))

    def test_enabled_accepts_actual_booleans_without_string_truthiness(self):
        for value in (True, False):
            with self.subTest(value=value):
                self.assertIs(normalize_config({"version": 1, "enabled": value})["enabled"], value)
        factory_enabled = normalize_config(None)["enabled"]
        for value in (None, 0, 1, "false", "true", [], {}):
            with self.subTest(malformed=value):
                self.assertIs(normalize_config({"version": 1, "enabled": value})["enabled"], factory_enabled)

    def test_unsupported_schema_versions_fall_back_without_interpreting_future_data(self):
        factory = normalize_config(None)
        for version in (0, 2, -1, 1.0, "1", None, True, False):
            with self.subTest(version=version):
                value = {"version": version, "enabled": not factory["enabled"],
                         "slots": {"model": ["Future_CustomCommand"] * 8}}
                self.assertEqual(normalize_config(value), factory)

    def test_missing_version_accepts_current_fields(self):
        value = {"enabled": False, "slots": {"model": ["Custom_ModelCommand"] * 8}}
        config = normalize_config(value)
        self.assertEqual(config["version"], 1)
        self.assertFalse(config["enabled"])
        self.assertEqual(config["slots"]["model"], value["slots"]["model"])

    def test_unknown_commands_and_intentionally_empty_slots_are_preserved(self):
        slots = ["Uninstalled_Addon_Command9", "", "_PrivateCommand", "a", "A_9", "Std_Delete", "MissingFeature", ""]
        config = normalize_config({"version": 1, "slots": {"assembly": slots}})
        self.assertEqual(config["slots"]["assembly"], slots)
        self.assertEqual(config["slots"]["model"], defaults("model"))

    def test_unsafe_or_non_string_identifiers_fall_back_per_slot(self):
        invalid = [None, 5, True, {}, [], "9Command", "Unsafe.Command", "Hyphen-Command",
                   "Std_Delete ", " Std_Delete", "Std_Delete\n", "Éxtrude", "Command/Path",
                   "Gui.runCommand('Std_Delete')", "Std_Delete;import os"]
        factory = defaults("model")
        for value in invalid:
            with self.subTest(value=value):
                slots = ["Custom_SafeCommand"] * 8
                slots[3] = value
                config = normalize_config({"version": 1, "slots": {"model": slots}})
                expected = ["Custom_SafeCommand"] * 8
                expected[3] = factory[3]
                self.assertEqual(config["slots"]["model"], expected)

    def test_short_lists_keep_valid_slots_and_fill_the_remaining_directions(self):
        config = normalize_config({"version": 1, "slots": {"sketch": ["Custom_Line", ""]}})
        self.assertEqual(config["slots"]["sketch"], ["Custom_Line", ""] + defaults("sketch")[2:])

    def test_long_lists_do_not_create_extra_directions(self):
        slots = ["Custom_Command" + str(index) for index in range(11)]
        config = normalize_config({"version": 1, "slots": {"drawing": slots}})
        self.assertEqual(config["slots"]["drawing"], slots[:8])

    def test_malformed_slot_containers_and_unknown_contexts_do_not_leak(self):
        for malformed in (None, "Std_Delete", 4, True, [], {"model": "Std_Delete"},
                          {"model": None}, {"model": {}}, {"unrecognized_workspace": ["Std_Delete"] * 8}):
            with self.subTest(slots=malformed):
                self.assertFactorySlots(normalize_config({"version": 1, "slots": malformed}))

    def test_normalization_does_not_alias_input_or_factory_lists(self):
        value = {"version": 1, "enabled": False, "slots": {"model": ["Custom_Command"] * 8}}
        original = copy.deepcopy(value)
        first = normalize_config(value)
        second = normalize_config(value)
        self.assertEqual(value, original)
        self.assertIsNot(first["slots"]["model"], value["slots"]["model"])
        self.assertIsNot(first["slots"]["sketch"], second["slots"]["sketch"])
        first["slots"]["model"][0] = "Changed_Command"
        first["slots"]["sketch"][0] = "Changed_SketchCommand"
        self.assertEqual(value, original)
        self.assertEqual(second, normalize_config(value))
        self.assertEqual(second["slots"]["sketch"], defaults("sketch"))


class PersistenceTests(unittest.TestCase):
    def test_read_uses_the_single_marking_menu_string_key(self):
        settings = Parameters()
        config = read_config(settings)
        self.assertEqual(settings.reads, [("MarkingMenu", "")])
        self.assertEqual(config, normalize_config(None))
        self.assertEqual(settings.writes, [])

    def test_invalid_json_and_non_object_json_are_safe_factory_fallbacks(self):
        for text in ("{", "null", "[]", "17", '"text"', "true", " "):
            with self.subTest(text=text):
                settings = Parameters(text)
                self.assertEqual(read_config(settings), normalize_config(None))
                self.assertEqual(settings.writes, [])

    def test_disabled_custom_slots_survive_a_json_write_and_restart_read(self):
        slots = ["Missing_Addon_Command", "", "Std_Delete", "Fission_Extrude", "", "Measure_Extension", "_Custom", "MyCommand9"]
        value = {"version": 1, "enabled": False, "slots": {"model": slots}}
        settings = Parameters()
        write_config(settings, value)
        self.assertEqual(len(settings.writes), 1)
        key, encoded = settings.writes[0]
        self.assertEqual(key, "MarkingMenu")
        self.assertIsInstance(encoded, str)
        self.assertEqual(json.loads(encoded), normalize_config(value))
        restarted = Parameters(encoded)
        self.assertEqual(read_config(restarted), normalize_config(value))
        self.assertFalse(read_config(restarted)["enabled"])
        self.assertEqual(read_config(restarted)["slots"]["model"], slots)

    def test_partial_saved_preferences_are_completed_without_overwriting_the_saved_text(self):
        encoded = json.dumps({"version": 1, "slots": {"mesh": ["Mesh_CustomRepair"]}})
        settings = Parameters(encoded)
        config = read_config(settings)
        self.assertEqual(config["slots"]["mesh"], ["Mesh_CustomRepair"] + defaults("mesh")[1:])
        self.assertEqual(settings.data["MarkingMenu"], encoded)
        self.assertEqual(settings.writes, [])

    def test_write_normalizes_malformed_values_before_serializing(self):
        value = {"version": 1, "enabled": "false", "slots": {"cam": [None, "CAM_CustomPath", ""]}}
        original = copy.deepcopy(value)
        settings = Parameters()
        write_config(settings, value)
        self.assertEqual(json.loads(settings.data["MarkingMenu"]), normalize_config(value))
        self.assertEqual(value, original)


class WedgeTests(unittest.TestCase):
    @staticmethod
    def point(angle, distance=100):
        radians = math.radians(angle)
        return distance * math.sin(radians), -distance * math.cos(radians)

    def test_compass_centers_are_clockwise_from_screen_north(self):
        for index, direction in enumerate(DIRECTIONS):
            with self.subTest(direction=direction):
                self.assertEqual(wedge_at(*self.point(index * 45)), index)

    def test_center_and_inside_deadzone_have_no_command(self):
        for point in ((0, 0), (27.999, 0), (0, -27.999), (15, 15), (-15, -15)):
            with self.subTest(point=point):
                self.assertIsNone(wedge_at(*point))

    def test_radius_limits_are_circular_and_include_the_annulus_edges(self):
        self.assertEqual(wedge_at(0, -28), 0)
        self.assertEqual(wedge_at(0, -160), 0)
        self.assertIsNone(wedge_at(0, -160.0001))
        self.assertIsNone(wedge_at(120, 120))
        self.assertEqual(wedge_at(100, 100), 3)

    def test_both_sides_of_every_sector_boundary_and_north_wraparound(self):
        for index in range(8):
            boundary = index * 45 + 22.5
            with self.subTest(boundary=boundary):
                self.assertEqual(wedge_at(*self.point(boundary - 0.00001)), index)
                self.assertEqual(wedge_at(*self.point(boundary + 0.00001)), (index + 1) % 8)

    def test_custom_radius_and_deadzone_change_only_the_hit_annulus(self):
        self.assertEqual(wedge_at(0, -12, radius=80, deadzone=12), 0)
        self.assertEqual(wedge_at(-80, 0, radius=80, deadzone=12), 6)
        self.assertIsNone(wedge_at(0, -11.999, radius=80, deadzone=12))
        self.assertIsNone(wedge_at(0, -80.001, radius=80, deadzone=12))
        self.assertIsNone(wedge_at(60, 60, radius=80, deadzone=12))


if __name__ == "__main__":
    unittest.main()
