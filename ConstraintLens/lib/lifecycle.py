# lib/lifecycle.py — command + palette registration (SPEC.md sections 4, 6, 7).

import os
import shutil
import time
import traceback

import adsk.core
import adsk.fusion

from . import actions, events, labels, messaging, scanner, selection, tokens


# Command and palette ids — must be unique across all add-ins.
_CMD_ID = "ConstraintLensShow"
_PALETTE_ID = "ConstraintLensPalette"

# SketchConstraintsPanel lives in the Sketch workspace (backlog #1 relocation).
# Falls back to a messageBox if the panel id is wrong for this Fusion build.
_PANEL_ID = "SketchConstraintsPanel"


# Module state — kept here, not duplicated across modules.
_addin_dir: str = ""
_palette: adsk.core.Palette | None = None
_command_definition: adsk.core.CommandDefinition | None = None
_button_control: adsk.core.ToolbarControl | None = None

# activeSelectionChanged callbacks fired before this monotonic timestamp
# are swallowed. Set by Show-underconstrained to a short future window so
# its own labelled "Underconstrained:" push isn't overwritten by the
# auto-update that the text command's selection side-effect triggers
# (whether Fusion fires that event synchronously or after a brief delay).
_swallow_selection_until: float = 0.0

# Set by JS on paletteReady and whenever the toggle is clicked.
_auto_zoom: bool = False


# --- Lifecycle entry points ---------------------------------------------


def start(addin_dir: str) -> None:
    global _addin_dir
    _addin_dir = addin_dir

    app = adsk.core.Application.get()
    ui = app.userInterface

    _copy_native_icons(ui, addin_dir)   # before palette is created
    _ensure_command(app, ui)
    _ensure_button(ui)

    # App-level events that signal "active sketch may have changed".
    events.register_app(app, ui, _on_change)

    # Selection-change events drive the bottom-bar selection-info mirror
    # (issue #3 follow-up). Falls back to a no-op subscription on builds
    # that don't expose activeSelectionChanged — the footer then only
    # refreshes on commandTerminated, which is still useful.
    events.register_selection_changed(ui, _on_selection_changed)


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


# --- Native icon copy ---------------------------------------------------

# Maps our ConstraintLens kind names → sketch resource subfolder names.
# Anchored via SketchGeomConstraintCmd.resourceFolder → .../sketch/Constraint_Coincident,
# then the parent of that is the sketch/ resource base.
# Per-kind command IDs to try when the standard folder has no dark variant.
# Each list is tried in order; first one whose resourceFolder contains a
# *-dark.png is used. Covers Horizontal/Vertical whose Constraint_* folders
# only ship light-variant PNGs in current Fusion builds.
_KIND_FALLBACK_CMDS: dict[str, tuple[str, ...]] = {
    # Fusion ships a single combined H/V command; no separate Constraint_Horizontal/
    # Constraint_Vertical dark PNGs exist in the standard resource folders.
    "HorizontalConstraint": ("ConstraintHorizontalVertical",),
    "VerticalConstraint":   ("ConstraintHorizontalVertical",),
}

_ICON_MAP: dict[str, str] = {
    "CoincidentConstraint":                  "Constraint_Coincident",
    "CoincidentToSurfaceConstraint":         "Constraint_Coincident",
    "CollinearConstraint":                   "Constraint_Collinear",
    "ConcentricConstraint":                  "Constraint_Concentric",
    "EqualConstraint":                       "Constraint_Equal",
    "HorizontalConstraint":                  "Constraint_Horizontal",
    "HorizontalPointsConstraint":            "Constraint_HorizontalVertical",
    "VerticalConstraint":                    "Constraint_Vertical",
    "VerticalPointsConstraint":              "Constraint_HorizontalVertical",
    "MidPointConstraint":                    "Constraint_MidPoint",
    "ParallelConstraint":                    "Constraint_Parallel",
    "PerpendicularConstraint":               "Constraint_Perpendicular",
    "PolygonConstraint":                     "Constraint_Polygon",
    "CircularPatternConstraint":             "pattern_circular",
    "RectangularPatternConstraint":          "pattern_rectangular",
    "SymmetryConstraint":                    "Constraint_Symmetry",
    "TangentConstraint":                     "Constraint_Tangent",
    "LineOnPlanarSurfaceConstraint":         "Constraint_Fix",
    "ImplicitCoincidentJoin":               "Constraint_Coincident",
}


