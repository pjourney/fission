# SPDX-License-Identifier: MIT
"""Canvas selection adapters; native selection gates and geometry remain authoritative."""
import math
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets


def active_canvas():
    document = Gui.activeDocument()
    if not document:
        return None, None
    view = document.activeView()
    if not view or not hasattr(view, "graphicsView") or not hasattr(view, "getObjectInfo"):
        return None, None
    return view, view.graphicsView().viewport()


def can_select():
    document = App.ActiveDocument
    gui_document = Gui.activeDocument()
    if not document or not gui_document or document.HasPendingTransaction:
        return False
    edit = gui_document.getInEdit()
    if (edit and not edit.Object.isDerivedFrom("Assembly::AssemblyObject")) or Gui.Control.activeDialog():
        return False
    command = Gui.Command.get("Std_BoxSelection")
    return active_canvas()[1] is not None and bool(command and command.isActive())


class PaintSelection(QtCore.QObject):
    """One stroke selects frontmost objects using the engine's actual ray picker."""
    def __init__(self, controller):
        super().__init__(controller)
        self.controller = controller
        self.viewport = None
        self.view = None
        self.stroke = False
        self.suppress_release = False
        self.last = None
        QtWidgets.QApplication.instance().installEventFilter(self)

    def start(self):
        if not can_select():
            return False
        self.cancel()
        self.view, self.viewport = active_canvas()
        self.document = App.ActiveDocument.Name
        self.original = [(item.DocumentName, item.ObjectName, list(item.SubElementNames))
                         for item in Gui.Selection.getSelectionEx(self.document, 0)]
        self.cursor = self.viewport.cursor()
        self.viewport.setCursor(QtCore.Qt.CrossCursor)
        self.stroke = False
        self.last = None
        self.seen = set()
        self.controller.notify("Paint selection: drag left mouse; Ctrl adds; Escape restores the previous selection.")
        self.viewport.setFocus()
        return True

    def cancel(self, restore=True):
        if self.viewport is None:
            return
        self.suppress_release = self.stroke
        try:
            self.viewport.setCursor(self.cursor)
        except RuntimeError:
            pass
        if restore and App.ActiveDocument and App.ActiveDocument.Name == self.document and can_select():
            Gui.Selection.clearSelection(self.document)
            for document, obj, subs in self.original:
                if document in App.listDocuments() and App.getDocument(document).getObject(obj):
                    if subs:
                        for sub in subs:
                            Gui.Selection.addSelection(document, obj, sub)
                    else:
                        Gui.Selection.addSelection(document, obj)
        self.viewport = None
        self.view = None
        self.stroke = False
        self.last = None

    def pick(self, point):
        # Qt's origin is top left; Coin's ray picker uses bottom left pixels.
        ratio = self.viewport.devicePixelRatioF()
        info = self.view.getObjectInfo((round(point.x() * ratio),
                                        self.view.getSize()[1] - round(point.y() * ratio) - 1), 5 * ratio)
        if not info or "Object" not in info:
            return
        parent = info.get("ParentObject")
        if parent:
            import Part
            document, obj = parent.Document.Name, parent.Name
            sub = Part.splitSubname(info.get("SubName", ""))[0]
        else:
            document, obj, sub = info["Document"], info["Object"], ""
        key = (document, obj, sub)
        if key not in self.seen:
            # addSelection consults any existing native selection gate. Never
            # replace the gate owned by a workbench or task.
            Gui.Selection.addSelection(document, obj, sub)
            self.seen.add(key)

    def sample(self, point):
        start = self.last or point
        count = max(1, int(math.hypot(point.x() - start.x(), point.y() - start.y()) / 5))
        for index in range(1, count + 1):
            fraction = index / count
            self.pick(QtCore.QPoint(round(start.x() + (point.x() - start.x()) * fraction),
                                   round(start.y() + (point.y() - start.y()) * fraction)))
        self.last = point

    def eventFilter(self, obj, event):
        if (event.type() == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.LeftButton
                and self.suppress_release):
            self.suppress_release = False
            return True
        if self.viewport is None:
            return False
        kind = event.type()
        if kind not in (QtCore.QEvent.KeyPress, QtCore.QEvent.MouseButtonPress,
                        QtCore.QEvent.MouseButtonRelease, QtCore.QEvent.MouseMove,
                        QtCore.QEvent.WindowDeactivate, QtCore.QEvent.Close):
            return False
        if (not self.controller.active or self.controller._activation_pending or not can_select()
                or QtWidgets.QApplication.instance().activeModalWidget() or not App.ActiveDocument
                or App.ActiveDocument.Name != self.document or active_canvas()[1] is not self.viewport):
            self.cancel(False)
            return False
        if kind == QtCore.QEvent.KeyPress and event.key() == QtCore.Qt.Key_Escape:
            self.cancel()
            return True
        if obj is self.controller.main and kind in (QtCore.QEvent.WindowDeactivate, QtCore.QEvent.Close):
            self.cancel()
            return False
        if kind == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.LeftButton and self.stroke:
            if obj is self.viewport:
                self.sample(event.position().toPoint())
            self.cancel(False)
            self.suppress_release = False
            self.controller.notify("Paint selection complete.")
            return True
        if obj is not self.viewport:
            return False
        if kind == QtCore.QEvent.MouseButtonPress:
            if event.button() == QtCore.Qt.LeftButton:
                self.stroke = True
                if not event.modifiers() & QtCore.Qt.ControlModifier:
                    Gui.Selection.clearSelection(self.document)
                self.sample(event.position().toPoint())
                return True
            self.cancel()
            return False
        if kind == QtCore.QEvent.MouseMove and self.stroke:
            self.sample(event.position().toPoint())
            return True
        return False

    def shutdown(self):
        self.cancel(False)
        QtWidgets.QApplication.instance().removeEventFilter(self)
