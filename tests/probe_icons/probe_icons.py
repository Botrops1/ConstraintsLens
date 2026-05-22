# tests/probe_icons/probe_icons.py
# Run from Fusion: Tools → Scripts and Add-Ins → Scripts → Run.
#
# Finds the resource folders for all built-in sketch-constraint commands so
# we can copy Fusion's native icons into the ConstraintLens palette.
#
# Output: writes a text file to the OS temp directory and opens a message box
# with the path. Paste the file contents back to the developer.

import os
import tempfile

import adsk.core


# ConstraintLens type names that we want icons for.
# We'll search commandDefinitions for each candidate ID list.
_WANT = {
    "HorizontalConstraint":             ["SketchConstraintHorizontal",   "SketchConstrainHorizontal"],
    "VerticalConstraint":               ["SketchConstraintVertical",     "SketchConstrainVertical"],
    "CoincidentConstraint":             ["SketchConstraintCoincident",   "SketchConstrainCoincident"],
    "TangentConstraint":                ["SketchConstraintTangent",      "SketchConstrainTangent"],
    "EqualConstraint":                  ["SketchConstraintEqual",        "SketchConstrainEqual"],
    "ParallelConstraint":               ["SketchConstraintParallel",     "SketchConstrainParallel"],
    "PerpendicularConstraint":          ["SketchConstraintPerpendicular","SketchConstrainPerpendicular"],
    "MidPointConstraint":               ["SketchConstraintMidPoint",     "SketchConstrainMidPoint",
                                         "SketchConstraintMidpoint",    "SketchConstrainMidpoint"],
    "ConcentricConstraint":             ["SketchConstraintConcentric",   "SketchConstrainConcentric"],
    "CollinearConstraint":              ["SketchConstraintCollinear",    "SketchConstrainCollinear"],
    "SymmetryConstraint":               ["SketchConstraintSymmetry",     "SketchConstrainSymmetry",
                                         "SketchConstraintSymmetric",   "SketchConstrainSymmetric"],
    "OffsetConstraint":                 ["SketchConstraintOffset",       "SketchConstrainOffset"],
    "PolygonConstraint":                ["SketchConstraintPolygon",      "SketchConstrainPolygon"],
    "FixedConstraint":                  ["SketchConstraintFix",          "SketchConstrainFix",
                                         "SketchConstraintFixed",       "SketchConstrainFixed"],
}


def run(context):
    app = adsk.core.Application.get()
    ui  = app.userInterface

    lines = []
    lines.append("=== probe_icons output ===\n")

    # --- Pass 1: try known candidate IDs -----------------------------------
    lines.append("--- Targeted search ---")
    found_kinds = set()
    for kind, candidates in _WANT.items():
        for cid in candidates:
            cmd = ui.commandDefinitions.itemById(cid)
            if cmd is None:
                continue
            folder = ""
            try:
                folder = cmd.resourceFolder or ""
            except Exception:
                pass
            png = os.path.join(folder, "16x16.png") if folder else ""
            exists = os.path.isfile(png)
            lines.append(f"  FOUND  {kind}: id={cid}  folder={folder}  16x16_exists={exists}")
            found_kinds.add(kind)
            break
        else:
            lines.append(f"  MISS   {kind}: none of {candidates}")

    # --- Pass 2: scan ALL commandDefinitions for anything sketch+constrain --
    lines.append("\n--- Full scan (sketch*constrain* or constrain*sketch*) ---")
    scan_hits = []
    try:
        total = ui.commandDefinitions.count
        for i in range(total):
            cmd = ui.commandDefinitions.item(i)
            cid_lower = cmd.id.lower()
            if "sketch" in cid_lower and "constrain" in cid_lower:
                folder = ""
                try:
                    folder = cmd.resourceFolder or ""
                except Exception:
                    pass
                png16 = os.path.join(folder, "16x16.png") if folder else ""
                has_png = os.path.isfile(png16)
                scan_hits.append((cmd.id, folder, has_png))
        for cid, folder, has_png in sorted(scan_hits):
            lines.append(f"  {cid}  |  {folder}  |  16x16={has_png}")
        lines.append(f"  (total commandDefinitions scanned: {total})")
    except Exception as exc:
        lines.append(f"  scan failed: {exc}")

    # --- Write to temp file -------------------------------------------------
    out = "\n".join(lines)
    tmp = os.path.join(tempfile.gettempdir(), "cl_probe_icons.txt")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(out)
        ui.messageBox(
            f"probe_icons complete.\n\nResults written to:\n{tmp}\n\n"
            f"Targeted hits: {len(found_kinds)} / {len(_WANT)}\n"
            f"Full scan hits: {len(scan_hits)}\n\n"
            "Paste the file contents back to the developer.",
            "ConstraintLens – probe_icons"
        )
    except Exception as exc:
        ui.messageBox(f"Could not write output file: {exc}\n\n{out[:2000]}")