def _copy_native_icons(ui: adsk.core.UserInterface, addin_dir: str) -> None:
    """Copy Fusion's built-in constraint PNGs into palette/icons/ for the webview."""
    try:
        # SketchGeomConstraintCmd.resourceFolder → .../sketch/Constraint_Coincident
        cmd = ui.commandDefinitions.itemById("SketchGeomConstraintCmd")
        if cmd is None:
            return
        base = os.path.dirname((cmd.resourceFolder or "").rstrip("/\\"))
        if not os.path.isdir(base):
            return

        icons_dir = os.path.join(addin_dir, "palette", "icons")
        os.makedirs(icons_dir, exist_ok=True)

        for kind, folder_name in _ICON_MAP.items():
            src_base = os.path.join(base, folder_name)
            dst = os.path.join(icons_dir, f"{kind}.png")
            dst_light = os.path.join(icons_dir, f"{kind}-light.png")
            # Dark slot: only accept -dark.png files (white glyphs).
            # Try the standard folder first, then per-kind command IDs as fallback.
            # If nothing found, remove stale file so JS SVG fallback is used.
            copied_dark = False
            dark_folders = [src_base]
            for cmd_id in _KIND_FALLBACK_CMDS.get(kind, ()):
                fallback_cmd = ui.commandDefinitions.itemById(cmd_id)
                if fallback_cmd is not None:
                    fb = (fallback_cmd.resourceFolder or "").rstrip("/\\")
                    if os.path.isdir(fb):
                        dark_folders.append(fb)
            for folder in dark_folders:
                for size in ("32x32-dark.png", "16x16-dark.png"):
                    try:
                        shutil.copy2(os.path.join(folder, size), dst)
                        copied_dark = True
                        break
                    except Exception:
                        pass
                if copied_dark:
                    break
            if not copied_dark:
                try:
                    os.remove(dst)
                except Exception:
                    pass
            # Light slot: prefer non-dark (dark glyphs); fall back to dark if needed.
            for size in ("32x32.png", "32x32-dark.png", "16x16.png", "16x16-dark.png"):
                try:
                    shutil.copy2(os.path.join(src_base, size), dst_light)
                    break
                except Exception:
                    pass

        # Dimension icon — try known sketch dimension command IDs, then scan base.
        _copy_dimension_icon(ui, base, icons_dir)
    except Exception:
        pass  # entire copy step is best-effort; SVG fallback covers all types


def _copy_dimension_icon(ui: adsk.core.UserInterface, sketch_base: str, icons_dir: str) -> None:
    """Copy Fusion sketch dimension icons to icons/dimension.png and icons/dimension-light.png."""
    # Locate source folder — try known command IDs first, then scan.
    source_folder: str | None = None
    for cmd_id in ("SketchDimension", "SketchGeneralDimension", "SketchLinearDimension"):
        cmd = ui.commandDefinitions.itemById(cmd_id)
        if cmd is None:
            continue
        folder = (cmd.resourceFolder or "").rstrip("/\\")
        if os.path.isdir(folder):
            source_folder = folder
            break
    if source_folder is None:
        try:
            for entry in sorted(os.listdir(sketch_base)):
                if "dimension" in entry.lower() and "cursor" not in entry.lower():
                    folder = os.path.join(sketch_base, entry)
                    if os.path.isdir(folder):
                        source_folder = folder
                        break
        except Exception:
            pass
    if source_folder is None:
        return
    dst = os.path.join(icons_dir, "dimension.png")
    dst_light = os.path.join(icons_dir, "dimension-light.png")
    copied_dark = False
    for size in ("32x32-dark.png", "16x16-dark.png"):
        try:
            shutil.copy2(os.path.join(source_folder, size), dst)
            copied_dark = True
            break
        except Exception:
            pass
    if not copied_dark:
        try:
            os.remove(dst)
        except Exception:
            pass
    for size in ("32x32.png", "32x32-dark.png", "16x16.png", "16x16-dark.png"):
        try:
            shutil.copy2(os.path.join(source_folder, size), dst_light)
            break
        except Exception:
            pass


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
        os.path.join(_addin_dir, "Resources", "ConstraintLens"),
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
    # Dock state is intentionally not set here — Fusion's drag-to-snap UX
    # handles docking natively and remembers the last position across
    # sessions, so any state we'd impose would override the user's choice.

    # setMinimumSize prevents the palette from being dragged below a
    # readable size. No setMaximumSize call — previous testing showed that
    # setMaximumSize(420, 700) capped height at 700 px; raising the cap
    # (2048) caused the palette to fill the dock area and lose its resize
    # handle when docked. Relying on isResizable=True alone to see whether
    # Fusion's palette system arms the handle without a max-size constraint.
    try:
        _palette.setMinimumSize(200, 150)
    except Exception:
        pass

    events.register_palette(_palette, _on_palette_message, _on_palette_closed)
    _publish_active(app)
    _push_selection_info(app)
    _push_selection_tokens(app)


