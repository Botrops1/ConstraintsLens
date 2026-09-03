# tests/probe_palette_position/probe_palette_position.py
# Run from Fusion: Tools -> Scripts and Add-Ins -> Scripts -> Run.
#
# Issue #11: on a multi-monitor setup with Fusion on a SECONDARY monitor, a
# custom palette can open at the top-left of the PRIMARY monitor, off the
# Fusion window entirely. The user sees nothing happen and cannot drag what
# they cannot find.
#
# The agreed fix is to dock the palette on first creation, which puts it inside
# the Fusion window by construction and sidesteps coordinates altogether. That
# fix rests on two assumptions this probe is here to test, because the project
# has already burned four releases (v1.2.0 - v1.3.2) guessing at palette
# geometry and only got it right once probe_dock_height* measured it.
#
# THREE QUESTIONS:
#
#   Q1. What frame are Palette.left / Palette.top in — desktop coordinates, or
#       relative to the Fusion window? Stage 0 dumps left/top for EVERY palette
#       in the session, native ones included. Native docked palettes (Browser,
#       Comments, ...) are inside the Fusion window by definition, so on a
#       secondary monitor:
#         * large left values (roughly the monitor's desktop offset, e.g. 1920
#           or -1920) => DESKTOP coordinates.
#         * small values (near 0, or a few hundred)             => WINDOW-relative.
#       This is the fact that makes setPosition usable or useless, and nothing
#       in the API docs settles it.
#
#   Q2. Does a freshly created palette come back already carrying the docking
#       state Fusion remembered from the previous session, and if so, is that
#       visible to the API immediately after palettes.add() returns? The fix
#       must NOT re-dock somebody who already had the palette docked where they
#       wanted it, so it has to be able to read the restored state correctly.
#       Answered by comparing stage 0 (id never seen before) against stage 1
#       (same id, after a Fusion restart, having been left docked right).
#
#   Q3. Does setPosition actually move a floating palette, and does the value
#       round-trip through left/top? Cheap to answer while we are here.
#
# HOW TO RUN — TWO RUNS with a FUSION RESTART in between:
#
#   Run #1 -> STAGE 0. Creates a throwaway palette with an id Fusion has never
#             seen, records where it lands, tests setPosition, then LEAVES IT
#             DOCKED RIGHT on purpose. Note in the message box whether the
#             palette was visible inside the Fusion window when it appeared.
#             Then RESTART FUSION.
#   Run #2 -> STAGE 1. Recreates the same id and records what state it comes
#             back in. Cleans the throwaway up at the end.
#
# The stage counter lives in %TEMP%\cl_probe_pos_stage.txt and wraps 0 -> 1 -> 0.
# Set _FORCE_STAGE below to pin a stage.
#
# Output: %TEMP%\cl_probe_palette_position_stage<N>.txt (one file per stage).
#
# SAFETY: this probe never calls setMaximumSize and never sets a size at all,
# so the two known landmines (a 0x0 lock, and a crash at >= 9999) are out of
# reach by construction. It only reads geometry, sets dockingState — which
# production already does in _apply_palette_height tier 3 — and calls
# setPosition on its own throwaway, never on the real ConstraintLens palette.

import os
import pathlib
import tempfile
import time
import traceback

import adsk.core


_FORCE_STAGE = None          # None = auto-advance; 0 or 1 = pin to that stage
_N_STAGES = 2

# Deliberately NOT the production id: creating the real one here would give it
# a docking history that muddies stage 1, and deleting it would disturb a
# palette the user may have open.
_THROWAWAY_ID = "ConstraintLensPositionProbe"
_PRODUCTION_ID = "ConstraintLensPalette"

_STATE_PATH = os.path.join(tempfile.gettempdir(), "cl_probe_pos_stage.txt")


def _stage() -> int:
    if _FORCE_STAGE is not None:
        return int(_FORCE_STAGE)
    try:
        with open(_STATE_PATH, "r", encoding="utf-8") as fh:
            return int(fh.read().strip()) % _N_STAGES
    except Exception:
        return 0


def _advance(stage: int) -> None:
    try:
        with open(_STATE_PATH, "w", encoding="utf-8") as fh:
            fh.write(str((stage + 1) % _N_STAGES))
    except Exception:
        pass


