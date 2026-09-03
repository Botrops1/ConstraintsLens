# lib/scanner.py — sketch enumeration (SPEC.md section 4).
#
# Walks the active sketch and produces the JSON payload defined in
# SPEC.md section 7. Never touches the palette directly.

import re

import adsk.core
import adsk.fusion

from . import dispatch, labels
from .labels import EntityLabeler
from .tokens import token_of


# A bare number with an optional unit suffix: "5", "5.13 mm", "-1.2e3", "45 deg".
# Anything else — "d5*2", "width/2", "10 mm + 2 mm" — is a formula.
_PLAIN_NUMBER = re.compile(r"^\s*[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?\s*[a-zA-Z°]*\s*$")


def dimension_display(param, expr: str, units) -> str:
    """The string shown for a dimension's value.

    A dimension created by dragging stores its full-precision value as the
    expression — "5.1290366508 mm" — which is unreadable in a narrow palette.
    For those, format the numeric value at the document's precision instead.

    Real formulas are passed through untouched: seeing that a dimension is
    driven by "d5*2" is the useful information, and formatting it away would
    hide it. The raw expression is still what seeds the inline editor, so
    nothing is lost either way.
    """
    if not expr or units is None:
        return expr
    if not _PLAIN_NUMBER.match(expr):
        return expr
    try:
        # param.unit keeps angular dimensions in degrees rather than being
        # formatted as a length.
        return units.formatValue(param.value, param.unit)
    except Exception:
        return expr


def active_sketch(app: adsk.core.Application) -> adsk.fusion.Sketch | None:
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        return None
    return adsk.fusion.Sketch.cast(design.activeEditObject)


_PATTERN_KINDS = frozenset({"CircularPatternConstraint", "RectangularPatternConstraint", "PolygonConstraint"})
# OffsetConstraint is already shown as a Dimension (SketchOffsetCurvesDimension),
# so it is scanned into neither section. dispatch.patch_offset_label() is the
# piece that fills in its label's distance placeholder and is unused for as long
# as that stays true — drop "OffsetConstraint" from this set to bring both back.
# Pattern constraints get their own palette section.
_GEOMETRIC_EXCLUDE = _PATTERN_KINDS | {"OffsetConstraint"}


def build_payload(sketch: adsk.fusion.Sketch) -> dict:
    """Build the full data payload for the palette."""
    lab = labels.labeler_for(sketch)

    name = ""
    try:
        name = sketch.name or ""
    except Exception:
        pass

    fully_constrained = False
    try:
        fully_constrained = bool(sketch.isFullyConstrained)
    except Exception:
        pass

    component_name = ""
    try:
        component_name = sketch.parentComponent.name
    except Exception:
        pass

    health_state = ""
    try:
        health_state = str(sketch.healthState)
    except Exception:
        pass

    error_msg = ""
    try:
        error_msg = sketch.errorOrWarningMessage or ""
    except Exception:
        pass

    geometric, patterns = _scan_constraint_rows(sketch, lab)

    return {
        "sketch": {
            "name": name,
            "componentName": component_name,
            "isFullyConstrained": fully_constrained,
            "healthState": health_state,
            "errorOrWarningMessage": error_msg,
        },
        "constraints": geometric,
        "dimensions": _scan_dimensions(sketch, lab),
        "patterns": patterns,
        "implicitJoins": _scan_implicit_joins(sketch, lab),
    }


def _scan_constraint_rows(
    sketch: adsk.fusion.Sketch, lab: EntityLabeler
) -> tuple[list[dict], list[dict]]:
    """One pass over geometricConstraints, split into the two sections that
    show them: (geometric, patterns).

    This used to be two passes — one filtering the patterns out, one filtering
    everything else out — and each of them ran every descriptor's builder
    before discarding the rows it did not want. Builders read entity accessors
    and an entityToken per chip, so the whole sketch was described twice per
    payload, and OffsetConstraint (which neither section shows) was described
    twice and thrown away twice. Deciding the section needs only the kind name,
    which is a dict lookup and a string split, so it is decided before the
    builder runs.
    """
    geometric: list[dict] = []
    patterns: list[dict] = []
    gc = sketch.geometricConstraints
    for i in range(gc.count):
        c = gc.item(i)
        obj_type = c.objectType
        desc = dispatch.DISPATCH.get(obj_type)
        kind = desc.kind if desc is not None else (
            obj_type.split("::")[-1] if obj_type else "UnknownConstraint"
        )
        # _GEOMETRIC_EXCLUDE is a superset of _PATTERN_KINDS, so the pattern
        # test has to come first. What is left in it is OffsetConstraint.
        if kind in _PATTERN_KINDS:
            bucket = patterns
        elif kind in _GEOMETRIC_EXCLUDE:
            continue
        else:
            bucket = geometric
        bucket.append(_constraint_row(c, obj_type, kind, desc, lab))
    return geometric, patterns