def _is_palette_alive(palette: adsk.core.Palette) -> bool:
    try:
        _ = palette.isVisible
        return True
    except Exception:
        return False


# --- Message handling ---------------------------------------------------


def _on_palette_message(action: str, raw: str) -> None:
    global _auto_zoom
    app = adsk.core.Application.get()
    payload = messaging.parse_incoming(raw)

    if action == messaging.ACTION_PALETTE_READY or action == messaging.ACTION_REQUEST_REFRESH:
        if action == messaging.ACTION_PALETTE_READY:
            _auto_zoom = bool(payload.get("autoZoom", False))
        _publish_active(app)
        _push_selection_info(app)
        _push_selection_tokens(app)
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

    if action == messaging.ACTION_SHOW_UNDERCONSTRAINED:
        _handle_show_underconstrained(app)
        return

    if action == messaging.ACTION_BULK_DELETE:
        _handle_bulk_delete(app, payload)
        return

    if action == messaging.ACTION_EDIT_DIMENSION:
        _handle_edit_dimension(app, payload)
        return

    if action == messaging.ACTION_FIND_SELECTED:
        _handle_find_selected(app)
        return

    if action == messaging.ACTION_OPEN_EDIT_DIALOG:
        _handle_open_edit_dialog(app, payload)
        return

    if action == messaging.ACTION_EDIT_PARAMETER:
        _handle_edit_parameter(app, payload)
        return

    if action == messaging.ACTION_SET_AUTO_ZOOM:
        _auto_zoom = bool(payload.get("enabled", False))
        return

    # Unknown action — log and ignore (forward-compat per SPEC.md section 7).


def _on_palette_closed() -> None:
    # No-op for MVP: subscribed events keep firing harmlessly because
    # send() gates on isVisible. The palette is reopenable via the button.
    pass


def _on_change() -> None:
    app = adsk.core.Application.get()
    _publish_active(app)


def _on_selection_changed() -> None:
    app = adsk.core.Application.get()
    # Swallow auto-updates briefly after Show-underconstrained so the
    # generic "Selected:" payload doesn't overwrite "Underconstrained:".
    if time.monotonic() < _swallow_selection_until:
        return
    _push_selection_info(app)
    _push_selection_tokens(app)
    _zoom_to_active_selection(app)


def _push_selection_info(app: adsk.core.Application) -> None:
    if _palette is None:
        return
    try:
        payload = _build_selection_info(app)
    except Exception:
        payload = {"items": []}
    messaging.send(_palette, messaging.PY_ACTION_SELECTION_INFO, payload)


def _push_selection_tokens(app: adsk.core.Application, prefix: str = "Selected:") -> None:
    """Read activeSelections, build entity tokens, push a selectionResult.
    Drives the row-highlighting + chip-readout that was previously triggered
    by the manual Find button."""
    if _palette is None:
        return
    ui = app.userInterface
    entity_tokens: list[str] = []
    try:
        sel = ui.activeSelections
        for i in range(sel.count):
            try:
                entity = sel.item(i).entity
                tok = tokens.token_of(entity) or ""
                if tok:
                    entity_tokens.append(tok)
            except Exception:
                continue
    except Exception:
        pass
    messaging.send(_palette, messaging.PY_ACTION_SELECTION, {
        "tokens": entity_tokens,
        "prefix": prefix,
    })


# Camera zoom constants (all values in Fusion internal units = cm).
_ZOOM_PADDING = 1.5   # multiply half-diagonal by this factor
_ZOOM_MIN_EXTENT = 0.5   # floor so a point doesn't zoom to nothing
_ZOOM_MAX_EXTENT = 50.0  # skip if union bbox is very large (whole sketch)


