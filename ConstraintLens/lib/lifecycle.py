# lib/lifecycle.py — command + palette registration (SPEC.md sections 4, 6, 7).

import os
import shutil
import threading
import time
import traceback

import adsk.core
import adsk.fusion

from . import actions, dispatch, events, labels, messaging, scanner, selection, tokens


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

# --- Palette visibility follows sketch-edit mode (issue #9) -------------
#
# The palette has no purpose outside a sketch, so it is hidden on sketch exit
# unconditionally — this was an opt-in pin toggle in the first cut and the
# toggle was dropped as pointless.
#
# It comes back automatically on the next sketch, but only once the user has
# opened it at least once this session: nobody wants a palette appearing in
# every sketch of a session where they never asked for it. Closing it with the
# X button clears the flag, which is the escape hatch — it then stays away
# until the toolbar button is clicked again.
_ever_opened: bool = False

# Set while we drive isVisible ourselves. The `closed` event is documented as
# firing when the *user* clicks the X, but if a build also raises it on a
# programmatic hide then auto-hide would clear _ever_opened and silently
# disable auto-open. Cheap insurance against that.
_suppress_closed_event: bool = False

# Reentrancy guard. _apply_palette_height() calls adsk.doEvents(), which can
# dispatch a queued poll tick mid-sequence — and that tick must not toggle
# isVisible while a height change is using isVisible and dockingState itself.
_applying_height: bool = False

# --- Docked height control (v1.6.0) -------------------------------------
#
# Established empirically by tests/probe_dock_height{,2} on Fusion 2704.1.36.
# The governing rule, which every probe observation fits:
#
#     docked height = min(maxHeight, columnHeight)
#
#   * setMaximumSize is the ONLY size constraint the dock layout preserves,
#     and it is honoured only while the palette is FLOATING. Called on an
#     already-docked palette it returns False and changes nothing (round 1 P2,
#     round 2 M5) — though it does register the ceiling for Fusion's own drag
#     handle, which is why v1.2.0's setMaximumSize(420, 700) appeared to work.
#   * setSize / the height property resize a floating palette, but the dock
#     layout discards the value on re-dock (round 2 M3). Useful only to GROW
#     before re-docking, since setMaximumSize can never enlarge.
#   * dockingOption is irrelevant here — round 2 stages 0 and 1 were both
#     undraggable with 3 (default) and 1 (ToVerticalOnly).
#
# Two landmines, both confirmed by earlier PC testing: setMaximumSize(0, 0)
# hard-locks the palette to 0x0 despite being documented as "no restriction",
# and values >= 9999 crash Fusion and deactivate the add-in. Never emit either.
_PALETTE_MIN_W = 200
_PALETTE_MIN_H = 150
_PALETTE_MAX_SAFE_PX = 4000

# Tallest height ever seen while docked. With no cap in force that is the dock
# column height; once a cap is applied every later reading is <= the column, so
# taking the maximum preserves the original measurement. The 100% preset asks
# for _PALETTE_MAX_SAFE_PX, which the dock layout clamps to the column — that
# re-measures it and keeps this fresh when the Fusion window is resized.
_dock_column_px: int = 0

# Which tier of _apply_palette_height last did the work, and whether the
# palette changed screen position doing it. Surfaced in the height button's
# tooltip so a single test run reports what actually happened — there is no
# way to observe this from the API afterwards.
_last_apply_note: str = ""

# Constraint/dimension tally as of the last published scan.
#
# commandTerminated is the only event-driven rescan trigger, but a constraint
# tool stays active across repeated applications — apply Coincident to five
# pairs in a row and it does not fire once, so the row counts sat stale until
# the user switched tools.
#
# activeSelectionChanged looked like the fix but is not: while a command is
# running, entity picks go into that command's own selection input rather than
# ui.activeSelections, so the event is silent during exactly the window that
# needed covering. No API event fires when a resident tool edits the sketch, so
# the palette's JS side polls instead (ACTION_POLL_SKETCH), and this tally is
# the gate — geometricConstraints.count and sketchDimensions.count are two plain
# property reads, cheap enough to run several times a second, whereas
# build_payload enumerates everything and is not.
_last_sketch_counts: tuple[int, int] = (-1, -1)


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

    # The only way to notice edits made by a tool that stays active.
    _start_sketch_poll(app)


