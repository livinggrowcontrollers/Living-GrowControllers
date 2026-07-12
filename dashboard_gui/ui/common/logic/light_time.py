# dashboard_gui/ui/common/logic/light_time.py
import time


def calculate_light_time(data: dict) -> str:
    mode = data.get('light_mode', 'man')
    if mode != "time":
        return "MODUS: MANUELL/AUS"

    h = int(data.get('l_start_h', 8))
    m = int(data.get('l_start_m', 0))
    dur = int(data.get('l_dur', 720))

    now = time.localtime()
    current_min = now.tm_hour * 60 + now.tm_min
    start_min = h * 60 + m
    end_min = start_min + dur

    is_active = False

    if end_min <= 1440:
        if start_min <= current_min < end_min:
            is_active = True
    else:
        if current_min >= start_min or current_min < (end_min % 1440):
            is_active = True

    if is_active:
        if current_min >= start_min:
            rem_min = end_min - current_min
        else:
            rem_min = (end_min % 1440) - current_min

        return f"REMAINING: {rem_min // 60}h {rem_min % 60:02d}m"

    wait_min = (start_min - current_min + 1440) % 1440
    return f"START IN: {wait_min // 60}h {wait_min % 60:02d}m"