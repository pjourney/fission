# SPDX-License-Identifier: MIT
"""An original compass menu over the native CAD canvas."""
import math
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets
from .marking_config import CONTEXTS, DIRECTIONS, defaults, read_config, write_config, wedge_at
from .selection import active_canvas
from .shortcuts import CLASSIC_PROFILE, is_typing_widget
from .theme import COLORS


class MarkingPopup(QtWidgets.QWidget):
    RADIUS = 160
    CENTER = 170

    def __init__(self, manager, entries, context, viewport):
        super().__init__(manager.controller.main, QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint)
        self.manager = manager
        self.entries = entries
        self.context = context
        self.viewport = viewport
        self.hover = None
        self.setObjectName("FissionMarkingMenu")
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.resize(340, 340)
        self.colors = COLORS.get(manager.controller.settings.GetString("Theme", "Dark"), COLORS["Dark"])

    def slot(self, point):
        return wedge_at(point.x() - self.CENTER, point.y() - self.CENTER, self.RADIUS)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        center = QtCore.QPointF(self.CENTER, self.CENTER)
        circle = QtCore.QRectF(10, 10, 320, 320)
        for index, entry in enumerate(self.entries):
            path = QtGui.QPainterPath(center)
            path.arcTo(circle, 112.5 - index * 45, -45)
            path.closeSubpath()
            color = self.colors["hover"] if index == self.hover and entry["enabled"] else self.colors["panel"]
            painter.fillPath(path, QtGui.QColor(color))
            painter.setPen(QtGui.QPen(QtGui.QColor(self.colors["border"]), 1))
            painter.drawPath(path)
            angle = math.radians(index * 45)
            x, y = self.CENTER + math.sin(angle) * 107, self.CENTER - math.cos(angle) * 107
            opacity = 1.0 if entry["enabled"] else 0.35
            painter.setOpacity(opacity)
            entry["icon"].paint(painter, QtCore.QRect(round(x - 13), round(y - 25), 26, 26))
            painter.setPen(QtGui.QColor(self.colors["text"]))
            font = QtGui.QFont("Segoe UI", 8)
            painter.setFont(font)
            painter.drawText(QtCore.QRectF(x - 43, y + 3, 86, 40),
                             QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop | QtCore.Qt.TextWordWrap, entry["title"])
            painter.setOpacity(1)
        painter.setPen(QtGui.QPen(QtGui.QColor(self.colors["accent"]), 1.5))
        painter.setBrush(QtGui.QColor(self.colors["raised"]))
        painter.drawEllipse(center, 30, 30)
        painter.setPen(QtGui.QColor(self.colors["text"]))
        painter.setFont(QtGui.QFont("Segoe UI", 8))
        painter.drawText(QtCore.QRectF(142, 148, 56, 44), QtCore.Qt.AlignCenter, "Esc\nClose")
        painter.end()

    def mouseMoveEvent(self, event):
        self.hover = self.slot(event.position())
        self.setToolTip(self.entries[self.hover]["hint"] if self.hover is not None else "Escape or click the center to close")
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.choose(event.position().toPoint())

    def choose(self, point, keep_center=False):
        index = self.slot(point)
        if index is None:
            if not keep_center:
                self.close()
            return
        entry = self.entries[index]
        if not entry["enabled"]:
            return
        command = entry["id"]
        self.close()
        self.manager.queue_command(command)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()
            event.accept()
        else:
            event.accept()  # CAD shortcuts never run through the popup.

    def closeEvent(self, event):
        self.manager.popup = None
        try:
            self.viewport.setFocus()
        except RuntimeError:
            pass
        super().closeEvent(event)
        self.deleteLater()