def _zoom_to_active_selection(app: adsk.core.Application) -> None:
    """Reframe the viewport to fit the active selection. No-op when
    _auto_zoom is False, selection is empty, or any error occurs."""
    if not _auto_zoom:
        return
    try:
        ui = app.userInterface
        sel = ui.activeSelections
        if sel.count == 0:
            return

        # Union all entity bounding boxes.
        INF = float("inf")
        min_x = min_y = min_z = INF
        max_x = max_y = max_z = -INF
        found = False
        for i in range(sel.count):
            try:
                bbox = sel.item(i).entity.boundingBox
                if bbox is None:
                    continue
                mn, mx = bbox.minPoint, bbox.maxPoint
                min_x = min(min_x, mn.x)
                min_y = min(min_y, mn.y)
                min_z = min(min_z, mn.z)
                max_x = max(max_x, mx.x)
                max_y = max(max_y, mx.y)
                max_z = max(max_z, mx.z)
                found = True
            except Exception:
                continue
        if not found:
            return

        cx = (min_x + max_x) / 2
        cy = (min_y + max_y) / 2
        cz = (min_z + max_z) / 2
        half_diag = ((max_x - min_x) ** 2 + (max_y - min_y) ** 2 + (max_z - min_z) ** 2) ** 0.5 / 2
        extent = max(half_diag * _ZOOM_PADDING, _ZOOM_MIN_EXTENT)
        if extent > _ZOOM_MAX_EXTENT:
            return

        vp = app.activeViewport
        if vp is None:
            return
        cam = vp.camera
        cam.target = adsk.core.Point3D.create(cx, cy, cz)
        cam.viewExtents = extent
        try:
            cam.isSmoothTransition = True
        except Exception:
            pass
        vp.camera = cam
        vp.refresh()
    except Exception:
        pass


def _build_selection_info(app: adsk.core.Application) -> dict:
    """Read ui.activeSelections and format each entity into a small dict
    suitable for the bottom selection footer. Mirrors what Fusion's own
    bottom-right status overlay shows (length / radius / area / volume / etc.)."""
    ui = app.userInterface
    units = None
    try:
        product = app.activeProduct
        units = product.unitsManager if product else None
    except Exception:
        units = None

    labeler = None
    try:
        sketch = scanner.active_sketch(app)
        if sketch is not None:
            labeler = labels.EntityLabeler(sketch)
    except Exception:
        labeler = None

    items: list[dict] = []
    entities: list = []
    try:
        sel = ui.activeSelections
        for i in range(sel.count):
            try:
                ent = sel.item(i).entity
            except Exception:
                continue
            if ent is None:
                continue
            entities.append(ent)
            item = _format_selection_entity(ent, units, labeler)
            if item is not None:
                items.append(item)
    except Exception:
        pass
    # Relationship measurement across the whole selection (issue #8).
    try:
        measure = _pairwise_measurement(entities, units)
        if measure is not None:
            items.append(measure)
    except Exception:
        pass
    return {"items": items}


def _format_selection_entity(entity, units, labeler) -> dict | None:
    label = _selection_label(entity, labeler)
    props = _selection_props(entity, units)
    # Suppress items whose props list is empty and whose label is just a raw
    # type name (i.e. the labeler had nothing better to offer). This prevents
    # the footer from showing e.g. "Profile" with a blank property list when
    # the area read fails, or any future entity type with no useful properties.
    if not props:
        raw_type_name = _raw_type_name(entity)
        if label == raw_type_name:
            return None
    return {"label": label, "props": props}


def _raw_type_name(entity) -> str:
    """Return the bare type name from objectType, e.g. 'Profile'."""
    try:
        return entity.objectType.split("::")[-1]
    except Exception:
        return "<entity>"


def _selection_label(entity, labeler) -> str:
    # Profile: include loop count for a more informative label.
    if isinstance(entity, adsk.fusion.Profile):
        try:
            n = entity.profileLoops.count
            return f"Profile ({n} loop{'s' if n != 1 else ''})"
        except Exception:
            return "Profile"
    if labeler is not None:
        try:
            lbl = labeler.label_for(entity)
            if lbl and lbl != "<unknown>":
                return lbl
        except Exception:
            pass
    return _raw_type_name(entity)


