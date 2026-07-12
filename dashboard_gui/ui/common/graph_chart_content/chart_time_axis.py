# dashboard_gui/ui/common/graph_chart_content/chart_time_axis.py

import config

def compute_time_axis_labels(display_len: int, refresh_rate: float, raw_res: float):
    """
    Berechnet Zeitlabels für Chart X-Achse.
    Rückgabe: list[str] mit 5 Labels
    """

    # --- Resolution handling (1:1 aus deinem Code) ---
    if raw_res <= 1.0:
        res_percent = max(1.0, raw_res * 100.0)
    else:
        res_percent = raw_res

    if res_percent < 1:
        res_percent = 1.0
    if res_percent > 100:
        res_percent = 100.0

    skip_interval = int(100.0 / res_percent)
    if skip_interval < 1:
        skip_interval = 1

    effective_sample_rate = refresh_rate * skip_interval
    total_seconds = display_len * effective_sample_rate
    total_minutes = total_seconds / 60

    labels = []

    for i in range(5):
        time_val = -total_minutes + (i * (total_minutes / 4))

        if abs(time_val) < 0.001:
            labels.append("Now")

        elif total_minutes < 1.0:
            seconds_val = int(time_val * 60)
            labels.append(f"{seconds_val}s")

        else:
            labels.append(
                f"{time_val:.1f}m" if abs(time_val) < 5 else f"{int(time_val)}m"
            )

    return labels