def stop() -> None:
    # Before unregister_all(), which drops the custom-event handler the worker
    # thread's fireCustomEvent calls are aimed at.
    _stop_sketch_poll()
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
    global _palette, _ever_opened
    app = adsk.core.Application.get()
    ui = app.userInterface

    # Clicking the toolbar button opts this session into auto-reopening the
    # palette on every later sketch (issue #9 / #3).
    _ever_opened = True

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

    # setMinimumSize is applied here, while the palette is still floating —
    # the only point at which the dock layout takes size constraints (see the
    # probe notes on _dock_column_px above). It sets the floor for both the
    # height controls and Fusion's own drag handle.
    #
    # No setMaximumSize call at creation: a cap would immediately shorten the
    # palette once docked, since docked height = min(maxHeight, columnHeight).
    # The default stays full-column height, and the user opts into a shorter
    # palette via the height cycle button or the resize grip.
    try:
        _palette.setMinimumSize(_PALETTE_MIN_W, _PALETTE_MIN_H)
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


# --- Docked height control ----------------------------------------------


def _palette_width() -> int:
    try:
        width = _palette.width
        if isinstance(width, int) and width > 0:
            return width
    except Exception:
        pass
    return 420


def _palette_height() -> int:
    try:
        height = _palette.height
        return height if isinstance(height, int) and height > 0 else 0
    except Exception:
        return 0


def _palette_position() -> tuple[int, int]:
    try:
        left, top = _palette.left, _palette.top
        if isinstance(left, int) and isinstance(top, int):
            return left, top
    except Exception:
        pass
    return 0, 0


def _is_docked() -> bool:
    try:
        floating = adsk.core.PaletteDockingStates.PaletteDockStateFloating
        return _palette.dockingState != floating
    except Exception:
        return False


def _note_dock_column() -> None:
    """Track the tallest docked height seen — that is the dock column height."""
    global _dock_column_px
    if _palette is None or not _is_palette_alive(_palette) or not _is_docked():
        return
    height = _palette_height()
    if height > _dock_column_px:
        _dock_column_px = height


def _apply_palette_height(target_px: int) -> int:
    """Resize the palette to target_px; return the height actually achieved.

    Three tiers, cheapest first, each verified by reading palette.height back
    rather than trusting a return value — setSize is documented to report
    success even when docking prevented the resize, and every setMaximumSize
    call the probes made returned False whether or not it took effect.
    """
    global _last_apply_note, _applying_height
    if _palette is None or not _is_palette_alive(_palette):
        return 0

    # Tiers 2 and 3 drive isVisible and dockingState, and call adsk.doEvents()
    # between steps — which can dispatch a queued poll tick. Block auto-hide
    # for the duration so it cannot fight us over isVisible mid-sequence.
    _applying_height = True
    try:
        return _apply_palette_height_inner(target_px)
    finally:
        _applying_height = False


