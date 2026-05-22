# tests/probe_pattern_icons/probe_pattern_icons.py
# Discover native Fusion icon folders for pattern and polygon commands.
# Run via Fusion Tools > Add-Ins > Scripts > probe_pattern_icons.
# Output written to probe_pattern_icons.txt next to this file.

import os
import adsk.core

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "probe_pattern_icons.txt")

KEYWORDS = [
    "pattern", "polygon", "rectangular", "circular",
]


def run(context):
    app = adsk.core.Application.get()
    ui = app.userInterface
    lines = []

    def w(s=""):
        lines.append(s)

    # --- A. Scan all commandDefinitions for pattern/polygon keywords -------

    w("=== A. Command definitions matching pattern/polygon keywords ===")
    w()
    all_cmds = ui.commandDefinitions
    matches = []
    for i in range(all_cmds.count):
        try:
            cmd = all_cmds.item(i)
            cid = cmd.id or ""
            name = ""
            try:
                name = cmd.name or ""
            except Exception:
                pass
            combined = (cid + " " + name).lower()
            if any(kw in combined for kw in KEYWORDS):
                matches.append((cid, name, cmd.resourceFolder or ""))
        except Exception:
            continue

    matches.sort(key=lambda t: t[0].lower())
    for cid, name, folder in matches:
        w(f"  id={cid}")
        w(f"    name={name}")
        w(f"    resourceFolder={folder}")
        if folder and os.path.isdir(folder):
            try:
                pngs = sorted(f for f in os.listdir(folder) if f.lower().endswith(".png"))
                w(f"    PNGs: {pngs}")
            except Exception as exc:
                w(f"    (error listing folder: {exc})")
        else:
            w("    (folder missing or empty)")
        w()

    # --- B. Walk the sketch resource base for folders with pattern/polygon --

    w()
    w("=== B. Sketch resource base — subfolders matching keywords ===")
    w()
    try:
        ref_cmd = ui.commandDefinitions.itemById("SketchGeomConstraintCmd")
        if ref_cmd is None:
            w("  SketchGeomConstraintCmd not found — cannot locate sketch resource base.")
        else:
            base = os.path.dirname((ref_cmd.resourceFolder or "").rstrip("/\\"))
            w(f"  Sketch resource base: {base}")
            w()
            if os.path.isdir(base):
                for entry in sorted(os.listdir(base)):
                    if any(kw in entry.lower() for kw in KEYWORDS):
                        full = os.path.join(base, entry)
                        if os.path.isdir(full):
                            try:
                                pngs = sorted(f for f in os.listdir(full) if f.lower().endswith(".png"))
                            except Exception:
                                pngs = ["(error)"]
                            w(f"  {entry}/")
                            w(f"    PNGs: {pngs}")
                            w()
    except Exception as exc:
        w(f"  Error: {exc}")

    # --- C. Check specific command IDs confirmed by probe_patterns ----------

    w()
    w("=== C. Resource folders for confirmed edit command IDs ===")
    w()
    for cid in [
        "SketchPatternCircularEdit",
        "SketchPatternCircular",
        "SketchRectangularPatternEdit",
        "SketchRectangularPattern",
        "SketchPolygon",
        "SketchPolygonEdit",
        "SketchPolygonInscribed",
        "SketchPolygonCircumscribed",
    ]:
        cmd = ui.commandDefinitions.itemById(cid)
        if cmd is None:
            w(f"  {cid}: not found")
            continue
        folder = cmd.resourceFolder or ""
        w(f"  {cid}:")
        w(f"    name={cmd.name}")
        w(f"    resourceFolder={folder}")
        if folder and os.path.isdir(folder):
            try:
                pngs = sorted(f for f in os.listdir(folder) if f.lower().endswith(".png"))
                w(f"    PNGs: {pngs}")
            except Exception as exc:
                w(f"    (error listing: {exc})")
        else:
            w("    (folder missing or empty)")
        w()

    # --- Write output -------------------------------------------------------

    text = "\n".join(lines)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(text)

    ui.messageBox(f"probe_pattern_icons done — {len(matches)} matches.\nOutput: {OUTPUT_FILE}")
