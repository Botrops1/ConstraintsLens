# lib/actions.py — destructive operations (SPEC.md section 4).

from dataclasses import dataclass

import adsk.core
import adsk.fusion

from . import tokens


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    message: str


def edit_dimension(app: adsk.core.Application, token: str, expression: str) -> ActionResult:
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        return ActionResult(False, "No active design.")
    entity = tokens.resolve(design, token)
    if entity is None:
        return ActionResult(False, "Dimension not found.")
    dim = adsk.fusion.SketchDimension.cast(entity)
    if dim is None:
        return ActionResult(False, "Entity is not a dimension.")
    try:
        param = dim.parameter
        if param is None:
            return ActionResult(False, "Dimension has no editable parameter.")
        param.expression = expression.strip()
        return ActionResult(True, f"Updated to {param.expression}.")
    except Exception as exc:
        return ActionResult(False, f"Edit failed: {exc}")


def delete_constraint(app: adsk.core.Application, token: str) -> ActionResult:
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        return ActionResult(False, "No active design.")
    entity = tokens.resolve(design, token)
    if entity is None:
        return ActionResult(False, "Constraint not found (token unresolved).")
    try:
        is_deletable = bool(entity.isDeletable)
    except Exception:
        is_deletable = True
    if not is_deletable:
        return ActionResult(False, "Constraint reports isDeletable == False.")
    try:
        ok = bool(entity.deleteMe())
    except Exception as exc:
        return ActionResult(False, f"deleteMe() raised: {exc}")
    if not ok:
        return ActionResult(False, "deleteMe() returned False.")
    return ActionResult(True, "Deleted.")
