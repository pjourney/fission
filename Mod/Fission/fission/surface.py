# SPDX-License-Identifier: MIT
"""Parameter entry for the native Surface::Sewing feature."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets


class StitchDialog(QtWidgets.QDialog):
    def __init__(self, controller):
        super().__init__(controller.main)
        self.controller = controller
        self.document = App.ActiveDocument
        self.links = []
        for selection in Gui.Selection.getSelectionEx():
            obj = selection.Object
            if not obj.isDerivedFrom("Part::Feature") or obj.Shape.isNull():
                continue
            faces = [name for name in selection.SubElementNames if name.startswith("Face")]
            self.links.append((obj, faces or [""]))
        self.setObjectName("FissionStitchDialog")
        self.setWindowTitle("Stitch Surfaces")
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        layout = QtWidgets.QVBoxLayout(self)
        intro = QtWidgets.QLabel("Join selected surfaces into a shell. A closed shell can then be converted to a solid.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        layout.addWidget(QtWidgets.QLabel("Selected surfaces: {}".format(len(self.links))))
        form = QtWidgets.QFormLayout()
        self.tolerance = QtWidgets.QDoubleSpinBox()
        self.tolerance.setObjectName("StitchTolerance")
        self.tolerance.setDecimals(6)
        self.tolerance.setRange(0.000001, 1000.0)
        self.tolerance.setValue(0.0001)
        self.tolerance.setSuffix(" mm")
        form.addRow("Sewing tolerance", self.tolerance)
        layout.addLayout(form)
        self.message = QtWidgets.QLabel("")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(420, 180)

    def accept(self):
        doc = self.document
        if not self.links or doc is None:
            self.message.setText("Select at least one surface before stitching.")
            return
        if App.ActiveDocument is not doc or doc.HasPendingTransaction or Gui.Control.activeDialog():
            self.message.setText("Return to this design and finish the current operation first.")
            return
        doc.openTransaction("Stitch surfaces")
        try:
            feature = doc.addObject("Surface::Sewing", "StitchedSurface")
            feature.Label = "Stitched Surfaces"
            feature.ShapeList = self.links
            feature.Tolerance = self.tolerance.value()
            doc.recompute()
            if feature.Shape.isNull() or not feature.Shape.isValid() or not feature.Shape.Faces:
                raise ValueError("The selected surfaces did not produce a valid shell. Check the surfaces and tolerance.")
            for obj, _ in self.links:
                obj.Visibility = False
            feature.Visibility = True
            doc.commitTransaction()
        except Exception as error:
            doc.abortTransaction()
            self.message.setText(str(error))
            return
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(feature)
        self.controller.notify("Surfaces stitched. Edit Tolerance in Properties; convert a closed shell with Convert to Solid.")
        super().accept()