def _selection_props(entity, units) -> list[dict]:
    """Return [{key, value}, ...] for one entity. Best-effort, never raises."""
    props: list[dict] = []
    try:
        if isinstance(entity, adsk.fusion.SketchLine):
            try:
                props.append({"key": "Length", "value": _fmt_length(units, entity.length)})
            except Exception:
                pass
            return props
        if isinstance(entity, adsk.fusion.SketchCircle):
            try:
                r = entity.radius
                props.append({"key": "Radius", "value": _fmt_length(units, r)})
                props.append({"key": "Diameter", "value": _fmt_length(units, r * 2)})
            except Exception:
                pass
            return props
        if isinstance(entity, adsk.fusion.SketchArc):
            try:
                props.append({"key": "Radius", "value": _fmt_length(units, entity.radius)})
            except Exception:
                pass
            try:
                sweep = abs(entity.endAngle - entity.startAngle)
                props.append({"key": "Sweep", "value": _fmt_angle(units, sweep)})
            except Exception:
                pass
            return props
        if isinstance(entity, adsk.fusion.SketchEllipse):
            for key, attr in (("Major", "majorAxisRadius"), ("Minor", "minorAxisRadius")):
                try:
                    val = getattr(entity, attr, None)
                    if val is not None:
                        props.append({"key": key, "value": _fmt_length(units, val)})
                except Exception:
                    pass
            return props
        if isinstance(entity, adsk.fusion.SketchPoint):
            try:
                g = entity.geometry
                props.append({"key": "X", "value": _fmt_length(units, g.x)})
                props.append({"key": "Y", "value": _fmt_length(units, g.y)})
            except Exception:
                pass
            return props
        if isinstance(entity, adsk.fusion.Profile):
            try:
                area_cm2 = entity.areaProperties().area
                props.append({"key": "Area", "value": _fmt_area(units, area_cm2)})
            except Exception:
                pass
            return props
        # Sketch dimensions all expose a .parameter with an expression.
        param = getattr(entity, "parameter", None)
        if param is not None:
            try:
                expr = getattr(param, "expression", None)
                if expr:
                    props.append({"key": "Value", "value": str(expr)})
                    return props
            except Exception:
                pass
        # B-Rep entities — match Fusion's own status overlay fields.
        if isinstance(entity, adsk.fusion.BRepEdge):
            try:
                props.append({"key": "Length", "value": _fmt_length(units, entity.length)})
            except Exception:
                pass
            return props
        if isinstance(entity, adsk.fusion.BRepFace):
            try:
                props.append({"key": "Area", "value": _fmt_area(units, entity.area)})
            except Exception:
                pass
            return props
        if isinstance(entity, adsk.fusion.BRepBody):
            try:
                pp = entity.physicalProperties
                props.append({"key": "Volume", "value": _fmt_volume(units, pp.volume)})
                props.append({"key": "Area", "value": _fmt_area(units, pp.area)})
            except Exception:
                pass
            return props
    except Exception:
        pass
    return props


def _pt_xyz(geom) -> tuple:
    """Return (x, y, z) from a Point3D, defaulting z to 0.0."""
    return (geom.x, geom.y, getattr(geom, "z", 0.0))


def _dist3(a: tuple, b: tuple) -> float:
    import math
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _line_endpoints(line) -> tuple:
    """Return (start_xyz, end_xyz) for a SketchLine."""
    s = _pt_xyz(line.startSketchPoint.geometry)
    e = _pt_xyz(line.endSketchPoint.geometry)
    return s, e


def _line_dir(line) -> tuple:
    s, e = _line_endpoints(line)
    return (e[0] - s[0], e[1] - s[1], e[2] - s[2])


def _vlen(v: tuple) -> float:
    import math
    return math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)


def _angle_between_lines(l1, l2) -> float:
    """Acute angle (radians) between two sketch lines' directions."""
    import math
    d1, d2 = _line_dir(l1), _line_dir(l2)
    n1, n2 = _vlen(d1), _vlen(d2)
    if n1 == 0 or n2 == 0:
        raise ValueError("degenerate line")
    dot = (d1[0] * d2[0] + d1[1] * d2[1] + d1[2] * d2[2]) / (n1 * n2)
    dot = max(-1.0, min(1.0, dot))
    ang = math.acos(dot)
    # Collapse to the acute representative — "angle between lines" is direction-agnostic.
    return ang if ang <= math.pi / 2 else math.pi - ang


def _point_to_segment_dist(p: tuple, a: tuple, b: tuple) -> float:
    """Minimal distance from point p to segment a-b (clamped to endpoints)."""
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ap = (p[0] - a[0], p[1] - a[1], p[2] - a[2])
    ab2 = ab[0] ** 2 + ab[1] ** 2 + ab[2] ** 2
    if ab2 == 0:
        return _dist3(p, a)
    t = (ap[0] * ab[0] + ap[1] * ab[1] + ap[2] * ab[2]) / ab2
    t = max(0.0, min(1.0, t))
    proj = (a[0] + t * ab[0], a[1] + t * ab[1], a[2] + t * ab[2])
    return _dist3(p, proj)


def _circle_center_radius(c) -> tuple:
    """Return (center_xyz, radius) for a SketchCircle/SketchArc."""
    center = _pt_xyz(c.centerSketchPoint.geometry)
    return center, c.radius


