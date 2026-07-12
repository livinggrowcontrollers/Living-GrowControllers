import os
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle, Line
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.scaling_utils import sp_scaled, dp_scaled

ASSET_ROOT = os.path.join("dashboard_gui", "assets")
ESP32_PIC = os.path.join(ASSET_ROOT, "hardware_pics", "esp32_s3.png")

VALUE_BOX_WIDTH = dp_scaled(220)


class ESP32Tile(BoxLayout):

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", spacing=dp_scaled(12), padding=dp_scaled(10), **kwargs)
        # ==================== BOX SIZES ====================
        self.padding = dp_scaled(8)
        self.spacing = dp_scaled(0)        
        # ==================== MAIN CONTAINER ====================
        self.content_container = BoxLayout(
            orientation="vertical",
            size_hint=(1, 1),
            spacing=dp_scaled(15),
            height=dp_scaled(100)
        )

        # ---------------- TOP BOX (wichtigste Infos) ----------------
        self.main_box = self._create_value_box(
            height=dp_scaled(590),
            title="ESP32 Controller"
        )
        
        self.content_container.add_widget(self.main_box)
        
        self.device_image = Image(
            source=ESP32_PIC,
            size_hint=(1, None),
            height=dp_scaled(220),
            allow_stretch=True,
            keep_ratio=True
        )
        self.add_widget(self.content_container)

        # Labels verwalten
        self.labels = {}
        self._create_labels()

        self._state = {
            "status": None,
            "ssid": None,
            "ip": None,
            "rssi": None,
            "sys_time": None, # <-- NEU
            "uptime": None,
            "fw_ver": None,
            "rev_grow": None,
            "boot_cause": None,
            "wifi_mode": None,
            "free_heap": None,
            "max_alloc": None,
        }


    def _create_value_box(self, height, title=""):
        box = BoxLayout(
            orientation="vertical",
            size_hint=(1, None),
            height=height,
            padding=dp_scaled(14),
            spacing=dp_scaled(6)
        )

        # Optionaler Titel
        if title:
            title_label = Label(
                text=title,
                font_size=sp_scaled(20),
                bold=True,
                color=(0.2, 1, 0.8, 1),
                size_hint_y=None,
                height=dp_scaled(28),
                halign="left"
            )
            box.add_widget(title_label)

        # Canvas (schöner Rahmen + Glow)
        with box.canvas.before:
            Color(0, 0, 0, 0.62)
            box.bg = RoundedRectangle(pos=box.pos, size=box.size, radius=[dp_scaled(16)])

            # Dein Standard-Blau als Basis
            box.glow_color = Color(0.1, 0.45, 0.9, 0.35)
            box.glow = Line(width=6, rounded_rectangle=(0, 0, 0, 0, dp_scaled(16)))

            box.border_color = Color(0.1, 0.45, 0.9, 0.85)
            box.border = Line(width=1.5, rounded_rectangle=(0, 0, 0, 0, dp_scaled(16)))

        box.bind(pos=self._update_canvas, size=self._update_canvas)
        return box

    def _create_labels(self):
        # === TOP BOX - WICHTIGSTE INFOS ===
        top_items = [
            ("status", "System Status"),
            ("ssid", "Connected To"),
            ("ip", "IP Address"),
            ("rssi", "Signal Strength"),
        ]
        
        for key, title in top_items:
            self._add_label(self.main_box, key, title)
        
        # Bild genau zwischen beiden Bereichen
        self.main_box.add_widget(self.device_image)
        
        bottom_items = [
            ("sys_time", "System Time"),
            ("uptime", "Uptime"),
            ("fw_ver", "Firmware"),
            ("rev_grow", "Revision"),
            ("boot_cause", "Boot Cause"),
            ("wifi_mode", "WiFi Mode"),
            ("free_heap", "Free Heap"),
            ("max_alloc", "Max Alloc"),
        ]
        
        for key, title in bottom_items:
            self._add_label(self.main_box, key, title)

    def _add_label(self, parent, key, title):
        lbl = Label(
            text=f"{title}: -",
            font_size=sp_scaled(18),
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp_scaled(20)
        )
        lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))

        self.labels[key] = lbl
        parent.add_widget(lbl)

    def _update_box_color(self, box, is_ok):
        """Schaltet die Canvas-Farben der übergebenen Box um."""
        if not hasattr(box, 'glow_color') or not hasattr(box, 'border_color'):
            return
            
        if is_ok:
            # Dein Standard-Blau
            box.glow_color.rgba = (0.1, 0.45, 0.9, 0.35)
            box.border_color.rgba = (0.1, 0.45, 0.9, 0.85)
        else:
            # Alarm-Rot bei Offline / Fehler
            box.glow_color.rgba = (1.0, 0.3, 0.2, 0.35)
            box.border_color.rgba = (1.0, 0.3, 0.2, 0.85)

    # ==================== CANVAS UPDATE ====================
    def _update_canvas(self, obj, *args):
        x, y = obj.pos
        w, h = obj.size
        r = dp_scaled(16)

        if hasattr(obj, 'bg'):
            obj.bg.pos = (x, y)
            obj.bg.size = (w, h)

        rect = (x, y, w, h, r)
        if hasattr(obj, 'glow'):
            obj.glow.rounded_rectangle = rect
        if hasattr(obj, 'border'):
            obj.border.rounded_rectangle = rect

    def _apply_state(self):
    
        self.labels["status"].text = (
            f"System Status: {self._state['status']}"
            if self._state["status"] is not None
            else "System Status: -"
        )
    
        self.labels["ssid"].text = (
            f"Connected To: {self._state['ssid']}"
            if self._state["ssid"]
            else "Connected To: -"
        )
    
        self.labels["ip"].text = (
            f"IP: {self._state['ip']}"
            if self._state["ip"]
            else "IP: -"
        )
    
        self.labels["rssi"].text = (
            f"RSSI: {self._state['rssi']} dBm"
            if self._state["rssi"] is not None
            else "RSSI: -"
        )
    
        self.labels["uptime"].text = (
            f"Uptime: {self._state['uptime']}"
            if self._state["uptime"]
            else "Uptime: -"
        )
    
        self.labels["fw_ver"].text = (
            f"Firmware: {self._state['fw_ver']}"
            if self._state["fw_ver"]
            else "Firmware: -"
        )
    
        self.labels["rev_grow"].text = (
            f"Revision: REV-{self._state['rev_grow']}"
            if self._state["rev_grow"] is not None
            else "Revision: -"
        )
    
        self.labels["boot_cause"].text = (
            f"Boot Cause: {self._state['boot_cause']}"
            if self._state["boot_cause"]
            else "Boot Cause: -"
        )
    
        self.labels["wifi_mode"].text = (
            f"WiFi Mode: {self._state['wifi_mode']}"
            if self._state["wifi_mode"]
            else "WiFi Mode: -"
        )
    
        self.labels["free_heap"].text = (
            f"Free Heap: {self._state['free_heap']}"
            if self._state["free_heap"] is not None
            else "Free Heap: -"
        )
    
        self.labels["max_alloc"].text = (
            f"Max Alloc: {self._state['max_alloc']}"
            if self._state["max_alloc"] is not None
            else "Max Alloc: -"
        ) 


        self.labels["sys_time"].text = (
            f"System Time: {self._state['sys_time']}"
            if self._state["sys_time"]
            else "System Time: -"
        )


         # -------------------------------------------------
        # RESET ALL LABEL COLORS
        # -------------------------------------------------

        for lbl in self.labels.values():
            lbl.color = (1, 1, 1, 1)

        # -------------------------------------------------
        # STATUS COLOR
        # -------------------------------------------------

        status = self._state["status"]

        if status is not None:
            status = str(status).upper()

            if status in ("ACTIVE", "OK"):
                self.labels["status"].color = (0.2, 1, 0.2, 1)

            else:
                self.labels["status"].color = (1, 0.7, 0.2, 1)

        # -------------------------------------------------
        # RSSI COLOR
        # -------------------------------------------------

        rssi = self._state["rssi"]

        if rssi is not None:
            try:
                val = int(str(rssi).replace(" dBm", ""))

                if val > -60:
                    self.labels["rssi"].color = (0.2, 1, 0.2, 1)

                elif val > -80:
                    self.labels["rssi"].color = (1, 0.85, 0.2, 1)

                else:
                    self.labels["rssi"].color = (1, 0.3, 0.2, 1)

            except:
                pass

        # -------------------------------------------------
        # FREE HEAP COLOR
        # -------------------------------------------------

        heap = self._state["free_heap"]

        if heap is not None:
            try:
                heap_val = int(str(heap).replace(".", ""))

                if heap_val < 90000:
                    self.labels["free_heap"].color = (1, 0.2, 0.2, 1)

                elif heap_val < 130000:
                    self.labels["free_heap"].color = (1, 0.65, 0, 1)

                else:
                    self.labels["free_heap"].color = (0.2, 1, 0.2, 1)

            except:
                pass
    # ==================== DATA UPDATE ====================
    # ==================== DATA UPDATE ====================
    def update_values(self, data):
    
        if not data:
            for key in self._state:
                self._state[key] = None
    
            self._apply_state()
            self._update_box_color(self.main_box, False)
            return
    
        web = data.get("webserver", data)
    
        # -------------------------------------------------
        # STATE RESET
        # -------------------------------------------------
        for key in self._state:
            self._state[key] = None
    
        status_ok = False
    
        # -------------------------------------------------
        # STATUS
        # -------------------------------------------------
        status = web.get("status")
    
        if status is not None:
            status = str(status).upper()
            self._state["status"] = status
    
            if status in ("ACTIVE", "OK"):
                status_ok = True
    
        # -------------------------------------------------
        # NETWORK
        # -------------------------------------------------
        self._state["ssid"] = web.get("ssid")
        self._state["ip"] = web.get("ip")
    
        # -------------------------------------------------
        # RSSI
        # -------------------------------------------------
        health = data.get("health", {})

        self._state["rssi"] = health.get("signal", {}).get("rssi")

    
        # -------------------------------------------------
        # UPTIME
        # -------------------------------------------------
        uptime_raw = web.get("uptime_esp_s")
    
        if uptime_raw is not None:
            try:
                s = int(uptime_raw)
    
                h = s // 3600
                m = (s % 3600) // 60
                sec = s % 60
    
                uptime_str = (
                    f"{h:02d}:{m:02d}:{sec:02d}"
                    if h < 24
                    else f"{h//24}d {h%24:02d}:{m:02d}:{sec:02d}"
                )
    
                self._state["uptime"] = uptime_str
    
            except:
                pass
    
        # -------------------------------------------------
        # SYSTEM
        # -------------------------------------------------
        self._state["fw_ver"] = web.get("fw_ver")
        self._state["rev_grow"] = web.get("rev_grow")
        self._state["boot_cause"] = web.get("boot_cause")
    
        wifi_mode = web.get("wifi_mode")
    
        if wifi_mode is not None:
            self._state["wifi_mode"] = (
                "AP Mode"
                if wifi_mode == 0
                else "Router Mode"
            )
    
        # -------------------------------------------------
        # MEMORY
        # -------------------------------------------------
        free_heap = web.get("free_heap")
    
        if free_heap is not None:
            try:
                self._state["free_heap"] = (
                    f"{int(free_heap):,}".replace(",", ".")
                )
            except:
                pass
    
        max_alloc = web.get("max_alloc")
    
        if max_alloc is not None:
            try:
                self._state["max_alloc"] = (
                    f"{int(max_alloc):,}".replace(",", ".")
                )
            except:
                pass

        # -------------------------------------------------
        # SYSTEM TIME (Direkt aus dem JSON)
        # -------------------------------------------------
        self._state["sys_time"] = web.get("system_time") 

        # -------------------------------------------------
        # FINAL APPLY
        # -------------------------------------------------
        self._apply_state()
    
        self._update_box_color(
            self.main_box,
            status_ok
        )
    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos): 
            return False
        
        GLOBAL_STATE.ui_handler.goto("grow_controller")  # Geht direkt zum Spezialisten
        