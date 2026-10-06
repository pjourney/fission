# SPDX-License-Identifier: MIT
"""Native CAD variants for Fission ribbon split buttons.

Each entry is ``(command_id, title, item_index)``. Ordinary Sketcher tools
have their own registered command IDs and use ``None``. Part Design primitive
tools share a registered group command and select its native item index.
Keeping this catalog independent of Qt and FreeCAD also lets the ribbon and
command toolbox use the same inventory without creating native actions.
"""


# IDs are registered by the pinned engine's Sketcher/Gui/CommandCreateGeo.cpp
# and CommandConstraints.cpp. Primary tools remain explicit menu choices.
VARIANTS = {
    "Fission_Cut": (
        ("Fission_Cut", "Extrude Cut", None),
        ("Fission_RevolveCut", "Revolve Cut", None),
        ("Fission_SweepCut", "Sweep Cut", None),
        ("Fission_LoftCut", "Loft Cut", None),
    ),
    "Fission_Plane": (
        ("Fission_Plane", "Construction Plane", None),
        ("Fission_Axis", "Construction Axis", None),
        ("Fission_Point", "Construction Point", None),
    ),
    "Fission_NewComponent": (
        ("Fission_NewComponent", "New Component", None),
        ("Fission_NewBody", "New Body", None),
    ),
    "Sketcher_CreatePolyline": (
        ("Sketcher_CreatePolyline", "Polyline", None),
        ("Sketcher_CreateLine", "Line", None),
    ),
    "Sketcher_CreateLine": (
        ("Sketcher_CreateLine", "Line", None),
        ("Sketcher_CreatePolyline", "Polyline", None),
    ),
    "Sketcher_CreateRectangle": (
        ("Sketcher_CreateRectangle", "2-Point Rectangle", None),
        ("Sketcher_CreateRectangle_Center", "Center Rectangle", None),
        ("Sketcher_CreateOblong", "Rounded Rectangle", None),
    ),
    "Sketcher_CreateCircle": (
        ("Sketcher_CreateCircle", "Center Circle", None),
        ("Sketcher_Create3PointCircle", "3-Point Circle", None),
        ("Sketcher_CreateEllipseByCenter", "Center Ellipse", None),
        ("Sketcher_CreateEllipseBy3Points", "3-Point Ellipse", None),
    ),
    "Sketcher_CreateArc": (
        ("Sketcher_CreateArc", "Center Arc", None),
        ("Sketcher_Create3PointArc", "3-Point Arc", None),
        ("Sketcher_CreateArcOfEllipse", "Elliptical Arc", None),
        ("Sketcher_CreateArcOfHyperbola", "Hyperbolic Arc", None),
        ("Sketcher_CreateArcOfParabola", "Parabolic Arc", None),
    ),
    "Sketcher_CreateRegularPolygon": (
        ("Sketcher_CreateRegularPolygon", "Regular Polygon", None),
        ("Sketcher_CreateTriangle", "Triangle", None),
        ("Sketcher_CreateSquare", "Square", None),
        ("Sketcher_CreatePentagon", "Pentagon", None),
        ("Sketcher_CreateHexagon", "Hexagon", None),
        ("Sketcher_CreateHeptagon", "Heptagon", None),
        ("Sketcher_CreateOctagon", "Octagon", None),
    ),
    "Sketcher_CreateSlot": (
        ("Sketcher_CreateSlot", "Straight Slot", None),
        ("Sketcher_CreateArcSlot", "Arc Slot", None),
    ),
    "Sketcher_CreateBSpline": (
        ("Sketcher_CreateBSpline", "Control Point Spline", None),
        ("Sketcher_CreatePeriodicBSpline", "Closed Control Point Spline", None),
        ("Sketcher_CreateBSplineByInterpolation", "Fit Point Spline", None),
        ("Sketcher_CreatePeriodicBSplineByInterpolation", "Closed Fit Point Spline", None),
    ),
    "Sketcher_Trimming": (
        ("Sketcher_Trimming", "Trim", None),
        ("Sketcher_Split", "Split", None),
        ("Sketcher_Extend", "Extend", None),
    ),
    "Sketcher_Projection": (
        ("Sketcher_Projection", "Project Geometry", None),
        ("Sketcher_Intersection", "Intersect Geometry", None),
        ("Sketcher_CarbonCopy", "Copy Sketch Geometry", None),
    ),
    "Sketcher_Dimension": (
        ("Sketcher_Dimension", "Smart Dimension", None),
        ("Sketcher_ConstrainDistanceX", "Horizontal Distance", None),
        ("Sketcher_ConstrainDistanceY", "Vertical Distance", None),
        ("Sketcher_ConstrainDistance", "Length / Distance", None),
        ("Sketcher_ConstrainRadiam", "Radius or Diameter", None),
        ("Sketcher_ConstrainRadius", "Radius", None),
        ("Sketcher_ConstrainDiameter", "Diameter", None),
        ("Sketcher_ConstrainAngle", "Angle", None),
        ("Sketcher_ConstrainLock", "Lock Position", None),
    ),
}


# CommandPrimitive.cpp maps these exact group-item indices to native feature
# types. Names such as PartDesign_AdditiveBox are action names, not commands.
_PRIMITIVES = ("Box", "Cylinder", "Sphere", "Cone", "Ellipsoid", "Torus", "Prism", "Wedge")
for _command in ("PartDesign_CompPrimitiveAdditive", "PartDesign_CompPrimitiveSubtractive"):
    VARIANTS[_command] = tuple(
        (_command, title, index) for index, title in enumerate(_PRIMITIVES)
    )


def variants_for(command_id):
    """Return native menu choices, or an empty tuple for an ordinary button."""
    return VARIANTS.get(command_id, ())
