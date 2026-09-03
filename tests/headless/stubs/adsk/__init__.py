"""Minimal stand-in for the Fusion 360 `adsk` package.

Only exists so ConstraintLens/lib/*.py can be imported outside Fusion and its
pure logic unit-tested. It implements the surface those modules touch at import
time — the handler base classes they subclass, the entity classes they use in
`isinstance` checks and type annotations, and the few module functions they
call — and nothing else. It is NOT a simulation of Fusion: anything that would
need real geometry, a real document or a real palette still has to be tested on
a PC.

Never shipped: this lives under tests/ and is not part of the add-in.
"""

from . import core, fusion  # noqa: F401  (imported for `import adsk.core` to work)


def doEvents():
    """Fusion pumps its event loop here. Nothing to pump in a test."""
    return None
