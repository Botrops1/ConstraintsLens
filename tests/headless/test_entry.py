"""ConstraintLens.py — the entry point loads its own code whatever else Fusion has loaded."""

import importlib
import sys
import types
import unittest

import _bootstrap  # noqa: F401


class EntryPointTest(unittest.TestCase):
    def test_uses_its_own_lib_when_another_add_in_s_lib_is_already_imported(self):
        # Fusion runs every add-in in one interpreter. Another add-in that did
        # `from lib import lifecycle` leaves its own `lib` package behind.
        other = types.ModuleType("lib")
        other.lifecycle = types.ModuleType("lib.lifecycle")
        sys.modules.update({"lib": other, "lib.lifecycle": other.lifecycle})
        sys.modules.pop("ConstraintLens.ConstraintLens", None)  # import it afresh
        try:
            entry = importlib.import_module("ConstraintLens.ConstraintLens")
        finally:
            del sys.modules["lib"], sys.modules["lib.lifecycle"]

        self.assertEqual(entry.lifecycle.__name__, "ConstraintLens.lib.lifecycle")


if __name__ == "__main__":
    unittest.main()
