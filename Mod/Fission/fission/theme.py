# SPDX-License-Identifier: MIT
"""Centralized compact Qt styling. CAD viewport colors remain FreeCAD settings."""
import FreeCAD as App
from PySide import QtGui, QtWidgets

COLORS = {
    "Dark": dict(bg="#202932", panel="#28333e", raised="#34424f", text="#e1e8ee",
                 muted="#a1b0bd", border="#42515e", accent="#22b7a8", hover="#3c4d5d"),
    "Light": dict(bg="#e8edf1", panel="#f5f7f9", raised="#ffffff", text="#253444",
                  muted="#596b7c", border="#c4cdd6", accent="#087f77", hover="#dce7ed"),
}


def apply(main_window, name=None):
    settings = App.ParamGet("User parameter:BaseApp/Preferences/Fission")
    name = name or settings.GetString("Theme", "Dark")
    c = COLORS.get(name, COLORS["Dark"])
    settings.SetString("Theme", name)
    # Scoped styling leaves the native task editors' validation colors intact.
    main_window.setStyleSheet("""
QMainWindow, QMenuBar, QStatusBar { background: %(bg)s; color: %(text)s; }
QMenuBar::item:selected, QMenu::item:selected { background: %(hover)s; }
QMenu { background: %(panel)s; color: %(text)s; border: 1px solid %(border)s; }
QDockWidget { color: %(text)s; font: 9pt 'Segoe UI'; }
QDockWidget::title { background: %(panel)s; padding: 5px; border-bottom: 1px solid %(border)s; }
QWidget#FissionRibbon, QWidget#FissionWelcome, QWidget#FissionNavigation,
QWidget#FissionTimelineContent { background: %(panel)s; color: %(text)s; }
QWidget#FissionRibbon QLabel, QWidget#FissionWelcome QLabel,
QWidget#FissionNavigation QLabel { color: %(text)s; }
QWidget#FissionRibbon QToolButton, QWidget#FissionNavigation QToolButton {
 color: %(text)s; background: transparent; border: 1px solid transparent; padding: 4px 7px; }
QWidget#FissionRibbon QToolButton:hover, QWidget#FissionNavigation QToolButton:hover {
 background: %(hover)s; border-color: %(border)s; }
QWidget#FissionRibbon QToolButton:disabled { color: %(muted)s; }
QWidget#FissionRibbon QTabBar::tab { background: %(panel)s; color: %(muted)s;
 padding: 7px 17px; border-bottom: 2px solid transparent; }
QWidget#FissionRibbon QTabBar::tab:selected { color: %(text)s; border-bottom-color: %(accent)s; }
QWidget#FissionRibbon QComboBox { min-width: 108px; background: %(raised)s;
 color: %(text)s; border: 1px solid %(border)s; padding: 4px; }
QTreeWidget#FissionBrowserTree, QListWidget#FissionTimelineList {
 background: %(panel)s; color: %(text)s; border: none; selection-background-color: %(hover)s; }
QWidget#FissionWelcome QPushButton { background: %(raised)s; color: %(text)s;
 border: 1px solid %(border)s; padding: 9px 20px; text-align: left; }
QWidget#FissionWelcome QPushButton:hover { border-color: %(accent)s; }
QDialog { font: 9pt 'Segoe UI'; }
""" % c)
    return name
