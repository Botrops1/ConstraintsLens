# tests/probe_dock_height/probe_dock_height.py
# Run from Fusion: Tools -> Scripts and Add-Ins -> Scripts -> Run.
#
# Probe for the docked-palette height problem (v1.6.0 candidate).
#
# BEFORE RUNNING: open a sketch and attach Fusion's own Sketch Palette the way
# you want ConstraintLens to behave (docked/snapped to a side edge, shorter than
# the full column). Section P1 photographs that working configuration so we can
# copy it.
#
# Sections:
#   P1  Read-only census of EVERY live palette (id, isNative, dockingState,
#       dockingOption, width, height, left, top). The Sketch Palette's row is
#       the reference config we are trying to reproduce, and it settles whether
#       that palette is genuinely *docked* or merely *snapped*.
#   P2  Measure the dock column height, then cap just under it and read the
#       height back. Tests the primary hypothesis: Fusion arms the bottom drag
#       handle only when setMaximumSize leaves slack in the column.
#   P3  The "grow trick" — setMaximumSize(T) -> setMinimumSize(T) ->
#       setMinimumSize(relax). Proves whether we can drive height to an exact
#       value from code, which both non-native controls depend on.
#   P4  dockingOption — never tried before in this repo. Assign each value,
#       read back.
#
# P2-P4 mutate a THROWAWAY palette only, never the live ConstraintLens palette:
# a max-size restriction cannot be cleanly removed afterwards, because
# setMaximumSize(0, 0) is documented as "no restriction" but was observed to
# hard-lock the palette to 0x0 in this build.
#
# Hard safety rails: never pass 0, never pass >= 9999 (crashes / deactivates the
# add-in). See _safe_px().
#
# Output: full dump to %TEMP%\cl_probe_dock_height.txt plus a message box. The
# throwaway palette is left OPEN and docked at the end so you can try dragging
# its bottom edge; close it with its own X button when done.

import os
import pathlib
import tempfile
import time
import traceback

import adsk.core


_THROWAWAY_PALETTE_ID = "ConstraintLensDockHeightProbe"

# Safety rails, from the recorded failure history:
#   >= 9999 -> Fusion crash / add-in deactivation
#   0       -> hard 0x0 lock (contradicts the docs; treat as a landmine)
_SAFE_PX_MIN = 40
_SAFE_PX_MAX = 4000

# Gap left below the palette when capping, so the dock column has slack for a
# separator to live in.
_CAP_GAP_PX = 60

_RELAX_MIN_W = 200
_RELAX_MIN_H = 150


def _safe_px(value: int, what: str) -> int:
    """Clamp a pixel value into the range known not to crash Fusion."""
    v = int(value)
    if v < _SAFE_PX_MIN:
        v = _SAFE_PX_MIN
    if v > _SAFE_PX_MAX:
        v = _SAFE_PX_MAX
    if v != int(value):
        _CLAMP_LOG.append(f"    (clamped {what}: {value} -> {v})")
    return v


_CLAMP_LOG: list[str] = []


def _section(out: list[str], title: str) -> None:
    out.append("")
    out.append("=" * 72)
    out.append(title)
    out.append("=" * 72)


def _settle(ticks: int = 3, pause: float = 0.08) -> None:
    """Give Fusion a chance to apply a docking / sizing change."""
    for _ in range(ticks):
        adsk.doEvents()
        time.sleep(pause)


def _enum_map(enum_cls) -> dict:
    """int value -> member name, for rendering dockingState / dockingOption."""
    mapping = {}
    try:
        for name in dir(enum_cls):
            if name.startswith("_"):
                continue
            try:
                value = getattr(enum_cls, name)
            except Exception:
                continue
            if isinstance(value, int):
                mapping[value] = name
    except Exception:
        pass
    return mapping


def _read(obj, attr):
    """Read a property, returning a marker string instead of raising."""
    try:
        return getattr(obj, attr)
    except Exception as exc:
        return f"<raised {type(exc).__name__}: {exc}>"


def _fmt_enum(value, mapping: dict) -> str:
    if isinstance(value, int):
        return f"{value} ({mapping.get(value, '?')})"
    return repr(value)


# --- P1  Census ---------------------------------------------------------