def _apply_palette_height_inner(target_px: int) -> int:
    global _last_apply_note

    target = max(_PALETTE_MIN_H, min(int(target_px), _PALETTE_MAX_SAFE_PX))
    width = _palette_width()

    # A docked palette can never exceed its column, so that is the best
    # achievable result when growing.
    if _is_docked() and _dock_column_px:
        expected = min(target, _dock_column_px)
    else:
        expected = target

    def _achieved() -> int:
        height = _palette_height()
        return height if height and abs(height - expected) <= 2 else 0

    # Tier 1 — in place. The probes say a docked palette ignores this, but the
    # call is free, it succeeds outright when floating, and even when it does
    # not resize it registers the ceiling for Fusion's native drag handle.
    try:
        _palette.setMaximumSize(width, target)
    except Exception:
        pass
    hit = _achieved()
    if hit:
        _last_apply_note = "tier 1 (in place, no undock)"
        return hit

    # Tier 2 — force a dock re-layout by hiding and re-showing. Untested by the
    # probes, but if it works it is strictly better than tier 3: it keeps the
    # palette's slot in the dock column instead of undocking and returning.
    try:
        _palette.isVisible = False
        adsk.doEvents()
        _palette.isVisible = True
        adsk.doEvents()
    except Exception:
        pass
    hit = _achieved()
    if hit:
        _last_apply_note = "tier 2 (visibility nudge, no undock)"
        return hit

    # Tier 3 — the mechanism probe M4 proved: a cap applied while FLOATING is
    # preserved through docking. setSize goes alongside it because
    # setMaximumSize only ever shrinks, so growing needs both.
    #
    # The two calls take different values on purpose. The cap gets the raw
    # target so that "full" (which asks for the safe ceiling) leaves no
    # practical limit if the Fusion window is later enlarged. setSize gets the
    # clamped height, so the palette does not briefly become 4000 px tall
    # while floating on its way to being re-docked.
    grow_to = min(expected, _dock_column_px or 1200)
    before_pos = _palette_position()
    previous_state = None
    try:
        floating = adsk.core.PaletteDockingStates.PaletteDockStateFloating
        previous_state = _palette.dockingState
        if previous_state != floating:
            _palette.dockingState = floating
            adsk.doEvents()
        try:
            _palette.setMaximumSize(width, target)
        except Exception:
            pass
        try:
            _palette.setSize(width, grow_to)
        except Exception:
            pass
        adsk.doEvents()
        if previous_state != floating:
            _palette.dockingState = previous_state
            adsk.doEvents()
    except Exception:
        # Never strand the palette floating because the sequence failed midway.
        if previous_state is not None:
            try:
                _palette.dockingState = previous_state
            except Exception:
                pass

    # Whether re-docking put the palette back in the same slot is the one
    # thing the probes could not answer, and it is invisible to the API after
    # the fact — so record the shift while we still have the before reading.
    after_pos = _palette_position()
    shift = (after_pos[0] - before_pos[0], after_pos[1] - before_pos[1])
    moved = "same slot" if shift == (0, 0) else f"moved by {shift[0]},{shift[1]} px"
    _last_apply_note = f"tier 3 (float + re-dock, {moved})"

    return _palette_height()


def _push_dock_info() -> None:
    if _palette is None:
        return
    messaging.send(_palette, messaging.PY_ACTION_DOCK_INFO, {
        "docked": _is_docked(),
        "heightPx": _palette_height(),
        "columnPx": _dock_column_px,
        "minPx": _PALETTE_MIN_H,
        "note": _last_apply_note,
    })


def _handle_set_palette_height(payload: dict) -> None:
    global _dock_column_px
    if _palette is None or not _is_palette_alive(_palette):
        return

    _note_dock_column()

    if bool(payload.get("full")):
        # The cap cannot be removed — setMaximumSize(0, 0) hard-locks the
        # palette. Raising it to the safe ceiling is equivalent, because the
        # dock layout clamps to the column; the clamped result also re-measures
        # the column, so this doubles as recalibration after a window resize.
        achieved = _apply_palette_height(_PALETTE_MAX_SAFE_PX)
        if achieved > 0 and _is_docked():
            _dock_column_px = achieved
    else:
        try:
            target = int(payload.get("heightPx", 0))
        except Exception:
            target = 0
        if target <= 0:
            return
        _apply_palette_height(target)

    _push_dock_info()


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
        _note_dock_column()
        _push_dock_info()
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

    if action == messaging.ACTION_SET_PALETTE_HEIGHT:
        _handle_set_palette_height(payload)
        return

    # Unknown action — log and ignore (forward-compat per SPEC.md section 7).


def _on_palette_closed() -> None:
    # Closing with the X is the opt-out from auto-reopening: the palette stays
    # away until the toolbar button is clicked again. Ignored when we are the
    # ones hiding it, so auto-hide cannot disable auto-open.
    global _ever_opened
    if _suppress_closed_event:
        return
    _ever_opened = False


def _on_change() -> None:
    app = adsk.core.Application.get()
    _update_poll_enabled(app)
    # republish=False because _publish_active below covers it. Doing both
    # scanned the sketch twice on every sketch entry — measured as ~30 ms of a
    # 47 ms SketchActivate, the most expensive event in the whole add-in.
    _sync_palette_visibility(app, republish=False)
    _publish_active(app)
    # There is no palette dock/resize event in the API, so commandTerminated is
    # the cheapest existing hook for noticing that the user has dragged the
    # palette into or out of a dock column.
    _note_dock_column()
    _push_dock_info()


