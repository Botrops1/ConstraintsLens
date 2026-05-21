# lib/lifecycle.py — command + palette registration (SPEC.md sections 4, 6, 7).

import os
import traceback

import adsk.core
import adsk.fusion

from . import actions, events, messaging, scanner, selection, tokens


# Command and palette ids — must be unique across all add-ins.
_CMD_ID = "ConstraintLensShow"
_PALETTE_ID = "ConstraintLensPalette"

# Per SPEC.md open question 1: the exact panel id is verified at runtime.
# SolidScriptsAddinsPanel exists in every install; the spike probe enumerates
# alternatives (e.g. SketchInspectPanel) for a later relocation.
_PANEL_ID = "SolidScriptsAddinsPanel"


# Module state — kept here, not duplicated across modules.
_addin_dir: str = ""
_palette: adsk.core.Palette | None = None
_command_definition: adsk.core.CommandDefinition | None = None
_button_control: adsk.core.ToolbarControl | None = None


# --- Lifecycle entry points ---------------------------------------------


def start(addin_dir: str) -> None:
    global _addin_dir
    _addin_dir = addin_dir

    app = adsk.core.Application.get()
    ui = app.userInterface

    _ensure_command(app, ui)
    _ensure_button(ui)

    # App-level events that signal "active sketch may have changed".
    events.register_app(app, ui, _on_change)


def stop() -> None:
    events.unregister_all()

    global _palette, _button_control, _command_definition
    if _palette is not None:
        try:
            _palette.deleteMe()
        except Exception:
            pass
        _palette = None

    if _button_control is not None:
        try:
            _button_control.deleteMe()
        except Exception:
            pass
        _button_control = None

    if _command_definition is not None:
        try:
            _command_definition.deleteMe()
        except Exception:
            pass
        _command_definition = None


# --- Command + button ---------------------------------------------------


def _ensure_command(app: adsk.core.Application, ui: adsk.core.UserInterface) -> None:
    global _command_definition
    existing = ui.commandDefinitions.itemById(_CMD_ID)
    if existing is not None:
        existing.deleteMe()
    cmd_def = ui.commandDefinitions.addButtonDefinition(
        _CMD_ID,
        "Constraint Lens",
        "Show the docked panel listing all constraints in the active sketch.",
        "",  # icon dir — empty for MVP; Fusion will use a default glyph.
    )
    _command_definition = cmd_def

    events.pin(cmd_def.commandCreated, _CommandCreatedHandler())


def _ensure_button(ui: adsk.core.UserInterface) -> None:
    global _button_control
    panel = ui.allToolbarPanels.itemById(_PANEL_ID)
    if panel is None:
        # Surface the missing panel as a visible warning, not a crash.
        try:
            ui.messageBox(
                f"ConstraintLens: panel '{_PANEL_ID}' not found. "
                "Run tests/spike_probe.py to find the correct panel id."
            )
        except Exception:
            pass
        return

    existing = panel.controls.itemById(_CMD_ID)
    if existing is not None:
        existing.deleteMe()
    _button_control = panel.controls.addCommand(_command_definition)
    try:
        _button_control.isPromotedByDefault = True
        _button_control.isPromoted = True
    except Exception:
        # Some panels disallow promotion; the button still appears in the overflow menu.
        pass


class _CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            _show_palette()
        except Exception:
            ui = adsk.core.Application.get().userInterface
            if ui:
                ui.messageBox("ConstraintLens command failed:\n" + traceback.format_exc())


# --- Palette ------------------------------------------------------------


def _show_palette() -> None:
    global _palette
    app = adsk.core.Application.get()
    ui = app.userInterface

    if _palette is not None and _is_palette_alive(_palette):
        _palette.isVisible = True
        _publish_active(app)
        return

    palette_html = os.path.join(_addin_dir, "palette", "index.html")
    # Fusion accepts both relative paths (resolved from the add-in dir) and
    # file:/// URLs. Use the relative form — simpler, works on Win and macOS.
    html_url = "palette/index.html"
    if not os.path.exists(palette_html):
        ui.messageBox(f"ConstraintLens: palette/index.html missing at\n{palette_html}")
        return

    _palette = ui.palettes.itemById(_PALETTE_ID)
    if _palette is not None:
        try:
            _palette.deleteMe()
        except Exception:
            pass
        _palette = None

    _palette = ui.palettes.add(
        _PALETTE_ID,
        "Constraint Lens",
        html_url,
        True,    # isVisible
        True,    # showCloseButton
        True,    # isResizable
        420,     # width
        600,     # height
        True,    # useNewWebBrowser (Qt — required per locked decision)
    )
    try:
        _palette.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateRight
    except Exception:
        # Some Fusion builds make this read-only on initial creation; ignore.
        pass

    events.register_palette(_palette, _on_palette_message, _on_palette_closed)
    _publish_active(app)


