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
    c = dict(COLORS.get(name, COLORS["Dark"]), glyph="black" if name == "Light" else "white")
    settings.SetString("Theme", name)
    # Scoped styling leaves the native task editors' validation colors intact.
    main_window.setStyleSheet("""
QMainWindow, QMenuBar, QStatusBar { background: %(bg)s; color: %(text)s; }
QMenuBar::item:selected, QMenu::item:selected { background: %(hover)s; }
QMenu { background: %(panel)s; color: %(text)s; border: 1px solid %(border)s; }
QDockWidget { color: %(text)s; font: 9pt 'Segoe UI'; }
QDockWidget::title { background: %(panel)s; color: %(text)s; padding: 5px; border-bottom: 1px solid %(border)s; }
QDockWidget#FissionBrowserDock, QDockWidget#FissionTimelineDock {
 titlebar-close-icon: url(qss:images_classic/close-%(glyph)s.svg);
 titlebar-normal-icon: url(qss:images_classic/float-%(glyph)s.svg); }
QDockWidget#FissionBrowserDock QWidget#OverlayTitle,
QDockWidget#FissionTimelineDock QWidget#OverlayTitle { background: %(panel)s; color: %(text)s; }
QDockWidget#FissionBrowserDock::close-button,
QDockWidget#FissionTimelineDock::close-button { image: url(qss:images_classic/close-%(glyph)s.svg); }
QDockWidget#FissionBrowserDock::float-button,
QDockWidget#FissionTimelineDock::float-button { image: url(qss:images_classic/float-%(glyph)s.svg); }
QWidget#FissionRibbon, QWidget#FissionWelcome, QWidget#FissionNavigation,
QWidget#FissionTimelineContent { background: %(panel)s; color: %(text)s; }
QWidget#FissionRibbon QWidget { background: transparent; color: %(text)s; }
QWidget#FissionRibbon QLabel, QWidget#FissionWelcome QLabel,
QWidget#FissionTimelineContent QLabel, QWidget#FissionNavigation QLabel { color: %(text)s; }
QWidget#FissionTimelineContent QToolButton { background: %(raised)s; color: %(text)s; }
QLineEdit#FissionBrowserFilter { background: %(raised)s; color: %(text)s;
 border: 1px solid %(border)s; padding: 4px; }
QLabel#FissionTimelineHint { color: %(text)s; }
QToolButton#FissionTimelineRecompute { background: %(raised)s; color: %(text)s;
 border: 1px solid %(border)s; padding: 4px 7px; }
QTreeWidget#FissionBrowserTree QHeaderView::section { background: %(raised)s; color: %(text)s; }
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
    # Native application palettes can remain dark while Fission changes theme.
    # Give product document views explicit text palettes before refreshing their
    # per-item brushes; native task editors keep their own validation colors.
    for widget_name in ("FissionBrowserTree", "FissionTimelineList"):
        view = main_window.findChild(QtWidgets.QAbstractItemView, widget_name)
        if view is not None:
            palette = view.palette()
            palette.setColor(QtGui.QPalette.Text, QtGui.QColor(c["text"]))
            palette.setColor(QtGui.QPalette.Base, QtGui.QColor(c["panel"]))
            view.setPalette(palette)
    line_edit = main_window.findChild(QtWidgets.QLineEdit, "FissionBrowserFilter")
    if line_edit is not None:
        palette = line_edit.palette()
        palette.setColor(QtGui.QPalette.PlaceholderText, QtGui.QColor(c["muted"]))
        line_edit.setPalette(palette)
    # Native dock titles can use Text as well as WindowText, while their
    # controls inherit the application palette. Scope every text role to our
    # two product docks; native Tasks retain their own palette and validation.
    for dock_name in ("FissionBrowserDock", "FissionTimelineDock"):
        dock = main_window.findChild(QtWidgets.QDockWidget, dock_name)
        if dock is None:
            continue
        title = dock.titleBarWidget()
        widgets = [dock] + ([title] if title is not None else [])
        widgets.extend(button for button in dock.findChildren(QtWidgets.QAbstractButton)
                       if button.objectName().startswith(("qt_dockwidget_", "OBTN ")))
        for widget in widgets:
            palette = widget.palette()
            for role in (QtGui.QPalette.WindowText, QtGui.QPalette.Text, QtGui.QPalette.ButtonText):
                palette.setColor(role, QtGui.QColor(c["text"]))
            widget.setPalette(palette)
            control = {"qt_dockwidget_closebutton": "close", "qt_dockwidget_floatbutton": "float"}.get(widget.objectName())
            if control:
                widget.setIcon(QtGui.QIcon("qss:images_classic/%s-%s.svg" % (control, c["glyph"])))
            widget.update()
    from .shell import existing_controller
    controller = existing_controller()
    if controller is not None and controller.main is main_window:
        controller.browser.refresh()
        controller.timeline.refresh()
    return name
