# backend/src/domain/entities/bounding_box.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BoundingBox:
    x0: float
    y0: float
    x1: float
    y1: float

    def area(self) -> float:
        return max(0.0, self.x1 - self.x0) * max(0.0, self.y1 - self.y0)

    def center(self) -> tuple[float, float]:
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)

    def is_below(self, other: BoundingBox, margin: float) -> bool:
        delta = self.y0 - other.y1
        return 0 < delta < margin

    def overlaps_horizontally(self, other: BoundingBox) -> bool:
        return self.x0 < other.x1 and other.x0 < self.x1

    def vertical_distance_to(self, other: BoundingBox) -> float:
        if self.y0 >= other.y1:
            return self.y0 - other.y1
        if other.y0 >= self.y1:
            return other.y0 - self.y1
        return 0.0
