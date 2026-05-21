# tests/spike_probe.py
# Run from Fusion: Tools -> Scripts and Add-Ins -> Scripts -> Run.
#
# Probes the five open questions from SPEC.md section 10 in a single shot.
# Prerequisite: run fixture_sketch.py first, then open the resulting sketch
# (named "ConstraintLens_Fixture") for edit. The probe also works on any
# other open sketch — it falls back to "first sketch in root" when nothing
# is currently being edited.
#
# Output: a message-box summary plus a full text file written to the OS
# temp directory. Paste the temp file contents back to the developer.

import os
import tempfile
import traceback

import adsk.core
import adsk.fusion


# --- Probes --------------------------------------------------------------


def probe_q1_panels(ui: adsk.core.UserInterface, out: list[str]) -> None:
    """Open question 1 — find the right panel id for the toolbar button."""
    out.append("=" * 72)
    out.append("Q1  Panel ids visible in the current workspace")
    out.append("=" * 72)
    try:
        ws = ui.activeWorkspace
        out.append(f"  active workspace: id={ws.id!r}  name={ws.name!r}")
        out.append(f"  total panels: {ws.toolbarPanels.count}")
        for i in range(ws.toolbarPanels.count):
            p = ws.toolbarPanels.item(i)
            visible = "visible" if p.isVisible else "hidden"
            out.append(f"    [{i:>2}] {visible:>7}  {p.id!r:40}  {p.name!r}")
    except Exception as exc:
        out.append(f"  ERROR: {exc}")
    out.append("")
    out.append("  Hint: re-run this probe with the Sketch toolbar active")
    out.append("  (open any sketch for edit first) to see SketchInspectPanel etc.")


def probe_q2_underconstrained(app: adsk.core.Application, out: list[str]) -> None:
    """Open question 2 — Sketch.ShowUnderconstrained precondition."""
    out.append("")
    out.append("=" * 72)
    out.append("Q2  Sketch.ShowUnderconstrained behavior in current context")
    out.append("=" * 72)
    design = adsk.fusion.Design.cast(app.activeProduct)
    edit_obj = design.activeEditObject if design else None
    in_sketch_edit = isinstance(edit_obj, adsk.fusion.Sketch)
    out.append(f"  in sketch edit mode: {in_sketch_edit}")
    try:
        result = app.executeTextCommand("Sketch.ShowUnderconstrained")
        out.append(f"  return value (repr): {result!r}")
    except Exception as exc:
        out.append(f"  raised: {type(exc).__name__}: {exc}")


def probe_q3_palette_events(out: list[str]) -> None:
    """Open question 3 — palette visibility event surface."""
    out.append("")
    out.append("=" * 72)
    out.append("Q3  Palette visibility events (static introspection)")
    out.append("=" * 72)
    # We cannot create a real palette here without polluting state, so we
    # just enumerate event-related attributes on the Palette class via the
    # API metadata we can reach.
    try:
        # Reach the class via a known import; introspect callable attrs.
        cls = adsk.core.Palette
        attrs = sorted(
            name for name in dir(cls)
            if "event" in name.lower() or name in {"closed", "navigatingURL", "incomingFromHTML"}
        )
        out.append(f"  Palette event-like attrs: {attrs}")
    except Exception as exc:
        out.append(f"  introspection failed: {exc}")
    out.append("  Manual follow-up: install the add-in, minimize/restore the")
    out.append("  palette, and observe which of these fire (Text Commands log).")


def _accessor_kinds(c) -> list[str]:
    """Return ['name=Type', ...] for every accessor on c that yields something."""
    names = (
        "line", "lineOne", "lineTwo",
        "point", "pointOne", "pointTwo",
        "entity", "entityOne", "entityTwo",
        "curveOne", "curveTwo",
        "midPointCurve", "symmetryLine",
        "surface", "planarSurface",
        "distance", "centerSketchPoint",
        "parentCurves", "childCurves", "lines",
    )
    out = []
    for n in names:
        if not hasattr(c, n):
            continue
        try:
            v = getattr(c, n)
        except Exception as e:
            out.append(f"{n}=<raise:{type(e).__name__}>")
            continue
        if v is None:
            out.append(f"{n}=None")
        else:
            out.append(f"{n}={type(v).__name__}")
    return out


def _pick_probe_sketch(design: adsk.fusion.Design) -> adsk.fusion.Sketch | None:
    sketch = adsk.fusion.Sketch.cast(design.activeEditObject)
    if sketch:
        return sketch
    # Prefer the fixture, fall back to first sketch in root with constraints.
    root = design.rootComponent
    for i in range(root.sketches.count):
        s = root.sketches.item(i)
        if s.name == "ConstraintLens_Fixture":
            return s
    for i in range(root.sketches.count):
        s = root.sketches.item(i)
        if s.geometricConstraints.count > 0:
            return s
    return root.sketches.item(0) if root.sketches.count else None


