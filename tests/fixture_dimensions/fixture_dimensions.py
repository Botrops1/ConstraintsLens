# tests/fixture_dimensions/fixture_dimensions.py
# Creates a sketch named "ConstraintLens_Dimensions" with one of every
# supported dimension type so #17 can be tested systematically.
# Run via Fusion Tools > Add-Ins > Scripts > fixture_dimensions.
#
# Dimension types created:
#   Linear, Angular, Diameter, Radial, Offset (point-to-line),
#   Distance (line-to-line), Concentric circles, Ellipse major/minor radius
#
# SketchOffsetCurvesDimension is created implicitly by the Offset command and
# cannot be added via the API directly — create an offset curve manually.

import adsk.core
import adsk.fusion
import math


def run(context):
    app = adsk.core.Application.get()
    ui = app.userInterface
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox("Open a Fusion design first.")
            return

        root = design.rootComponent
        sketches = root.sketches
        xy = root.xYConstructionPlane

        # Remove old fixture if present.
        for i in range(sketches.count):
            if sketches.item(i).name == "ConstraintLens_Dimensions":
                sketches.item(i).deleteMe()
                break

        sk = sketches.add(xy)
        sk.name = "ConstraintLens_Dimensions"
        lines = sk.sketchCurves.sketchLines
        circles = sk.sketchCurves.sketchCircles
        arcs = sk.sketchCurves.sketchArcs
        ellipses = sk.sketchCurves.sketchEllipses
        dims = sk.sketchDimensions
        p = adsk.core.Point3D

        # --- 1. Linear dimension -------------------------------------------
        # Horizontal line; dimension its length.
        l1 = lines.addByTwoPoints(p.create(0, 0, 0), p.create(4, 0, 0))
        dims.addDistanceDimension(
            l1.startSketchPoint, l1.endSketchPoint,
            adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
            p.create(2, -1, 0)
        )

        # --- 2. Angular dimension ------------------------------------------
        # Two lines meeting at origin; dimension the angle.
        l2a = lines.addByTwoPoints(p.create(0, 0, 0), p.create(3, 0, 0))
        l2b = lines.addByTwoPoints(p.create(0, 0, 0), p.create(2, 2, 0))
        dims.addAngularDimension(l2a, l2b, p.create(2, 0.5, 0))

        # --- 3. Diameter dimension -----------------------------------------
        c3 = circles.addByCenterRadius(p.create(7, 0, 0), 1.5)
        dims.addDiameterDimension(c3, p.create(7, 2, 0))

        # --- 4. Radial dimension -------------------------------------------
        c4 = circles.addByCenterRadius(p.create(11, 0, 0), 1.0)
        dims.addRadialDimension(c4, p.create(12.5, 1, 0))

        # --- 5. Offset dimension (point to line) ---------------------------
        # Vertical line; dimension distance from a point above it.
        l5 = lines.addByTwoPoints(p.create(0, 4, 0), p.create(0, 8, 0))
        pt5 = sk.sketchPoints.add(p.create(3, 6, 0))
        dims.addOffsetDimension(l5, pt5, p.create(1.5, 6, 0))

        # --- 6. Distance between two lines ---------------------------------
        l6a = lines.addByTwoPoints(p.create(5, 4, 0), p.create(5, 8, 0))
        l6b = lines.addByTwoPoints(p.create(9, 4, 0), p.create(9, 8, 0))
        dims.addDistanceDimension(
            l6a.startSketchPoint, l6b.startSketchPoint,
            adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
            p.create(7, 3.5, 0)
        )

        # --- 7. Concentric circles dimension --------------------------------
        c7a = circles.addByCenterRadius(p.create(13, 6, 0), 0.8)
        c7b = circles.addByCenterRadius(p.create(13, 6, 0), 1.6)
        try:
            dims.addConcentricCircleDimension(c7a, c7b, p.create(15, 6, 0))
        except Exception:
            pass  # not available in all Fusion builds

        # --- 8. Ellipse major radius dimension ------------------------------
        e8 = ellipses.add(p.create(3, 11, 0), p.create(5, 11, 0), p.create(3, 12.2, 0))
        try:
            dims.addEllipseMajorRadiusDimension(e8, p.create(4, 13, 0))
        except Exception:
            pass

        # --- 9. Ellipse minor radius dimension ------------------------------
        try:
            dims.addEllipseMinorRadiusDimension(e8, p.create(5.5, 11, 0))
        except Exception:
            pass

        # --- 10. Arc / tangent arc (for radial on arc) --------------------
        arc10 = arcs.addByCenterStartSweep(
            p.create(9, 11, 0),
            p.create(11, 11, 0),
            math.pi * 0.75
        )
        dims.addRadialDimension(arc10, p.create(10, 13, 0))

        sk.isVisible = True
        ui.messageBox(
            "ConstraintLens_Dimensions sketch created.\n"
            "Open it for edit and open ConstraintLens to test all dimension types.\n\n"
            "Note: SketchOffsetCurvesDimension must be created manually "
            "via Sketch → Offset Curves."
        )

    except Exception as exc:
        import traceback
        ui.messageBox(f"fixture_dimensions failed:\n{traceback.format_exc()}")