def probe_census(ui: adsk.core.UserInterface, out: list[str]) -> dict:
    """Read-only inventory of every live palette. Returns the Sketch Palette row."""
    _section(out, "P1  Census of every live palette (READ-ONLY)")

    state_map = _enum_map(adsk.core.PaletteDockingStates)
    option_map = _enum_map(getattr(adsk.core, "PaletteDockingOptions", object))

    out.append(f"  PaletteDockingStates  : {state_map}")
    out.append(f"  PaletteDockingOptions : {option_map}")
    out.append("")

    sketch_row: dict = {}
    try:
        palettes = ui.palettes
        count = palettes.count
        out.append(f"  ui.palettes.count = {count}")
    except Exception as exc:
        out.append(f"  ERROR reading ui.palettes: {exc}")
        return sketch_row

    for i in range(count):
        try:
            p = palettes.item(i)
        except Exception as exc:
            out.append(f"  [{i:2}] <could not read item: {exc}>")
            continue

        pid = _read(p, "id")
        row = {
            "id": pid,
            "name": _read(p, "name"),
            "isNative": _read(p, "isNative"),
            "isVisible": _read(p, "isVisible"),
            "dockingState": _read(p, "dockingState"),
            "dockingOption": _read(p, "dockingOption"),
            "width": _read(p, "width"),
            "height": _read(p, "height"),
            "left": _read(p, "left"),
            "top": _read(p, "top"),
            "isTransparent": _read(p, "isTransparent"),
        }

        out.append("")
        out.append(f"  [{i:2}] id={row['id']!r}  name={row['name']!r}")
        out.append(f"       isNative={row['isNative']}  isVisible={row['isVisible']}"
                   f"  isTransparent={row['isTransparent']}")
        out.append(f"       dockingState  = {_fmt_enum(row['dockingState'], state_map)}")
        out.append(f"       dockingOption = {_fmt_enum(row['dockingOption'], option_map)}")
        out.append(f"       size  w={row['width']} h={row['height']}")
        out.append(f"       pos   left={row['left']} top={row['top']}")

        if isinstance(pid, str) and "sketch" in pid.lower():
            sketch_row = row
            out.append("       ^^^ SKETCH PALETTE — this is the reference config.")

    out.append("")
    if sketch_row:
        out.append("  >>> Sketch Palette found. Its dockingOption will be mirrored onto")
        out.append("      the throwaway palette for the final visual check.")
    else:
        out.append("  >>> No palette with 'sketch' in its id was found. Either no sketch")
        out.append("      is open, or the Sketch Palette is not exposed via ui.palettes.")
        out.append("      Re-run this probe with a sketch open and the Sketch Palette")
        out.append("      attached the way you want ConstraintLens to behave.")

    return sketch_row


# --- Throwaway palette --------------------------------------------------


def _palette_html_url(out: list[str]) -> str:
    """Absolute file:/// URL to the real palette page, so the throwaway has the
    same CSS size-hint behaviour as production. Falls back to about:blank."""
    here = os.path.dirname(os.path.realpath(__file__))
    candidates = [
        # Running from the repo: tests/probe_dock_height/ -> ../../ConstraintLens/
        os.path.join(here, "..", "..", "ConstraintLens", "palette", "index.html"),
        # Running from a deployed add-in tree.
        os.path.join(
            os.environ.get("APPDATA", ""),
            "Autodesk", "Autodesk Fusion 360", "API", "AddIns",
            "ConstraintLens", "palette", "index.html",
        ),
    ]
    for candidate in candidates:
        path = os.path.normpath(candidate)
        if os.path.exists(path):
            # as_uri() percent-encodes; the repo path contains spaces, which a
            # hand-built "file:///" + path would leave broken.
            url = pathlib.Path(path).as_uri()
            out.append(f"  Throwaway page: {url}")
            return url
    out.append("  Throwaway page: about:blank (real index.html not found —")
    out.append("    results are still valid but the web view's size hint may differ).")
    return "about:blank"


def _make_throwaway(ui: adsk.core.UserInterface, out: list[str]):
    try:
        existing = ui.palettes.itemById(_THROWAWAY_PALETTE_ID)
        if existing is not None:
            existing.deleteMe()
            _settle(1)
    except Exception:
        pass

    html_url = _palette_html_url(out)
    try:
        palette = ui.palettes.add(
            _THROWAWAY_PALETTE_ID,
            "CL dock-height probe",
            html_url,
            True,    # isVisible
            True,    # showCloseButton  (you close it yourself when done)
            True,    # isResizable
            420,
            600,
            True,    # useNewWebBrowser
        )
        out.append("  Throwaway palette created (420x600, isResizable=True).")
        _settle()
        return palette
    except Exception as exc:
        out.append(f"  Could not create throwaway palette: {exc}")
        return None


def _dock_right(palette, out: list[str]) -> bool:
    try:
        palette.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateRight
        _settle()
        out.append(f"  Docked right. dockingState now = {_read(palette, 'dockingState')}")
        return True
    except Exception as exc:
        out.append(f"  Could not dock right: {type(exc).__name__}: {exc}")
        return False


# --- P2  Measure the column, then cap under it --------------------------