def probe_q5_constraint_inventory(app: adsk.core.Application, out: list[str]) -> None:
    """Open question 5 + general inventory."""
    out.append("")
    out.append("=" * 72)
    out.append("Q5  GeometricConstraint inventory on probe sketch")
    out.append("=" * 72)
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        out.append("  no active design")
        return
    sketch = _pick_probe_sketch(design)
    if not sketch:
        out.append("  no usable sketch found — run fixture_sketch.py first")
        return
    edit_obj = design.activeEditObject
    being_edited = isinstance(edit_obj, adsk.fusion.Sketch) and edit_obj.entityToken == sketch.entityToken
    out.append(f"  sketch: {sketch.name!r}  (being edited: {being_edited})")
    out.append(f"  isFullyConstrained: {sketch.isFullyConstrained}")
    try:
        out.append(f"  healthState: {sketch.healthState}")
        out.append(f"  errorOrWarningMessage: {sketch.errorOrWarningMessage!r}")
    except Exception as exc:
        out.append(f"  health probe raised: {exc}")

    out.append("")
    out.append("  geometricConstraints:")
    seen: set[str] = set()
    gc = sketch.geometricConstraints
    for i in range(gc.count):
        c = gc.item(i)
        seen.add(c.objectType)
        try:
            deletable = c.isDeletable
        except Exception:
            deletable = "?"
        accessors = ", ".join(_accessor_kinds(c)) or "<none>"
        out.append(f"    [{i:>2}] {c.objectType:55}  del={deletable}  {{ {accessors} }}")
    out.append(f"  distinct objectTypes: {sorted(seen)}")

    out.append("")
    out.append("  sketchDimensions:")
    dims = sketch.sketchDimensions
    for i in range(dims.count):
        d = dims.item(i)
        try:
            expr = d.parameter.expression
        except Exception as e:
            expr = f"<raise:{type(e).__name__}>"
        out.append(f"    [{i:>2}] {d.objectType:55}  expr={expr!r}")

    out.append("")
    out.append("  sketchPoints with connectedEntities.count > 1 (implicit joins):")
    sp = sketch.sketchPoints
    join_count = 0
    for i in range(sp.count):
        p = sp.item(i)
        try:
            n = p.connectedEntities.count
        except Exception:
            n = -1
        if n > 1:
            join_count += 1
            kinds = []
            for j in range(min(n, 6)):
                kinds.append(type(p.connectedEntities.item(j)).__name__)
            out.append(f"    [{i:>2}] connects {n}: {kinds}")
    out.append(f"  total implicit-join points: {join_count}")


def probe_q4_token(app: adsk.core.Application, out: list[str]) -> None:
    """Open question 4 — capture a constraint entityToken for save-reload test."""
    out.append("")
    out.append("=" * 72)
    out.append("Q4  Capture constraint entityToken for save-reload stability test")
    out.append("=" * 72)
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        out.append("  no design")
        return
    sketch = _pick_probe_sketch(design)
    if not sketch or sketch.geometricConstraints.count == 0:
        out.append("  no sketch with constraints — run fixture_sketch.py first")
        return
    c = sketch.geometricConstraints.item(0)
    try:
        token = c.entityToken
    except Exception as exc:
        out.append(f"  c.entityToken raised: {exc}")
        return
    out.append(f"  picked: constraint [0] of {sketch.name!r}  type={c.objectType}")
    out.append(f"  entityToken (len={len(token)}):")
    out.append(f"    {token}")
    try:
        resolved = design.findEntityByToken(token)
        n = len(resolved) if resolved else 0
        first_kind = type(resolved[0]).__name__ if n else "<empty>"
        out.append(f"  same-session resolve: count={n}  first_type={first_kind}")
    except Exception as exc:
        out.append(f"  same-session resolve raised: {exc}")
    out.append("")
    out.append("  ACTION FOR DEVELOPER:")
    out.append("    1. Save the document.")
    out.append("    2. Close the document tab; reopen it.")
    out.append("    3. Re-run this probe.")
    out.append("    4. Paste the entityToken above into a Text Commands cell:")
    out.append("         > Python: app.activeProduct.findEntityByToken('<paste>')")
    out.append("       — record whether it returns the same constraint.")


# --- Entry point ----------------------------------------------------------


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        out: list[str] = []
        out.append("ConstraintLens spike probe — paste the contents of the")
        out.append("temp file (path shown at the end) back to the developer.")
        out.append("")
        probe_q1_panels(ui, out)
        probe_q2_underconstrained(app, out)
        probe_q3_palette_events(out)
        probe_q5_constraint_inventory(app, out)
        probe_q4_token(app, out)

        text = "\n".join(out)
        out_path = os.path.join(tempfile.gettempdir(), "constraintlens_probe.txt")
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)
            preview = text if len(text) <= 1500 else text[:1500] + "\n...[truncated; see full file]"
            ui.messageBox(
                f"Probe complete.\n\nFull output written to:\n{out_path}\n\n"
                f"--- preview ---\n\n{preview}"
            )
        except Exception:
            ui.messageBox(
                "Probe complete (could not write temp file):\n\n" + text[:3000]
            )
    except Exception:
        if ui:
            ui.messageBox("Probe failed:\n" + traceback.format_exc())
