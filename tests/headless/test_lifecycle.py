"""lifecycle helpers that are pure enough to run outside Fusion."""

import unittest

import _bootstrap  # noqa: F401

import fakes
from lib import lifecycle


class DerivedUnitFormattingTest(unittest.TestCase):
    """Fusion stores areas in cm^2 and volumes in cm^3 and offers no formatter
    for either, so the conversion table is ours to get right."""

    def test_area_in_each_supported_unit(self):
        self.assertEqual(lifecycle._fmt_area(fakes.FakeUnits("mm"), 1.0), "100 mm^2")
        self.assertEqual(lifecycle._fmt_area(fakes.FakeUnits("cm"), 1.0), "1 cm^2")
        self.assertEqual(lifecycle._fmt_area(fakes.FakeUnits("m"), 10_000.0), "1 m^2")
        self.assertEqual(lifecycle._fmt_area(fakes.FakeUnits("in"), 6.4516), "1 in^2")
        self.assertEqual(lifecycle._fmt_area(fakes.FakeUnits("ft"), 929.0304), "1 ft^2")

    def test_volume_in_each_supported_unit(self):
        self.assertEqual(lifecycle._fmt_volume(fakes.FakeUnits("mm"), 1.0), "1000 mm^3")
        self.assertEqual(lifecycle._fmt_volume(fakes.FakeUnits("cm"), 1.0), "1 cm^3")
        self.assertEqual(lifecycle._fmt_volume(fakes.FakeUnits("m"), 1_000_000.0), "1 m^3")
        self.assertEqual(lifecycle._fmt_volume(fakes.FakeUnits("in"), 16.387064), "1 in^3")
        self.assertEqual(lifecycle._fmt_volume(fakes.FakeUnits("ft"), 28_316.846592), "1 ft^3")

    def test_an_unknown_unit_falls_back_to_cm_rather_than_mislabelling(self):
        self.assertEqual(lifecycle._fmt_area(fakes.FakeUnits("yd"), 2.5), "2.5 cm^2")

    def test_no_units_manager_at_all(self):
        self.assertEqual(lifecycle._fmt_area(None, 2.5), "2.5 cm^2")
        self.assertEqual(lifecycle._fmt_volume(None, 2.5), "2.5 cm^3")


class SelectionPropsTest(unittest.TestCase):
    def test_a_line_reports_its_length(self):
        line = fakes.FakeEntity("l1")
        line.length = 3.0
        props = lifecycle._selection_props(line, fakes.FakeUnits("mm"))
        self.assertEqual(props, [{"key": "Length", "value": "3.0 mm"}])

    def test_a_point_reports_z_even_when_it_is_zero(self):
        # Issue #10b: in a 3D sketch Z=0 is a real answer, so hiding the field
        # there would read as "no Z information".
        point = fakes.FakeSketchPoint("p1")
        point.geometry = _Geometry(1.0, 2.0, 0.0)
        keys = [p["key"] for p in lifecycle._selection_props(point, fakes.FakeUnits("mm"))]
        self.assertEqual(keys, ["X", "Y", "Z"])

    def test_a_dimension_reports_its_name_before_its_value(self):
        # Issue #10a: d526 is the field that says *which* dimension this is
        # when several of them read the same value.
        dim = fakes.FakeDimension(
            "adsk::fusion::SketchLinearDimension", "dim1",
            fakes.FakeParameter(name="d526", expression="30 mm", value=3.0),
        )
        props = lifecycle._selection_props(dim, fakes.FakeUnits("mm"))
        self.assertEqual([p["key"] for p in props], ["Name", "Value"])
        self.assertEqual(props[0]["value"], "d526")


class SessionStateTest(unittest.TestCase):
    def test_stopping_the_addin_forgets_that_the_palette_was_opened(self):
        # Restarting from Scripts and Add-Ins does not reload the module, so
        # without the reset the next run auto-opens a palette the user closed.
        lifecycle._ever_opened = True
        lifecycle._dock_column_px = 812
        lifecycle._last_sketch_counts = (4, 2)
        lifecycle._auto_zoom = True

        lifecycle._reset_session_state()

        self.assertFalse(lifecycle._ever_opened)
        self.assertEqual(lifecycle._dock_column_px, 0)
        self.assertEqual(lifecycle._last_sketch_counts, (-1, -1))
        self.assertFalse(lifecycle._auto_zoom)


class _Geometry:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


if __name__ == "__main__":
    unittest.main()
