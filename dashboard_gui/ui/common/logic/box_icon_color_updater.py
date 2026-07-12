# dashboard_gui/ui/common/logic/box_icon_color_updater.py




class BoxColorUpdater:

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

    def _update_box_color(self, rpm):

        color = self.get_rpm_color(rpm)

        self.glow_color.rgba = (*color, 0.35)
        self.border_color.rgba = (*color, 0.85)