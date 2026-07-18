# dashboard_gui/ui/device_picker_content/device_row.py

import os
import config
from dashboard_gui.global_state_manager import GLOBAL_STATE
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label, Widget
from kivy.uix.image import AsyncImage
from kivy.uix.button import Button
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.uix.gridlayout import GridLayout


from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.ui.common.icons.led_circle import LEDCircle
from dashboard_gui.ui.device_picker_content.edit_modal import DeviceEditModal
import dashboard_gui.ui.device_picker_content.config_actions as actions
from dashboard_gui.ui.common.icons.signal_bars import SignalBars
from dashboard_gui.ui.common.icons.icon_label import IconLabel



ASSET_ROOT = os.path.join("dashboard_gui", "assets")
from kivy.uix.behaviors import ButtonBehavior


class ClickableBox(ButtonBehavior, BoxLayout):
    pass


class ClickableLabel(ButtonBehavior, Label):
    pass


class IconButton(ButtonBehavior, IconLabel):
    def __init__(self, **kwargs):
        self._cap_callback = None
        super().__init__(**kwargs)

    def set_icon(self, icon, color):
        if self.text != icon:
            self.text = icon
        if tuple(self.color) != tuple(color):
            self.color = color

    def update_callback(self, callback):
        if callback is self._cap_callback:
            return
        if self._cap_callback is not None:
            self.unbind(on_release=self._cap_callback)
        self._cap_callback = callback
        if callback is not None:
            self.bind(on_release=callback)