def _constraint_row(c, obj_type: str, kind: str, desc, lab: EntityLabeler) -> dict:
    if desc is None:
        result = dispatch.ScanResult(f"Unknown: {obj_type}", [], [])
        glyph = "coincident.svg"
    else:
        glyph = desc.glyph
        try:
            result = desc.build(c, lab)
        except Exception as exc:
            result = dispatch.ScanResult(
                f"{kind} (builder raised)", [], [f"builder raised: {exc}"]
            )
    tok = token_of(c) or ""
    try:
        is_deletable = bool(c.isDeletable)
    except Exception:
        is_deletable = True
    return {
        "rowKey": tok,
        "token": tok,
        "kind": kind,
        "objectType": obj_type,
        "label": result.label,
        "glyph": glyph,
        "entities": result.entities,
        "isDeletable": is_deletable,
        "isPseudo": False,
        "errors": result.errors,
        "parameters": _extract_constraint_params(c, kind),
    }


def _extract_constraint_params(c, kind: str) -> list[dict]:
    """Return editable ModelParameter entries for pattern constraints (#15).
    PolygonConstraint has no ModelParameter properties; return side count as
    a read-only info entry (no token = no pencil shown in UI).
    """
    if kind == "CircularPatternConstraint":
        return _read_model_params(c, [
            ("quantity",   "Count"),
            ("totalAngle", "Angle"),
        ])
    if kind == "RectangularPatternConstraint":
        return _read_model_params(c, [
            ("quantityOne",  "Count 1"),
            ("quantityTwo",  "Count 2"),
            ("distanceOne",  "Spacing 1"),
            ("distanceTwo",  "Spacing 2"),
        ])
    if kind == "PolygonConstraint":
        try:
            sides = len(list(c.lines))
            return [{"label": "Sides", "token": "", "expression": str(sides)}]
        except Exception:
            return []
    return []


def _read_model_params(c, attr_pairs: list[tuple[str, str]]) -> list[dict]:
    result = []
    for attr_name, label in attr_pairs:
        try:
            param = getattr(c, attr_name)
            if param is None:
                continue
            result.append({
                "label": label,
                "token": token_of(param) or "",
                "expression": param.expression,
            })
        except Exception:
            continue
    return result


def _units_manager():
    """UnitsManager for the active design, or None. Used only for formatting."""
    try:
        product = adsk.core.Application.get().activeProduct
        return product.unitsManager if product else None
    except Exception:
        return None


def _scan_dimensions(sketch: adsk.fusion.Sketch, lab: EntityLabeler) -> list[dict]:
    rows: list[dict] = []
    units = _units_manager()
    dims = sketch.sketchDimensions
    for i in range(dims.count):
        d = dims.item(i)
        tok = token_of(d) or ""
        try:
            expr = d.parameter.expression
        except Exception:
            expr = ""
        try:
            display = dimension_display(d.parameter, expr, units)
        except Exception:
            display = expr
        # The label is what the tooltip shows and what the filter box searches,
        # so it gets the same rounded value the row displays. Without this a
        # dragged dimension put its full internal precision back in both —
        # "Linear: Line 1 -> Line 3 = 5.1290366508 mm" on hover, and typing the
        # 5.13 mm you can see on screen matched nothing.
        try:
            result = dispatch.describe_dimension(d, lab, sketch, value_text=display or expr)
        except Exception as exc:
            result = dispatch.ScanResult("Dimension (builder raised)", [], [f"builder raised: {exc}"])
        try:
            is_deletable = bool(d.isDeletable)
        except Exception:
            is_deletable = True
        rows.append({
            "rowKey": tok,
            "token": tok,
            "kind": dispatch.dimension_kind(d.objectType),
            "objectType": d.objectType,
            "label": result.label,
            "glyph": "dimension.svg",
            "entities": result.entities,
            # Raw expression seeds the inline editor; display is what is shown.
            "parameterExpression": expr,
            "parameterDisplay": display,
            "isDeletable": is_deletable,
            "isPseudo": False,
            "isDimension": True,
            "errors": result.errors,
        })
    return rows


def _scan_implicit_joins(sketch: adsk.fusion.Sketch, lab: EntityLabeler) -> list[dict]:
    """Reconstruct coincident endpoint joins (landmine M-3)."""
    rows: list[dict] = []
    points = sketch.sketchPoints
    for i in range(points.count):
        p = points.item(i)
        try:
            connected = p.connectedEntities
            n = connected.count
        except Exception:
            continue
        if n <= 1:
            continue
        entity_chips: list[dict] = [lab.chip_for(p)]
        labels: list[str] = []
        for j in range(n):
            try:
                e = connected.item(j)
            except Exception:
                continue
            entity_chips.append(lab.chip_for(e))
            labels.append(lab.label_for(e))
        ptok = token_of(p) or f"pt{i}"
        rows.append({
            "rowKey": f"join:{ptok}",
            "token": None,
            "kind": "ImplicitCoincidentJoin",
            "objectType": "",
            "label": f"Endpoint join — {lab.label_for(p)} connects {', '.join(labels)}",
            "glyph": "coincident.svg",
            "entities": entity_chips,
            "isDeletable": False,
            "isPseudo": True,
            "errors": [],
        })
    return rows
