# tests/spike_probe_spline/spike_probe_spline.py
# Run from Fusion: Tools -> Scripts and Add-Ins -> Scripts -> Run.
#
# Probes whether spline "guide lines" (the control-polygon / curvature
# handle lines that define curvature at spline points) are enumerable with
# stable entityTokens, so EntityLabeler can number them "Spline N Guide M"
# for better filtering. See GitHub issue follow-up (spline guide numbering).
#
# Prerequisite: open a sketch for edit that contains at least one
# control-point spline (and ideally a fitted spline too). The probe falls
# back to the first sketch in root that has any spline.
#
# Output: a message-box summary plus a full text file written to the OS
# temp directory. Paste the temp file contents back to the developer.
#
# What to verify in the output:
#   1. controlPointLines is present and its items report a non-empty
#      entityToken and an isVisible flag.
#   2. (Optional) save the doc, reopen, re-run — confirm the tokens are
#      stable across reload (same gate as SPEC.md Q4).
# If (1) holds, the EntityLabeler change is safe to enable for real.

import os
import tempfile
import traceback

import adsk.core
import adsk.fusion


def _pick_spline_sketch(design: adsk.fusion.Design) -> adsk.fusion.Sketch | None:
    sketch = adsk.fusion.Sketch.cast(design.activeEditObject)
    if sketch:
        return sketch
    root = design.rootComponent
    for i in range(root.sketches.count):
        s = root.sketches.item(i)
        curves = s.sketchCurves
        try:
            has_cps = curves.sketchControlPointSplines.count > 0
        except Exception:
            has_cps = False
        try:
            has_fit = curves.sketchFittedSplines.count > 0
        except Exception:
            has_fit = False
        if has_cps or has_fit:
            return s
    return root.sketches.item(0) if root.sketches.count else None


def _probe_collection(coll, label: str, out: list[str]) -> None:
    """Dump a collection's items: type, entityToken presence, isVisible."""
    try:
        count = coll.count
    except Exception as exc:
        out.append(f"      {label}: <no .count: {type(exc).__name__}: {exc}>")
        return
    out.append(f"      {label}: count={count}")
    for j in range(count):
        try:
            item = coll.item(j)
        except Exception as exc:
            out.append(f"        [{j}] item() raised: {exc}")
            continue
        kind = type(item).__name__
        try:
            tok = item.entityToken
            tok_info = f"token(len={len(tok)})" if tok else "token=<empty>"
        except Exception as exc:
            tok_info = f"token raised: {type(exc).__name__}"
        try:
            vis = item.isVisible
        except Exception:
            vis = "?"
        out.append(f"        [{j}] {kind:20} {tok_info:22} isVisible={vis}")


def probe_splines(app: adsk.core.Application, out: list[str]) -> None:
    out.append("=" * 72)
    out.append("Spline guide-line probe")
    out.append("=" * 72)
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        out.append("  no active design")
        return
    sketch = _pick_spline_sketch(design)
    if not sketch:
        out.append("  no usable sketch found — create a sketch with a spline first")
        return
    out.append(f"  sketch: {sketch.name!r}")
    curves = sketch.sketchCurves

    # Control-point splines — the primary target (controlPointLines).
    cps = getattr(curves, "sketchControlPointSplines", None)
    out.append("")
    if cps is None:
        out.append("  sketchControlPointSplines: <not exposed on this build>")
    else:
        try:
            n = cps.count
        except Exception as exc:
            n = -1
            out.append(f"  sketchControlPointSplines.count raised: {exc}")
        out.append(f"  sketchControlPointSplines: count={n}")
        for i in range(max(n, 0)):
            try:
                sp = cps.item(i)
            except Exception as exc:
                out.append(f"    [{i}] item() raised: {exc}")
                continue
            out.append(f"    control-point spline [{i}] {type(sp).__name__}")
            for attr in ("controlPointLines", "controlPoints", "fitPoints"):
                coll = getattr(sp, attr, None)
                if coll is None:
                    out.append(f"      {attr}: <attr absent>")
                else:
                    _probe_collection(coll, attr, out)

    # Fitted splines — fit points and any handle geometry.
    out.append("")
    try:
        nf = curves.sketchFittedSplines.count
    except Exception as exc:
        nf = -1
        out.append(f"  sketchFittedSplines.count raised: {exc}")
    out.append(f"  sketchFittedSplines: count={nf}")
    for i in range(max(nf, 0)):
        try:
            sp = curves.sketchFittedSplines.item(i)
        except Exception as exc:
            out.append(f"    [{i}] item() raised: {exc}")
            continue
        out.append(f"    fitted spline [{i}] {type(sp).__name__}")
        for attr in ("fitPoints", "controlPointLines", "controlPoints",
                     "activatedCurvatureHandleCount", "activatedTangentHandleCount"):
            obj = getattr(sp, attr, None)
            if obj is None:
                out.append(f"      {attr}: <attr absent>")
            elif hasattr(obj, "count"):
                _probe_collection(obj, attr, out)
            else:
                out.append(f"      {attr}: {obj!r}")

    out.append("")
    out.append("  VERDICT GUIDE:")
    out.append("    If controlPointLines items show a non-empty token, the")
    out.append("    EntityLabeler 'Spline N Guide M' numbering will work.")
    out.append("    Save+reopen+re-run to confirm token stability.")


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        out: list[str] = []
        out.append("ConstraintLens spline guide-line probe — paste the temp")
        out.append("file contents (path shown at the end) back to the developer.")
        out.append("")
        probe_splines(app, out)

        text = "\n".join(out)
        out_path = os.path.join(tempfile.gettempdir(), "constraintlens_spline_probe.txt")
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)
            preview = text if len(text) <= 1500 else text[:1500] + "\n...[truncated; see full file]"
            ui.messageBox(
                f"Spline probe complete.\n\nFull output written to:\n{out_path}\n\n"
                f"--- preview ---\n\n{preview}"
            )
        except Exception:
            ui.messageBox("Spline probe complete (no temp file):\n\n" + text[:3000])
    except Exception:
        if ui:
            ui.messageBox("Spline probe failed:\n" + traceback.format_exc())
