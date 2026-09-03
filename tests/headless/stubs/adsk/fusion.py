"""Stub of adsk.fusion — see the package docstring.

Every class here is an empty marker. The lib modules use them in three ways
and all three work against a bare subclass of core.Base:

  * `adsk.fusion.Sketch | None` in an annotation, evaluated at def time;
  * `adsk.fusion.Design.cast(x)` / `Sketch.cast(x)`;
  * `isinstance(entity, adsk.fusion.SketchLine)` and friends, which is how
    lifecycle._selection_props picks the properties to read.

Fakes in tests subclass the relevant one so those isinstance checks land.
"""

from .core import Base


class Design(Base):
    pass


class Sketch(Base):
    pass


class SketchEntity(Base):
    pass


class SketchCurve(SketchEntity):
    pass


class SketchLine(SketchCurve):
    pass


class SketchCircle(SketchCurve):
    pass


class SketchArc(SketchCurve):
    pass


class SketchEllipse(SketchCurve):
    pass


class SketchFittedSpline(SketchCurve):
    pass


class SketchControlPointSpline(SketchCurve):
    pass


class SketchPoint(SketchEntity):
    pass


class Profile(Base):
    pass


class BRepEdge(Base):
    pass


class BRepFace(Base):
    pass


class BRepBody(Base):
    pass


class ModelParameter(Base):
    pass


class SketchDimension(Base):
    pass


class SketchOffsetCurvesDimension(SketchDimension):
    pass