def _on_selection_changed() -> None:
    app = adsk.core.Application.get()
    # Swallow auto-updates briefly after Show-underconstrained so the
    # generic "Selected:" payload doesn't overwrite "Underconstrained:".
    if time.monotonic() < _swallow_selection_until:
        return
    # No rescan here: selection changes cannot alter the constraint tally, and
    # the poll covers anything that can within one interval.
    _push_selection_info(app)
    _push_selection_tokens(app)
    _zoom_to_active_selection(app)


# --- Sketch poll --------------------------------------------------------
#
# No Fusion event fires while a resident sketch tool edits the sketch. Measured
# 2026-07-25 (tests log %TEMP%\cl_poll.log): applying three tangent constraints
# with the tool left active produced 22 seconds of total event silence — no
# commandTerminated, no activeSelectionChanged — then a single
# "TERM cmd=ConstraintTangent" with the tally already advanced 9 -> 12.
#
# The counts DO move mid-command — confirmed in the same run, which caught
# gc stepping 9 -> 10 -> 11 -> 12 as each tangent constraint landed, well before
# the terminating event. So Fusion does not hold a resident tool's edits in a
# transient state; nothing was simply watching for them.
#
# A setInterval in the palette web view was tried first and abandoned. Note its
# failure reason was never established — that run logged no messages at all,
# equally consistent with the JS not having been deployed. A worker thread is the
# sounder mechanism regardless, since it does not depend on the web view being
# loaded or focused.
#
# The thread itself only calls fireCustomEvent. Fusion runs the handler on the
# main thread; touching the API from the worker would crash.
_POLL_EVENT_ID = "ConstraintLensSketchPoll"
_POLL_INTERVAL_S = 0.5

_poll_stop: threading.Event | None = None
_poll_thread: threading.Thread | None = None

# The poll only fires while a sketch is being edited.
#
# It exists solely to catch edits made by a resident sketch tool, so outside
# sketch-edit mode there is nothing for it to find. Leaving it running there was
# an active harm, not just waste: a custom event dispatched on the main thread
# every 500 ms sits right on Windows' ~500 ms double-click threshold, and a tick
# landing between the two clicks broke double-click-to-edit-sketch in the
# browser and the timeline.
#
# commandTerminated flips this: it fires on SketchActivate when entering a
# sketch and SketchStop when leaving (both confirmed in the probe log), so the
# poll resumes without needing a poll to notice it should resume.
_poll_enabled: bool = False

# At most one tick in flight. Without this the worker fires on schedule whether
# or not the main thread is keeping up, and Fusion queues the events: a measured
# 3.9-second main-thread stall was followed by 8 ticks delivered within 30 ms.
# A minute-long stall would queue 120. Set before firing, cleared by the handler.
_poll_in_flight = threading.Event()


def _start_sketch_poll(app: adsk.core.Application) -> None:
    global _poll_stop, _poll_thread
    if _poll_thread is not None:
        return
    if events.register_custom_event(app, _POLL_EVENT_ID, _on_poll_tick) is None:
        return

    _poll_stop = threading.Event()
    _poll_in_flight.clear()

    def _loop(stop_flag: threading.Event) -> None:
        # wait() doubles as the sleep and the cancellation check, so stop() is
        # never left waiting a full interval for the thread to notice.
        while not stop_flag.wait(_POLL_INTERVAL_S):
            if not _poll_enabled:
                continue          # not editing a sketch — stay completely quiet
            if _poll_in_flight.is_set():
                continue          # main thread still busy — skip, don't queue
            _poll_in_flight.set()
            try:
                adsk.core.Application.get().fireCustomEvent(_POLL_EVENT_ID)
            except Exception:
                _poll_in_flight.clear()
                return

    _poll_thread = threading.Thread(target=_loop, args=(_poll_stop,), daemon=True)
    _poll_thread.start()


def _stop_sketch_poll() -> None:
    global _poll_stop, _poll_thread
    if _poll_stop is not None:
        _poll_stop.set()
    if _poll_thread is not None:
        try:
            _poll_thread.join(timeout=2.0)
        except Exception:
            pass
    _poll_thread = None
    _poll_stop = None
    try:
        adsk.core.Application.get().unregisterCustomEvent(_POLL_EVENT_ID)
    except Exception:
        pass