def _pairwise_measurement(entities: list, units) -> dict | None:
    """Relationship measurement across the selection (issue #8). Best-effort.

    Returns a footer item {"label", "props", "kind": "measurement"} or None.
    """
    import math

    def point(e):
        return isinstance(e, adsk.fusion.SketchPoint)

    def line(e):
        return isinstance(e, adsk.fusion.SketchLine)

    def circle(e):
        return isinstance(e, adsk.fusion.SketchCircle)

    def arc(e):
        return isinstance(e, adsk.fusion.SketchArc)

    try:
        n = len(entities)
        if n == 2:
            a, b = entities[0], entities[1]
            # 2 points -> distance + deltas
            if point(a) and point(b):
                pa, pb = _pt_xyz(a.geometry), _pt_xyz(b.geometry)
                return {"kind": "measurement", "label": "Measurement", "props": [
                    {"key": "Distance", "value": _fmt_length(units, _dist3(pa, pb))},
                    {"key": "ΔX", "value": _fmt_length(units, abs(pb[0] - pa[0]))},
                    {"key": "ΔY", "value": _fmt_length(units, abs(pb[1] - pa[1]))},
                ]}
            # 2 lines -> angle (+ gap when parallel)
            if line(a) and line(b):
                ang = _angle_between_lines(a, b)
                props = [{"key": "Angle", "value": _fmt_angle(units, ang)}]
                if ang < math.radians(0.5):  # treat as parallel
                    sa, _ = _line_endpoints(a)
                    sb, eb = _line_endpoints(b)
                    props.append({"key": "Gap", "value": _fmt_length(units, _point_to_segment_dist(sa, sb, eb))})
                return {"kind": "measurement", "label": "Measurement", "props": props}
            # point + line -> minimal distance to the segment
            if point(a) and line(b) or line(a) and point(b):
                pt = a if point(a) else b
                ln = b if point(a) else a
                p = _pt_xyz(pt.geometry)
                s, e = _line_endpoints(ln)
                return {"kind": "measurement", "label": "Measurement", "props": [
                    {"key": "Distance", "value": _fmt_length(units, _point_to_segment_dist(p, s, e))},
                ]}
            # 2 circles -> concentric? offset (|r1-r2|) : center-to-center
            if circle(a) and circle(b):
                ca, ra = _circle_center_radius(a)
                cb, rb = _circle_center_radius(b)
                d = _dist3(ca, cb)
                if d < 1e-5:  # concentric
                    return {"kind": "measurement", "label": "Measurement", "props": [
                        {"key": "Offset", "value": _fmt_length(units, abs(ra - rb))},
                    ]}
                return {"kind": "measurement", "label": "Measurement", "props": [
                    {"key": "Distance", "value": _fmt_length(units, d)},
                ]}
            # point + circle/arc -> distance to center and to edge
            if (point(a) and (circle(b) or arc(b))) or (point(b) and (circle(a) or arc(a))):
                pt = a if point(a) else b
                cc = b if point(a) else a
                p = _pt_xyz(pt.geometry)
                center, r = _circle_center_radius(cc)
                to_center = _dist3(p, center)
                return {"kind": "measurement", "label": "Measurement", "props": [
                    {"key": "To center", "value": _fmt_length(units, to_center)},
                    {"key": "To edge", "value": _fmt_length(units, abs(to_center - r))},
                ]}
            return None
        # >2 entities, all lines -> total length
        if n > 2 and all(line(e) for e in entities):
            total = 0.0
            for e in entities:
                total += e.length
            return {"kind": "measurement", "label": "Measurement", "props": [
                {"key": "Total length", "value": _fmt_length(units, total)},
            ]}
    except Exception:
        return None
    return None


def _fmt_length(units, value_cm) -> str:
    if units is not None:
        try:
            return units.formatInternalValue(value_cm, units.defaultLengthUnits, True)
        except Exception:
            pass
    return f"{value_cm:.4g} cm"


def _fmt_angle(units, value_rad) -> str:
    if units is not None:
        try:
            return units.formatInternalValue(value_rad, "deg", True)
        except Exception:
            pass
    # Fusion stores angles in radians; convert for the manual fallback.
    import math
    return f"{math.degrees(value_rad):.3g}°"


def _fmt_area(units, value_cm2) -> str:
    # No dedicated area formatter on UnitsManager; emit a sensible default.
    if units is not None:
        try:
            default = units.defaultLengthUnits
            if default in ("mm",):
                return f"{value_cm2 * 100:.4g} mm^2"
            if default in ("m",):
                return f"{value_cm2 / 10000:.4g} m^2"
            if default in ("in",):
                return f"{value_cm2 / 6.4516:.4g} in^2"
        except Exception:
            pass
    return f"{value_cm2:.4g} cm^2"


def _fmt_volume(units, value_cm3) -> str:
    if units is not None:
        try:
            default = units.defaultLengthUnits
            if default in ("mm",):
                return f"{value_cm3 * 1000:.4g} mm^3"
            if default in ("m",):
                return f"{value_cm3 / 1_000_000:.4g} m^3"
            if default in ("in",):
                return f"{value_cm3 / 16.387064:.4g} in^3"
        except Exception:
            pass
    return f"{value_cm3:.4g} cm^3"


