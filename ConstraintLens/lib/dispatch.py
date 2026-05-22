# lib/dispatch.py — constraint type dispatch table (SPEC.md section 5).
#
# DISPATCH is keyed by objectType string. Each entry knows how to build
# a label and the entity-chip list for that subtype. Defensive guards
# implement landmines M-1 (MidPoint .point), M-2 (pattern stubs), and
# the universal "accessor raised" fallback.

from collections.abc import Callable
from dataclasses import dataclass, field

from .labels import EntityLabeler


@dataclass(frozen=True)
class ScanResult:
    label: str
    entities: list[dict]
    errors: list[str] = field(default_factory=list)


Builder = Callable[[object, EntityLabeler], ScanResult]


@dataclass(frozen=True)
class ConstraintDescriptor:
    object_type: str
    kind: str
    glyph: str
    build: Builder


def _safe(getter, default=None):
    try:
        return getter()
    except Exception:
        return default


def _chips(lab: EntityLabeler, *entities) -> list[dict]:
    return [lab.chip_for(e) for e in entities if e is not None]


def _two_entity(c, lab, a: str, b: str, sep: str, kind_label: str) -> ScanResult:
    e1 = _safe(lambda: getattr(c, a))
    e2 = _safe(lambda: getattr(c, b))
    errors: list[str] = []
    if e1 is None:
        errors.append(f"accessor unavailable: .{a}")
    if e2 is None:
        errors.append(f"accessor unavailable: .{b}")
    l1 = lab.label_for(e1) if e1 else "<error>"
    l2 = lab.label_for(e2) if e2 else "<error>"
    return ScanResult(f"{kind_label} — {l1} {sep} {l2}", _chips(lab, e1, e2), errors)


def _single_line(c, lab, kind_label: str) -> ScanResult:
    line = _safe(lambda: c.line)
    errors = [] if line else ["accessor unavailable: .line"]
    label = f"{kind_label} — {lab.label_for(line) if line else '<error>'}"
    return ScanResult(label, _chips(lab, line), errors)


def _line_on_surface(c, lab, kind_label: str) -> ScanResult:
    line = _safe(lambda: c.line)
    surface = _safe(lambda: c.planarSurface)
    errors = []
    if line is None:
        errors.append("accessor unavailable: .line")
    if surface is None:
        errors.append("accessor unavailable: .planarSurface")
    line_label = lab.label_for(line) if line else "<error>"
    chips = _chips(lab, line)
    if surface is not None:
        # External-surface fallback per SPEC.md table row 9.
        try:
            comp_name = surface.body.parentComponent.name
            surface_label = f"face on {comp_name}"
        except Exception:
            surface_label = "external surface"
        chips.append({"token": "", "kind": "BRepFace", "label": surface_label})
    return ScanResult(f"{kind_label} — {line_label}", chips, errors)


# --- Builders, in dispatch-table order ----------------------------------


def _b_horizontal(c, lab):
    return _single_line(c, lab, "Horizontal")


def _b_vertical(c, lab):
    return _single_line(c, lab, "Vertical")


def _b_horizontal_points(c, lab):
    return _two_entity(c, lab, "pointOne", "pointTwo", "↔", "Horizontal align")


def _b_vertical_points(c, lab):
    return _two_entity(c, lab, "pointOne", "pointTwo", "↔", "Vertical align")


def _b_parallel(c, lab):
    return _two_entity(c, lab, "lineOne", "lineTwo", "∥", "Parallel")


def _b_perpendicular(c, lab):
    return _two_entity(c, lab, "lineOne", "lineTwo", "⊥", "Perpendicular")


def _b_collinear(c, lab):
    return _two_entity(c, lab, "lineOne", "lineTwo", "⋯", "Collinear")


def _b_coincident(c, lab):
    p = _safe(lambda: c.point)
    e = _safe(lambda: c.entity)
    errors = []
    if p is None:
        errors.append("accessor unavailable: .point")
    if e is None:
        errors.append("accessor unavailable: .entity")
    return ScanResult(
        f"Coincident — {lab.label_for(p) if p else '<error>'} on "
        f"{lab.label_for(e) if e else '<error>'}",
        _chips(lab, p, e),
        errors,
    )


def _b_coincident_to_surface(c, lab):
    p = _safe(lambda: c.point)
    surface = _safe(lambda: c.surface)
    errors = []
    if p is None:
        errors.append("accessor unavailable: .point")
    if surface is None:
        errors.append("accessor unavailable: .surface")
    chips = _chips(lab, p)
    if surface is not None:
        try:
            comp_name = surface.body.parentComponent.name
            surface_label = f"face on {comp_name}"
        except Exception:
            surface_label = "external surface"
        chips.append({"token": "", "kind": "Surface", "label": surface_label})
    return ScanResult(
        f"Coincident to surface — {lab.label_for(p) if p else '<error>'}",
        chips,
        errors,
    )


