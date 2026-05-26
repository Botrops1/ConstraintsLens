# lib/messaging.py — palette <-> Python wire format (SPEC.md section 7).

import json

import adsk.core


# Action names — single source of truth, mirrored in palette/app.js.
ACTION_PALETTE_READY = "paletteReady"
ACTION_REQUEST_REFRESH = "requestRefresh"
ACTION_SELECT_ENTITIES = "selectEntities"
ACTION_SELECT_CONSTRAINT = "selectConstraint"
ACTION_DELETE_CONSTRAINT = "deleteConstraint"
ACTION_SHOW_UNDERCONSTRAINED = "showUnderconstrained"
ACTION_BULK_DELETE = "bulkDelete"
ACTION_EDIT_DIMENSION = "editDimension"
ACTION_FIND_SELECTED = "findSelected"
ACTION_OPEN_EDIT_DIALOG = "openEditDialog"
ACTION_EDIT_PARAMETER = "editParameter"
ACTION_SET_AUTO_ZOOM = "setAutoZoom"

PY_ACTION_DATA = "data"
PY_ACTION_NO_ACTIVE_SKETCH = "noActiveSketch"
PY_ACTION_ERROR = "error"
PY_ACTION_RESULT = "actionResult"
PY_ACTION_SELECTION = "selectionResult"
PY_ACTION_SELECTION_INFO = "selectionInfo"


def send(palette: adsk.core.Palette, action: str, payload: dict | None = None) -> bool:
    """Send a Python->JS message; respects landmine M-8 (skip when invisible)."""
    if palette is None:
        return False
    try:
        if not palette.isVisible:
            return False
    except Exception:
        return False
    body = json.dumps(payload or {}, default=str)
    try:
        palette.sendInfoToHTML(action, body)
        return True
    except Exception:
        return False


def parse_incoming(raw: str) -> dict:
    """Parse a JSON message coming in from the palette; return {} on error."""
    if not raw:
        return {}
    try:
        result = json.loads(raw)
        return result if isinstance(result, dict) else {}
    except Exception:
        return {}