class DeviceRow(BoxLayout):
    def __init__(self, mac, dev, screen_instance, large_layout=False, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        # layout scaling helpers
        scale = 1.35 if large_layout else 1.0
        dp = lambda v: dp_scaled(v) * scale
        sp = lambda v: sp_scaled(v) * scale

        self.padding = [dp(12), dp(8)]
        self.spacing = dp_scaled(8)
        self.size_hint_y = None
        self.height = dp(100)
        
        # --- Mixed Bar Setup ---
        self.mixed_position = None
        
        # Nutzen der existierenden ClickableBox und Erhöhung der Breite auf dp(35) für Treffsicherheit
        self.mixed_bar = ClickableBox(
            size_hint=(None, 1),
            width=dp(35),
        )
        
        with self.mixed_bar.canvas:
            self._mixed_color = Color(0, 1, 0, 0.6)  # grünlich
            self._mixed_line = Line(width=2.2)            # aussen glow effekt 
        
        # Binden des Klicks an die Methode, die wir im nächsten Schritt anlegen
        self.mixed_bar.bind(on_release=self._toggle_mixed_mode)
        self.add_widget(self.mixed_bar)
        
        self.mac = mac
        self.dev = dev
        self.screen = screen_instance

        with self.canvas.before:
            Color(0, 0, 0, 0.6)
            self.rect = RoundedRectangle(radius=[dp_scaled(8)], pos=self.pos, size=self.size)

        self.bind(
            pos=lambda *_: setattr(self.rect, "pos", self.pos),
            size=lambda *_: setattr(self.rect, "size", self.size)
        )

        displayed_mac = dev.get("mac", mac)


        self.signal = SignalBars(
            size_hint=(None, None),
            size=(dp(42), dp(24)),
            pos_hint={"center_y": 0.5},
        )
        self.signal.set_rssi(None)


        self.cap_container = GridLayout(
            cols=3,                     # 👈 3 Spalten → ergibt automatisch 3 Reihen
            size_hint=(None, None),
            height=dp(80),       # etwas höher für 3 Reihen
            width=dp(160),        # kompakter als vorher
            spacing=dp(2),
            padding=[0, 0]
        )
        self.cap_container.width = dp(160)  # erstmal fix
        self.cap_widgets = []
        self.cap_widgets = []
        
        


        if not hasattr(self.screen, "device_cap_containers"):
            self.screen.device_cap_containers = {}

        self.screen.device_cap_containers[mac] = self.cap_container
        
        
        # Wertebox
        self.value_container = BoxLayout(
            orientation="vertical",
            size_hint=(None, None),
            width=dp(240),
            height=dp(80),
            spacing=dp(2),
        )

        # Default placeholder texts include units from UnitEngine
        # Platzhalter ausschließlich über die UnitEngine
        temp_unit = GLOBAL_STATE.get_unit_for_metric(mac, "temp_in")
        hum_unit = GLOBAL_STATE.get_unit_for_metric(mac, "hum_in")
        vpd_unit = GLOBAL_STATE.get_unit_for_metric(mac, "vpd_in")

        def make_pair(default_text):
            row = BoxLayout(
                orientation="horizontal",
                spacing=dp(6),
            )

            lbl_i = Label(
                text="I",
                size_hint=(None, 1),
                width=dp(16),
                color=(0.45, 0.75, 1, 1),
                font_size=sp(13),
                bold=True,
            )

            val_i = ClickableLabel(
                text=default_text,
                markup=True,
                halign="left",
                valign="middle",
                font_size=sp(18),
            )

            lbl_e = Label(
                text="E",
                size_hint=(None, 1),
                width=dp(16),
                color=(1, 0.70, 0.25, 1),
                font_size=sp(13),
                bold=True,
            )

            val_e = ClickableLabel(
                text=default_text,
                markup=True,
                halign="left",
                valign="middle",
                font_size=sp(18),
            )

            for w in (val_i, val_e):
                w.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))

            row.add_widget(lbl_i)
            row.add_widget(val_i)
            row.add_widget(lbl_e)
            row.add_widget(val_e)

            return row, lbl_i, val_i, lbl_e, val_e

        temp_row, self.temp_i_lbl, self.lbl_temp_in, self.temp_e_lbl, self.lbl_temp_ex = make_pair(f"-- {temp_unit}")

        hum_row, self.hum_i_lbl, self.lbl_hum_in, self.hum_e_lbl, self.lbl_hum_ex = make_pair(f"-- {hum_unit}")

        vpd_row, self.vpd_i_lbl, self.lbl_vpd_in, self.vpd_e_lbl, self.lbl_vpd_ex = make_pair(f"-- {vpd_unit}")

        self.value_container.add_widget(temp_row)
        self.value_container.add_widget(hum_row)
        self.value_container.add_widget(vpd_row)

        if not hasattr(self.screen, "device_value_labels"):
            self.screen.device_value_labels = {}

        # Register pairs: ((temp_in, temp_ex), (hum_in, hum_ex), (vpd_in, vpd_ex))
        self.screen.device_value_labels[mac] = {
            "temp": {
                "row": temp_row,
                "i_lbl": self.temp_i_lbl,
                "i_val": self.lbl_temp_in,
                "e_lbl": self.temp_e_lbl,
                "e_val": self.lbl_temp_ex,
            },
            "hum": {
                "row": hum_row,
                "i_lbl": self.hum_i_lbl,
                "i_val": self.lbl_hum_in,
                "e_lbl": self.hum_e_lbl,
                "e_val": self.lbl_hum_ex,
            },
            "vpd": {
                "row": vpd_row,
                "i_lbl": self.vpd_i_lbl,
                "i_val": self.lbl_vpd_in,
                "e_lbl": self.vpd_e_lbl,
                "e_val": self.lbl_vpd_ex,
            },
        }

        # Bind clicks: first activate/select the device, then open fullscreen
        def _bind_metric(lbl, metric_id):
            lbl.bind(on_release=lambda *_: self._activate_and_open(metric_id))

        _bind_metric(self.lbl_temp_in, "temp_in")
        _bind_metric(self.lbl_temp_ex, "temp_ex")
        _bind_metric(self.lbl_hum_in, "hum_in")
        _bind_metric(self.lbl_hum_ex, "hum_ex")
        _bind_metric(self.lbl_vpd_in, "vpd_in")
        _bind_metric(self.lbl_vpd_ex, "vpd_ex")
        # LED initialisieren und im Screen für die Pipeline registrieren
        self.led = LEDCircle(
            size_hint=(None, None),
            size=(dp(22), dp(22)),
            pos_hint={"center_y": 0.5}
        )
        self.screen.device_leds[mac] = self.led
        if not hasattr(self.screen, "device_signalbars"):
            self.screen.device_signalbars = {}

        self.screen.device_signalbars[mac] = self.signal        
        self.led.set_state(False, "offline")

        # Bild-Vorschau
        image_file = config.get_device_image(mac)
        img_path = os.path.join(ASSET_ROOT, "hardware_pics", image_file) if image_file else ""
        final_src = img_path if (img_path and os.path.exists(img_path)) else ""

        img_box = BoxLayout(size_hint=(None, 1), height=dp(80))
        img_label = AsyncImage(source=final_src, allow_stretch=True, keep_ratio=True, size_hint=(1, 1))
        img_box.add_widget(img_label)

        # Text-Spalte
        text_col = BoxLayout(orientation="vertical", size_hint_x=0.4)
        name_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(45), spacing=dp(8))
        
        name_lbl = Label(text=dev.get("name", "<unnamed>"), font_size=sp(18), halign="left", valign="middle", shorten=True, shorten_from="right")
        name_lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        name_row.add_widget(name_lbl)

        mac_lbl = Label(text=f"BLE MAC: {displayed_mac}", font_size=sp(18), color=(0.6, 0.6, 0.65, 1), size_hint_y=None, height=dp(18), halign="left", shorten=True)
        mac_lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        
        text_col.add_widget(name_row)
        text_col.add_widget(mac_lbl)

        # Channel Status Spalte
        channel_col = BoxLayout(orientation="horizontal", size_hint=(None, 1), width=dp(580), spacing=dp(8))
       
        status_col = BoxLayout(
            orientation="vertical",
            size_hint=(None, None),
            width=dp(70),
            height=dp(80),
            spacing=dp(8),
        )       
        adv_lbl = ClickableLabel(
            text="ADV",
            size_hint_y=None,
            height=dp_scaled(20),
            font_size=sp_scaled(18),
            bold=True,
            color=(0.5, 0.5, 0.5, 1),
        )

        gatt_lbl = ClickableLabel(
            text="GATT",
            size_hint_y=None,
            height=dp_scaled(20),
            font_size=sp_scaled(18),
            bold=True,
            color=(0.5, 0.5, 0.5, 1),
        )

        web_lbl = ClickableLabel(
            text="WEB",
            size_hint_y=None,
            height=dp_scaled(20),
            font_size=sp_scaled(18),
            bold=True,
            color=(0.5, 0.5, 0.5, 1),
        )

        web_lbl.bind(on_release=lambda *_: self._activate_web_channel())
        adv_lbl.bind(on_release=lambda *_: self._activate_adv_channel())
        gatt_lbl.bind(on_release=lambda *_: self._activate_gatt_channel())

        channel_col.add_widget(self.signal)

        channel_col.add_widget(
            Widget(size_hint_x=None, width=dp(12))
        )
        
        channel_col.add_widget(self.led)
        status_col.add_widget(adv_lbl)
        status_col.add_widget(gatt_lbl)
        status_col.add_widget(web_lbl)

        channel_col.add_widget(status_col)
       
        channel_col.add_widget(self.cap_container)
        channel_col.add_widget(self.value_container)


        if not hasattr(self.screen, "device_channel_labels"):
            self.screen.device_channel_labels = {}
        self.screen.device_channel_labels[mac] = {"adv": adv_lbl, "gatt": gatt_lbl, "web": web_lbl}

        # Aktionsbuttons
        action_row = GridLayout(
            cols=2,
            rows=2,
            size_hint=(None, None),
            width=dp(90),
            height=dp(90),
            spacing=dp(2),
            pos_hint={"center_y": 0.5},  # ◄ DIESE ZEILE HINZUFÜGEN
        )
        BTN_SIZE = dp(45)
        
        btn_up = Button(text="[font=FA]\uf062[/font]", markup=True, font_size=sp(18), size_hint=(None, None), width=BTN_SIZE, height=BTN_SIZE, background_down="", background_color=(0.22, 0.23, 0.27, 1))
        btn_up.bind(on_release=lambda *_: actions.move_device(mac, "up", self.screen._build))
        
        btn_down = Button(text="[font=FA]\uf063[/font]", markup=True, font_size=sp(18), size_hint=(None, None), width=BTN_SIZE, height=BTN_SIZE, background_down="", background_color=(0.22, 0.23, 0.27, 1))
        btn_down.bind(on_release=lambda *_: actions.move_device(mac, "down", self.screen._build))
        
        btn_copy = Button(text="[font=FA]\uf0c5[/font]", markup=True, font_size=sp(18), size_hint=(None, None), width=BTN_SIZE, height=BTN_SIZE, background_down="", background_color=(0.2, 0.4, 0.6, 1))
        btn_copy.bind(on_release=lambda *_: actions.copy_device(mac, self.screen._build))

        current_cfg = config._init()
        total_devices = len(current_cfg.get("devices", {}))

        btn_delete = Button(
            text="[font=FA]\uf1f8[/font]", markup=True, font_size=sp(18), size_hint=(None, None), width=BTN_SIZE, height=BTN_SIZE, background_down="",
            background_color=(0.7, 0.25, 0.25, 1) if total_devices > 1 else (0.4, 0.4, 0.4, 0.5),
            disabled=total_devices <= 1
        )
        btn_delete.bind(on_release=lambda *_: actions.delete_device(mac, self.screen._build))

        action_row.add_widget(btn_up)
        action_row.add_widget(btn_copy)

        action_row.add_widget(btn_down)
        action_row.add_widget(btn_delete)

        btn_edit = Button(
            text="[font=FA]\uf013[/font]",
            markup=True,
            font_size=sp(22),
            size_hint=(None, None),
            width=dp(80),
            height=dp(80),
            background_down="",
            background_color=(0.2, 0.5, 0.7, 1)
        )
        btn_edit.bind(on_release=lambda *_: DeviceEditModal(mac, dev, displayed_mac, self.screen._build).open())

        device_area = ClickableBox(
            orientation="horizontal",
            size_hint_x=0.4,
            spacing=dp(8),
        )

        device_area.bind(on_release=self._activate_device)

        device_area.add_widget(img_box)
        device_area.add_widget(text_col)

        self.add_widget(device_area)
        self.add_widget(channel_col)
        self.add_widget(action_row)
        
        
        self.add_widget(btn_edit)
        
        # Bind position/size updates for mixed bar rendering
        self.bind(pos=self._update_mixed_bar, size=self._update_mixed_bar)

    def update_capabilities(self, caps):
        if caps is None:
            caps = []

        # Keep existing widgets when possible.
        for index, cap in enumerate(caps[:8]):
            if index < len(self.cap_widgets):
                icon_widget = self.cap_widgets[index]
                icon_widget.set_icon(cap["icon"], cap["color"])
                icon_widget.update_callback(lambda *_args, _cap_type=cap["type"]: self._open_capability(_cap_type))
            else:
                icon_widget = IconButton(
                    text=cap["icon"],
                    font_size=26,
                    color=cap["color"]
                )
                icon_widget.update_callback(lambda *_args, _cap_type=cap["type"]: self._open_capability(_cap_type))
                self.cap_widgets.append(icon_widget)
                self.cap_container.add_widget(icon_widget)

        if len(self.cap_widgets) > len(caps[:8]):
            for extra in self.cap_widgets[len(caps[:8]):]:
                if extra._cap_callback is not None:
                    extra.unbind(on_release=extra._cap_callback)
                self.cap_container.remove_widget(extra)
            self.cap_widgets = self.cap_widgets[:len(caps[:8])]

    def _activate_device(self, *_):
        from dashboard_gui.global_state_manager import GLOBAL_STATE
        from dashboard_gui.data_buffer import BUFFER

        devices = GLOBAL_STATE.get_device_list()

        try:
            idx = devices.index(self.mac)
        except ValueError:
            return

        GLOBAL_STATE.set_active_index(idx)

        BUFFER.soft_reload()
        data = BUFFER.get()

        frame = next(
            (f for f in data if f.get("device_id") == self.mac),
            None
        )

        if frame:
            if frame.get("webserver", {}).get("alive"):
                GLOBAL_STATE.set_active_channel("webserver")
            elif frame.get("adv", {}).get("alive"):
                GLOBAL_STATE.set_active_channel("adv")
            elif frame.get("gatt", {}).get("alive"):
                GLOBAL_STATE.set_active_channel("gatt")

        GLOBAL_STATE.data_flow.process_cycle()

    def _make_header_touch(self, widget):
        touch = type("Touch", (), {})()
        touch.pos = widget.center
        return touch

    def _open_capability(self, cap_type):
        self._activate_device()

        header = getattr(self.screen, "header", None)
        if not header:
            return

        if cap_type == "light" and hasattr(header, "light"):
            header.light.on_touch_down(self._make_header_touch(header.light))
        elif cap_type.startswith("circulation_fan_") and hasattr(header, "circulation_fans"):
            try:
                fan_id = int(cap_type.rsplit("_", 1)[1])
                fan = header.circulation_fans.get(fan_id)
            except (ValueError, AttributeError):
                fan = None
            if fan:
                fan.on_touch_down(self._make_header_touch(fan))
        elif cap_type == "exhaust_fan" and hasattr(header, "exhaust_fan"):
            header.exhaust_fan.on_touch_down(self._make_header_touch(header.exhaust_fan))
        elif cap_type == "climate_hub" and hasattr(header, "climate_hub"):
            header.climate_hub.on_touch_down(self._make_header_touch(header.climate_hub))
        elif cap_type == "battery" and hasattr(header, "battery"):
            # Battery icon has no overlay in HeaderBar; only refresh the widget state.
            pass
        elif cap_type == "external" and hasattr(header, "external"):
            # External icon has no overlay in HeaderBar; only refresh the widget state.
            pass

    def _activate_web_channel(self, *_):
        self._activate_device()
        GLOBAL_STATE.set_active_channel("webserver")
        GLOBAL_STATE.data_flow.process_cycle()

    def _activate_adv_channel(self, *_):
        self._activate_device()
        GLOBAL_STATE.set_active_channel("adv")
        GLOBAL_STATE.data_flow.process_cycle()

    def _activate_gatt_channel(self, *_):
        self._activate_device()
        GLOBAL_STATE.set_active_channel("gatt")
        GLOBAL_STATE.data_flow.process_cycle()

    def _activate_and_open(self, tile_id):
        """Activate/select this device, then open the requested fullscreen tile."""
        try:
            self._activate_device()
        except Exception:
            pass
        return self._open_fullscreen(tile_id)

    def _open_fullscreen(self, tile_id):
        """Open fullscreen for this device and tile_id.

        Tries active channel first, then falls back to webserver/gatt/adv.
        """
        try:
            # prefer current active channel
            channel = GLOBAL_STATE.get_active_channel() or "webserver"
            full_key = f"{self.mac}_{channel}_{tile_id}"
            eng = getattr(GLOBAL_STATE.ggm, 'engines', {}).get('dashboard') if hasattr(GLOBAL_STATE, 'ggm') else None
            if eng and eng.open_fullscreen(full_key):
                return True

            # fallback channels
            for ch in ("webserver", "gatt", "adv"):
                full_key = f"{self.mac}_{ch}_{tile_id}"
                if eng and eng.open_fullscreen(full_key):
                    return True
        except Exception as e:
            print(f"[DeviceRow] Open fullscreen error: {e}")
        return False
    
    def _update_mixed_bar(self, *_):
        """Render the mixed bar connector on the left side."""
        # Prüfen, ob DIESES Gerät überhaupt im Mixed Mode ausgewählt ist
        is_selected = self.mac in GLOBAL_STATE.mixed_selected_buffers
        
        if not is_selected:
            self._mixed_line.points = []
            return

        # Gesamtzahl der aktuell ausgewählten Mixed-Mode Geräte ermitteln
        total_selected = len(GLOBAL_STATE.mixed_selected_buffers)
        
        # Farblogik: Wenn nur 1 Gerät aktiv ist -> Orange hinterlegen. Ab 2 Geräten -> Grün.
        if total_selected == 1:
            self._mixed_color.rgba = (1, 0.5, 0, 0.8) # Orange
        else:
            self._mixed_color.rgba = (0, 1, 0, 0.6)   # Das gewohnte Grün
        
        x = self.mixed_bar.x + self.mixed_bar.width / 2
        y1 = self.y
        y2 = self.top
        
        # WICHTIG: Wenn nur ein einzelnes Gerät aktiv ist (oder Position "single" ist),
        # zeichnen wir einen kurzen, zentrierten Kontroll-Strich, statt die Linie zu löschen.
        if total_selected == 1 or self.mixed_position == "single" or not self.mixed_position:
            self._mixed_line.points = [x, self.center_y - dp_scaled(15), x, self.center_y + dp_scaled(15)]
            return
        
        # Wenn mehrere Geräte aktiv sind, greift die normale Verbindungs-Logik
        if self.mixed_position == "top":
            self._mixed_line.points = [x, self.y, x, self.center_y]
        
        elif self.mixed_position == "middle":
            self._mixed_line.points = [x, y1, x, y2]
        
        elif self.mixed_position == "bottom":
            self._mixed_line.points = [x, self.center_y, x, y2]
    
    def _toggle_mixed_mode(self, *_):
        actions.toggle_mixed_mode(self.mac, self.screen)
