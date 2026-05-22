# tests/probe_patterns/probe_patterns.py
# Run from Fusion: Tools → Scripts and Add-Ins → Scripts → Run.
#
# Combined probe for backlog #13 and #15:
#   A) Discover commandDefinition IDs for opening Offset Curves / Pattern /
#      Polygon EDIT dialogs (to implement double-click-to-edit in ConstraintLens).
#   B) Inspect PolygonConstraint, CircularPatternConstraint,
#      RectangularPatternConstraint objects for readable / writable properties
#      (to decide whether inline editing is feasible without opening a dialog).
#
# Prerequisites: have a sketch open for edit that contains at least one of:
#   polygon, circular pattern, rectangular pattern, offset curves.
# Output: writes a text file to %TEMP%/cl_probe_patterns.txt and shows a
#         message box with the path. Paste the file contents back to the dev.

import os
import tempfile
import traceback

import adsk.core
import adsk.fusion


# ── Property access helper ────────────────────────────────────────────────────

def _probe_obj(obj, label: str) -> list[str]:
    """Return a list of lines describing every attribute of obj."""
    lines = [f"\n  [{label}]  type={type(obj).__name__}"]
    for name in sorted(dir(obj)):
        if name.startswith("_"):
            continue
        try:
            val = getattr(obj, name)
            if callable(val):
                lines.append(f"    {name}()  <method>")
            else:
                lines.append(f"    {name} = {val!r}")
        except Exception as exc:
            lines.append(f"    {name} = <ERROR: {exc}>")
    return lines


# ── Section A: commandDefinition scan ────────────────────────────────────────

_KEYWORDS_A = ("offset", "pattern", "polygon")


def _scan_commands(ui: adsk.core.UserInterface) -> list[str]:
    lines = []
    lines.append("\n=== A: commandDefinition scan (offset / pattern / polygon) ===")
    hits: list[tuple[str, str, bool]] = []
    try:
        total = ui.commandDefinitions.count
        for i in range(total):
            cmd = ui.commandDefinitions.item(i)
            cid_lower = cmd.id.lower()
            if any(kw in cid_lower for kw in _KEYWORDS_A):
                folder = ""
                try:
                    folder = cmd.resourceFolder or ""
                except Exception:
                    pass
                name = ""
                try:
                    name = cmd.name or ""
                except Exception:
                    pass
                hits.append((cmd.id, name, folder))
        for cid, name, folder in sorted(hits):
            lines.append(f"  {cid:<55}  name={name!r}")
        lines.append(f"  (scanned {total} commandDefinitions, {len(hits)} hits)")
    except Exception as exc:
        lines.append(f"  scan error: {exc}")
    return lines


# ── Section B: active sketch constraint property inspection ───────────────────

_INSPECT_TYPES = {
    "adsk::fusion::PolygonConstraint":
        "PolygonConstraint",
    "adsk::fusion::CircularPatternConstraint":
        "CircularPatternConstraint",
    "adsk::fusion::RectangularPatternConstraint":
        "RectangularPatternConstraint",
}

# Also scan dimensions for SketchOffsetCurvesDimension.
_INSPECT_DIM_TYPES = {
    "adsk::fusion::SketchOffsetCurvesDimension":
        "SketchOffsetCurvesDimension",
}


def _scan_sketch(sketch: adsk.fusion.Sketch) -> list[str]:
    lines = []
    lines.append("\n=== B: active sketch object inspection ===")

    # Geometric constraints
    gc = sketch.geometricConstraints
    found_any = False
    for i in range(gc.count):
        c = gc.item(i)
        label = _INSPECT_TYPES.get(c.objectType)
        if label is None:
            continue
        found_any = True
        lines.extend(_probe_obj(c, f"{label} #{i}"))

    # Sketch dimensions
    dims = sketch.sketchDimensions
    for i in range(dims.count):
        d = dims.item(i)
        label = _INSPECT_DIM_TYPES.get(d.objectType)
        if label is None:
            continue
        found_any = True
        lines.extend(_probe_obj(d, f"{label} #{i}"))
        # Also probe the parameter object.
        try:
            param = d.parameter
            if param is not None:
                lines.extend(_probe_obj(param, f"  .parameter for {label} #{i}"))
        except Exception as exc:
            lines.append(f"    .parameter error: {exc}")

    if not found_any:
        lines.append(
            "  No PolygonConstraint / CircularPatternConstraint / "
            "RectangularPatternConstraint / SketchOffsetCurvesDimension found "
            "in the active sketch.\n"
            "  Open a sketch that contains at least one of these before running."
        )

    return lines


# ── Section C: executeTextCommand guesses ────────────────────────────────────

_GUESSES: list[tuple[str, str]] = [
    ("Sketch.OffsetCurves",            "offset curves (create/edit?)"),
    ("Sketch.CircularPattern",         "circular pattern (create/edit?)"),
    ("Sketch.RectangularPattern",      "rectangular pattern (create/edit?)"),
    ("Sketch.Polygon",                 "polygon (create/edit?)"),
    ("SketchOffsetCurves",             "offset curves alt"),
    ("SketchCircularPattern",          "circular pattern alt"),
    ("SketchRectangularPattern",       "rectangular pattern alt"),
    ("SketchPolygon",                  "polygon alt"),
    ("EditSketchFeature",              "generic edit sketch feature"),
    ("SketchEditFeature",              "generic edit sketch feature alt"),
]


def _try_commands(app: adsk.core.Application) -> list[str]:
    lines = []
    lines.append("\n=== C: executeTextCommand guesses ===")
    lines.append("  (These are fired at the active sketch; note any dialogs that open.)")
    for cmd, desc in _GUESSES:
        try:
            result = app.executeTextCommand(cmd)
            lines.append(f"  OK   {cmd:<45}  desc={desc!r}  result={result!r}")
        except Exception as exc:
            lines.append(f"  FAIL {cmd:<45}  {exc}")
    return lines


# ── Entry point ───────────────────────────────────────────────────────────────

def run(context):
    app = adsk.core.Application.get()
    ui  = app.userInterface

    all_lines: list[str] = ["=== probe_patterns output ==="]

    # Section A — always runs.
    all_lines.extend(_scan_commands(ui))

    # Section B — only if a sketch is active.
    design = adsk.fusion.Design.cast(app.activeProduct)
    sketch = None
    if design:
        sketch = adsk.fusion.Sketch.cast(design.activeEditObject)

    if sketch:
        all_lines.append(f"\n  Active sketch: {sketch.name!r}")
        all_lines.extend(_scan_sketch(sketch))
    else:
        all_lines.append(
            "\n=== B: SKIPPED — no sketch is open for edit. "
            "Open a sketch containing polygon/pattern/offset objects and re-run. ==="
        )

    # Section C — only if a sketch is active (commands need sketch context).
    if sketch:
        all_lines.extend(_try_commands(app))
    else:
        all_lines.append(
            "\n=== C: SKIPPED — executeTextCommand needs sketch edit context. ==="
        )

    # Write output.
    out = "\n".join(all_lines)
    tmp = os.path.join(tempfile.gettempdir(), "cl_probe_patterns.txt")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(out)
        ui.messageBox(
            f"probe_patterns complete.\n\nResults written to:\n{tmp}\n\n"
            "Paste the file contents back to the developer.",
            "ConstraintLens – probe_patterns"
        )
    except Exception as exc:
        ui.messageBox(f"Could not write output: {exc}\n\n{out[:3000]}")
