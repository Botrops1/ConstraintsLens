# tests/probe_palette/probe_palette.py
# Run from Fusion: Tools -> Scripts and Add-Ins -> Scripts -> Run.
#
# Probe for the v1.2.0 dock-blocks-status-text follow-up to issue #3.
# Answers four questions about the Palette API in the current Fusion build:
#
#   1. Which members of adsk.core.PaletteDockingStates exist?
#   2. Which sizing methods exist on adsk.core.Palette (setMaximumSize,
#      setMinimumSize, height, width, dockingOption, ...)?
#   3. Does setMaximumSize cap the height of a *docked* palette, or is it
#      only respected in floating mode?
#   4. Which dock-state assignments succeed vs raise?
#
# A throwaway palette is created, exercised, and deleted. Output is a
# message-box summary plus a full text file in the OS temp directory.

import os
import tempfile
import time
import traceback

import adsk.core


_THROWAWAY_PALETTE_ID = "ConstraintLensProbePalette"


def _section(out: list[str], title: str) -> None:
    out.append("")
    out.append("=" * 72)
    out.append(title)
    out.append("=" * 72)


def probe_enum_members(out: list[str]) -> None:
    _section(out, "Q1  PaletteDockingStates enumeration members")
    try:
        states = adsk.core.PaletteDockingStates
        members = sorted(name for name in dir(states) if not name.startswith("_"))
        out.append(f"  dir(adsk.core.PaletteDockingStates) = {members}")
        for candidate in (
            "PaletteDockStateFloating",
            "PaletteDockStateRight",
            "PaletteDockStateLeft",
            "PaletteDockStateBottom",
            "PaletteDockStateTop",
        ):
            present = hasattr(states, candidate)
            value = getattr(states, candidate, None) if present else "<missing>"
            out.append(f"  {candidate:35} present={present!s:5}  value={value!r}")
    except Exception as exc:
        out.append(f"  ERROR: {exc}")


def probe_palette_attrs(out: list[str]) -> None:
    _section(out, "Q2  Palette sizing / docking API surface")
    try:
        cls = adsk.core.Palette
        attrs = sorted(name for name in dir(cls) if not name.startswith("_"))
        interesting = [
            n for n in attrs
            if any(s in n.lower() for s in (
                "size", "dock", "height", "width", "resize", "maxim", "minim"
            ))
        ]
        out.append(f"  Palette size/dock attrs: {interesting}")
        out.append("")
        out.append("  All public Palette attrs (for reference):")
        for line in _wrap_list(attrs, width=64, indent="    "):
            out.append(line)
    except Exception as exc:
        out.append(f"  ERROR: {exc}")


