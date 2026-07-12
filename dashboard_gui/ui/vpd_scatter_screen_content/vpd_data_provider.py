class VPDDataProvider:
    def __init__(self, gsm):
        self.gsm = gsm

    def _last_float(self, buf):
        if not buf:
            return None
        v = buf[-1]
        return float(v) if v is not None else None

    def get_data(self):
        idx = self.gsm.get_active_index()
        dev_list = self.gsm.get_device_list()
        if not dev_list or idx >= len(dev_list):
            return {
                "values": {
                    "in": {"t": None, "h": None, "vpd": None},
                    "ex": {"t": None, "h": None, "vpd": None},
                    "outside": {"t": None, "h": None, "vpd": None},
                    "inside": {"t": None, "h": None, "vpd": None},
                },
                "coords": {
                    "in": (None, None),
                    "ex": (None, None),
                    "outside": (None, None),
                    "inside": (None, None),
                },
            }

        dev_id = dev_list[idx]
        ch = self.gsm.get_active_channel()
        prefix = f"{dev_id}_{ch}"

        def get_last(metric):
            buf = self.gsm.get_graph_data(f"{prefix}_{metric}")
            value = self._last_float(buf)
            if value is None:
                return None
            if value < -250:
                return None
            return value

        values = {
            "in": {
                "t": get_last("temp_in"),
                "h": get_last("hum_in"),
                "vpd": get_last("vpd_in"),
            },
            "ex": {
                "t": get_last("temp_ex"),
                "h": get_last("hum_ex"),
                "vpd": get_last("vpd_ex"),
            },
            "outside": {
                "t": get_last("ble_temp_outside"),
                "h": get_last("ble_hum_outside"),
                "vpd": get_last("ble_vpd_outside"),
            },
            "inside": {
                "t": get_last("ble_temp_inside"),
                "h": get_last("ble_hum_inside"),
                "vpd": get_last("ble_vpd_inside"),
            },
        }

        coords = {
            "in": (get_last("vpd_x_in"), get_last("vpd_y_in")),
            "ex": (get_last("vpd_x_ex"), get_last("vpd_y_ex")),
            "outside": (get_last("vpd_x_outside"), get_last("vpd_y_outside")),
            "inside": (get_last("vpd_x_inside"), get_last("vpd_y_inside")),
        }

        return {"values": values, "coords": coords}
