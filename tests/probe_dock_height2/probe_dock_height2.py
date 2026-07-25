# tests/probe_dock_height2/probe_dock_height2.py
# Run from Fusion: Tools -> Scripts and Add-Ins -> Scripts -> Run.
#
# Follow-up to probe_dock_height. Round 1 established:
#
#   * Every native side-docked palette (Browser, Comments, Sketch Palette, ...)
#     uses dockingOption = 1 (ToVerticalOnly). A custom palette defaults to
#     3 (ToVerticalAndHorizontal) — the one value no native side palette uses.
#   * The round-1 throwaway WAS drag-resizable when docked, but only after P4
#     had already changed its dockingOption to 1. Cause vs. coincidence is
#     unresolved — that is question A below.
#   * setMaximumSize(420, 481) on a DOCKED palette returns False and does not
#     resize it, but it does register a drag ceiling: the observed limit was
#     ~85%, and 481/541 = 88.9%. So the call half-works.
#   * setSize() and the height property were never tested at all — that is
#     question B, and both requested controls depend on the answer.
#
# TWO QUESTIONS:
#   A. Does dockingOption=1 cause the docked drag handle, or was it already
#      there? Answered by running this script TWICE and comparing.
#   B. Can a docked palette's height be set from code at all? Answered by the
#      automated matrix in stage 1 (M1-M5), no eyeballing needed.
#
# HOW TO RUN — this is a TWO-RUN probe, it advances a stage automatically:
#
#   Run #1  -> STAGE 0 (baseline: dockingOption left at the 3 default, no size
#              calls whatsoever). Dismiss the message box, TRY TO DRAG the
#              palette's bottom edge, note the answer, then close the palette.
#   Run #2  -> STAGE 1 (dockingOption = 1, nothing else different) plus the
#              automated M1-M5 size-API matrix. Same drill: dismiss, drag, note.
#
# If A's answer is "stage 0 not draggable, stage 1 draggable", dockingOption is
# the fix and it is a one-line change in lifecycle.py.
#
# The stage counter lives in %TEMP%\cl_probe_dock2_stage.txt and wraps 0 -> 1 -> 0.
# Set _FORCE_STAGE below to 0 or 1 to re-run a specific stage.
#
# Output: %TEMP%\cl_probe_dock_height2_stage<N>.txt (one file per stage, so both
# survive). Safety rails from round 1 still apply: never 0, never >= 9999.

import os
import pathlib
import tempfile
import time
import traceback

import adsk.core


_FORCE_STAGE = None          # None = auto-advance; 0 or 1 = pin to that stage
_N_STAGES = 2

_THROWAWAY_ID = "ConstraintLensDockHeightProbe2"
_MATRIX_ID = "ConstraintLensDockHeightMatrix"

_STATE_PATH = os.path.join(tempfile.gettempdir(), "cl_probe_dock2_stage.txt")

_SAFE_PX_MIN = 40
_SAFE_PX_MAX = 4000


def _safe_px(value: int) -> int:
    return max(_SAFE_PX_MIN, min(_SAFE_PX_MAX, int(value)))


def _section(out: list[str], title: str) -> None:
    out.append("")
    out.append("=" * 72)
    out.append(title)
    out.append("=" * 72)


def _settle(ticks: int = 3, pause: float = 0.08) -> None:
    for _ in range(ticks):
        adsk.doEvents()
        time.sleep(pause)


def _read(obj, attr):
    try:
        return getattr(obj, attr)
    except Exception as exc:
        return f"<raised {type(exc).__name__}: {exc}>"


def _stage() -> int:
    if _FORCE_STAGE is not None:
        return int(_FORCE_STAGE)
    try:
        with open(_STATE_PATH, encoding="utf-8") as f:
            return int(f.read().strip()) % _N_STAGES
    except Exception:
        return 0


def _advance(stage: int) -> None:
    try:
        with open(_STATE_PATH, "w", encoding="utf-8") as f:
            f.write(str((stage + 1) % _N_STAGES))
    except Exception:
        pass


# --- Palette helpers ----------------------------------------------------


def _palette_html_url(out: list[str]) -> str:
    here = os.path.dirname(os.path.realpath(__file__))
    candidates = [
        os.path.join(here, "..", "..", "ConstraintLens", "palette", "index.html"),
        os.path.join(
            os.environ.get("APPDATA", ""),
            "Autodesk", "Autodesk Fusion 360", "API", "AddIns",
            "ConstraintLens", "palette", "index.html",
        ),
    ]
    for candidate in candidates:
        path = os.path.normpath(candidate)
        if os.path.exists(path):
            url = pathlib.Path(path).as_uri()
            out.append(f"  page: {url}")
            return url
    out.append("  page: about:blank (real index.html not found)")
    return "about:blank"


