"""Put the adsk stubs and the add-in package on sys.path.

Imported first by every test module here. The stubs directory has to come
before anything else so `import adsk.core` finds the fake rather than failing.
Fusion loads the add-in folder as a package, so tests import
`ConstraintLens.lib…` the same way.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(_HERE))

for _path in (os.path.join(_HERE, "stubs"), _REPO_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)
