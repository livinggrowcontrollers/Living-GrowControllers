# dashboard_gui/overlays/components/status_colors.py

"""Canonical color mapping for overlay panels, tiles and header icons."""


class StatusColors:

    def __init__(self):
        self.glow_color = None
        self.border_color = None


    @staticmethod
    def get_rpm_color(rpm):

        if rpm is None or rpm < 0:
            return (0.3, 0.3, 0.3)

        if rpm <= 0:
            return (1, 0, 0)  # nein rot!

        elif rpm < 200:
            return (0.6, 0.9, 1)

        elif rpm < 400:
            return (0.5, 1, 0.9)

        elif rpm < 600:
            return (0.5, 1, 0.7)

        elif rpm < 800:
            return (0.7, 1, 0.5)

        elif rpm < 1000:
            return (0.9, 1, 0.5)

        elif rpm < 1200:
            return (1, 1, 0.6)

        elif rpm < 1400:
            return (1, 0.9, 0.5)

        elif rpm < 1600:
            return (1, 0.8, 0.5)

        elif rpm < 1800:
            return (1, 0.7, 0.5)

        return (1, 0.6, 0.5)


    @staticmethod
    def get_light_color(brightness):

        if brightness is None or brightness < 0:
            return (0.5, 0.5, 0.5)

        if brightness <= 0:
            return (0.2, 0.2, 0.2)

        elif brightness < 20:
            return (0.6, 0.5, 0.0)

        elif brightness < 50:
            return (0.8, 0.8, 0.0)

        elif brightness < 80:
            return (1.0, 1.0, 0.0)

        return (1.0, 1.0, 0.6)

    @staticmethod
    def get_output_color(percent):
        """Shared colour scale for actuator outputs without RPM feedback."""
        if percent is None or percent < 0:
            return (0.35, 0.35, 0.35)
        if percent <= 0:
            return (1.0, 0.4, 0.4)
        if percent < 20:
            return (0.6, 0.9, 1.0)
        if percent < 40:
            return (0.5, 1.0, 0.9)
        if percent < 60:
            return (0.5, 1.0, 0.7)
        if percent < 80:
            return (0.9, 1.0, 0.5)
        return (1.0, 0.8, 0.5)
    
    @staticmethod
    def get_battery_color(voltage):

        if voltage is None:
            return (0.4, 0.4, 0.4)

        if voltage < 0.1:
            return (0.4, 0.4, 0.4)

        elif voltage >= 3.9:
            return (0.3, 1.0, 0.3)

        elif voltage >= 3.6:
            return (1.0, 0.8, 0.2)

        return (1.0, 0.2, 0.2)
    
    @staticmethod
    def get_battery_state(voltage):

        if voltage is None:
            return "\uf244", "--"

        if voltage < 0.1:
            return "\uf244", "OFF"

        if voltage >= 3.9:
            return "\uf240", f"{float(voltage):.2f}V"

        elif voltage >= 3.6:
            return "\uf242", f"{float(voltage):.2f}V"

        return "\uf243", f"{float(voltage):.2f}V"

    @staticmethod
    def get_external_color():

        return (0.3, 1.0, 0.3)

    @staticmethod
    def get_external_state(present):

        if not present:
            return "\uf059", "EXT"

        return "\uf2c7", "EXT"

    @staticmethod
    def get_climate_color(data):
        """Return one shared climate colour from live values and target ranges.

        Grey means the Climate Hub is not configured, cyan means targets exist
        but no live internal climate values are available yet, green is within
        range, amber is a moderate deviation and red is a severe deviation.
        """
        data = data or {}
        target_keys = (
            "target_temp_min", "target_temp_max",
            "target_humidity_min", "target_humidity_max",
            "target_vpd_min", "target_vpd_max",
        )
        if any(data.get(key) is None for key in target_keys):
            return (0.35, 0.35, 0.35)

        internal = data.get("internal", {}) if isinstance(data.get("internal"), dict) else {}
        temp = internal.get("temperature", {}).get("value") if isinstance(internal.get("temperature"), dict) else None
        humidity = internal.get("humidity", {}).get("value") if isinstance(internal.get("humidity"), dict) else None
        vpd_node = data.get("vpd_internal", {})
        vpd = vpd_node.get("value") if isinstance(vpd_node, dict) else vpd_node
        if any(value is None for value in (temp, humidity, vpd)):
            return (0.3, 0.8, 1.0)

        def deviation(value, lower, upper):
            value, lower, upper = float(value), float(lower), float(upper)
            span = max(upper - lower, 0.1)
            if value < lower:
                return (lower - value) / span
            if value > upper:
                return (value - upper) / span
            return 0.0

        worst = max(
            deviation(temp, data["target_temp_min"], data["target_temp_max"]),
            deviation(humidity, data["target_humidity_min"], data["target_humidity_max"]),
            deviation(vpd, data["target_vpd_min"], data["target_vpd_max"]),
        )
        if worst == 0:
            return (0.25, 1.0, 0.45)
        if worst <= 0.35:
            return (1.0, 0.72, 0.2)
        return (1.0, 0.28, 0.2)

    def _update_box_color(self, rpm):

        color = self.get_rpm_color(rpm)

        self.glow_color.rgba = (*color, 0.35)
        self.border_color.rgba = (*color, 0.85)