def _make(ui, palette_id: str, name: str, out: list[str]):
    """Create a throwaway with EXACTLY production's palettes.add() arguments."""
    try:
        existing = ui.palettes.itemById(palette_id)
        if existing is not None:
            existing.deleteMe()
            _settle(1)
    except Exception:
        pass
    try:
        p = ui.palettes.add(
            palette_id, name, _palette_html_url(out),
            True,   # isVisible
            True,   # showCloseButton
            True,   # isResizable
            420, 600,
            True,   # useNewWebBrowser
        )
        _settle()
        out.append(f"  created {palette_id} (420x600) — "
                   f"dockingOption at creation = {_read(p, 'dockingOption')}")
        return p
    except Exception as exc:
        out.append(f"  could not create {palette_id}: {exc}")
        return None


def _dock_right(p, out: list[str]) -> bool:
    """Round 1 hit InternalValidationError re-assigning Right while already Right."""
    right = adsk.core.PaletteDockingStates.PaletteDockStateRight
    if _read(p, "dockingState") == right:
        out.append("  already docked right — no re-assignment (round 1 threw on this)")
        return True
    try:
        p.dockingState = right
        _settle()
        out.append(f"  docked right; dockingState = {_read(p, 'dockingState')}")
        return True
    except Exception as exc:
        out.append(f"  dock right FAILED: {type(exc).__name__}: {exc}")
        return False


def _float(p, out: list[str]) -> bool:
    floating = adsk.core.PaletteDockingStates.PaletteDockStateFloating
    if _read(p, "dockingState") == floating:
        return True
    try:
        p.dockingState = floating
        _settle()
        return True
    except Exception as exc:
        out.append(f"  float FAILED: {type(exc).__name__}: {exc}")
        return False


# --- Question B: can a docked palette's height be set from code? --------


def matrix(ui, out: list[str]) -> None:
    _section(out, "B  Size-API matrix — can a DOCKED palette be resized from code?")
    out.append("  Round 1 only tested the setMinimumSize/setMaximumSize bounce.")
    out.append("  setSize() and the height property were never tried. Both the")
    out.append("  50/75/100 toggle and the drag grip need one of these to work.")

    p = _make(ui, _MATRIX_ID, "CL size matrix", out)
    if p is None:
        return

    try:
        if not _dock_right(p, out):
            return
        column = _read(p, "height")
        width = _read(p, "width")
        if not isinstance(column, int) or column <= 0:
            out.append("  column height unreadable — aborting matrix")
            return
        if not isinstance(width, int) or width <= 0:
            width = 420
        target = _safe_px(int(column * 0.60))
        out.append("")
        out.append(f"  column height = {column}, width = {width}, target T = {target}")

        def report(tag: str) -> None:
            out.append(f"    {tag:<44} height={_read(p, 'height')} "
                       f"dockState={_read(p, 'dockingState')}")

        # M1 — setSize() while docked.
        out.append("")
        out.append("  --- M1  setSize(w, T) while docked ---")
        try:
            rv = p.setSize(width, target)
            _settle()
            out.append(f"    returned {rv!r}")
            report("after setSize")
        except Exception as exc:
            out.append(f"    RAISED {type(exc).__name__}: {exc}")

        # M2 — the height property while docked.
        out.append("")
        out.append("  --- M2  palette.height = T while docked ---")
        try:
            p.height = target
            _settle()
            report("after height =")
        except Exception as exc:
            out.append(f"    RAISED {type(exc).__name__}: {exc}")

        # M3 — float, resize, re-dock. Does the height survive the round trip?
        out.append("")
        out.append("  --- M3  float -> setSize(T) -> re-dock right ---")
        _float(p, out)
        report("floating")
        try:
            p.setSize(width, target)
            _settle()
            report("floating, after setSize")
        except Exception as exc:
            out.append(f"    setSize RAISED {type(exc).__name__}: {exc}")
        _dock_right(p, out)
        report("re-docked")

        # M4 — cap set WHILE FLOATING, then dock. Round 1 only ever capped
        # while already docked. Production sets its size constraints right
        # after add(), i.e. while still floating — so this is the case that
        # actually matches the shipped code path.
        out.append("")
        out.append("  --- M4  setMaximumSize while FLOATING, then dock ---")
        _float(p, out)
        try:
            rv = p.setMaximumSize(width, target)
            _settle()
            out.append(f"    setMaximumSize returned {rv!r} (floating)")
            report("floating, after setMaximumSize")
        except Exception as exc:
            out.append(f"    RAISED {type(exc).__name__}: {exc}")
        _dock_right(p, out)
        report("re-docked with a pre-set cap")

        # M5 — cap while docked, then float/re-dock to force a re-layout.
        out.append("")
        out.append("  --- M5  cap while docked, then float+redock as a nudge ---")
        bigger = _safe_px(int(column * 0.80))
        try:
            rv = p.setMaximumSize(width, bigger)
            out.append(f"    setMaximumSize(w, {bigger}) returned {rv!r} (docked)")
            report("docked, right after cap")
        except Exception as exc:
            out.append(f"    RAISED {type(exc).__name__}: {exc}")
        _float(p, out)
        report("floated")
        _dock_right(p, out)
        report("re-docked after the nudge")

        out.append("")
        out.append("  READ THIS SECTION AS: any row where height changed to the")
        out.append("  target is a mechanism we can build the toggle and grip on.")
        out.append("  If every row stays at the column height, both controls have")
        out.append("  to be driven by the drag-ceiling trick instead.")
    finally:
        try:
            p.deleteMe()
            _settle(1)
        except Exception:
            pass


