# dashboard_gui/ui/plant_planner_content/plant_logic.py


import time
from datetime import datetime, date

PHASES = [
    "germination",
    "seedling",
    "vegetative",
    "flowering",
    "drying",
    "curing"
]


def get_current_phase(plant):
    today = date.today()
    current = "UNKNOWN"

    for phase in PHASES:
        start = plant.get(f"{phase}_start", "")
        if not start:
            continue
        try:
            s = datetime.strptime(start, "%Y-%m-%d").date()
            if s <= today:
                current = phase
        except:
            pass

    return current


def phase_color(phase):
    colors = {
        "germination": (0.4, 0.8, 0.4, 1),
        "seedling": (0.5, 0.9, 0.3, 1),
        "vegetative": (0.2, 0.7, 1, 1),
        "flowering": (0.9, 0.3, 0.9, 1),
        "drying": (0.1, 0.9, 0.2, 1),
        "curing": (0.1, 0.9, 0.2, 1),
    }
    return colors.get(phase, (0.7, 0.7, 0.7, 1))


def calc_phase_days(plant, phase):
    start_str = plant.get(f"{phase}_start", "")
    if not start_str:
        return 0

    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        if start_date > date.today():
            return 0

        end_date = date.today()
        phase_index = PHASES.index(phase)

        for next_phase in PHASES[phase_index + 1:]:
            next_start_str = plant.get(f"{next_phase}_start", "")
            if next_start_str:
                try:
                    next_start_date = datetime.strptime(next_start_str, "%Y-%m-%d").date()
                    if next_start_date <= date.today():
                        end_date = next_start_date
                        break
                except:
                    pass

        return max(0, (end_date - start_date).days)
    except:
        return 0


def calc_total_days(plant):
    first_start = None
    for phase in PHASES:
        start_str = plant.get(f"{phase}_start", "")
        if start_str:
            try:
                s = datetime.strptime(start_str, "%Y-%m-%d").date()
                if s <= date.today():
                    if first_start is None or s < first_start:
                        first_start = s
            except:
                pass

    if first_start is None:
        return 0

    return (date.today() - first_start).days


def format_relative_timestamp(timestamp, now=None):
    if not timestamp or timestamp == 0:
        return "NEVER"

    if now is None:
        now = int(time.time())

    diff = max(0, int(now) - int(timestamp))
    
    # 1. Minuten-Bereich (unter 1 Stunde)
    if diff < 3600:
        minutes = diff // 60
        if minutes < 1:
            return "just now"
        if minutes == 1:
            return "1 min ago"
        return f"{minutes} mins ago"
        
    # 2. Reiner Stunden-Bereich (unter 1 Tag / 24 Stunden)
    if diff < 86400:
        hours = diff // 3600
        if hours == 1:
            return "1 hr ago"
        return f"{hours} hrs ago"

    # 3. Kombinierter Bereich (Ab 24 Stunden: Tage + restliche Stunden)
    days = diff // 86400
    remaining_hours = (diff % 86400) // 3600
    
    # Text für Tage bauen (Einzahl/Mehrzahl)
    days_str = "1 day" if days == 1 else f"{days} days"
    
    # Wenn es glatte Tage sind (0 Reststunden), zeige nur die Tage
    if remaining_hours == 0:
        return f"{days_str} ago"
        
    # Text für Reststunden bauen (Einzahl/Mehrzahl)
    hours_str = "1 hour" if remaining_hours == 1 else f"{remaining_hours} hrs"
    
    return f"{days_str}, {hours_str} ago"
def calc_grow_progress(plant):
    from datetime import datetime, date

    today = date.today()

    veg_start = plant.get("vegetative_start", "")
    # Grow abgeschlossen (Ernte eingeleitet)
    if plant.get("drying_start") or plant.get("curing_start"):
        return 100    
    
    if not veg_start:
        return 3

    try:
        veg_start = datetime.strptime(veg_start, "%Y-%m-%d").date()
    except:
        return 0

    # Blüte bereits gestartet?
    flower_start = plant.get("flowering_start", "")

    if flower_start:
        try:
            flower_start = datetime.strptime(flower_start, "%Y-%m-%d").date()

            real_veg_days = max(0, (flower_start - veg_start).days)
            flower_days_passed = max(0, (today - flower_start).days)

            estimated_flower_days = int(plant.get("estimated_flower_days", 60))

            total = real_veg_days + estimated_flower_days
            if total <= 0:
                return 0

            progress = ((real_veg_days + flower_days_passed) / total) * 100
            return max(0, min(100, int(progress)))

        except:
            pass

    # Noch in der Vegetation
    veg_days_passed = max(0, (today - veg_start).days)
    estimated_veg_days = int(plant.get("estimated_veg_days", 30))

    if estimated_veg_days <= 0:
        return 0

    progress = (veg_days_passed / estimated_veg_days) * 100

    # Während Veg nie über 99 %, bis Blüte wirklich startet
    return max(0, min(99, int(progress)))