# backend/tests/unit/domain/test_bounding_box.py
from src.domain.entities.bounding_box import BoundingBox


class TestBoundingBoxGeometry:
    def test_area_positive(self) -> None:
        bb = BoundingBox(0, 0, 10, 20)
        assert bb.area() == 200.0

    def test_area_zero_when_inverted(self) -> None:
        bb = BoundingBox(10, 20, 0, 0)
        assert bb.area() == 0.0

    def test_center(self) -> None:
        bb = BoundingBox(0, 0, 10, 20)
        assert bb.center() == (5.0, 10.0)

    def test_is_below_within_margin(self) -> None:
        above = BoundingBox(0, 0, 10, 10)
        below = BoundingBox(0, 15, 10, 25)
        assert below.is_below(above, margin=20) is True

    def test_is_below_delta_exactly_zero_is_false(self) -> None:
        above = BoundingBox(0, 0, 10, 10)
        below = BoundingBox(0, 10, 10, 20)
        assert below.is_below(above, margin=10) is False

    def test_is_below_outside_margin(self) -> None:
        above = BoundingBox(0, 0, 10, 10)
        below = BoundingBox(0, 100, 10, 110)
        assert below.is_below(above, margin=50) is False

    def test_is_below_self_above_other(self) -> None:
        above = BoundingBox(0, 0, 10, 10)
        below = BoundingBox(0, 15, 10, 25)
        assert above.is_below(below, margin=50) is False

    def test_is_below_same_level(self) -> None:
        a = BoundingBox(0, 0, 10, 10)
        b = BoundingBox(0, 0, 10, 10)
        assert a.is_below(b, margin=10) is False

    def test_overlaps_horizontally_partial(self) -> None:
        a = BoundingBox(0, 0, 10, 5)
        b = BoundingBox(5, 10, 15, 15)
        assert a.overlaps_horizontally(b) is True

    def test_overlaps_horizontally_no_overlap(self) -> None:
        a = BoundingBox(0, 0, 10, 5)
        b = BoundingBox(10, 10, 20, 15)
        assert a.overlaps_horizontally(b) is False

    def test_overlaps_horizontally_touching_is_no_overlap(self) -> None:
        a = BoundingBox(0, 0, 10, 5)
        b = BoundingBox(10, 0, 20, 5)
        assert a.overlaps_horizontally(b) is False

    def test_overlaps_horizontally_full_containment(self) -> None:
        a = BoundingBox(0, 0, 20, 5)
        b = BoundingBox(5, 10, 15, 15)
        assert a.overlaps_horizontally(b) is True

    def test_vertical_distance_separated(self) -> None:
        a = BoundingBox(0, 0, 10, 10)
        b = BoundingBox(0, 15, 10, 25)
        assert a.vertical_distance_to(b) == 5.0
        assert b.vertical_distance_to(a) == 5.0

    def test_vertical_distance_overlapping(self) -> None:
        a = BoundingBox(0, 0, 10, 20)
        b = BoundingBox(0, 15, 10, 25)
        assert a.vertical_distance_to(b) == 0.0

    def test_vertical_distance_touching(self) -> None:
        a = BoundingBox(0, 0, 10, 10)
        b = BoundingBox(0, 10, 10, 20)
        assert a.vertical_distance_to(b) == 0.0

    def test_frozen_immutable(self) -> None:
        bb = BoundingBox(0, 0, 10, 10)
        try:
            bb.x0 = 5  # type: ignore[misc]
            raise AssertionError("Expected FrozenInstanceError")
        except Exception as exc:  # noqa: BLE001
            assert "frozen" in type(exc).__name__.lower() or "cannot" in str(exc).lower()