def _update_poll_enabled(app: adsk.core.Application) -> None:
    """Enable the poll only while a sketch is being edited (see _poll_enabled)."""
    global _poll_enabled
    try:
        _poll_enabled = scanner.active_sketch(app) is not None
    except Exception:
        _poll_enabled = False


def _on_poll_tick() -> None:
    try:
        app = adsk.core.Application.get()
        # Lets the poll switch itself off the moment the sketch closes, without
        # waiting for a commandTerminated that may not come.
        _update_poll_enabled(app)
        # Before the rescan: _republish_if_sketch_changed() bails out on a
        # hidden palette, so auto-show has to get its chance first.
        _sync_palette_visibility(app)
        _republish_if_sketch_changed(app)
    finally:
        # In a finally so a raising tick cannot wedge the poll permanently.
        _poll_in_flight.clear()


def _sync_palette_visibility(app: adsk.core.Application, republish: bool = True) -> None:
    """Track sketch-edit mode: hidden outside it, restored on re-entry.

    Restoring is gated on _ever_opened so the palette only reappears in
    sessions where it was actually asked for.

    Collapse is deliberately not touched. Fusion's native collapse arrows on a
    docked palette are not exposed to the API — the whole Palette surface is
    isVisible / dockingState / dockingOption / size / position — so whatever
    collapsed state Fusion remembers is simply carried through the hide/show.
    Dock position is left alone too: forcing it was tried in v1.2.0 and
    reverted in v1.2.1 as redundant and confusing.
    """
    global _suppress_closed_event
    if _palette is None or _applying_height:
        return
    if not _is_palette_alive(_palette):
        return
    try:
        in_sketch = scanner.active_sketch(app) is not None
    except Exception:
        return

    try:
        if not in_sketch:
            if _palette.isVisible:
                _suppress_closed_event = True
                try:
                    _palette.isVisible = False
                finally:
                    _suppress_closed_event = False
        elif _ever_opened and not _palette.isVisible:
            _palette.isVisible = True
            # Data went stale while hidden: messaging.send() drops everything
            # for an invisible palette (landmine M-8). Skipped when the caller
            # is about to publish anyway.
            if republish:
                _publish_active(app)
                _push_selection_info(app)
                _push_selection_tokens(app)
    except Exception:
        pass


def _sketch_counts(sketch) -> tuple[int, int]:
    """Geometric-constraint and dimension tally — two property reads, no
    enumeration, so it is safe to call on every selection change."""
    try:
        return sketch.geometricConstraints.count, sketch.sketchDimensions.count
    except Exception:
        return (-1, -1)


def _republish_if_sketch_changed(app: adsk.core.Application) -> None:
    """Rescan when constraints have been added or removed since the last scan.

    Covers the case commandTerminated misses: a constraint tool that stays
    active while the user applies it to one pair of entities after another.
    """
    if _palette is None:
        return
    # Nothing to update behind a hidden palette, and messaging.send() would
    # drop the payload anyway — so skip before doing any scanning work.
    try:
        if not _palette.isVisible:
            return
    except Exception:
        return
    try:
        sketch = scanner.active_sketch(app)
    except Exception:
        return
    if sketch is None:
        return
    counts = _sketch_counts(sketch)
    if counts == (-1, -1) or counts == _last_sketch_counts:
        return
    _publish_active(app)


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
    # Kept separately from `items` because a pair measurement needs both raw
    # entities even when one of them has no per-entity properties to show.
    selected: list = []
    try:
        sel = ui.activeSelections
        for i in range(sel.count):
            try:
                ent = sel.item(i).entity
            except Exception:
                continue
            if ent is None:
                continue
            selected.append(ent)
            item = _format_selection_entity(ent, units, labeler)
            if item is not None:
                items.append(item)
    except Exception:
        pass

    pair = _pair_measurements(app, selected, units, labeler)
    if pair is not None:
        items.insert(0, pair)
    return {"items": items}


