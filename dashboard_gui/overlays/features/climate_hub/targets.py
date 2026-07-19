from dataclasses import dataclass


@dataclass(frozen=True)
class ClimateTargets:
    temp_min: float = 22.0
    temp_max: float = 28.0
    humidity_min: int = 40
    humidity_max: int = 70
    vpd_min: float = 0.8
    vpd_max: float = 1.5
