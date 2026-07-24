
# dashboard_gui/ui/formatters.py


from dashboard_gui.ui.scaling_utils import dp_scaled

class UIFormatter:

    @staticmethod
    def format_number(value, style=None):
        style = style or {}
        decimals = int(style.get("decimals", 2))
        return f"{value:.{decimals}f}" if isinstance(value, (int, float)) else str(value)

    @staticmethod
    def format_sensor_label(name, value, unit, trend="", sz_val=24, sz_trend=24,
                            sz_unit=24, sz_name=24, style=None):
        from dashboard_gui.ui.scaling_utils import dp_scaled

        style = style or {}
        sz_val = style.get("sz_val", sz_val)
        sz_trend = style.get("sz_trend", sz_trend)
        sz_unit = style.get("sz_unit", sz_unit)
        sz_name = style.get("sz_name", sz_name)
        color_sub = style.get("color_sub", "#bbbbbb")
        color_name = style.get("color_name", color_sub)
        color_value = style.get("color_value")

        def scale(size):
            return int(dp_scaled(size))

        val_str = UIFormatter.format_number(value, style)

        s_name = f"[color={color_name}][size={scale(sz_name)}]{name}[/size][/color]" if name else ""
        s_trend = f"  [size={scale(sz_trend)}][font=FA]{trend}[/font][/size]  " if trend else "  "
        value_markup = f"[size={scale(sz_val)}]{val_str}[/size]"
        s_val = f"[color={color_value}]{value_markup}[/color]" if color_value else value_markup
        s_unit = f" [color={color_sub}][size={scale(sz_unit)}]{unit}[/size][/color]"

        return f"{s_name}{s_trend}{s_val}{s_unit}"
