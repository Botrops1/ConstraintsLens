# tests/probe_camera/probe_camera.py
# Run from Fusion: Tools -> Scripts and Add-Ins -> Scripts -> + -> select this
# folder -> Run.  Works with or without an active sketch.
#
# Probes Fusion's viewport / camera API to assess feasibility of a
# "zoom to selected entity" feature (ConstraintLens backlog Pack 4).
#
# Answers five questions:
#
#  Q1. Which methods / properties exist on adsk.core.Viewport?
#  Q2. Which methods / properties exist on adsk.core.Camera?
#      (Focus on fit, zoom, extents, viewExtents, eye, target, up.)
#  Q3. Does camera.fit = True → viewport.camera = camera produce a
#      visible fit-all?  Camera state is captured and restored after.
#  Q4. Are there text commands that fit/zoom to the current selection?
#      (Tries a list of candidate command strings.)
#  Q5. Do sketch entities expose a boundingBox that could be used to
#      manually compute a fit-to-entity camera position?
#      (Tested on the first selected entity, if any; otherwise reports
#      what attributes SketchLine / SketchCircle / SketchArc expose.)
#
# Output: messageBox summary + full text at
#   <tempdir>/cl_probe_camera.txt

import os
import tempfile
import time
import traceback

import adsk.core
import adsk.fusion


def _section(out: list, title: str) -> None:
    out.append("")
    out.append("=" * 72)
    out.append(title)
    out.append("=" * 72)


# ---------------------------------------------------------------------------
# Q1 — Viewport API surface
# ---------------------------------------------------------------------------

def probe_viewport_attrs(app: adsk.core.Application, out: list) -> None:
    _section(out, "Q1  adsk.core.Viewport attributes")
    try:
        vp = app.activeViewport
        if vp is None:
            out.append("  app.activeViewport is None — no viewport available.")
            return
        attrs = sorted(a for a in dir(vp) if not a.startswith("_"))
        interesting = [
            a for a in attrs
            if any(k in a.lower() for k in (
                "fit", "zoom", "camera", "extent", "size", "refresh", "refresh",
                "screen", "render",
            ))
        ]
        out.append(f"  Viewport type: {type(vp).__name__}")
        out.append(f"  Viewport interesting attrs: {interesting}")
        out.append("")
        out.append("  All public Viewport attrs:")
        for chunk in _chunks(attrs, 6):
            out.append("    " + ",  ".join(chunk))
    except Exception as exc:
        out.append(f"  ERROR: {exc}\n{traceback.format_exc()}")


# ---------------------------------------------------------------------------
# Q2 — Camera API surface
# ---------------------------------------------------------------------------

def probe_camera_attrs(app: adsk.core.Application, out: list) -> None:
    _section(out, "Q2  adsk.core.Camera attributes")
    try:
        vp = app.activeViewport
        if vp is None:
            out.append("  No viewport — cannot get camera.")
            return
        cam = vp.camera
        if cam is None:
            out.append("  viewport.camera is None.")
            return
        attrs = sorted(a for a in dir(cam) if not a.startswith("_"))
        interesting = [
            a for a in attrs
            if any(k in a.lower() for k in (
                "fit", "zoom", "extent", "eye", "target", "up", "view",
                "near", "far", "persp",
            ))
        ]
        out.append(f"  Camera type: {type(cam).__name__}")
        out.append(f"  Camera interesting attrs: {interesting}")
        # Inspect the important ones by value
        for attr in interesting:
            try:
                val = getattr(cam, attr)
                if hasattr(val, "x"):
                    val = f"Point3D({val.x:.4g}, {val.y:.4g}, {val.z:.4g})"
                out.append(f"    {attr}: {val!r}")
            except Exception as exc2:
                out.append(f"    {attr}: <error: {exc2}>")
        out.append("")
        out.append("  All public Camera attrs:")
        for chunk in _chunks(attrs, 6):
            out.append("    " + ",  ".join(chunk))
    except Exception as exc:
        out.append(f"  ERROR: {exc}\n{traceback.format_exc()}")


# ---------------------------------------------------------------------------
# Q3 — camera.fit = True round-trip
# ---------------------------------------------------------------------------