class MarkingMenu(QtCore.QObject):
    def __init__(self, controller):
        super().__init__(controller)
        self.controller = controller
        self.popup = None
        self.gesture = False
        self.gesture_start = None
        self.refresh_settings()
        QtWidgets.QApplication.instance().installEventFilter(self)

    def refresh_settings(self):
        self.config = read_config(self.controller.settings)
        self.close()

    def available(self):
        if (not self.controller.active or self.controller._activation_pending or not self.config["enabled"]
                or not App.ActiveDocument):
            return False
        app = QtWidgets.QApplication.instance()
        if app.activeModalWidget() or app.activePopupWidget() or is_typing_widget(app.focusWidget()):
            return False
        if active_canvas()[1] is None:
            return False
        document = Gui.activeDocument()
        edit = document.getInEdit() if document else None
        sketch = bool(edit and edit.Object.isDerivedFrom("Sketcher::SketchObject"))
        assembly = bool(edit and edit.Object.isDerivedFrom("Assembly::AssemblyObject"))
        if not sketch and (Gui.Control.activeDialog() or (edit and not assembly) or App.ActiveDocument.HasPendingTransaction):
            return False
        command = Gui.Command.get("Std_BoxSelection")
        if not sketch and command and not command.isActive():
            return False
        return self.controller.paint.viewport is None

    def open(self, position=None):
        if not self.available():
            return False
        from .commands import catalog
        from .shell import command_icon
        Gui.Command.update()
        self.document = App.ActiveDocument.Name
        self.context = self.controller.context()
        self.view, viewport = active_canvas()
        self.viewport = viewport
        lookup = {entry["id"]: entry for entry in catalog()}
        entries = []
        for command in self.config["slots"][self.context]:
            info = lookup.get(command, {})
            native = Gui.Command.get(command) if command else None
            enabled = False
            if native:
                actions = native.getAction()
                enabled = any(action.isEnabled() for action in actions) if actions else bool(native.isActive())
            title = info.get("title", "Unavailable" if command else "Empty")
            entries.append(dict(id=command, title=title, enabled=enabled, icon=command_icon(command),
                                hint=(title if info or not command else command)
                                + ("" if enabled else " — unavailable for the current selection or task")))
        popup = MarkingPopup(self, entries, self.context, viewport)
        self.popup = popup
        point = position or QtGui.QCursor.pos()
        if not viewport.rect().contains(viewport.mapFromGlobal(point)):
            point = viewport.mapToGlobal(viewport.rect().center())
        screen = QtWidgets.QApplication.screenAt(point) or self.controller.main.screen()
        bounds = screen.availableGeometry()
        popup.move(max(bounds.left(), min(point.x() - popup.CENTER, bounds.right() - popup.width() + 1)),
                   max(bounds.top(), min(point.y() - popup.CENTER, bounds.bottom() - popup.height() + 1)))
        popup.show()
        popup.setFocus()
        return True

    def queue_command(self, command):
        document, context, viewport = self.document, self.context, self.viewport
        def dispatch():
            if (self.controller.active and App.ActiveDocument and App.ActiveDocument.Name == document
                    and self.controller.context() == context and active_canvas()[1] is viewport):
                self.controller.execute(command)
        QtCore.QTimer.singleShot(0, dispatch)

    def close(self):
        if self.popup is not None:
            self.popup.close()

    def validate(self):
        if self.popup and (not App.ActiveDocument or App.ActiveDocument.Name != self.document
                           or self.controller.context() != self.context or active_canvas()[1] is not self.viewport):
            self.close()

    def eventFilter(self, obj, event):
        kind = event.type()
        if kind == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.RightButton and self.gesture:
            self.gesture = False
            point = event.globalPosition().toPoint()
            moved = self.gesture_start is not None and (point - self.gesture_start).manhattanLength() >= 8
            self.gesture_start = None
            # Screen-edge fitting can shift the center away from the initial
            # pointer. A click must open the menu without choosing a sector.
            if self.popup and moved:
                self.popup.choose(self.popup.mapFromGlobal(event.globalPosition().toPoint()), keep_center=True)
            return True
        if kind != QtCore.QEvent.MouseButtonPress or event.button() != QtCore.Qt.RightButton:
            return False
        if (event.modifiers() != QtCore.Qt.AltModifier or not self.controller.active
                or self.controller.shortcuts.profile.name == CLASSIC_PROFILE):
            return False
        view, viewport = active_canvas()
        if obj is not viewport or not view or view.getNavigationType() != "Gui::FissionNavigationStyle":
            return False
        if self.open(event.globalPosition().toPoint()):
            self.gesture = True
            self.gesture_start = event.globalPosition().toPoint()
            return True  # Neither half of this gesture reaches Coin.
        return False

    def shutdown(self):
        self.close()
        QtWidgets.QApplication.instance().removeEventFilter(self)
