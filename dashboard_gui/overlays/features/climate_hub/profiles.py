# dashboard_gui/overlays/features/climate_hub/profiles.py

from .targets import ClimateTargets


PROFILES = {
    "seedling": ClimateTargets(24.0, 27.0, 60, 70, 0.6, 0.9),
    "vegetative": ClimateTargets(24.0, 28.0, 55, 70, 0.8, 1.2),
    "flowering": ClimateTargets(22.0, 27.0, 45, 60, 1.2, 1.5),
    "drying": ClimateTargets(18.0, 22.0, 50, 60, 0.7, 1.0),
    "curing": ClimateTargets(18.0, 21.0, 55, 62, 0.6, 0.9),
}

PROFILE_LABELS = {
    "seedling": "SEEDLING",
    "vegetative": "VEG",
    "flowering": "FLOWERING",
    "drying": "DRYING",
    "curing": "CURING",
    "custom": "CUSTOM",
}


def match_profile(targets, tolerance=0.01):
    for name, profile in PROFILES.items():
        numeric_pairs = zip(targets.__dict__.values(), profile.__dict__.values())
        if all(abs(float(left) - float(right)) <= tolerance for left, right in numeric_pairs):
            return name
    return "custom"
