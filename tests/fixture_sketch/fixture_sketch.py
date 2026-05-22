# tests/fixture_sketch.py
# Run from Fusion: Tools -> Scripts and Add-Ins -> Scripts -> +/folder ->
#   point at this file -> Run.
# Creates a fully-known fixture sketch for ConstraintLens dev iteration.
#
# Produces (per SPEC.md section 8):
#   - 4 lines (rectangle, shared endpoints -> 4 implicit coincident joins)
#   - 1 circle
#   - 4 explicit geometric constraints: Horizontal, Vertical, Parallel, Tangent
#   - 2 dimensions: linear (rectangle width), diameter (circle)

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
            ui.messageBox("Open a Fusion design (not a drawing) first.")
            return

        root = design.rootComponent
        sketch = root.sketches.add(root.xYConstructionPlane)
        sketch.name = "ConstraintLens_Fixture"

        # Rectangle as four lines with shared endpoints — this gives us
        # the implicit coincident-join behavior to test against.
        lines = sketch.sketchCurves.sketchLines
        P = adsk.core.Point3D.create
        bottom = lines.addByTwoPoints(P(0, 0, 0), P(4, 0, 0))
        right = lines.addByTwoPoints(bottom.endSketchPoint, P(4, 2, 0))
        top = lines.addByTwoPoints(right.endSketchPoint, P(0, 2, 0))
        left = lines.addByTwoPoints(top.endSketchPoint, bottom.startSketchPoint)

        # Circle positioned to allow a tangent with the top edge.
        circles = sketch.sketchCurves.sketchCircles
        circle = circles.addByCenterRadius(P(2.0, 1.4, 0), 0.5)

        # Four explicit geometric constraint subtypes.
        gc = sketch.geometricConstraints
        gc.addHorizontal(bottom)         # HorizontalConstraint
        gc.addVertical(left)             # VerticalConstraint
        gc.addParallel(top, bottom)      # ParallelConstraint
        gc.addTangent(circle, top)       # TangentConstraint

        # Two dimensions: one linear (rectangle width), one diameter (circle).
        dims = sketch.sketchDimensions
        dims.addDistanceDimension(
            bottom.startSketchPoint,
            bottom.endSketchPoint,
            adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
            P(2.0, -0.7, 0),
        )
        dims.addDiameterDimension(circle, P(3.2, 2.0, 0))

        ui.messageBox(
            "ConstraintLens fixture created.\n"
            f"Sketch: {sketch.name}\n"
            f"Geometric constraints: {sketch.geometricConstraints.count}\n"
            f"Dimensions: {sketch.sketchDimensions.count}\n"
            f"Fully constrained: {sketch.isFullyConstrained}"
        )
    except Exception:
        if ui:
            ui.messageBox("Failed:\n" + traceback.format_exc())