def _b_tangent(c, lab):
    return _two_entity(c, lab, "curveOne", "curveTwo", "⌒", "Tangent")


def _b_equal(c, lab):
    return _two_entity(c, lab, "curveOne", "curveTwo", "=", "Equal")


def _b_concentric(c, lab):
    return _two_entity(c, lab, "entityOne", "entityTwo", "⊙", "Concentric")


def _b_midpoint(c, lab):
    # Landmine M-1: .point raises on midpoint-to-midpoint configurations.
    p = _safe(lambda: c.point)
    curve = _safe(lambda: c.midPointCurve)
    errors = []
    if p is None:
        errors.append("midpoint-to-midpoint: .point accessor unavailable (Fusion bug M-1)")
    if curve is None:
        errors.append("accessor unavailable: .midPointCurve")
    return ScanResult(
        f"Midpoint — {lab.label_for(p) if p else '<error>'} mid "
        f"{lab.label_for(curve) if curve else '<error>'}",
        _chips(lab, p, curve),
        errors,
    )


def _b_symmetry(c, lab):
    e1 = _safe(lambda: c.entityOne)
    e2 = _safe(lambda: c.entityTwo)
    sym = _safe(lambda: c.symmetryLine)
    errors = []
    if e1 is None:
        errors.append("accessor unavailable: .entityOne")
    if e2 is None:
        errors.append("accessor unavailable: .entityTwo")
    if sym is None:
        errors.append("accessor unavailable: .symmetryLine")
    return ScanResult(
        f"Symmetric — {lab.label_for(e1) if e1 else '<error>'} ↔ "
        f"{lab.label_for(e2) if e2 else '<error>'} about "
        f"{lab.label_for(sym) if sym else '<error>'}",
        _chips(lab, e1, e2, sym),
        errors,
    )


def _iter_curves_into_chips(coll, lab, chips: list[dict]) -> int:
    """Iterate a curve collection (SketchCurveVector or ObjectCollection),
    append a chip for each item, return the count appended.
    Tolerates both iteration patterns: direct `for x in coll` (vectors) and
    `.count` + `.item(i)` (ObjectCollection)."""
    if coll is None:
        return 0
    n = 0
    try:
        for curve in coll:
            chips.append(lab.chip_for(curve))
            n += 1
        return n
    except TypeError:
        pass
    except Exception:
        return n
    try:
        for i in range(coll.count):
            chips.append(lab.chip_for(coll.item(i)))
            n += 1
    except Exception:
        pass
    return n


def _b_offset(c, lab):
    parent = _safe(lambda: c.parentCurves)
    child = _safe(lambda: c.childCurves)
    distance = _safe(lambda: c.distance)
    chips: list[dict] = []
    n = _iter_curves_into_chips(parent, lab, chips)
    m = _iter_curves_into_chips(child, lab, chips)
    expr = "?"
    try:
        if distance is not None:
            expr = distance.expression
    except Exception:
        expr = "?"
    return ScanResult(f"Offset ({n}→{m} curves, {expr})", chips, [])


def _b_polygon(c, lab):
    lines = _safe(lambda: c.lines)
    center = (
        _safe(lambda: c.centerSketchPoint) or
        _safe(lambda: c.center) or
        _safe(lambda: c.centerPoint)
    )
    chips: list[dict] = []
    if center is not None:
        chips.append(lab.chip_for(center))
    n = _iter_curves_into_chips(lines, lab, chips)
    label = (
        f"Polygon ({n} sides) about {lab.label_for(center)}"
        if center is not None
        else f"Polygon ({n} sides)"
    )
    return ScanResult(label, chips, [])


def _b_circular_pattern(c, lab):
    # Landmine M-2: read-only stub.
    return ScanResult("Circular pattern (read-only)", [], [])


def _b_rectangular_pattern(c, lab):
    # Landmine M-2: read-only stub.
    return ScanResult("Rectangular pattern (read-only)", [], [])


def _b_line_on_surface(c, lab):
    return _line_on_surface(c, lab, "Line on surface")


def _b_line_parallel_surface(c, lab):
    return _line_on_surface(c, lab, "Line ∥ surface")


def _b_perpendicular_surface(c, lab):
    return _line_on_surface(c, lab, "Line ⊥ surface")


# --- The table ----------------------------------------------------------