def probe_dock_state_assignment(ui: adsk.core.UserInterface, out: list[str]) -> None:
    _section(out, "Q3+Q4  Dock-state assignment + setMaximumSize while docked")

    palette = _make_throwaway_palette(ui, out)
    if palette is None:
        return

    try:
        states = adsk.core.PaletteDockingStates
        candidates = [
            ("Floating", "PaletteDockStateFloating"),
            ("Right",    "PaletteDockStateRight"),
            ("Left",     "PaletteDockStateLeft"),
            ("Bottom",   "PaletteDockStateBottom"),
            ("Top",      "PaletteDockStateTop"),
        ]
        for label, attr in candidates:
            out.append("")
            if not hasattr(states, attr):
                out.append(f"  [{label:8}] enum member {attr} not present in build — skipped.")
                continue
            value = getattr(states, attr)
            try:
                palette.dockingState = value
                # Give Fusion a tick to honour the docking change.
                adsk.doEvents()
                time.sleep(0.05)
                out.append(f"  [{label:8}] assignment OK; palette.dockingState now = {palette.dockingState!r}")
            except Exception as exc:
                out.append(f"  [{label:8}] assignment RAISED {type(exc).__name__}: {exc}")

        # Q3 — does setMaximumSize work when docked-right?
        out.append("")
        out.append("  --- setMaximumSize behaviour while docked-right ---")
        if not hasattr(palette, "setMaximumSize"):
            out.append("  Palette.setMaximumSize not present — cannot cap docked height via API.")
        elif not hasattr(states, "PaletteDockStateRight"):
            out.append("  PaletteDockStateRight missing — cannot test docked behaviour.")
        else:
            try:
                palette.dockingState = states.PaletteDockStateRight
                adsk.doEvents()
                time.sleep(0.05)
                try:
                    palette.setMaximumSize(420, 500)
                    out.append("  setMaximumSize(420, 500) returned without raising.")
                    out.append("  VISUAL CHECK: did the palette height visibly stop at ~500 px,")
                    out.append("  or does it still fill the full right column? Note the answer.")
                except Exception as exc:
                    out.append(f"  setMaximumSize RAISED {type(exc).__name__}: {exc}")
                try:
                    palette.setMinimumSize(420, 200)
                    out.append("  setMinimumSize(420, 200) returned without raising.")
                except Exception as exc:
                    out.append(f"  setMinimumSize RAISED {type(exc).__name__}: {exc}")
            except Exception as exc:
                out.append(f"  Could not dock right for the size test: {exc}")
    finally:
        try:
            palette.deleteMe()
        except Exception:
            pass


def probe_selection_event(out: list[str]) -> None:
    _section(out, "Q5  UserInterface.activeSelectionChanged availability")
    try:
        ui_cls = adsk.core.UserInterface
        present = hasattr(ui_cls, "activeSelectionChanged")
        out.append(f"  UserInterface.activeSelectionChanged present: {present}")
        if present:
            handler_cls = getattr(adsk.core, "ActiveSelectionEventHandler", None)
            out.append(f"  adsk.core.ActiveSelectionEventHandler present: {handler_cls is not None}")
    except Exception as exc:
        out.append(f"  ERROR: {exc}")


def _make_throwaway_palette(ui: adsk.core.UserInterface, out: list[str]) -> adsk.core.Palette | None:
    try:
        existing = ui.palettes.itemById(_THROWAWAY_PALETTE_ID)
        if existing is not None:
            existing.deleteMe()
    except Exception:
        pass
    try:
        html_url = "about:blank"
        palette = ui.palettes.add(
            _THROWAWAY_PALETTE_ID,
            "CL probe palette",
            html_url,
            True,    # isVisible
            True,    # showCloseButton
            True,    # isResizable
            420,
            600,
            True,
        )
        out.append("  Throwaway palette created OK.")
        return palette
    except Exception as exc:
        out.append(f"  Could not create throwaway palette: {exc}")
        return None


def _wrap_list(items: list[str], width: int, indent: str) -> list[str]:
    lines: list[str] = []
    current = indent
    for item in items:
        addition = item + ", "
        if len(current) + len(addition) > width:
            lines.append(current.rstrip())
            current = indent + addition
        else:
            current += addition
    if current.strip():
        lines.append(current.rstrip().rstrip(","))
    return lines


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        out: list[str] = []
        out.append("ConstraintLens palette probe (v1.2.0 dock follow-up).")
        out.append("Run with no sketch open is fine.")

        probe_enum_members(out)
        probe_palette_attrs(out)
        probe_dock_state_assignment(ui, out)
        probe_selection_event(out)

        text = "\n".join(out)
        out_path = os.path.join(tempfile.gettempdir(), "cl_probe_palette.txt")
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)
            preview = text if len(text) <= 1800 else text[:1800] + "\n...[truncated; see full file]"
            ui.messageBox(
                f"Palette probe complete.\n\nFull output:\n{out_path}\n\n"
                f"--- preview ---\n\n{preview}"
            )
        except Exception:
            ui.messageBox("Probe complete (could not write temp file):\n\n" + text[:3000])
    except Exception:
        if ui:
            ui.messageBox("Probe failed:\n" + traceback.format_exc())