def _settle(ticks: int = 3, pause: float = 0.08) -> None:
    for _ in range(ticks):
        adsk.doEvents()
        time.sleep(pause)


def _read(obj, attr):
    try:
        return getattr(obj, attr)
    except Exception as exc:
        return f"<raised {type(exc).__name__}>"


def _dock_name(value) -> str:
    """Turn a dockingState int into something readable in the log."""
    try:
        states = adsk.core.PaletteDockingStates
        names = {
            states.PaletteDockStateFloating: "Floating",
            states.PaletteDockStateTop: "Top",
            states.PaletteDockStateBottom: "Bottom",
            states.PaletteDockStateLeft: "Left",
            states.PaletteDockStateRight: "Right",
        }
        return f"{value} ({names.get(value, 'unknown')})"
    except Exception:
        return str(value)


def _geometry(p) -> str:
    return (
        f"left={_read(p, 'left')} top={_read(p, 'top')} "
        f"w={_read(p, 'width')} h={_read(p, 'height')} "
        f"dock={_dock_name(_read(p, 'dockingState'))} "
        f"visible={_read(p, 'isVisible')}"
    )


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
            return pathlib.Path(path).as_uri()
    return "about:blank"


# --- Q1: where does every palette in the session think it is? -----------


def _inventory(ui, out: list[str]) -> None:
    out.append("Q1 — palette inventory (native palettes included)")
    out.append("  A docked NATIVE palette is inside the Fusion window by")
    out.append("  definition. Its left/top therefore reveals the frame:")
    out.append("  large offsets => desktop coords, small => window-relative.")
    out.append("")
    try:
        palettes = ui.palettes
        out.append(f"  count = {palettes.count}")
        for i in range(palettes.count):
            try:
                p = palettes.item(i)
                pid = _read(p, "id")
                marker = ""
                if pid == _PRODUCTION_ID:
                    marker = "   <-- ConstraintLens (read only, untouched)"
                elif pid == _THROWAWAY_ID:
                    marker = "   <-- this probe's throwaway"
                out.append(f"  [{i:02d}] {pid}{marker}")
                out.append(f"       {_geometry(p)}")
            except Exception as exc:
                out.append(f"  [{i:02d}] <unreadable: {exc}>")
    except Exception:
        out.append("  FAILED:\n" + traceback.format_exc())
    out.append("")


# --- Q2/Q3: the throwaway ------------------------------------------------


def _make(ui, out: list[str]):
    """Create the throwaway with production's exact palettes.add() arguments."""
    p = ui.palettes.add(
        _THROWAWAY_ID, "CL Position Probe", _palette_html_url(out),
        True,    # isVisible
        True,    # showCloseButton
        True,    # isResizable
        420, 600,
        True,    # useNewWebBrowser
    )
    return p


def _stage0(ui, out: list[str]) -> list[str]:
    """Never-seen id: where does Fusion put a brand-new palette?"""
    questions = []
    out.append("STAGE 0 — brand-new palette id, no docking history")
    out.append("=" * 62)
    out.append("")

    _inventory(ui, out)

    existing = ui.palettes.itemById(_THROWAWAY_ID)
    if existing is not None:
        out.append("  NOTE: the throwaway id already existed and was deleted.")
        out.append("  Stage 0 is only meaningful for an id Fusion has never")
        out.append("  seen, so re-run stage 0 after a restart if this fires.")
        try:
            existing.deleteMe()
            _settle(2)
        except Exception:
            pass

    out.append("Q2a — geometry of a NEW palette, read at three moments")
    p = _make(ui, out)
    out.append(f"  immediately after add(): {_geometry(p)}")
    adsk.doEvents()
    out.append(f"  after one doEvents():    {_geometry(p)}")
    _settle(5)
    out.append(f"  after settling:          {_geometry(p)}")
    out.append("")

    out.append("Q3 — setPosition on a FLOATING palette")
    before = (_read(p, "left"), _read(p, "top"))
    try:
        result = p.setPosition(300, 200)
        _settle(3)
        out.append(f"  setPosition(300, 200) returned {result}")
        out.append(f"  before: left={before[0]} top={before[1]}")
        out.append(f"  after:  left={_read(p, 'left')} top={_read(p, 'top')}")
        out.append("  If left/top now read 300/200 the value round-trips, but")
        out.append("  that still does not say WHICH origin it counted from —")
        out.append("  only the Q1 inventory answers that.")
    except Exception:
        out.append("  setPosition RAISED:\n" + traceback.format_exc())
    out.append("")
    questions.append(
        "1. Did the probe palette appear INSIDE the Fusion window, or on "
        "another monitor? (This is the bug reproducing, or not.)"
    )
    questions.append(
        "2. After the setPosition call, did it visibly MOVE — and did it stay "
        "on the same monitor?"
    )

    out.append("Q2b — docking, then left open for stage 1")
    try:
        p.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateRight
        _settle(5)
        out.append(f"  after docking right: {_geometry(p)}")
        out.append("  Leaving it docked. Fusion should remember this for the")
        out.append("  next session — which is what stage 1 checks.")
    except Exception:
        out.append("  docking RAISED:\n" + traceback.format_exc())
    out.append("")
    questions.append(
        "3. Is the probe palette now docked on the right of the Fusion "
        "window, and clearly visible? If yes, docking is a valid fix for #11."
    )
    questions.append("4. NOW RESTART FUSION, then run this probe again.")
    return questions


