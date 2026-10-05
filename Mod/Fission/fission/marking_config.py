# SPDX-License-Identifier: MIT
"""Portable marking-menu settings and compass hit testing."""
import json
import math
import re

CONTEXTS = ("model", "sketch", "assembly", "surface", "mesh", "drawing", "cam")
DIRECTIONS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
_DEFAULTS = {
    "model": ["Fission_CreateSketch", "Fission_Extrude", "Fission_Hole", "Fission_Fillet",
              "Fission_Measure", "Fission_Move", "Std_Delete", "Fission_EditFeature"],
    "sketch": ["Sketcher_CreateLine", "Sketcher_CreateRectangle", "Sketcher_CreateCircle",
               "Sketcher_Dimension", "Fission_FinishSketch", "Sketcher_Trimming",
               "Sketcher_ToggleConstruction", "Sketcher_Projection"],
    "assembly": ["Assembly_InsertLink", "Fission_AssemblyJoint", "Assembly_CreateJointRevolute",
                 "Assembly_SolveAssembly", "Fission_Measure", "Fission_Move",
                 "Assembly_ToggleGrounded", "Fission_EditFeature"],
    "surface": ["Surface_Filling", "Surface_GeomFillSurface", "Part_RuledSurface",
                "Fission_Stitch", "Fission_Measure", "Fission_Move", "Part_MakeSolid", "Part_CheckGeometry"],
    "mesh": ["Mesh_Import", "Mesh_FromPartShape", "Mesh_Evaluation", "Mesh_Smoothing",
             "Fission_Measure", "Fission_Move", "Part_ShapeFromMesh", "Mesh_Export"],
    "drawing": ["TechDraw_PageDefault", "TechDraw_View", "TechDraw_ProjectionGroup",
                "TechDraw_Dimension", "TechDraw_ExportPagePDF", "TechDraw_Annotation",
                "TechDraw_Balloon", "TechDraw_RedrawPage"],
    "cam": ["CAM_Job", "CAM_Profile", "CAM_Pocket_Shape", "CAM_Drilling",
            "CAM_SimulatorGL", "CAM_Post", "CAM_ToolController", "CAM_Sanity"],
}


def defaults(context):
    return list(_DEFAULTS.get(context, _DEFAULTS["model"]))


def normalize_config(value):
    schema = value.get("version", 1) if isinstance(value, dict) else None
    value = value if type(schema) is int and schema == 1 else {}
    enabled = value.get("enabled", True)
    slots = value.get("slots", {})
    slots = slots if isinstance(slots, dict) else {}
    result = {"version": 1, "enabled": enabled if isinstance(enabled, bool) else True, "slots": {}}
    for context in CONTEXTS:
        entries = slots.get(context)
        entries = entries if isinstance(entries, list) else []
        result["slots"][context] = [
            item if isinstance(item, str) and (not item or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", item))
            else defaults(context)[index]
            for index, item in enumerate((entries + defaults(context)[len(entries):])[:8])
        ]
    return result


def read_config(settings):
    try:
        return normalize_config(json.loads(settings.GetString("MarkingMenu", "")))
    except (ValueError, TypeError):
        return normalize_config(None)


def write_config(settings, config):
    settings.SetString("MarkingMenu", json.dumps(normalize_config(config), sort_keys=True))


def wedge_at(x, y, radius=160, deadzone=28):
    distance = math.hypot(x, y)
    if distance < deadzone or distance > radius:
        return None
    return int((math.degrees(math.atan2(x, -y)) + 22.5) % 360 // 45)
