# lib/labels.py — entity-display naming for the active sketch (SPEC.md sections 4, 5).

import adsk.fusion


def _safe_token(entity) -> str | None:
    try:
        return entity.entityToken
    except Exception:
        return None


class EntityLabeler:
    """Build (token -> 'Line 3') maps once per scan of a sketch.

    Indexes lines, points, circles, arcs, ellipses, and both spline kinds.
    Any entity not in those collections falls back to its bare class name.
    """

    def __init__(self, sketch: adsk.fusion.Sketch):
        self._tokens: dict[str, str] = {}
        self._kinds: dict[str, str] = {}
        curves = sketch.sketchCurves
        self._index(curves.sketchLines, "Line", "SketchLine")
        self._index(sketch.sketchPoints, "Point", "SketchPoint")
        self._index(curves.sketchCircles, "Circle", "SketchCircle")
        self._index(curves.sketchArcs, "Arc", "SketchArc")
        self._index(curves.sketchEllipses, "Ellipse", "SketchEllipse")
        self._index(curves.sketchFittedSplines, "Spline", "SketchFittedSpline")
        # Some Fusion builds don't expose control-point splines on the curves
        # bag; guard the lookup so labeler construction never fails.
        cps = getattr(curves, "sketchControlPointSplines", None)
        if cps is not None:
            self._index(cps, "Spline", "SketchControlPointSpline")

    def _index(self, coll, name: str, kind: str) -> None:
        try:
            count = coll.count
        except Exception:
            return
        for i in range(count):
            try:
                ent = coll.item(i)
            except Exception:
                continue
            tok = _safe_token(ent)
            if tok:
                self._tokens[tok] = f"{name} {i + 1}"
                self._kinds[tok] = kind

    def label_for(self, entity) -> str:
        tok = _safe_token(entity)
        if tok and tok in self._tokens:
            return self._tokens[tok]
        try:
            return entity.objectType.split("::")[-1]
        except Exception:
            return "<unknown>"

    def kind_for(self, entity) -> str:
        tok = _safe_token(entity)
        if tok and tok in self._kinds:
            return self._kinds[tok]
        try:
            return entity.objectType.split("::")[-1]
        except Exception:
            return "SketchEntity"

    def chip_for(self, entity) -> dict:
        invisible = False
        try:
            invisible = not bool(entity.isVisible)
        except Exception:
            pass
        return {
            "token": _safe_token(entity) or "",
            "kind": self.kind_for(entity),
            "label": self.label_for(entity),
            "invisible": invisible,
        }


# --- Per-sketch labeler cache -------------------------------------------
#
# Building an EntityLabeler reads entityToken for every line, point, circle,
# arc, ellipse and spline in the sketch, and entityToken is one of the more
# expensive reads in the API. One was being built twice per scan (once in
# build_payload, once for the selection footer) and again on EVERY
# activeSelectionChanged — that is, on every canvas click — which is exactly
# the per-click cost the v1.6.0 timing pass set out to hold down.
#
# The key is the sketch's name, its component's name, and the size of each
# indexed collection: nine property reads, none of which touch entityToken.
# Labels are positional ("Line 3" is the third line), so any change to those
# counts has to invalidate. A change that leaves every count identical —
# deleting one line and drawing another within a single command — would not,
# but commandTerminated republishes immediately afterwards and every
# build_payload refreshes the cache, so a stale labeler cannot outlive the
# operation that made it stale.
_cached_key: tuple | None = None
_cached_labeler: EntityLabeler | None = None


def _cache_key_for(sketch) -> tuple | None:
    """Cheap fingerprint of everything EntityLabeler indexes, or None if any
    part of it could not be read (in which case the cache is bypassed)."""
    try:
        curves = sketch.sketchCurves
        splines = getattr(curves, "sketchControlPointSplines", None)
        return (
            sketch.name,
            sketch.parentComponent.name,
            curves.sketchLines.count,
            sketch.sketchPoints.count,
            curves.sketchCircles.count,
            curves.sketchArcs.count,
            curves.sketchEllipses.count,
            curves.sketchFittedSplines.count,
            splines.count if splines is not None else -1,
        )
    except Exception:
        return None


def labeler_for(sketch: adsk.fusion.Sketch) -> EntityLabeler:
    """An EntityLabeler for `sketch`, reused while nothing that affects entity
    names has changed. Always returns a usable labeler."""
    global _cached_key, _cached_labeler
    key = _cache_key_for(sketch)
    if key is not None and key == _cached_key and _cached_labeler is not None:
        return _cached_labeler
    labeler = EntityLabeler(sketch)
    _cached_key = key
    _cached_labeler = labeler
    return labeler


def invalidate() -> None:
    """Drop the cached labeler. Called on add-in stop so a restart inside the
    same Fusion session cannot inherit a labeler from the previous run."""
    global _cached_key, _cached_labeler
    _cached_key = None
    _cached_labeler = None