def probe_measure_and_cap(palette, out: list[str]) -> int:
    """Returns the measured dock column height, or 0 if it could not be read."""
    _section(out, "P2  Measure dock column height, then cap just under it")

    if not _dock_right(palette, out):
        return 0

    column_h = _read(palette, "height")
    width = _read(palette, "width")
    out.append("")
    out.append("  While docked and filling the column:")
    out.append(f"    palette.width  = {width}")
    out.append(f"    palette.height = {column_h}   <-- THIS IS THE DOCK COLUMN HEIGHT")

    if not isinstance(column_h, int) or column_h <= 0:
        out.append("  Height is not a usable integer — cannot continue with P2.")
        return 0
    if not isinstance(width, int) or width <= 0:
        width = 420
        out.append(f"  Width unreadable; using {width} for subsequent calls.")

    target = _safe_px(column_h - _CAP_GAP_PX, "cap target")
    out.append("")
    out.append(f"  Calling setMaximumSize({width}, {target})  "
               f"(column {column_h} minus {_CAP_GAP_PX} px gap)")
    try:
        result = palette.setMaximumSize(width, target)
        out.append(f"    returned {result!r}  (NOTE: return value is unreliable per the docs)")
    except Exception as exc:
        out.append(f"    RAISED {type(exc).__name__}: {exc}")
        return column_h

    _settle()
    after = _read(palette, "height")
    out.append(f"    palette.height read back = {after}")
    out.append("")
    if isinstance(after, int) and after <= target + 2:
        out.append("  => CAP WAS APPLIED. The palette is now shorter than the column,")
        out.append("     which is the precondition for a bottom drag handle to exist.")
    else:
        out.append("  => CAP WAS IGNORED. The palette still fills the column.")
        out.append("     If so, the max-size lever does not work here and the")
        out.append("     implementation must go to Branch B (custom controls only).")

    return column_h


# --- P3  The grow trick -------------------------------------------------


def probe_grow_trick(palette, column_h: int, out: list[str]) -> None:
    _section(out, "P3  Grow trick — drive the height to an exact value from code")

    out.append("  Sequence under test, for a target height T:")
    out.append("    setMaximumSize(w, T)      -> shrinks if currently taller")
    out.append("    setMinimumSize(w, T)      -> grows if currently shorter")
    out.append("    setMinimumSize(200, 150)  -> relax the floor again")
    out.append("  Both non-native controls (size toggle + drag grip) depend on this")
    out.append("  working, independently of whether P2's native handle appears.")

    width = _read(palette, "width")
    if not isinstance(width, int) or width <= 0:
        width = 420

    if not column_h:
        out.append("  No column height measured in P2 — skipping.")
        return

    # Shrink to 50% of the column, then grow to 75%. Growing is the hard
    # direction: setMaximumSize alone can never enlarge a palette.
    for label, fraction in (("50%", 0.50), ("75%", 0.75), ("100%-gap", None)):
        if fraction is None:
            target = _safe_px(column_h - _CAP_GAP_PX, "T(100%-gap)")
        else:
            target = _safe_px(int(column_h * fraction), f"T({label})")

        out.append("")
        out.append(f"  --- target {label} = {target} px ---")
        before = _read(palette, "height")
        out.append(f"    height before                  = {before}")

        for call, args in (
            ("setMaximumSize", (width, target)),
            ("setMinimumSize", (width, target)),
            ("setMinimumSize", (_RELAX_MIN_W, _RELAX_MIN_H)),
        ):
            try:
                getattr(palette, call)(*args)
                _settle(2)
                out.append(f"    after {call}{args}".ljust(52)
                           + f"= {_read(palette, 'height')}")
            except Exception as exc:
                out.append(f"    {call}{args} RAISED {type(exc).__name__}: {exc}")

        final = _read(palette, "height")
        hit = isinstance(final, int) and abs(final - target) <= 2
        out.append(f"    FINAL height = {final}   target = {target}   "
                   f"{'HIT' if hit else 'MISS'}")


# --- P4  dockingOption --------------------------------------------------


def probe_docking_option(palette, out: list[str]) -> None:
    _section(out, "P4  dockingOption — never exercised before in this repo")

    options_cls = getattr(adsk.core, "PaletteDockingOptions", None)
    if options_cls is None:
        out.append("  adsk.core.PaletteDockingOptions not present in this build.")
        return

    option_map = _enum_map(options_cls)
    out.append(f"  Current dockingOption = "
               f"{_fmt_enum(_read(palette, 'dockingOption'), option_map)}")

    for name in (
        "PaletteDockOptionsToVerticalOnly",
        "PaletteDockOptionsToHorizontalOnly",
        "PaletteDockOptionsToVerticalAndHorizontal",
        "PaletteDockOptionsNone",
    ):
        out.append("")
        if not hasattr(options_cls, name):
            out.append(f"  [{name}] not present — skipped.")
            continue
        value = getattr(options_cls, name)
        try:
            palette.dockingOption = value
            _settle(2)
            out.append(f"  [{name}] assigned {value}; "
                       f"read back = {_read(palette, 'dockingOption')}; "
                       f"height = {_read(palette, 'height')}; "
                       f"dockingState = {_read(palette, 'dockingState')}")
        except Exception as exc:
            out.append(f"  [{name}] RAISED {type(exc).__name__}: {exc}")


