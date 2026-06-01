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
            self._index_control_point_splines(cps)

    def _index_control_point_splines(self, coll) -> None:
        """Number control-point splines and their guide (control-polygon)
        lines so the latter filter as 'Spline N Guide M' instead of an
        anonymous 'SketchLine'. Best-effort: any failure is skipped."""
        try:
            count = coll.count
        except Exception:
            return
        for i in range(count):
            try:
                spline = coll.item(i)
            except Exception:
                continue
            tok = _safe_token(spline)
            if tok:
                self._tokens[tok] = f"Spline {i + 1}"
                self._kinds[tok] = "SketchControlPointSpline"
            guides = getattr(spline, "controlPointLines", None)
            if guides is None:
                continue
            try:
                gcount = guides.count
            except Exception:
                continue
            for j in range(gcount):
                try:
                    line = guides.item(j)
                except Exception:
                    continue
                gtok = _safe_token(line)
                if gtok:
                    self._tokens[gtok] = f"Spline {i + 1} Guide {j + 1}"
                    # Keep kind as SketchLine so icon lookup still resolves.
                    self._kinds[gtok] = "SketchLine"

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