_ENTRIES: list[ConstraintDescriptor] = [
    ConstraintDescriptor("adsk::fusion::HorizontalConstraint", "HorizontalConstraint", "horizontal.svg", _b_horizontal),
    ConstraintDescriptor("adsk::fusion::VerticalConstraint", "VerticalConstraint", "vertical.svg", _b_vertical),
    ConstraintDescriptor("adsk::fusion::HorizontalPointsConstraint", "HorizontalPointsConstraint", "horizontal.svg", _b_horizontal_points),
    ConstraintDescriptor("adsk::fusion::VerticalPointsConstraint", "VerticalPointsConstraint", "vertical.svg", _b_vertical_points),
    ConstraintDescriptor("adsk::fusion::ParallelConstraint", "ParallelConstraint", "parallel.svg", _b_parallel),
    ConstraintDescriptor("adsk::fusion::PerpendicularConstraint", "PerpendicularConstraint", "perpendicular.svg", _b_perpendicular),
    ConstraintDescriptor("adsk::fusion::CollinearConstraint", "CollinearConstraint", "collinear.svg", _b_collinear),
    ConstraintDescriptor("adsk::fusion::CoincidentConstraint", "CoincidentConstraint", "coincident.svg", _b_coincident),
    ConstraintDescriptor("adsk::fusion::CoincidentToSurfaceConstraint", "CoincidentToSurfaceConstraint", "surface.svg", _b_coincident_to_surface),
    ConstraintDescriptor("adsk::fusion::TangentConstraint", "TangentConstraint", "tangent.svg", _b_tangent),
    ConstraintDescriptor("adsk::fusion::EqualConstraint", "EqualConstraint", "equal.svg", _b_equal),
    ConstraintDescriptor("adsk::fusion::ConcentricConstraint", "ConcentricConstraint", "concentric.svg", _b_concentric),
    ConstraintDescriptor("adsk::fusion::MidPointConstraint", "MidPointConstraint", "midpoint.svg", _b_midpoint),
    ConstraintDescriptor("adsk::fusion::SymmetryConstraint", "SymmetryConstraint", "symmetric.svg", _b_symmetry),
    ConstraintDescriptor("adsk::fusion::OffsetConstraint", "OffsetConstraint", "offset.svg", _b_offset),
    ConstraintDescriptor("adsk::fusion::PolygonConstraint", "PolygonConstraint", "polygon.svg", _b_polygon),
    ConstraintDescriptor("adsk::fusion::CircularPatternConstraint", "CircularPatternConstraint", "pattern.svg", _b_circular_pattern),
    ConstraintDescriptor("adsk::fusion::RectangularPatternConstraint", "RectangularPatternConstraint", "pattern.svg", _b_rectangular_pattern),
    ConstraintDescriptor("adsk::fusion::LineOnPlanarSurfaceConstraint", "LineOnPlanarSurfaceConstraint", "surface.svg", _b_line_on_surface),
    ConstraintDescriptor("adsk::fusion::LineParallelToPlanarSurfaceConstraint", "LineParallelToPlanarSurfaceConstraint", "surface.svg", _b_line_parallel_surface),
    ConstraintDescriptor("adsk::fusion::PerpendicularToSurfaceConstraint", "PerpendicularToSurfaceConstraint", "surface.svg", _b_perpendicular_surface),
]


DISPATCH: dict[str, ConstraintDescriptor] = {d.object_type: d for d in _ENTRIES}


def describe(constraint) -> tuple[ConstraintDescriptor, ScanResult]:
    """Return (descriptor, scan_result) for a constraint; falls back to a generic row."""
    try:
        obj_type = constraint.objectType
    except Exception:
        obj_type = ""
    desc = DISPATCH.get(obj_type)
    if desc is None:
        kind = obj_type.split("::")[-1] if obj_type else "UnknownConstraint"
        desc = ConstraintDescriptor(obj_type, kind, "coincident.svg", _b_unknown)
    try:
        return desc, desc.build(constraint, _EMPTY_LABELER)
    except Exception as exc:
        return desc, ScanResult(f"{desc.kind} (unreadable)", [], [f"builder raised: {exc}"])


def _b_unknown(c, lab):
    obj_type = getattr(c, "objectType", "?")
    return ScanResult(f"Unknown constraint kind: {obj_type}", [], [])


# Sentinel labeler used only by describe()'s fallback path; real scans use
# a per-sketch EntityLabeler instance.
class _NullLabeler:
    def label_for(self, _):
        return "<no labeler>"

    def kind_for(self, _):
        return "SketchEntity"

    def chip_for(self, _):
        return {"token": "", "kind": "SketchEntity", "label": "<no labeler>"}


