# SPDX-License-Identifier: MIT
"""Real Qt regressions for command resources and the original SVG glyphs."""
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
class CommandIconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6 import QtGui, QtWidgets
        from fission import icons
        cls.QtGui = QtGui
        cls.application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        cls.icons = icons

    def setUp(self):
        self.commands = {}
        self.resources = {}
        self.requests = []

        def native_icon(name):
            self.requests.append(name)
            return self.resources.get(name, self.QtGui.QIcon())

        native = types.SimpleNamespace(Command=types.SimpleNamespace(get=self.commands.get),
                                       getIcon=native_icon)
        self.gui_patch = patch.object(self.icons, "Gui", native)
        self.gui_patch.start()
        self.addCleanup(self.gui_patch.stop)

    def command(self, pixmap, actions=()):
        return types.SimpleNamespace(getInfo=lambda: {"pixmap": pixmap},
                                     getAction=lambda: actions)

    def painted_icon(self, color):
        pixmap = self.QtGui.QPixmap(26, 26)
        pixmap.fill(self.QtGui.QColor(color))
        return self.QtGui.QIcon(pixmap)

    def test_native_svg_suffix_reaches_exact_cache_name_without_an_action(self):
        native = self.painted_icon("#8e48ba")
        self.commands["Mesh_TestResource"] = self.command("mesh-test-resource.svg")
        self.resources["mesh-test-resource.svg"] = native

        resolved = self.icons.resolve("Mesh_TestResource")

        self.assertEqual(self.requests, ["mesh-test-resource.svg"])
        self.assertEqual(resolved.cacheKey(), native.cacheKey())
        self.assertTrue(self.icons.has_pixels(resolved))

    def test_wrapper_uses_backend_actual_pixmap_instead_of_fabricated_name(self):
        native = self.painted_icon("#b5574e")
        self.commands["Std_Measure"] = self.command("native-measurement-tool.svg")
        self.commands["Fission_Measure"] = self.command("Std_Measure")
        self.resources["native-measurement-tool.svg"] = native

        resolved = self.icons.resolve("Fission_Measure")

        self.assertEqual(self.requests, ["native-measurement-tool.svg"])
        self.assertEqual(resolved.cacheKey(), native.cacheKey())

    def test_transparent_non_null_native_icon_falls_back_to_visible_symbol(self):
        transparent = self.painted_icon("#00000000")
        self.assertFalse(transparent.isNull())
        self.assertFalse(transparent.pixmap(26, 26).isNull())
        self.assertFalse(self.icons.has_pixels(transparent))
        self.commands["Test_TransparentResource"] = self.command("fission-test-transparent.svg")
        self.resources["fission-test-transparent.svg"] = transparent

        resolved = self.icons.resolve("Test_TransparentResource")

        expected = self.QtGui.QIcon(str(ROOT / "Mod" / "Fission" / "resources" / "icons" / "command.svg"))
        self.assertTrue(self.icons.has_pixels(resolved))
        self.assertEqual(resolved.pixmap(26, 26).toImage(), expected.pixmap(26, 26).toImage())

    def test_later_native_registration_replaces_earlier_missing_fallback(self):
        first = self.icons.resolve("Test_LazyResource")
        self.assertTrue(self.icons.has_pixels(first))
        native = self.painted_icon("#7561d2")
        self.commands["Test_LazyResource"] = self.command("fission-test-lazy.svg")
        self.resources["fission-test-lazy.svg"] = native

        resolved = self.icons.resolve("Test_LazyResource")

        self.assertEqual(self.requests, ["fission-test-lazy.svg"])
        self.assertEqual(resolved.cacheKey(), native.cacheKey())
        self.assertNotEqual(first.pixmap(26, 26).toImage(), resolved.pixmap(26, 26).toImage())

    def test_native_action_supplies_icon_when_resource_does_not_render(self):
        native = self.painted_icon("#675099")
        action = self.QtGui.QAction()
        action.setIcon(native)
        self.commands["Test_ActionResource"] = self.command("fission-test-missing-action.svg", [action])

        resolved = self.icons.resolve("Test_ActionResource")

        self.assertEqual(self.requests, ["fission-test-missing-action.svg"])
        self.assertEqual(resolved.cacheKey(), native.cacheKey())
        self.assertTrue(self.icons.has_pixels(resolved))

    def test_original_svg_assets_paint_at_menu_and_ribbon_sizes(self):
        paths = sorted((ROOT / "Mod" / "Fission" / "resources" / "icons").glob("*.svg"))
        self.assertTrue(paths)
        for path in paths:
            icon = self.QtGui.QIcon(str(path))
            for size in (16, 26):
                with self.subTest(asset=path.name, size=size):
                    pixmap = icon.pixmap(size, size)
                    self.assertFalse(pixmap.isNull())
                    self.assertEqual((pixmap.width(), pixmap.height()), (size, size))
                    image = pixmap.toImage()
                    pixels = sum(image.pixelColor(x, y).alpha() > 0
                                 for y in range(size) for x in range(size))
                    self.assertGreater(pixels, size, "SVG must paint a useful glyph, not a stray pixel")


if __name__ == "__main__":
    unittest.main()