def _is_palette_alive(palette: adsk.core.Palette) -> bool:
    try:
        _ = palette.isVisible
        return True
    except Exception:
        return False


# --- Message handling ---------------------------------------------------


def _on_palette_message(action: str, raw: str) -> None:
    app = adsk.core.Application.get()
    payload = messaging.parse_incoming(raw)

    if action == messaging.ACTION_PALETTE_READY or action == messaging.ACTION_REQUEST_REFRESH:
        _publish_active(app)
        return

    if action == messaging.ACTION_SELECT_ENTITIES:
        _handle_select_entities(app, payload)
        return

    if action == messaging.ACTION_SELECT_CONSTRAINT:
        _handle_select_constraint(app, payload)
        return

    if action == messaging.ACTION_DELETE_CONSTRAINT:
        _handle_delete(app, payload)
        return

    # Unknown action — log and ignore (forward-compat per SPEC.md section 7).


def _on_palette_closed() -> None:
    # No-op for MVP: subscribed events keep firing harmlessly because
    # send() gates on isVisible. The palette is reopenable via the button.
    pass


def _on_change() -> None:
    app = adsk.core.Application.get()
    _publish_active(app)


def _publish_active(app: adsk.core.Application) -> None:
    if _palette is None:
        return
    sketch = scanner.active_sketch(app)
    if sketch is None:
        messaging.send(_palette, messaging.PY_ACTION_NO_ACTIVE_SKETCH, {
            "reason": "Open a sketch for edit to see its constraints.",
        })
        return
    try:
        payload = scanner.build_payload(sketch)
    except Exception as exc:
        messaging.send(_palette, messaging.PY_ACTION_ERROR, {
            "message": f"Scan failed: {exc}",
            "context": "build_payload",
        })
        return
    messaging.send(_palette, messaging.PY_ACTION_DATA, payload)


# --- Action handlers ----------------------------------------------------


def _handle_select_entities(app: adsk.core.Application, payload: dict) -> None:
    row_key = payload.get("rowKey") or ""
    sketch = scanner.active_sketch(app)
    if sketch is None:
        return
    design = adsk.fusion.Design.cast(app.activeProduct)

    # Implicit-join rows: rowKey starts with "join:" + sketchPoint token.
    if row_key.startswith("join:"):
        point_token = row_key[len("join:"):]
        point = tokens.resolve(design, point_token)
        if point is None:
            return
        ents = [point]
        try:
            for j in range(point.connectedEntities.count):
                ents.append(point.connectedEntities.item(j))
        except Exception:
            pass
        selection.select_entities(app.userInterface, ents)
        return

    constraint = tokens.resolve(design, row_key)
    if constraint is None:
        return
    ents = _entities_for_row(constraint)
    selection.select_entities(app.userInterface, ents)


def _handle_select_constraint(app: adsk.core.Application, payload: dict) -> None:
    token = payload.get("token") or ""
    design = adsk.fusion.Design.cast(app.activeProduct)
    entity = tokens.resolve(design, token)
    if entity is None:
        return
    selection.select_constraint(app.userInterface, entity)


def _handle_delete(app: adsk.core.Application, payload: dict) -> None:
    token = payload.get("token") or ""
    result = actions.delete_constraint(app, token)
    messaging.send(_palette, messaging.PY_ACTION_RESULT, {
        "action": messaging.ACTION_DELETE_CONSTRAINT,
        "ok": result.ok,
        "message": result.message,
    })
    _publish_active(app)


def _entities_for_row(constraint) -> list:
    """Re-resolve the entities for a constraint (rather than caching tokens)."""
    candidates: list = []
    names = (
        "line", "lineOne", "lineTwo",
        "point", "pointOne", "pointTwo",
        "entity", "entityOne", "entityTwo",
        "curveOne", "curveTwo",
        "midPointCurve", "symmetryLine",
        "centerSketchPoint",
    )
    for name in names:
        if not hasattr(constraint, name):
            continue
        try:
            v = getattr(constraint, name)
        except Exception:
            continue
        if v is not None:
            candidates.append(v)
    # Collections: parentCurves / childCurves / lines on Offset/Polygon.
    # parentCurves / childCurves are SketchCurveVector (supports iteration + len,
    # not .count); lines on PolygonConstraint is ObjectCollection (.count + .item).
    for coll_name in ("parentCurves", "childCurves", "lines"):
        if not hasattr(constraint, coll_name):
            continue
        try:
            coll = getattr(constraint, coll_name)
            if coll is None:
                continue
            # Try direct iteration first (works for both SketchCurveVector and
            # ObjectCollection); fall back to .item(i) loop if that fails.
            try:
                for item in coll:
                    candidates.append(item)
            except TypeError:
                for i in range(coll.count):
                    candidates.append(coll.item(i))
        except Exception:
            continue
    return candidates