def probe_camera_fit_roundtrip(app: adsk.core.Application, out: list) -> None:
    _section(out, "Q3  camera.fit = True round-trip (view is restored after)")
    try:
        vp = app.activeViewport
        if vp is None:
            out.append("  No viewport.")
            return
        # Capture original state
        original = vp.camera
        out.append("  Original camera captured.")

        # Attempt fit = True
        cam = vp.camera
        fit_attr_exists = hasattr(cam, "fit")
        out.append(f"  camera has 'fit' attribute: {fit_attr_exists}")
        if fit_attr_exists:
            try:
                cam.fit = True
                out.append("  camera.fit = True did not raise.")
                vp.camera = cam
                adsk.doEvents()
                time.sleep(0.2)
                out.append("  viewport.camera = cam set without raising.")
                out.append("  VISUAL CHECK: did the viewport zoom to fit all geometry?")
            except Exception as exc:
                out.append(f"  camera.fit = True RAISED: {exc}")
        else:
            out.append("  camera.fit not present — cannot use this approach.")

        # Also try isFitView if present
        cam2 = vp.camera
        if hasattr(cam2, "isFitView"):
            out.append(f"  camera.isFitView exists; current value = {cam2.isFitView!r}")
        else:
            out.append("  camera.isFitView: not present")

        # Restore
        try:
            vp.camera = original
            adsk.doEvents()
            out.append("  Original camera restored.")
        except Exception as exc:
            out.append(f"  Could not restore camera: {exc}")
    except Exception as exc:
        out.append(f"  ERROR: {exc}\n{traceback.format_exc()}")


# ---------------------------------------------------------------------------
# Q4 — Text command candidates for fit-to-selection / zoom
# ---------------------------------------------------------------------------

_ZOOM_CMDS = [
    "View.Fit",
    "View.FitAll",
    "View.FitSelected",
    "View.ZoomSelected",
    "View.ZoomIn",
    "Commands.Fit",
    "Commands.FitAll",
    "Commands.FitSelected",
    "Commands.ZoomSelected",
    "Sketch.ZoomToSketch",
    "FitSelected",
    "FitAll",
    "ZoomSelected",
]


def probe_text_commands(app: adsk.core.Application, out: list) -> None:
    _section(out, "Q4  Text commands for fit / zoom (tried sequentially; view restored after each)")
    try:
        vp = app.activeViewport
        if vp is None:
            out.append("  No viewport — cannot test commands.")
            return
        original = vp.camera

        for cmd in _ZOOM_CMDS:
            try:
                result = app.executeTextCommand(cmd)
                adsk.doEvents()
                time.sleep(0.1)
                out.append(f"  {cmd:<40} OK    result={result!r}")
                # Restore after each success to keep the view stable
                try:
                    vp.camera = original
                    adsk.doEvents()
                except Exception:
                    pass
            except Exception as exc:
                # Truncate long exception strings
                msg = str(exc)[:80]
                out.append(f"  {cmd:<40} RAISE {msg}")

        out.append("")
        out.append("  NOTE: 'OK' only means the call did not raise, not that it did")
        out.append("  something visually useful. Check which ones actually panned/zoomed.")
    except Exception as exc:
        out.append(f"  ERROR: {exc}\n{traceback.format_exc()}")


# ---------------------------------------------------------------------------
# Q5 — Entity bounding box (manual fit-to-entity fallback)
# ---------------------------------------------------------------------------