_EMPTY_LABELER = _NullLabeler()


# --- Dimension dispatch (smaller, uniform shape) ------------------------


# Per-type entity accessor names for sketch dimensions.
# Types absent from this map fall back to ("entityOne", "entityTwo").
_DIM_ACCESSORS: dict[str, tuple[str, ...]] = {
    "adsk::fusion::SketchAngularDimension":                             ("lineOne", "lineTwo"),
    "adsk::fusion::SketchConcentricCircleDimension":                    ("circleOne", "circleTwo"),
    "adsk::fusion::SketchDiameterDimension":                            ("entity",),
    "adsk::fusion::SketchDistanceBetweenLineAndPlanarSurfaceDimension": ("line",),
    "adsk::fusion::SketchDistanceBetweenTwoLinesDimension":             ("lineOne", "lineTwo"),
    "adsk::fusion::SketchEllipseMajorRadiusDimension":                  ("ellipse",),
    "adsk::fusion::SketchEllipseMinorRadiusDimension":                  ("ellipse",),
    "adsk::fusion::SketchRadialDimension":                              ("entity",),
}
_DIM_ACCESSOR_DEFAULT = ("entityOne", "entityTwo")


def _entities_from_dim(dim, obj_type: str) -> list:
    """Return sketch entities for a dimension using type-specific accessors,
    falling back to entityOne/entityTwo if the primary accessors yield nothing."""
    accessor_names = _DIM_ACCESSORS.get(obj_type, _DIM_ACCESSOR_DEFAULT)
    ents = [e for attr in accessor_names
            for e in [_safe(lambda a=attr: getattr(dim, a, None))]
            if e is not None]
    if not ents and accessor_names is not _DIM_ACCESSOR_DEFAULT:
        ents = [e for attr in _DIM_ACCESSOR_DEFAULT
                for e in [_safe(lambda a=attr: getattr(dim, a, None))]
                if e is not None]
    return ents


_DIMENSION_KINDS: dict[str, str] = {
    "adsk::fusion::SketchAngularDimension": "Angular",
    "adsk::fusion::SketchConcentricCircleDimension": "Concentric circles",
    "adsk::fusion::SketchDiameterDimension": "Diameter",
    "adsk::fusion::SketchDistanceBetweenLineAndPlanarSurfaceDimension": "Line ↔ surface",
    "adsk::fusion::SketchDistanceBetweenTwoLinesDimension": "Distance (lines)",
    "adsk::fusion::SketchEllipseMajorRadiusDimension": "Ellipse major radius",
    "adsk::fusion::SketchEllipseMinorRadiusDimension": "Ellipse minor radius",
    "adsk::fusion::SketchLinearDimension": "Linear",
    "adsk::fusion::SketchOffsetCurvesDimension": "Offset curves",
    "adsk::fusion::SketchOffsetDimension": "Offset",
    "adsk::fusion::SketchRadialDimension": "Radial",
    "adsk::fusion::SketchTangentDistanceDimension": "Tangent distance",
}


def _find_offset_constraint_for_dim(dim, sketch):
    """Match a SketchOffsetCurvesDimension to its source OffsetConstraint.
    OffsetConstraint.distance is unreliable in the January 2026 build (often
    returns None), so this stacks fallbacks: parameter entityToken, parameter
    name, positional pairing of offset-dims vs offset-constraints, and finally
    "just use the only one if there is only one"."""
    if sketch is None:
        return None

    # Collect all OffsetConstraints up front — every fallback needs them.
    offset_constraints: list = []
    try:
        gc = sketch.geometricConstraints
        for i in range(gc.count):
            c = gc.item(i)
            if getattr(c, "objectType", "") == "adsk::fusion::OffsetConstraint":
                offset_constraints.append(c)
    except Exception:
        return None
    if not offset_constraints:
        return None

    dim_param = _safe(lambda: dim.parameter)
    dim_tok = _safe(lambda: dim_param.entityToken) if dim_param else None
    dim_name = _safe(lambda: dim_param.name) if dim_param else None

    # 1. Match by parameter entityToken (clean path when .distance works).
    if dim_tok:
        for c in offset_constraints:
            d = _safe(lambda c=c: c.distance)
            if d is None:
                continue
            if _safe(lambda d=d: d.entityToken) == dim_tok:
                return c

    # 2. Match by parameter name.
    if dim_name:
        for c in offset_constraints:
            d = _safe(lambda c=c: c.distance)
            if d is None:
                continue
            if _safe(lambda d=d: d.name) == dim_name:
                return c

    # 3. Positional pairing: assume nth offset-dim corresponds to nth offset-constraint.
    own_tok = _safe(lambda: dim.entityToken)
    if own_tok:
        offset_dims: list = []
        try:
            dims = sketch.sketchDimensions
            for i in range(dims.count):
                d = dims.item(i)
                if getattr(d, "objectType", "") == "adsk::fusion::SketchOffsetCurvesDimension":
                    offset_dims.append(d)
        except Exception:
            offset_dims = []
        for idx, od in enumerate(offset_dims):
            if _safe(lambda od=od: od.entityToken) == own_tok and idx < len(offset_constraints):
                return offset_constraints[idx]

    # 4. Last resort — if exactly one OffsetConstraint, it must be the one.
    if len(offset_constraints) == 1:
        return offset_constraints[0]

    return None


