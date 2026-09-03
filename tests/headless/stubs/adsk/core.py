"""Stub of adsk.core — see the package docstring."""


class Base:
    """Root of the Fusion object hierarchy. Fakes subclass it."""

    objectType = ""

    @classmethod
    def cast(cls, obj):
        return obj if isinstance(obj, cls) else None


class EventHandler(Base):
    pass


class DocumentEventHandler(EventHandler):
    pass


class ApplicationCommandEventHandler(EventHandler):
    pass


class HTMLEventHandler(EventHandler):
    pass


class UserInterfaceGeneralEventHandler(EventHandler):
    pass


class CustomEventHandler(EventHandler):
    pass


class CommandCreatedEventHandler(EventHandler):
    pass


class UserInterface(Base):
    pass


class CommandDefinition(Base):
    pass


class ToolbarControl(Base):
    pass


class Palette(Base):
    pass


class PaletteDockingStates:
    PaletteDockStateFloating = 0
    PaletteDockStateTop = 1
    PaletteDockStateBottom = 2
    PaletteDockStateLeft = 3
    PaletteDockStateRight = 4


class Point3D(Base):
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = x, y, z

    @staticmethod
    def create(x, y, z):
        return Point3D(x, y, z)


class Application(Base):
    """`Application.get()` returns whatever a test has installed, or None."""

    _current = None

    @classmethod
    def get(cls):
        return cls._current

    @classmethod
    def _set(cls, app):
        cls._current = app
