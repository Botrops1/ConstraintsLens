"""scanner.build_payload — sectioning, per-constraint work, and row contents."""

import unittest

import _bootstrap  # noqa: F401

import fakes
from lib import labels, scanner


def _line(token):
    return fakes.FakeEntity(token)


def _parallel(token, a, b):
    return fakes.FakeConstraint(
        "adsk::fusion::ParallelConstraint", token, {"lineOne": a, "lineTwo": b}
    )


class SectioningTest(unittest.TestCase):
    def setUp(self):
        labels.invalidate()

    def test_constraints_and_patterns_land_in_their_own_sections(self):
        a, b = _line("l1"), _line("l2")
        sketch = fakes.FakeSketch(
            lines=[a, b],
            constraints=[
                _parallel("c1", a, b),
                fakes.FakeConstraint("adsk::fusion::CircularPatternConstraint", "c2"),
                fakes.FakeConstraint("adsk::fusion::RectangularPatternConstraint", "c3"),
            ],
        )
        payload = scanner.build_payload(sketch)
        self.assertEqual([r["kind"] for r in payload["constraints"]], ["ParallelConstraint"])
        self.assertEqual(
            [r["kind"] for r in payload["patterns"]],
            ["CircularPatternConstraint", "RectangularPatternConstraint"],
        )

    def test_offset_constraints_appear_in_neither_section(self):
        # They are shown as their SketchOffsetCurvesDimension instead.
        sketch = fakes.FakeSketch(
            constraints=[fakes.FakeConstraint("adsk::fusion::OffsetConstraint", "c1")]
        )
        payload = scanner.build_payload(sketch)
        self.assertEqual(payload["constraints"], [])
        self.assertEqual(payload["patterns"], [])

    def test_each_constraint_is_described_exactly_once(self):
        # Regression: the scan used to run every builder twice — once per
        # section pass — and throw away the rows the pass did not want.
        a, b = _line("l1"), _line("l2")
        parallel = _parallel("c1", a, b)
        offset = fakes.FakeConstraint("adsk::fusion::OffsetConstraint", "c2")
        pattern = fakes.FakeConstraint("adsk::fusion::CircularPatternConstraint", "c3")
        sketch = fakes.FakeSketch(lines=[a, b], constraints=[parallel, offset, pattern])

        scanner.build_payload(sketch)

        self.assertEqual(parallel.reads["lineOne"], 1)
        self.assertEqual(parallel.reads["lineTwo"], 1)
        self.assertEqual(parallel.reads["entityToken"], 1)
        # A row shown in no section costs nothing at all now.
        self.assertEqual(offset.reads["parentCurves"], 0)
        self.assertEqual(offset.reads["entityToken"], 0)
        self.assertEqual(pattern.reads["entityToken"], 1)

    def test_unknown_constraint_type_still_produces_a_geometric_row(self):
        sketch = fakes.FakeSketch(
            constraints=[fakes.FakeConstraint("adsk::fusion::SomethingNewConstraint", "c1")]
        )
        rows = scanner.build_payload(sketch)["constraints"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "SomethingNewConstraint")
        self.assertTrue(rows[0]["label"].startswith("Unknown:"))

    def test_a_raising_accessor_degrades_to_an_error_row(self):
        a = _line("l1")
        constraint = fakes.FakeConstraint(
            "adsk::fusion::ParallelConstraint", "c1",
            {"lineOne": a, "lineTwo": a}, raises=("lineTwo",),
        )
        rows = scanner.build_payload(fakes.FakeSketch(lines=[a], constraints=[constraint]))["constraints"]
        self.assertEqual(len(rows), 1)
        self.assertIn("accessor unavailable: .lineTwo", rows[0]["errors"])
        self.assertIn("<error>", rows[0]["label"])

    def test_row_carries_token_deletability_and_chips(self):
        a, b = _line("l1"), _line("l2")
        b.isVisible = False
        sketch = fakes.FakeSketch(lines=[a, b], constraints=[_parallel("c1", a, b)])
        row = scanner.build_payload(sketch)["constraints"][0]
        self.assertEqual(row["rowKey"], "c1")
        self.assertEqual(row["token"], "c1")
        self.assertTrue(row["isDeletable"])
        self.assertFalse(row["isPseudo"])
        self.assertEqual([c["label"] for c in row["entities"]], ["Line 1", "Line 2"])
        self.assertEqual([c["invisible"] for c in row["entities"]], [False, True])


class SketchHeaderTest(unittest.TestCase):
    def setUp(self):
        labels.invalidate()

    def test_header_reports_name_component_and_constrained_state(self):
        payload = scanner.build_payload(
            fakes.FakeSketch(name="Base", component="Body1", fully_constrained=True)
        )
        self.assertEqual(payload["sketch"]["name"], "Base")
        self.assertEqual(payload["sketch"]["componentName"], "Body1")
        self.assertTrue(payload["sketch"]["isFullyConstrained"])

    def test_a_raising_header_accessor_does_not_lose_the_whole_payload(self):
        sketch = fakes.FakeSketch(constraints=[_parallel("c1", _line("l1"), _line("l2"))])
        sketch._name = fakes._Raising
        sketch._fully = fakes._Raising
        payload = scanner.build_payload(sketch)
        self.assertEqual(payload["sketch"]["name"], "")
        self.assertFalse(payload["sketch"]["isFullyConstrained"])
        self.assertEqual(len(payload["constraints"]), 1)


class ImplicitJoinTest(unittest.TestCase):
    def setUp(self):
        labels.invalidate()

    def test_a_point_shared_by_two_curves_becomes_a_pseudo_row(self):
        a, b = _line("l1"), _line("l2")
        shared = fakes.FakeSketchPoint("p1", connected=[a, b])
        lone = fakes.FakeSketchPoint("p2", connected=[a])
        sketch = fakes.FakeSketch(lines=[a, b], points=[shared, lone])
        rows = scanner.build_payload(sketch)["implicitJoins"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["rowKey"], "join:p1")
        self.assertIsNone(rows[0]["token"])
        self.assertTrue(rows[0]["isPseudo"])
        self.assertFalse(rows[0]["isDeletable"])


if __name__ == "__main__":
    unittest.main()