def _publish_active(app: adsk.core.Application) -> None:
    if _palette is None:
        return
    sketch = scanner.active_sketch(app)
    if sketch is None:
        messaging.send(_palette, messaging.PY_ACTION_NO_ACTIVE_SKETCH, {
            "reason": "Open a sketch for edit to see its constraints.",
        })
        _push_selection_info(app)
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
    _push_selection_info(app)


# --- Action handlers ----------------------------------------------------


def _handle_select_entities(app: adsk.core.Application, payload: dict) -> None:
    design = adsk.fusion.Design.cast(app.activeProduct)
    entity_tokens: list[str] = payload.get("entityTokens") or []

    # Primary path: JS sends the entity tokens it already has from the scan.
    # Resolving by token returns the concrete typed object, which is more
    # reliable than re-scanning accessor names (avoids the spline proxy issue).
    if entity_tokens:
        ents = [e for tok in entity_tokens if (e := tokens.resolve(design, tok)) is not None]
        if ents:
            selection.select_entities(app.userInterface, ents)
            return

    # Fallback: re-derive entities from the constraint object directly.
    # Covers rows whose entity chips had empty tokens (surface refs, unknowns).
    row_key = payload.get("rowKey") or ""
    if not row_key:
        return

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
    selection.select_entities(app.userInterface, _entities_for_row(constraint))


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


def _handle_bulk_delete(app: adsk.core.Application, payload: dict) -> None:
    tokens: list[str] = payload.get("tokens") or []
    if not tokens:
        return
    ok_count = 0
    fail_count = 0
    for tok in tokens:
        result = actions.delete_constraint(app, tok)
        if result.ok:
            ok_count += 1
        else:
            fail_count += 1
    n = ok_count + fail_count
    msg = (f"Deleted {ok_count} of {n} constraints." if fail_count
           else f"Deleted {ok_count} constraint{'s' if ok_count != 1 else ''}.")
    messaging.send(_palette, messaging.PY_ACTION_RESULT, {
        "action": messaging.ACTION_BULK_DELETE,
        "ok": fail_count == 0,
        "message": msg,
    })
    _publish_active(app)


def _handle_show_underconstrained(app: adsk.core.Application) -> None:
    # Guard: executeTextCommand only works inside sketch edit context (M-11).
    if scanner.active_sketch(app) is None:
        messaging.send(_palette, messaging.PY_ACTION_RESULT, {
            "action": messaging.ACTION_SHOW_UNDERCONSTRAINED,
            "ok": False,
            "message": "No active sketch.",
        })
        return

    # The text command programmatically selects the underconstrained entities
    # on the canvas, which fires activeSelectionChanged. Open a short
    # suppression window so any auto-update (sync or async) doesn't
    # overwrite the labelled "Underconstrained:" push we issue below.
    # 750ms is long enough to absorb async dispatch latency, short enough
    # that a user's next real selection click isn't ignored.
    global _swallow_selection_until
    _swallow_selection_until = time.monotonic() + 0.75

    try:
        result = app.executeTextCommand("Sketch.ShowUnderconstrained")
        msg = str(result).strip() if result else "No underconstrained entities found."
        messaging.send(_palette, messaging.PY_ACTION_RESULT, {
            "action": messaging.ACTION_SHOW_UNDERCONSTRAINED,
            "ok": True,
            "message": msg,
        })
        # Push the now-selected underconstrained entities into the Selected
        # strip as clickable chips, labelled "Underconstrained:". The
        # properties footer also refreshes from the same active selection.
        _push_selection_tokens(app, prefix="Underconstrained:")
        _push_selection_info(app)
    except Exception as exc:
        _swallow_selection_until = 0.0
        exc_str = str(exc)
        if "fully constrained" in exc_str.lower():
            messaging.send(_palette, messaging.PY_ACTION_RESULT, {
                "action": messaging.ACTION_SHOW_UNDERCONSTRAINED,
                "ok": True,
                "message": "Sketch is fully constrained.",
            })
        else:
            messaging.send(_palette, messaging.PY_ACTION_RESULT, {
                "action": messaging.ACTION_SHOW_UNDERCONSTRAINED,
                "ok": False,
                "message": f"Show underconstrained failed: {exc}",
            })


