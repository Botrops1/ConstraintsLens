# lib/scanner.py — sketch enumeration (SPEC.md section 4).
#
# Walks the active sketch and produces the JSON payload defined in
# SPEC.md section 7. Never touches the palette directly.

import adsk.core
import adsk.fusion

from . import dispatch
from .labels import EntityLabeler
from .tokens import token_of


def active_sketch(app: adsk.core.Application) -> adsk.fusion.Sketch | None:
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        return None
    return adsk.fusion.Sketch.cast(design.activeEditObject)


def build_payload(sketch: adsk.fusion.Sketch) -> dict:
    """Build the full data payload for the palette."""
    lab = EntityLabeler(sketch)

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

    return {
        "sketch": {
            "name": sketch.name,
            "componentName": component_name,
            "isFullyConstrained": bool(sketch.isFullyConstrained),
            "healthState": health_state,
            "errorOrWarningMessage": error_msg,
        },
        "constraints": _scan_constraints(sketch, lab),
        "dimensions": _scan_dimensions(sketch, lab),
        "implicitJoins": _scan_implicit_joins(sketch, lab),
    }


def _scan_constraints(sketch: adsk.fusion.Sketch, lab: EntityLabeler) -> list[dict]:
    rows: list[dict] = []
    gc = sketch.geometricConstraints
    for i in range(gc.count):
        c = gc.item(i)
        desc = dispatch.DISPATCH.get(c.objectType)
        if desc is None:
            kind = c.objectType.split("::")[-1] if c.objectType else "UnknownConstraint"
            result = dispatch.ScanResult(f"Unknown: {c.objectType}", [], [])
            glyph = "coincident.svg"
        else:
            kind = desc.kind
            glyph = desc.glyph
            try:
                result = desc.build(c, lab)
            except Exception as exc:
                result = dispatch.ScanResult(
                    f"{desc.kind} (builder raised)", [], [f"builder raised: {exc}"]
                )
        tok = token_of(c) or ""
        try:
            is_deletable = bool(c.isDeletable)
        except Exception:
            is_deletable = True
        rows.append({
            "rowKey": tok,
            "token": tok,
            "kind": kind,
            "objectType": c.objectType,
            "label": result.label,
            "glyph": glyph,
            "entities": result.entities,
            "isDeletable": is_deletable,
            "isPseudo": False,
            "errors": result.errors,
        })
    return rows


def _scan_dimensions(sketch: adsk.fusion.Sketch, lab: EntityLabeler) -> list[dict]:
    rows: list[dict] = []
    dims = sketch.sketchDimensions
    for i in range(dims.count):
        d = dims.item(i)
        try:
            result = dispatch.describe_dimension(d, lab, sketch)
        except Exception as exc:
            result = dispatch.ScanResult("Dimension (builder raised)", [], [f"builder raised: {exc}"])
        tok = token_of(d) or ""
        try:
            expr = d.parameter.expression
        except Exception:
            expr = ""
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
            "parameterExpression": expr,
            "isDeletable": is_deletable,
            "isPseudo": False,
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
