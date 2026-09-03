"""Fake Fusion objects, shaped like the ones the scanner walks.

They are deliberately dumb: attributes and counts, no geometry. What they do
add is bookkeeping — every accessor read is counted — which is how the tests
assert that a constraint is described once per scan rather than twice.
"""

import collections

import _bootstrap  # noqa: F401  (sys.path side effect)

import adsk.fusion


class FakeCollection:
    """Stands in for both collection shapes the add-in meets: `.count` +
    `.item(i)` (ObjectCollection) and plain iteration (SketchCurveVector)."""

    def __init__(self, items=()):
        self._items = list(items)

    @property
    def count(self):
        return len(self._items)

    def item(self, i):
        return self._items[i]

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)


class _Counted:
    """Base for fakes that record which accessors were read, and how often."""

    def __init__(self, token="", object_type=""):
        self.reads = collections.Counter()
        self._token = token
        self.objectType = object_type

    @property
    def entityToken(self):
        self.reads["entityToken"] += 1
        return self._token


class FakeEntity(_Counted, adsk.fusion.SketchLine):
    """A sketch entity. Subclasses SketchLine so the isinstance checks in
    lifecycle._selection_props see something concrete; tests that care about a
    different type build their own subclass."""

    def __init__(self, token, object_type="adsk::fusion::SketchLine", visible=True):
        _Counted.__init__(self, token, object_type)
        self.isVisible = visible


class FakeConstraint(_Counted):
    """A geometric constraint. Accessors are served from `entities` through
    __getattr__, so reading one that was not supplied raises AttributeError
    exactly as a Fusion accessor that is unavailable on this build would."""

    def __init__(self, object_type, token="", entities=None, deletable=True, raises=()):
        _Counted.__init__(self, token, object_type)
        self._entities = dict(entities or {})
        self._raises = set(raises)
        self.isDeletable = deletable

    def __getattr__(self, name):
        # Only called when normal attribute lookup fails, so the real
        # attributes set in __init__ never come through here.
        if name.startswith("_") or name in ("reads",):
            raise AttributeError(name)
        self.__dict__["reads"][name] += 1
        if name in self._raises:
            raise RuntimeError(f"accessor {name} raised")
        if name in self._entities:
            return self._entities[name]
        raise AttributeError(name)


class FakeParameter(_Counted):
    def __init__(self, name="d1", expression="10 mm", value=1.0, unit="mm", token="param"):
        _Counted.__init__(self, token, "adsk::fusion::ModelParameter")
        self.name = name
        self.expression = expression
        self.value = value
        self.unit = unit


class FakeDimension(_Counted):
    def __init__(self, object_type, token="", parameter=None, entities=None, deletable=True):
        _Counted.__init__(self, token, object_type)
        self.parameter = parameter or FakeParameter()
        self._entities = dict(entities or {})
        self.isDeletable = deletable

    def __getattr__(self, name):
        if name.startswith("_") or name in ("reads",):
            raise AttributeError(name)
        self.__dict__["reads"][name] += 1
        if name in self._entities:
            return self._entities[name]
        raise AttributeError(name)


class FakeSketchPoint(_Counted, adsk.fusion.SketchPoint):
    def __init__(self, token, connected=(), visible=True):
        _Counted.__init__(self, token, "adsk::fusion::SketchPoint")
        self.connectedEntities = FakeCollection(connected)
        self.isVisible = visible


class FakeCurves:
    def __init__(self, lines=(), circles=(), arcs=(), ellipses=(), fitted=(), control=None):
        self.sketchLines = FakeCollection(lines)
        self.sketchCircles = FakeCollection(circles)
        self.sketchArcs = FakeCollection(arcs)
        self.sketchEllipses = FakeCollection(ellipses)
        self.sketchFittedSplines = FakeCollection(fitted)
        if control is not None:
            self.sketchControlPointSplines = FakeCollection(control)


class FakeComponent:
    def __init__(self, name="Component1"):
        self.name = name


class _Raising:
    """Sentinel: assigning this to a fake's attribute makes reading it raise."""


class FakeSketch(adsk.fusion.Sketch):
    def __init__(self, name="Sketch1", lines=(), points=(), constraints=(), dimensions=(),
                 circles=(), arcs=(), ellipses=(), fitted=(), control=None,
                 fully_constrained=False, component="Component1"):
        self._name = name
        self._fully = fully_constrained
        self.sketchCurves = FakeCurves(lines, circles, arcs, ellipses, fitted, control)
        self.sketchPoints = FakeCollection(points)
        self.geometricConstraints = FakeCollection(constraints)
        self.sketchDimensions = FakeCollection(dimensions)
        self.parentComponent = FakeComponent(component)
        self.healthState = 0
        self.errorOrWarningMessage = ""

    @property
    def name(self):
        if self._name is _Raising:
            raise RuntimeError("name unavailable")
        return self._name

    @property
    def isFullyConstrained(self):
        if self._fully is _Raising:
            raise RuntimeError("isFullyConstrained unavailable")
        return self._fully


class FakeUnits:
    """Just enough UnitsManager to exercise dimension_display."""

    def __init__(self, default="mm", precision=2):
        self.defaultLengthUnits = default
        self._precision = precision

    def formatValue(self, value, units):
        return f"{round(value, self._precision)} {units}"
