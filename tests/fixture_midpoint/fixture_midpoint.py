# tests/fixture_midpoint.py
# Exercises landmine M-1 — MidPointConstraint.point raising on
# midpoint-to-midpoint configurations. Creates the canonical setup
# referenced in the Autodesk forum thread (one sketch point constrained
# as the midpoint of two different lines). If M-1 triggers, the
# ConstraintLens panel must render the row with an "accessor error"
# badge rather than crashing.

import adsk.core
import adsk.fusion
import traceback


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox("Open a Fusion design first.")
            return

        root = design.rootComponent
        sketch = root.sketches.add(root.xYConstructionPlane)
        sketch.name = "ConstraintLens_Midpoint_M1"

        lines = sketch.sketchCurves.sketchLines
        P = adsk.core.Point3D.create

        # Two crossing lines whose midpoints should coincide at the origin.
        line_a = lines.addByTwoPoints(P(-2, 0, 0), P(2, 0, 0))
        line_b = lines.addByTwoPoints(P(0, -1.5, 0), P(0, 1.5, 0))

        # Free sketch point at the crossing.
        mid_point = sketch.sketchPoints.add(P(0, 0, 0))

        gc = sketch.geometricConstraints
        # Point is the midpoint of line A.
        gc.addMidPoint(mid_point, line_a)
        # Same point is the midpoint of line B — the configuration that
        # Brian Ekins flagged on the Autodesk forum as triggering the
        # .point accessor exception on the second constraint.
        gc.addMidPoint(mid_point, line_b)

        ui.messageBox(
            "Midpoint M-1 fixture created.\n\n"
            f"Sketch: {sketch.name}\n"
            f"Geometric constraints: {sketch.geometricConstraints.count}\n"
            f"Fully constrained: {sketch.isFullyConstrained}\n\n"
            "Open the sketch for edit and click Constraint Lens. The two "
            "midpoint rows should both render — one of them may show an "
            "'accessor' badge if M-1 triggers. Either outcome confirms the "
            "defensive guard works; a Fusion crash here would be the bug."
        )
    except Exception:
        if ui:
            ui.messageBox("Failed:\n" + traceback.format_exc())
