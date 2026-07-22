# dashboard_gui/overlays/features/shared/coercion.py

def as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)
