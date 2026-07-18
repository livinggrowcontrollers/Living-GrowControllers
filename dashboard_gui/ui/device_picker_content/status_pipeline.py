#dashboard_gui/ui/device_picker_content/status_pipeline.py

from kivy.clock import Clock
from dashboard_gui.data_buffer import BUFFER
from dashboard_gui.ui.common.logic.box_icon_color_updater import BoxColorUpdater
from dashboard_gui.ui.common.header_capabilities import build_header_capabilities, build_header_state
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.formatters import UIFormatter
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.circulation_fan_registry import MAX_CIRCULATION_FANS, fan_snapshot
class DeviceStatusPipeline:
    def __init__(self, screen_instance):
        self.screen = screen_instance
        self._last_packet_counters = {}

    def process_global_update(self, d):
        self.screen.header.update_from_global(d)

        if not isinstance(d, dict) or not d:
            return

        raw_buffer = BUFFER.get()
        
        frame_map = {
            str(frame.get("device_id", ""))
                .replace(":", "")
                .replace("-", "")
                .strip()
                .upper(): frame
            for frame in raw_buffer
            if isinstance(frame, dict)
        }
        if not isinstance(raw_buffer, list):
            return

        updates = []

        def _get_trend_icon(key):
            try:
                return GLOBAL_STATE.get_trend_icon(key) or ""
            except Exception:
                return ""

        for mac, led_widget in list(self.screen.device_leds.items()):
            alive = False
            status = "offline"
            current_counter = None
            rssi = None
            target_clean = str(mac).replace(":", "").replace("-", "").strip().upper()

            matched_frame = frame_map.get(target_clean)

            if matched_frame:
                adv = matched_frame.get("adv", {})
                gatt = matched_frame.get("gatt", {})
                web = matched_frame.get("webserver", {})
                health = matched_frame.get("health", {})

                rssi = health.get("signal", {}).get("rssi")

                adv_alive = bool(adv.get("alive", False))
                gatt_alive = bool(gatt.get("alive", False))
                web_alive = bool(web.get("alive", False))

                alive = adv_alive or gatt_alive or web_alive
                status = "active" if alive else "offline"

                current_counter = (
                    adv.get("packet_counter")
                    or gatt.get("packet_counter")
                    or web.get("timestamp")
                    or matched_frame.get("timestamp")
                )

            channel_colors = {
                "adv": (0.2, 0.2, 0.2, 1),
                "gatt": (0.2, 0.2, 0.2, 1),
                "web": (0.2, 0.2, 0.2, 1),
            }

            if matched_frame is not None:
                adv = matched_frame.get("adv", {})
                gatt = matched_frame.get("gatt", {})
                web = matched_frame.get("webserver", {})
                adv_alive = bool(adv.get("alive", False))
                gatt_alive = bool(gatt.get("alive", False))
                web_alive = bool(web.get("alive", False))

                channel_colors = {
                    "adv": (0.2, 1.0, 0.2, 1) if adv_alive else (0.2, 0.2, 0.2, 1),
                    "gatt": (0.2, 0.7, 1.0, 1) if gatt_alive else (0.2, 0.2, 0.2, 1),
                    "web": (1.0, 0.4, 1.0, 1) if web_alive else (0.2, 0.2, 0.2, 1),
                }

            if alive and current_counter is not None:
                last_counter = self._last_packet_counters.get(mac)
                if last_counter is not None and current_counter != last_counter:
                    status = "flow"
                self._last_packet_counters[mac] = current_counter
            elif not alive:
                self._last_packet_counters[mac] = None

            internal_temp_unit = GLOBAL_STATE.get_unit_for_metric(mac, "temp_in")
            external_temp_unit = GLOBAL_STATE.get_unit_for_metric(mac, "temp_ex")
            internal_hum_unit = GLOBAL_STATE.get_unit_for_metric(mac, "hum_in")
            external_hum_unit = GLOBAL_STATE.get_unit_for_metric(mac, "hum_ex")
            internal_vpd_unit = GLOBAL_STATE.get_unit_for_metric(mac, "vpd_in")
            external_vpd_unit = GLOBAL_STATE.get_unit_for_metric(mac, "vpd_ex")

            payload = {
                "mac": mac,
                "alive": alive,
                "status": status,
                "rssi": rssi,
                "channel_colors": channel_colors,
                "caps": [],
                "external_present": False,
                "internal_temp": None,
                "internal_hum": None,
                "internal_vpd": None,
                "external_temp": None,
                "external_hum": None,
                "external_vpd": None,
                "trend_temp_in": "",
                "trend_temp_ex": "",
                "trend_hum_in": "",
                "trend_hum_ex": "",
                "trend_vpd_in": "",
                "trend_vpd_ex": "",
                "internal_temp_unit": internal_temp_unit,
                "external_temp_unit": external_temp_unit,
                "internal_hum_unit": internal_hum_unit,
                "external_hum_unit": external_hum_unit,
                "internal_vpd_unit": internal_vpd_unit,
                "external_vpd_unit": external_vpd_unit,
            }

            if matched_frame is not None:
                adv = matched_frame.get("adv", {})
                gatt = matched_frame.get("gatt", {})
                web = matched_frame.get("webserver", {})
                health = matched_frame.get("health", {})

                internal_t = []
                internal_h = []
                internal_v = []
                external_t = []
                external_h = []
                external_v = []

                for ch in (adv, gatt, web):
                    t = ch.get("internal", {}).get("temperature", {}).get("value")
                    h = ch.get("internal", {}).get("humidity", {}).get("value")
                    v = ch.get("vpd_internal", {}).get("value")
                    if t is not None:
                        internal_t.append(float(t))
                    if h is not None:
                        internal_h.append(float(h))
                    if v is not None:
                        internal_v.append(float(v))

                    vals = ch.get("external", {})
                    if vals.get("present"):
                        payload["external_present"] = True

                    t = vals.get("temperature", {}).get("value")
                    h = vals.get("humidity", {}).get("value")
                    v = ch.get("vpd_external", {}).get("value")
                    if t is not None:
                        external_t.append(float(t))
                    if h is not None:
                        external_h.append(float(h))
                    if v is not None:
                        external_v.append(float(v))

                payload["internal_temp"] = sum(internal_t) / len(internal_t) if internal_t else None
                payload["internal_hum"] = sum(internal_h) / len(internal_h) if internal_h else None
                payload["internal_vpd"] = sum(internal_v) / len(internal_v) if internal_v else None
                payload["external_temp"] = sum(external_t) / len(external_t) if external_t else None
                payload["external_hum"] = sum(external_h) / len(external_h) if external_h else None
                payload["external_vpd"] = sum(external_v) / len(external_v) if external_v else None

                for metric_base in ("temp", "hum", "vpd"):
                    for suffix in ("in", "ex"):
                        metric = f"{metric_base}_{suffix}"
                        for ch in ("webserver", "gatt", "adv"):
                            key = f"{mac}_{ch}_{metric}"
                            try:
                                val = GLOBAL_STATE.graph_engine.get_last_value(key)
                            except Exception:
                                val = None
                            if val is not None:
                                payload[f"trend_{metric}"] = _get_trend_icon(key)
                                break

                payload["caps"] = [
                    {"type": cap["id"], "icon": cap["icon"], "color": cap["color"]}
                    for cap in build_header_capabilities(build_header_state(matched_frame))
                    if cap["show_in_picker"] and cap["enabled"]
                ]

            updates.append(payload)

        def _set_text(widget, new_text):
            if widget is None or widget.text == new_text:
                return
            widget.text = new_text

        def _set_color(widget, new_color):
            if widget is None or tuple(widget.color) == tuple(new_color):
                return
            widget.color = new_color

        def _do_update(dt):
            for payload in updates:
                mac = payload["mac"]
                row = self.screen.device_rows.get(mac)
                if not row:
                    continue

                row.led.set_state(payload["alive"], payload["status"])
                row.signal.set_rssi(payload["rssi"])

                for channel, color in payload["channel_colors"].items():
                    _set_color(self.screen.device_channel_labels.get(mac, {}).get(channel), color)

                row.update_capabilities(payload["caps"])

                entries = getattr(self.screen, "device_value_labels", {}).get(mac)
                if not entries:
                    continue

                def set_entry(entry, in_text, ex_text, in_trend="", ex_trend=""):

                    row = entry["row"]

                    i_lbl = entry["i_lbl"]
                    e_lbl = entry["e_lbl"]

                    i_val = entry["i_val"]
                    e_val = entry["e_val"]

                    has_i = bool(in_text and in_text != "--")
                    has_e = bool(ex_text and ex_text != "--")

                    if not has_i and not has_e:
                        row.opacity = 0
                        row.disabled = True
                        return

                    row.opacity = 1
                    row.disabled = False

                    i_lbl.opacity = 1
                    e_lbl.opacity = 1

                    i_lbl.width = dp_scaled(16)
                    e_lbl.width = dp_scaled(16)

                    i_val.size_hint_x = 1
                    e_val.size_hint_x = 1

                    i_val.font_size = sp_scaled(18)
                    e_val.font_size = sp_scaled(18)

                    if has_i and has_e:

                        _set_text(
                            i_val,
                            f"{in_text} [size=12][font=FA]{in_trend}[/font][/size]"
                            if in_trend else in_text
                        )

                        _set_text(
                            e_val,
                            f"{ex_text} [size=12][font=FA]{ex_trend}[/font][/size]"
                            if ex_trend else ex_text
                        )

                        return

                    if has_i:

                        e_lbl.opacity = 0
                        e_lbl.width = 0

                        e_val.text = ""
                        e_val.size_hint_x = 0

                        i_val.size_hint_x = 2
                        i_val.font_size = sp_scaled(22)

                        _set_text(
                            i_val,
                            f"{in_text} [size=13][font=FA]{in_trend}[/font][/size]"
                            if in_trend else in_text
                        )

                        return

                    i_lbl.opacity = 0
                    i_lbl.width = 0

                    i_val.text = ""
                    i_val.size_hint_x = 0

                    e_val.size_hint_x = 2
                    e_val.font_size = sp_scaled(22)

                    _set_text(
                        e_val,
                        f"{ex_text} [size=13][font=FA]{ex_trend}[/font][/size]"
                        if ex_trend else ex_text
                    )


                set_entry(
                    entries["temp"],
                    "--" if payload["internal_temp"] is None else f"{payload['internal_temp']:.2f}{payload['internal_temp_unit']}",
                    "--" if payload["external_temp"] is None else f"{payload['external_temp']:.2f}{payload['external_temp_unit']}",
                    payload["trend_temp_in"],
                    payload["trend_temp_ex"],
                )

                set_entry(
                    entries["hum"],
                    "--" if payload["internal_hum"] is None else f"{payload['internal_hum']:.2f}{payload['internal_hum_unit']}",
                    "--" if payload["external_hum"] is None else f"{payload['external_hum']:.2f}{payload['external_hum_unit']}",
                    payload["trend_hum_in"],
                    payload["trend_hum_ex"],
                )

                set_entry(
                    entries["vpd"],
                    "--" if payload["internal_vpd"] is None else f"{payload['internal_vpd']:.2f}{payload['internal_vpd_unit']}",
                    "--" if payload["external_vpd"] is None else f"{payload['external_vpd']:.2f}{payload['external_vpd_unit']}",
                    payload["trend_vpd_in"],
                    payload["trend_vpd_ex"],
                )
        Clock.schedule_once(_do_update)