# commandDefinition IDs confirmed by tests/probe_patterns/probe_patterns.py section A.
# Use commandDefinitions.itemById(id).execute() — executeTextCommand does not work for these.
_EDIT_DIALOG_COMMANDS: dict[str, str] = {
    "Offset curves":                "OffsetSketchEdit",
    "CircularPatternConstraint":    "SketchPatternCircularEdit",
    "RectangularPatternConstraint": "SketchRectangularPatternEdit",
}


def _handle_open_edit_dialog(app: adsk.core.Application, payload: dict) -> None:
    kind = payload.get("kind") or ""
    # Kind-specific override takes priority (e.g. "Offset curves" → OffsetSketchEdit).
    cmd_id = _EDIT_DIALOG_COMMANDS.get(kind)
    # Generic fallback: all other dimension types share one edit command.
    if not cmd_id and payload.get("isDimension"):
        cmd_id = "SketchEditDimensionCmdDef"
    if not cmd_id:
        messaging.send(_palette, messaging.PY_ACTION_RESULT, {
            "action": messaging.ACTION_OPEN_EDIT_DIALOG,
            "ok": False,
            "message": f"No edit dialog configured for {kind}.",
        })
        return
    if scanner.active_sketch(app) is None:
        messaging.send(_palette, messaging.PY_ACTION_RESULT, {
            "action": messaging.ACTION_OPEN_EDIT_DIALOG,
            "ok": False,
            "message": "No active sketch.",
        })
        return

    # Select the entity so the edit command has context.
    ui = app.userInterface
    design = adsk.fusion.Design.cast(app.activeProduct)
    row_key = payload.get("rowKey") or ""
    if row_key and design:
        entity = tokens.resolve(design, row_key)
        if entity is not None:
            # For offset dimensions, select the underlying OffsetConstraint.
            if kind == "Offset curves":
                try:
                    dim = adsk.fusion.SketchOffsetCurvesDimension.cast(entity)
                    if dim and dim.offsetConstraint:
                        entity = dim.offsetConstraint
                except Exception:
                    pass
            try:
                selection.select_constraint(ui, entity)
            except Exception:
                pass

    try:
        cmd = ui.commandDefinitions.itemById(cmd_id)
        if cmd is None:
            messaging.send(_palette, messaging.PY_ACTION_RESULT, {
                "action": messaging.ACTION_OPEN_EDIT_DIALOG,
                "ok": False,
                "message": f"Command '{cmd_id}' not found in this Fusion build.",
            })
            return
        cmd.execute()
        # Success — dialog opens on canvas; no palette message needed.
    except Exception as exc:
        messaging.send(_palette, messaging.PY_ACTION_RESULT, {
            "action": messaging.ACTION_OPEN_EDIT_DIALOG,
            "ok": False,
            "message": f"Open dialog failed: {exc}",
        })


def _handle_edit_parameter(app: adsk.core.Application, payload: dict) -> None:
    token = payload.get("token") or ""
    expression = payload.get("expression") or ""
    if not token or not expression:
        return
    result = actions.edit_parameter(app, token, expression)
    messaging.send(_palette, messaging.PY_ACTION_RESULT, {
        "action": messaging.ACTION_EDIT_PARAMETER,
        "ok": result.ok,
        "message": result.message,
    })
    _publish_active(app)


def _handle_edit_dimension(app: adsk.core.Application, payload: dict) -> None:
    token = payload.get("token") or ""
    expression = payload.get("expression") or ""
    if not token or not expression:
        return
    result = actions.edit_dimension(app, token, expression)
    messaging.send(_palette, messaging.PY_ACTION_RESULT, {
        "action": messaging.ACTION_EDIT_DIMENSION,
        "ok": result.ok,
        "message": result.message,
    })
    _publish_active(app)  # always refresh — restores original value on failure


def _handle_find_selected(app: adsk.core.Application) -> None:
    # Pack 2: Find logic is now driven automatically by
    # activeSelectionChanged. This stub remains so the action constant
    # still routes for any stale JS message (e.g. an older cached palette).
    _push_selection_tokens(app)


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
    # Collections: parentCurves / childCurves / lines (Offset/Polygon) and
    # curves (SketchOffsetCurvesDimension).  parentCurves / childCurves / curves
    # are SketchCurveVector (iteration + len, no .count); lines is ObjectCollection.
    for coll_name in ("parentCurves", "childCurves", "lines", "curves"):
        if not hasattr(constraint, coll_name):
            continue
        try:
            coll = getattr(constraint, coll_name)
            if coll is None:
                continue
            # Direct iteration works for both SketchCurveVector and ObjectCollection.
            try:
                for item in coll:
                    candidates.append(item)
            except TypeError:
                for i in range(coll.count):
                    candidates.append(coll.item(i))
        except Exception:
            continue
    return candidates