# --- Final visual state -------------------------------------------------


def setup_visual_state(palette, sketch_row: dict, column_h: int, out: list[str]) -> list[str]:
    """Leave the throwaway in the most promising configuration for eyeballing."""
    _section(out, "FINAL  Visual-check state")

    option_map = _enum_map(getattr(adsk.core, "PaletteDockingOptions", object))
    width = _read(palette, "width")
    if not isinstance(width, int) or width <= 0:
        width = 420

    # Mirror the Sketch Palette's dockingOption if we captured it; otherwise
    # guess vertical-only, which is the closest match to a side-docked panel.
    chosen = sketch_row.get("dockingOption")
    source = "copied from the Sketch Palette"
    if not isinstance(chosen, int):
        options_cls = getattr(adsk.core, "PaletteDockingOptions", None)
        chosen = getattr(options_cls, "PaletteDockOptionsToVerticalOnly", None)
        source = "guessed (Sketch Palette value unavailable)"

    if isinstance(chosen, int):
        try:
            palette.dockingOption = chosen
            out.append(f"  dockingOption set to {_fmt_enum(chosen, option_map)} — {source}")
        except Exception as exc:
            out.append(f"  dockingOption assignment failed: {exc}")

    _dock_right(palette, out)

    if column_h:
        target = _safe_px(column_h - _CAP_GAP_PX, "final cap")
        try:
            palette.setMaximumSize(width, target)
            palette.setMinimumSize(_RELAX_MIN_W, _RELAX_MIN_H)
            _settle()
            out.append(f"  Capped at {target} px (column {column_h} - {_CAP_GAP_PX}).")
            out.append(f"  height now = {_read(palette, 'height')}")
        except Exception as exc:
            out.append(f"  Final cap failed: {exc}")

    questions = [
        "V1. Is there a visible GAP between the bottom of the probe palette and",
        "    the bottom of the Fusion window? (i.e. did the cap take effect)",
        "V2. Can you DRAG the palette's bottom edge up and down to resize it?",
        "V3. If V2 is yes — what is the smallest and largest height you can drag to?",
        "V4. Compare against the Sketch Palette next to it: does the probe palette",
        "    now behave the same way, or is it still different?",
    ]
    out.append("")
    out.extend(questions)
    return questions


# --- Entry point --------------------------------------------------------


def run(context):
    ui = None
    palette = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        out: list[str] = []
        out.append("ConstraintLens dock-height probe")
        out.append("Fusion build: " + str(_read(app, "version")))
        out.append("Run with a sketch open and the Sketch Palette attached as desired.")

        sketch_row = probe_census(ui, out)

        _section(out, "Throwaway palette setup (all mutation tests use this, never the live one)")
        palette = _make_throwaway(ui, out)
        if palette is None:
            ui.messageBox("Probe aborted: could not create the throwaway palette.\n\n"
                          + "\n".join(out[-8:]))
            return

        column_h = probe_measure_and_cap(palette, out)
        probe_grow_trick(palette, column_h, out)
        probe_docking_option(palette, out)
        questions = setup_visual_state(palette, sketch_row, column_h, out)

        if _CLAMP_LOG:
            _section(out, "Safety clamps applied")
            out.extend(_CLAMP_LOG)

        text = "\n".join(out)
        out_path = os.path.join(tempfile.gettempdir(), "cl_probe_dock_height.txt")
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)
            saved = f"Full output written to:\n{out_path}"
        except Exception as exc:
            saved = f"Could not write the dump file ({exc}). Scroll this box instead:\n\n" + text[:2500]

        ui.messageBox(
            "Dock-height probe complete.\n\n"
            + saved
            + "\n\nThe probe palette has been LEFT OPEN on purpose.\n"
            "Dismiss this box, then answer:\n\n"
            + "\n".join(questions)
            + "\n\nClose the probe palette with its own X button when you are done."
        )
    except Exception:
        # Only clean up on failure — on success the palette is left open for the
        # visual checks and you close it yourself.
        if palette is not None:
            try:
                palette.deleteMe()
            except Exception:
                pass
        if ui:
            ui.messageBox("Dock-height probe failed:\n" + traceback.format_exc())
