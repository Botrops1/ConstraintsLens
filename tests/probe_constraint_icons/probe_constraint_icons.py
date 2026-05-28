"""
Probe: find correct Fusion command IDs for H/V constraint icons.

Run this in Fusion's Script Editor (Tools → Add-Ins → Scripts and Add-Ins →
click the "+" to add a script, paste this file, then Run).

Output appears in the Fusion TEXT COMMANDS panel (View → Show Text Commands).
"""

import adsk.core
import adsk.fusion
import os
import traceback

def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui  = app.userInterface
        out = []

        def p(s=""):
            out.append(str(s))

        # ── 1. List files in the known Constraint_Horizontal / _Vertical folders ──
        # We'll find the base resource path from any known constraint command, e.g. Coincident
        known_ids = [
            "SketchGeomConstraintCoincident",
            "SketchConstraintCoincident",
            "SketchCoincidentConstraint",
            "SketchGeomConstraintHorizontal",
            "SketchConstraintHorizontal",
            "SketchHorizontalConstraint",
            "SketchHorizontal",
            "SketchGeomConstraintVertical",
            "SketchConstraintVertical",
            "SketchVerticalConstraint",
            "SketchVertical",
        ]
        p("=== Known ID probe ===")
        for kid in known_ids:
            cmd = ui.commandDefinitions.itemById(kid)
            if cmd is not None:
                p(f"  FOUND  {kid!r}  →  {cmd.resourceFolder!r}")
            else:
                p(f"  miss   {kid!r}")

        # ── 2. Find the Fusion resource root from a command we know works ──
        # SketchConstraintCoincident is used in lifecycle.py _ICON_MAP successfully
        resource_root = None
        for probe_id in ("SketchGeomConstraintCoincident",
                         "SketchConstraintCoincident",
                         "SketchCoincidentConstraint"):
            cmd = ui.commandDefinitions.itemById(probe_id)
            if cmd and cmd.resourceFolder:
                folder = cmd.resourceFolder.rstrip("/\\")
                # e.g. .../Constraint_Coincident  →  parent is the resource root
                resource_root = os.path.dirname(folder)
                p(f"\nResource root (via {probe_id!r}): {resource_root!r}")
                break

        # ── 3. List Constraint_Horizontal and _Vertical folder contents ──
        for subfolder in ("Constraint_Horizontal", "Constraint_Vertical"):
            if resource_root:
                full = os.path.join(resource_root, subfolder)
            else:
                full = None
            p(f"\n=== {subfolder} ===")
            if full and os.path.isdir(full):
                files = sorted(os.listdir(full))
                for f in files:
                    p(f"  {f}")
            else:
                p(f"  (folder not found at {full!r})")

        # ── 4. Scan ALL commandDefinitions for any containing dark PNGs ──
        #    AND whose ID/name suggests horizontal or vertical or sketch constraint
        keywords = {"horizontal", "vertical", "constraint", "sketchgeomconstraint",
                    "sketchconstraint"}
        p("\n=== CommandDefinitions scan (H/V/Constraint with dark PNGs) ===")
        total = ui.commandDefinitions.count
        hits = []
        for i in range(total):
            try:
                cmd = ui.commandDefinitions.item(i)
                cid = cmd.id or ""
                cid_lower = cid.lower()
                if not any(k in cid_lower for k in keywords):
                    continue
                rf = (cmd.resourceFolder or "").rstrip("/\\")
                if not rf or not os.path.isdir(rf):
                    continue
                dark_files = [f for f in os.listdir(rf) if "-dark." in f]
                has_dark = bool(dark_files)
                hits.append((cid, rf, dark_files))
                marker = "  DARK" if has_dark else "  "
                p(f"{marker}  {cid!r}")
                if has_dark:
                    for df in dark_files:
                        p(f"          {df}")
            except Exception:
                pass
        p(f"\n({len(hits)} commands matched keywords out of {total} total)")

        # ── 5. Also print every command whose resource folder name contains
        #       "Horizontal" or "Vertical" regardless of its command ID ──
        p("\n=== Resource folders named *Horizontal* or *Vertical* ===")
        for i in range(total):
            try:
                cmd = ui.commandDefinitions.item(i)
                rf = (cmd.resourceFolder or "")
                base = os.path.basename(rf.rstrip("/\\")).lower()
                if "horizontal" in base or "vertical" in base:
                    dark_files = []
                    if os.path.isdir(rf.rstrip("/\\")):
                        dark_files = [f for f in os.listdir(rf.rstrip("/\\"))
                                      if "-dark." in f]
                    p(f"  {cmd.id!r}  →  {rf!r}")
                    if dark_files:
                        for df in dark_files:
                            p(f"      DARK: {df}")
            except Exception:
                pass

        result = "\n".join(out)
        # Show in Text Commands panel
        app.log(result)
        # Also show a dialog so it's impossible to miss
        ui.messageBox(result[:3000] + ("\n…(truncated, see Text Commands)" if len(result) > 3000 else ""),
                      "ConstraintLens Icon Probe")

    except Exception:
        if ui:
            ui.messageBox("Probe failed:\n" + traceback.format_exc())
