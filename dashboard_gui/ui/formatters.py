
# dashboard_gui/ui/formatters.py


from dashboard_gui.ui.scaling_utils import dp_scaled

class UIFormatter:

    @staticmethod
    def format_sensor_label(name, value, unit, trend="", sz_val=24, sz_trend=24, sz_unit=24, sz_name=24):
        from dashboard_gui.ui.scaling_utils import dp_scaled

        C_SUB = "#bbbbbb"

        def scale(size):
            return int(dp_scaled(size))

        val_str = f"{value:.2f}" if isinstance(value, (int, float)) else str(value)

        s_name = f"[color={C_SUB}][size={scale(sz_name)}]{name}[/size][/color]"
        s_trend = f"  [size={scale(sz_trend)}][font=FA]{trend}[/font][/size]  " if trend else "  "
        s_val = f"[size={scale(sz_val)}]{val_str}[/size]"
        s_unit = f" [color={C_SUB}][size={scale(sz_unit)}]{unit}[/size][/color]"

        return f"{s_name}{s_trend}{s_val}{s_unit}"