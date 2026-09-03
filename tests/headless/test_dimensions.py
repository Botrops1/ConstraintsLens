"""Dimension rows: value formatting, and where the formatted value ends up."""

import unittest

import _bootstrap  # noqa: F401

import fakes
from lib import dispatch, labels, scanner


def _linear(expression, value, unit="mm", entities=None):
    param = fakes.FakeParameter(name="d5", expression=expression, value=value, unit=unit)
    return fakes.FakeDimension(
        "adsk::fusion::SketchLinearDimension", "dim1", param, entities or {}
    )


class DimensionDisplayTest(unittest.TestCase):
    def test_a_dragged_full_precision_value_is_rounded_for_display(self):
        param = fakes.FakeParameter(expression="5.1290366508 mm", value=5.1290366508)
        shown = scanner.dimension_display(param, param.expression, fakes.FakeUnits())
        self.assertEqual(shown, "5.13 mm")

    def test_a_formula_is_passed_through_untouched(self):
        # Seeing that a dimension is driven by another one is the useful part.
        param = fakes.FakeParameter(expression="d5*2", value=10.0)
        self.assertEqual(
            scanner.dimension_display(param, param.expression, fakes.FakeUnits()), "d5*2"
        )

    def test_an_expression_with_units_arithmetic_counts_as_a_formula(self):
        param = fakes.FakeParameter(expression="10 mm + 2 mm", value=12.0)
        self.assertEqual(
            scanner.dimension_display(param, param.expression, fakes.FakeUnits()),
            "10 mm + 2 mm",
        )

    def test_without_a_units_manager_the_raw_expression_survives(self):
        param = fakes.FakeParameter(expression="5.1290366508 mm", value=5.1290366508)
        self.assertEqual(
            scanner.dimension_display(param, param.expression, None), "5.1290366508 mm"
        )


class DimensionLabelTest(unittest.TestCase):
    def setUp(self):
        labels.invalidate()

    def test_describe_dimension_prefers_the_formatted_value(self):
        dim = _linear("5.1290366508 mm", 5.1290366508)
        result = dispatch.describe_dimension(dim, labels.EntityLabeler(fakes.FakeSketch()),
                                             value_text="5.13 mm")
        self.assertEqual(result.label, "Linear = 5.13 mm")

    def test_describe_dimension_falls_back_to_the_raw_expression(self):
        dim = _linear("30 mm", 30.0)
        result = dispatch.describe_dimension(dim, labels.EntityLabeler(fakes.FakeSketch()))
        self.assertEqual(result.label, "Linear = 30 mm")

    def test_the_row_keeps_the_raw_expression_and_shows_the_formatted_one(self):
        # data-expr seeds the inline editor and must stay exact; the label is
        # what the tooltip shows and what the filter box searches, so it gets
        # the rounded value the user can actually see on screen.
        line = fakes.FakeEntity("l1")
        dim = _linear("5.1290366508 mm", 5.1290366508, entities={"entityOne": line})
        sketch = fakes.FakeSketch(lines=[line], dimensions=[dim])

        rows = _scan_with_units(sketch, fakes.FakeUnits())
        self.assertEqual(rows[0]["parameterExpression"], "5.1290366508 mm")
        self.assertEqual(rows[0]["parameterDisplay"], "5.13 mm")
        self.assertEqual(rows[0]["label"], "Linear: Line 1 = 5.13 mm")
        self.assertNotIn("5.1290366508", rows[0]["label"])

    def test_dimension_rows_are_flagged_and_not_pseudo(self):
        dim = _linear("30 mm", 30.0)
        rows = _scan_with_units(fakes.FakeSketch(dimensions=[dim]), fakes.FakeUnits())
        self.assertTrue(rows[0]["isDimension"])
        self.assertFalse(rows[0]["isPseudo"])
        self.assertEqual(rows[0]["kind"], "Linear")


def _scan_with_units(sketch, units):
    """build_payload reads the UnitsManager off the live Application; there
    isn't one here, so hand the scanner a fake for the duration."""
    original = scanner._units_manager
    scanner._units_manager = lambda: units
    try:
        return scanner.build_payload(sketch)["dimensions"]
    finally:
        scanner._units_manager = original


if __name__ == "__main__":
    unittest.main()