def _stage1(ui, out: list[str]) -> list[str]:
    """Same id, new session: does the remembered dock come back, and when?"""
    questions = []
    out.append("STAGE 1 — same id, after a Fusion restart")
    out.append("=" * 62)
    out.append("")
    out.append("Stage 0 left this id docked right. If Fusion restores that on")
    out.append("its own, the production fix must read dockingState and skip")
    out.append("its first-run dock for anyone already docked — otherwise it")
    out.append("would yank an existing user's palette to a different edge.")
    out.append("")

    _inventory(ui, out)

    existing = ui.palettes.itemById(_THROWAWAY_ID)
    out.append(f"  itemById before add() -> {existing is not None}")
    if existing is not None:
        out.append(f"    {_geometry(existing)}")
        try:
            existing.deleteMe()
            _settle(2)
        except Exception:
            pass
    out.append("")

    out.append("Q2c — geometry of the RECREATED palette, three moments")
    try:
        p = _make(ui, out)
        out.append(f"  immediately after add(): {_geometry(p)}")
        adsk.doEvents()
        out.append(f"  after one doEvents():    {_geometry(p)}")
        _settle(5)
        out.append(f"  after settling:          {_geometry(p)}")
        out.append("")
        out.append("  READ THIS AS:")
        out.append("   * dock=Right at any of the three -> Fusion restores the")
        out.append("     remembered state; production can read it and skip.")
        out.append("   * dock=Floating at all three     -> the remembered state")
        out.append("     is NOT visible to the API, and a first-run dock cannot")
        out.append("     tell a returning docked user from a new one. In that")
        out.append("     case the fix must be gated on a settings file only.")
        try:
            p.deleteMe()
            _settle(2)
            out.append("  throwaway deleted; nothing left behind.")
        except Exception:
            pass
    except Exception:
        out.append("  FAILED:\n" + traceback.format_exc())

    questions.append(
        "1. Did the recreated probe palette come back DOCKED on the right, or "
        "floating? Compare against what the log recorded."
    )
    questions.append("2. Send both stage files back.")
    return questions


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        stage = _stage()

        out: list[str] = []
        out.append("ConstraintLens — palette position probe (issue #11)")
        out.append(f"Fusion build: {_read(app, 'version')}")
        out.append(f"stage: {stage}")
        out.append("")

        questions = _stage0(ui, out) if stage == 0 else _stage1(ui, out)
        _advance(stage)

        path = os.path.join(
            tempfile.gettempdir(), f"cl_probe_palette_position_stage{stage}.txt"
        )
        saved = path
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(out))
        except Exception:
            saved = "(could not write the log file)"

        ui.messageBox(
            f"Position probe, stage {stage} done.\n\n"
            f"Log: {saved}\n\n"
            + "\n\n".join(questions)
        )
    except Exception:
        if ui:
            ui.messageBox("Position probe failed:\n" + traceback.format_exc())