def probe_entity_bbox(app: adsk.core.Application, out: list) -> None:
    _section(out, "Q5  Entity boundingBox for manual fit-to-entity camera computation")
    try:
        ui = app.userInterface
        sel = ui.activeSelections
        if sel.count == 0:
            out.append("  No entity selected.  Select a sketch entity before running")
            out.append("  this script to test bounding-box access.")
            out.append("  Falling back to static API inspection of SketchLine attrs:")
            _report_static_attrs(out)
            return

        entity = sel.item(0).entity
        out.append(f"  Selected entity type: {type(entity).__name__}")
        out.append(f"  objectType string:    {getattr(entity, 'objectType', '<n/a>')}")

        # Bounding box
        bbox = getattr(entity, "boundingBox", None)
        if bbox is None:
            out.append("  entity.boundingBox: NOT PRESENT on this entity type.")
        else:
            try:
                mn = bbox.minPoint
                mx = bbox.maxPoint
                cx = (mn.x + mx.x) / 2
                cy = (mn.y + mx.y) / 2
                cz = (mn.z + mx.z) / 2
                diag = ((mx.x-mn.x)**2 + (mx.y-mn.y)**2 + (mx.z-mn.z)**2) ** 0.5
                out.append(f"  entity.boundingBox.minPoint: ({mn.x:.4g}, {mn.y:.4g}, {mn.z:.4g})")
                out.append(f"  entity.boundingBox.maxPoint: ({mx.x:.4g}, {mx.y:.4g}, {mx.z:.4g})")
                out.append(f"  Bounding-box centre:         ({cx:.4g}, {cy:.4g}, {cz:.4g})")
                out.append(f"  Bounding-box diagonal (cm):  {diag:.4g}")
                out.append("  -> camera.target = centre; camera.viewExtents = diag / 2 * padding")
                out.append("     should produce a fit-to-entity view.")
            except Exception as exc:
                out.append(f"  boundingBox read error: {exc}")

        # Extra useful attrs
        for attr in ("startSketchPoint", "endSketchPoint", "centerSketchPoint",
                     "radius", "length", "geometry"):
            val = getattr(entity, attr, "<not present>")
            if val != "<not present>":
                out.append(f"  entity.{attr}: {val!r}")

        # Check if camera.viewExtents is settable
        _section(out, "Q5b  camera.viewExtents — readable and settable?")
        try:
            vp = app.activeViewport
            cam = vp.camera
            ve = getattr(cam, "viewExtents", None)
            out.append(f"  camera.viewExtents: {ve!r}")
            if ve is not None:
                try:
                    cam.viewExtents = ve * 0.5   # try half — should zoom in
                    vp.camera = cam
                    adsk.doEvents()
                    time.sleep(0.2)
                    out.append("  Set camera.viewExtents = original/2 without raising.")
                    out.append("  VISUAL CHECK: did view zoom in ~2×?")
                    # Restore
                    cam2 = vp.camera
                    cam2.viewExtents = ve
                    vp.camera = cam2
                    adsk.doEvents()
                    out.append("  Restored original viewExtents.")
                except Exception as exc:
                    out.append(f"  Setting camera.viewExtents raised: {exc}")
        except Exception as exc:
            out.append(f"  camera.viewExtents probe error: {exc}")

    except Exception as exc:
        out.append(f"  ERROR: {exc}\n{traceback.format_exc()}")


def _report_static_attrs(out: list) -> None:
    for cls_name in ("SketchLine", "SketchCircle", "SketchArc", "SketchPoint"):
        cls = getattr(adsk.fusion, cls_name, None)
        if cls is None:
            out.append(f"  adsk.fusion.{cls_name}: not found")
            continue
        attrs = sorted(a for a in dir(cls) if not a.startswith("_"))
        bbox_related = [a for a in attrs if any(
            k in a.lower() for k in ("bound", "extent", "length", "radius", "geom")
        )]
        out.append(f"  {cls_name} geometry/bounds attrs: {bbox_related}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chunks(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        out: list = []
        out.append("ConstraintLens camera / auto-zoom probe.")
        out.append("Answers Q1-Q5 for Pack 4 planning.")
        out.append("Open a design (sketch edit preferred) before running for")
        out.append("best results; select a sketch entity for Q5 bounding-box test.")

        probe_viewport_attrs(app, out)
        probe_camera_attrs(app, out)
        probe_camera_fit_roundtrip(app, out)
        probe_text_commands(app, out)
        probe_entity_bbox(app, out)

        text = "\n".join(out)
        out_path = os.path.join(tempfile.gettempdir(), "cl_probe_camera.txt")
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)
            preview = text if len(text) <= 2000 else text[:2000] + "\n...[see full file]"
            ui.messageBox(
                f"Camera probe complete.\n\nFull output: {out_path}\n\n"
                f"--- preview ---\n\n{preview}",
                "ConstraintLens camera probe",
            )
        except Exception:
            ui.messageBox(
                "Probe complete (could not write temp file):\n\n" + text[:3000],
                "ConstraintLens camera probe",
            )

    except Exception:
        if ui:
            ui.messageBox("Probe failed:\n" + traceback.format_exc(),
                          "ConstraintLens camera probe — ERROR")
