"""EntityLabeler naming and the per-sketch labeler cache."""

import unittest

import _bootstrap  # noqa: F401

import fakes
from lib import labels


class LabelerTest(unittest.TestCase):
    def test_entities_are_named_by_position_within_their_collection(self):
        a, b = fakes.FakeEntity("l1"), fakes.FakeEntity("l2")
        point = fakes.FakeSketchPoint("p1")
        lab = labels.EntityLabeler(fakes.FakeSketch(lines=[a, b], points=[point]))
        self.assertEqual(lab.label_for(a), "Line 1")
        self.assertEqual(lab.label_for(b), "Line 2")
        self.assertEqual(lab.label_for(point), "Point 1")

    def test_an_unindexed_entity_falls_back_to_its_type_name(self):
        lab = labels.EntityLabeler(fakes.FakeSketch())
        stranger = fakes.FakeEntity("x", "adsk::fusion::SketchLine")
        self.assertEqual(lab.label_for(stranger), "SketchLine")

    def test_chip_carries_token_kind_label_and_visibility(self):
        a = fakes.FakeEntity("l1", visible=False)
        lab = labels.EntityLabeler(fakes.FakeSketch(lines=[a]))
        self.assertEqual(
            lab.chip_for(a),
            {"token": "l1", "kind": "SketchLine", "label": "Line 1", "invisible": True},
        )


class LabelerCacheTest(unittest.TestCase):
    def setUp(self):
        labels.invalidate()

    def test_an_unchanged_sketch_reuses_the_same_labeler(self):
        sketch = fakes.FakeSketch(lines=[fakes.FakeEntity("l1")])
        self.assertIs(labels.labeler_for(sketch), labels.labeler_for(sketch))

    def test_the_cache_does_not_re_read_entity_tokens(self):
        # This is the point of the cache: building a labeler reads an
        # entityToken per entity, and it used to happen on every canvas click.
        line = fakes.FakeEntity("l1")
        sketch = fakes.FakeSketch(lines=[line])
        labels.labeler_for(sketch)
        first = line.reads["entityToken"]
        labels.labeler_for(sketch)
        labels.labeler_for(sketch)
        self.assertEqual(line.reads["entityToken"], first)

    def test_adding_geometry_invalidates_the_cache(self):
        sketch = fakes.FakeSketch(lines=[fakes.FakeEntity("l1")])
        before = labels.labeler_for(sketch)
        sketch.sketchCurves.sketchLines = fakes.FakeCollection(
            [fakes.FakeEntity("l1"), fakes.FakeEntity("l2")]
        )
        after = labels.labeler_for(sketch)
        self.assertIsNot(before, after)
        self.assertEqual(after.label_for(sketch.sketchCurves.sketchLines.item(1)), "Line 2")

    def test_switching_to_a_different_sketch_invalidates_the_cache(self):
        one = fakes.FakeSketch(name="Sketch1", lines=[fakes.FakeEntity("l1")])
        two = fakes.FakeSketch(name="Sketch2", lines=[fakes.FakeEntity("m1")])
        self.assertIsNot(labels.labeler_for(one), labels.labeler_for(two))

    def test_invalidate_forces_a_rebuild(self):
        sketch = fakes.FakeSketch(lines=[fakes.FakeEntity("l1")])
        before = labels.labeler_for(sketch)
        labels.invalidate()
        self.assertIsNot(before, labels.labeler_for(sketch))

    def test_an_unreadable_sketch_bypasses_the_cache_rather_than_poisoning_it(self):
        sketch = fakes.FakeSketch(lines=[fakes.FakeEntity("l1")])
        sketch._name = fakes._Raising
        self.assertIsNot(labels.labeler_for(sketch), labels.labeler_for(sketch))


if __name__ == "__main__":
    unittest.main()