# --- Question A: is dockingOption the cause of the drag handle? ---------


def visual_stage(ui, stage: int, out: list[str]) -> list[str]:
    _section(out, f"A  Drag-handle isolation — STAGE {stage}")

    p = _make(ui, _THROWAWAY_ID, f"CL probe2 stage {stage}", out)
    if p is None:
        return ["Palette could not be created — nothing to check."]

    if stage == 0:
        out.append("  BASELINE: dockingOption left untouched, no setMinimumSize,")
        out.append("  no setMaximumSize. This is production's exact configuration")
        out.append("  minus the setMinimumSize(200,150) call.")
    else:
        option = adsk.core.PaletteDockingOptions.PaletteDockOptionsToVerticalOnly
        try:
            p.dockingOption = option
            _settle()
            out.append(f"  dockingOption set to {option} (ToVerticalOnly) — the value")
            out.append(f"  every native side palette uses. read back = "
                       f"{_read(p, 'dockingOption')}")
        except Exception as exc:
            out.append(f"  dockingOption assignment FAILED: {exc}")
        out.append("  Still NO setMinimumSize / setMaximumSize calls, so this differs")
        out.append("  from stage 0 by exactly one property.")

    _dock_right(p, out)
    out.append(f"  height while docked = {_read(p, 'height')}  "
               f"width = {_read(p, 'width')}")

    questions = [
        f"STAGE {stage} — can you DRAG the palette's bottom edge to resize it?",
        "",
        "  Answer just: draggable YES or NO.",
        "  If YES, roughly what height range does the drag cover?",
        "",
        "Then close this palette with its X button and run the script again",
        f"to get stage {(stage + 1) % _N_STAGES}.",
    ]
    out.append("")
    out.extend(questions)
    return questions


# --- Entry point --------------------------------------------------------


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        stage = _stage()
        out: list[str] = []
        out.append(f"ConstraintLens dock-height probe — ROUND 2, STAGE {stage}")
        out.append("Fusion build: " + str(_read(app, "version")))

        # The size matrix only needs to run once; fold it into stage 1 so
        # stage 0 stays a clean, untouched baseline.
        if stage == 1:
            matrix(ui, out)

        questions = visual_stage(ui, stage, out)

        text = "\n".join(out)
        out_path = os.path.join(
            tempfile.gettempdir(), f"cl_probe_dock_height2_stage{stage}.txt"
        )
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)
            saved = f"Output written to:\n{out_path}"
        except Exception as exc:
            saved = f"Could not write dump ({exc}):\n\n" + text[:2500]

        _advance(stage)

        ui.messageBox(
            f"Round 2, stage {stage} ready.\n\n"
            + saved
            + "\n\nThe probe palette is LEFT OPEN on purpose.\n\n"
            + "\n".join(questions)
        )
    except Exception:
        if ui:
            ui.messageBox("Round-2 probe failed:\n" + traceback.format_exc())