def _pair_measurements(app, entities: list, units, labeler) -> dict | None:
    """Derived measurements for a two-entity selection (issue #8).

    Uses Fusion's own MeasureManager rather than hand-rolled geometry, so the
    numbers match what Fusion's Measure tool reports. Its docs state both
    methods accept "any sketch entity", which covers every case in the issue
    with one mechanism:

      2 points      -> Distance   (minimum distance)
      point + line  -> Distance   (Fusion handles point-to-segment properly)
      2 circles     -> Distance   (gap between circumferences; for concentric
                                   circles this is |r1 - r2|, the radial offset)
      2 lines       -> Angle, and Distance too — for parallel lines the angle
                       is 0 and the distance is the number you actually want

    Returned as an ordinary selection item, so the existing footer renderer
    needs no changes. Placed first in the list because when you select two
    entities, the derived value is the thing you selected them to see.
    """
    if len(entities) != 2:
        return None
    a, b = entities

    try:
        measure = app.measureManager
    except Exception:
        return None
    if measure is None:
        return None

    props: list[dict] = []
    try:
        result = measure.measureMinimumDistance(a, b)
        if result is not None:
            props.append({"key": "Distance", "value": _fmt_length(units, result.value)})
    except Exception:
        # Some entity combinations are not measurable; skip rather than error.
        pass

    # Angle only means something between two linear entities.
    if isinstance(a, adsk.fusion.SketchLine) and isinstance(b, adsk.fusion.SketchLine):
        try:
            result = measure.measureAngle(a, b)
            if result is not None:
                props.append({"key": "Angle", "value": _fmt_angle(units, result.value)})
        except Exception:
            pass

    if not props:
        return None
    label = f"{_selection_label(a, labeler)} ↔ {_selection_label(b, labeler)}"
    return {"label": label, "props": props}


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
    # Sketch dimensions have no entity label, and the raw type name leaked
    # through as e.g. "SketchDiameterDimension". Use the friendly kind name
    # plus the parameter identifier: "Diameter d56".
    param = getattr(entity, "parameter", None)
    if param is not None:
        try:
            kind = dispatch.dimension_kind(entity.objectType)
            name = getattr(param, "name", "") or ""
            return f"{kind} {name}".strip()
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
                # geometry is sketch-space, so Z is meaningful in a 3D sketch
                # (issue #10b). Shown unconditionally rather than only when
                # non-zero: in a 3D sketch a point can legitimately sit at Z=0,
                # and hiding the field there would read as "no Z information".
                g = entity.geometry
                props.append({"key": "X", "value": _fmt_length(units, g.x)})
                props.append({"key": "Y", "value": _fmt_length(units, g.y)})
                props.append({"key": "Z", "value": _fmt_length(units, g.z)})
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
            got_any = False
            # Identifier first (issue #10a): d526 is what you reference from
            # other expressions, and it is the field that says *which*
            # dimension this is when several read the same value.
            try:
                name = getattr(param, "name", None)
                if name:
                    props.append({"key": "Name", "value": str(name)})
                    got_any = True
            except Exception:
                pass
            try:
                expr = getattr(param, "expression", None)
                if expr:
                    # Same treatment as the dimension rows: format plain
                    # numbers at document precision, pass formulas through.
                    shown = scanner.dimension_display(param, str(expr), units)
                    props.append({"key": "Value", "value": shown})
                    got_any = True
            except Exception:
                pass
            if got_any:
                return props
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


# formatValue, not formatInternalValue.
#
# formatInternalValue is not in the API stubs and formats at full precision —
# it is what produced readouts like "RADIUS 2.7873295 mm". formatValue takes the
# same internal-unit input (cm for length, radians for angle) but defaults to
# precision=-1, meaning "use the precision from the user's preferences", so the
# palette now matches the numbers Fusion shows everywhere else.
def _fmt_length(units, value_cm) -> str:
    if units is not None:
        try:
            return units.formatValue(value_cm, units.defaultLengthUnits)
        except Exception:
            pass
    return f"{value_cm:.4g} cm"


def _fmt_angle(units, value_rad) -> str:
    if units is not None:
        try:
            return units.formatValue(value_rad, "deg")
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
    global _last_sketch_counts
    if _palette is None:
        return
    sketch = scanner.active_sketch(app)
    if sketch is None:
        _last_sketch_counts = (-1, -1)
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
    # Recorded here, the one place a scan is published, so the tally cannot
    # drift out of step with what the palette is actually showing.
    _last_sketch_counts = _sketch_counts(sketch)
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