def _find_offset_dim_for_constraint(c, sketch):
    """Find the SketchOffsetCurvesDimension governing OffsetConstraint c.
    Mirrors _find_offset_constraint_for_dim in the reverse direction."""
    if sketch is None:
        return None
    offset_dims: list = []
    try:
        dims = sketch.sketchDimensions
        for i in range(dims.count):
            d = dims.item(i)
            if getattr(d, "objectType", "") == "adsk::fusion::SketchOffsetCurvesDimension":
                offset_dims.append(d)
    except Exception:
        return None
    if not offset_dims:
        return None

    c_dist = _safe(lambda: c.distance)
    c_tok = _safe(lambda: c_dist.entityToken) if c_dist is not None else None
    c_name = _safe(lambda: c_dist.name) if c_dist is not None else None

    if c_tok:
        for d in offset_dims:
            if _safe(lambda d=d: d.parameter.entityToken) == c_tok:
                return d
    if c_name:
        for d in offset_dims:
            if _safe(lambda d=d: d.parameter.name) == c_name:
                return d
    if len(offset_dims) == 1:
        return offset_dims[0]
    return None


def patch_offset_label(result: ScanResult, c, sketch) -> ScanResult:
    """Replace ', ?)' distance placeholder with the real expression from
    c.distance or the matching SketchOffsetCurvesDimension."""
    if not result.label.endswith(", ?)"):
        return result
    d = _safe(lambda: c.distance)
    expr = _safe(lambda: d.expression) if d is not None else None
    if expr is None:
        dim = _find_offset_dim_for_constraint(c, sketch)
        if dim is not None:
            expr = _safe(lambda: dim.parameter.expression)
    if expr is None:
        return result
    new_label = result.label[:-len(", ?)")] + f", {expr})"
    return ScanResult(new_label, result.entities, result.errors)


def describe_dimension(dim, lab: EntityLabeler, sketch=None) -> ScanResult:
    obj_type = getattr(dim, "objectType", "")
    kind_label = _DIMENSION_KINDS.get(obj_type, obj_type.split("::")[-1] or "Dimension")

    # SketchOffsetCurvesDimension does not expose its source curves directly
    # in any reliable accessor on the dimension itself — try common attribute
    # names first, then fall back to finding the matching OffsetConstraint
    # by parameter and reading its parentCurves / childCurves.
    if obj_type == "adsk::fusion::SketchOffsetCurvesDimension":
        chips: list[dict] = []
        n = 0
        for attr in ("curves", "parentCurves", "childCurves"):
            coll = _safe(lambda a=attr: getattr(dim, a, None))
            n += _iter_curves_into_chips(coll, lab, chips)
        if not chips:
            ofc = _find_offset_constraint_for_dim(dim, sketch)
            if ofc is not None:
                n += _iter_curves_into_chips(_safe(lambda: ofc.parentCurves), lab, chips)
                n += _iter_curves_into_chips(_safe(lambda: ofc.childCurves), lab, chips)
        expr = "?"
        try:
            expr = dim.parameter.expression
        except Exception:
            pass
        return ScanResult(f"{kind_label} ({n} curves) = {expr}", chips, [])

    ents = _entities_from_dim(dim, obj_type)
    e1 = ents[0] if ents else None
    e2 = ents[1] if len(ents) > 1 else None
    expr = "?"
    try:
        expr = dim.parameter.expression
    except Exception:
        expr = "?"
    if e1 and e2:
        label = f"{kind_label}: {lab.label_for(e1)} → {lab.label_for(e2)} = {expr}"
    elif e1:
        label = f"{kind_label}: {lab.label_for(e1)} = {expr}"
    else:
        label = f"{kind_label} = {expr}"
    return ScanResult(label, _chips(lab, e1, e2), [])


def dimension_kind(obj_type: str) -> str:
    return _DIMENSION_KINDS.get(obj_type, obj_type.split("::")[-1] or "Dimension")
