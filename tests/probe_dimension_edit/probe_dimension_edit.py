# tests/probe_dimension_edit/probe_dimension_edit.py
# Discover command IDs for editing sketch dimensions.
# Run via Fusion Tools > Add-Ins > Scripts > probe_dimension_edit.
# Output written to probe_dimension_edit.txt next to this file.

import os
import adsk.core

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "probe_dimension_edit.txt")

KEYWORDS = ["dimension", "sketchdim", "editdim", "dim_edit"]


def run(context):
    app = adsk.core.Application.get()
    ui = app.userInterface
    lines = []

    def w(s=""):
        lines.append(s)

    # --- A. commandDefinitions matching dimension/edit keywords --------------

    w("=== A. commandDefinitions matching dimension-edit keywords ===")
    w()
    all_cmds = ui.commandDefinitions
    matches = []
    for i in range(all_cmds.count):
        try:
            cmd = all_cmds.item(i)
            cid = (cmd.id or "").lower()
            name = ""
            try:
                name = (cmd.name or "").lower()
            except Exception:
                pass
            combined = cid + " " + name
            if any(kw in combined for kw in KEYWORDS):
                matches.append((cmd.id, cmd.name if hasattr(cmd, "name") else "", cmd.resourceFolder or ""))
        except Exception:
            continue

    matches.sort(key=lambda t: t[0].lower())
    for cid, name, folder in matches:
        w(f"  id={cid}  name={name}")
        if folder and os.path.isdir(folder):
            try:
                pngs = sorted(f for f in os.listdir(folder) if f.lower().endswith(".png"))
                w(f"    PNGs: {pngs}")
            except Exception:
                pass
    w()

    # --- B. Probe specific candidate IDs -----------------------------------

    w("=== B. Specific candidate IDs (exists / not found) ===")
    w()
    candidates = [
        # Sketch dimension edit candidates
        "SketchEditDimension",
        "SketchDimensionEdit",
        "SketchDimension",
        "SketchDimensionCmd",
        "SketchGeneralDimension",
        "SketchGeneralDimensionCmd",
        "SketchLinearDimension",
        "SketchAngularDimension",
        "SketchRadialDimension",
        "SketchDiameterDimension",
        "SketchOffsetDimension",
        "SketchConstraintDimensionEdit",
        "SketchDimensionEditCmd",
        "SketchEditLinearDimension",
        "EditDimension",
        "SketchChangeDimension",
        # Generic edit patterns
        "SketchEdit",
        "SketchItemEdit",
    ]
    for cid in candidates:
        cmd = ui.commandDefinitions.itemById(cid)
        if cmd is None:
            w(f"  {cid}: NOT FOUND")
        else:
            name = ""
            try:
                name = cmd.name
            except Exception:
                pass
            w(f"  {cid}: FOUND  name={name}")
            folder = cmd.resourceFolder or ""
            if folder and os.path.isdir(folder):
                try:
                    pngs = sorted(f for f in os.listdir(folder) if f.lower().endswith(".png"))
                    w(f"    folder={folder}")
                    w(f"    PNGs={pngs}")
                except Exception:
                    pass
    w()

    # --- C. executeTextCommand guesses ------------------------------------

    w("=== C. executeTextCommand guesses (errors expected for wrong ones) ===")
    w("NOTE: run with an active sketch edit context and a dimension selected")
    w()
    guesses = [
        "Sketch.EditDimension",
        "Sketch.ChangeDimension",
        "Sketch.DimensionEdit",
        "Sketch.ActivateDimension",
        "Sketch.EditSketchDimension",
    ]
    for g in guesses:
        try:
            result = app.executeTextCommand(g)
            w(f"  {g}: OK  result={result!r}")
        except Exception as exc:
            w(f"  {g}: ERROR  {exc}")
    w()

    # --- Write output -------------------------------------------------------

    text = "\n".join(lines)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(text)

    ui.messageBox(f"probe_dimension_edit done.\nOutput: {OUTPUT_FILE}")
