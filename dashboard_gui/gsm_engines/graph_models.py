from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class GraphStats:
    average: float
    minimum: float
    maximum: float


@dataclass(frozen=True)
class GraphPoint:
    graph_x: float
    value: float
    timestamp: Optional[float]
    index: int
    total: int
    role: str = ""
    label: str = ""

    @property
    def coordinates(self):
        return (self.graph_x, self.value)


@dataclass(frozen=True)
class GraphSnapshot:
    mode: str
    points: Tuple[Tuple[float, float], ...]
    timestamps: Tuple[float, ...]
    values: Tuple[float, ...]
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    labels: Tuple[str, ...]
    last_value: float
    stats: Optional[GraphStats]
    trend_icon: str = ""
    range_label: str = ""
    notable_points: Tuple[GraphPoint, ...] = ()


def axis_bounds(values):
    minimum = min(values)
    maximum = max(values)
    if minimum == maximum:
        return minimum - 1.0, maximum + 1.0

    difference = maximum - minimum
    return (
        minimum - (difference * 0.08),
        maximum + (difference * 0.08),
    )
