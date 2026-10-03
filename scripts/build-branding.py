# SPDX-License-Identifier: MIT
"""Convert the original code-native SVG mark to a Windows executable icon."""
import os
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6 import QtCore, QtGui, QtWidgets, QtSvg

root = Path(__file__).resolve().parents[1]
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
image = QtGui.QImage(256, 256, QtGui.QImage.Format_ARGB32)
image.fill(QtCore.Qt.transparent)
painter = QtGui.QPainter(image)
QtSvg.QSvgRenderer(str(root / "Mod/Fission/resources/fission.svg")).render(painter)
painter.end()
if not image.save(str(root / "Mod/Fission/resources/fission.ico"), "ICO"):
    raise RuntimeError("Qt's Windows icon encoder failed")
print("Original Fission executable icon generated.")
