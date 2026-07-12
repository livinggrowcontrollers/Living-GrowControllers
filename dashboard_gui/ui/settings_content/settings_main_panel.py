# -*- coding: utf-8 -*-
"""
SettingsMainPanel – Scrollbare Version (Setup-Style)
Perfekt kompatibel mit SettingsScreen
© 2025 Dominik Rosenthal (Hackintosh1980)
"""
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.button import Button
import time
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
import config
from dashboard_gui.ui.i18n import I18N
from kivy.graphics import Rectangle, Color
from kivy.core.image import Image as CoreImage
import os
from kivy.uix.image import Image
from kivy.graphics import Color, Rectangle
from kivy.uix.togglebutton import ToggleButton

class SettingsMainPanel(BoxLayout):
    def __init__(self, on_save, on_cancel, **kw):
        super().__init__(**kw)
        self.orientation = "vertical"
        self.spacing = dp_scaled(10)
        self.padding = dp_scaled(12)

        self.on_save = on_save
        self.on_cancel = on_cancel
        self._lang_clicks = 0
        self._last_lang_ts = 0.0

        # --- Background mit Fallback ---
        bg_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "assets", "background2.png"
        )
        bg_path = os.path.abspath(bg_path)

        with self.canvas.before:
            
            
            if os.path.exists(bg_path):
                tex = CoreImage(bg_path).texture
                self.bg = Rectangle(texture=tex, pos=self.pos, size=self.size)
            else:
                Color(0.08,0.08,0.08,1)
                self.bg = Rectangle(pos=self.pos, size=self.size)
            
            self.bind(pos=self._update_bg, size=self._update_bg)

        # --- Rest deines bisherigen __init__ ---
        self.cfg = config._init()
        self.inputs = {}
        self.is_dev = config.is_developer_mode()

        # --- Scroll Area ---
        scroll = ScrollView(size_hint=(1,1))
        container = GridLayout(
            cols=1,
            spacing=dp_scaled(12),
            padding=[0, dp_scaled(6), 0, dp_scaled(6)],
            size_hint_y=None
        )
        container.bind(minimum_height=container.setter("height"))

# --- Haupt-Layout für den Inhalt (Horizontal) ---
        # Dies hält die linke und die rechte Spalte nebeneinander
        content_layout = BoxLayout(orientation="horizontal", spacing=dp_scaled(20))

        # --- LINKE SPALTE ---
        scroll_left = ScrollView(size_hint=(0.5, 1))
        container_left = GridLayout(cols=1, spacing=dp_scaled(12), size_hint_y=None)
        container_left.bind(minimum_height=container_left.setter("height"))
        
        # --- RECHTE SPALTE ---
        scroll_right = ScrollView(size_hint=(0.5, 1))
        container_right = GridLayout(cols=1, spacing=dp_scaled(12), size_hint_y=None)
        container_right.bind(minimum_height=container_right.setter("height"))

        # Überarbeiteter Helper: add_slider braucht jetzt ein "target_container"
        def add_slider(label_text, key, min_v, max_v, step, target_container):
            # Compact vertical layout: label+value on top, slider beneath
            row = BoxLayout(orientation="vertical", size_hint_y=None, height=dp_scaled(72), spacing=dp_scaled(6))
            # remember the normal visible height so toggling dev mode restores correctly
            row._visible_height = dp_scaled(72)

            top = BoxLayout(size_hint_y=None, height=dp_scaled(26), spacing=dp_scaled(8))
            lbl = Label(text=f"{I18N.t(label_text)}:", size_hint=(0.6, 1), font_size=sp_scaled(18), halign="left", valign="middle")
            val = Label(text=str(self.cfg.get(key,0)), size_hint=(0.4, 1), font_size=sp_scaled(18), halign="right", valign="middle")
            top.add_widget(lbl)
            top.add_widget(val)

            slider = Slider(min=min_v, max=max_v, step=step, value=float(self.cfg.get(key,0)), size_hint=(1, None), height=dp_scaled(28))
            slider.bind(value=lambda inst, v, lab=val: setattr(lab, "text", f"{v:.1f}"))
            self.inputs[key] = slider

            row.add_widget(top)
            row.add_widget(slider)

            # Dev-Check Logik bleibt gleich (wir verstecken die ganze Zeile)
            if not self.is_dev and key in ("refresh_interval","graph_resolution","stale_timeout","tile_graph_window"):
                row.height = 0
                row.opacity = 0
                row.disabled = True

            target_container.add_widget(row)

        # --- Verteilung der Slider ---
        
        # LINKS: System & Intervalle
        add_slider("settings.stale_timeout", "stale_timeout", 5, 60, 1, container_left)
        
        add_slider("settings.refresh_interval", "refresh_interval", 0.1, 3.0, 0.1, container_left)
        add_slider("settings.graph_resolution", "graph_resolution", 1.1, 100.0, 1, container_left)
        add_slider("settings.tile_graph_window", "tile_graph_window", 200, 2000, 10, container_left)
        add_slider("settings.graph_smoothing_factor", "graph_smoothing_factor", 0.0, 1.0, 0.01, container_left)
        # RECHTS: Offsets & Mesh
        add_slider("settings.temp_offset", "temperature_offset", -10, 10, 0.1, container_right)
        add_slider("settings.humidity_offset", "humidity_offset", -20, 20, 1, container_right)
        add_slider("settings.leaf_offset", "leaf_offset", -10, 10, 0.1, container_right)
        add_slider("LGS Send-Kanal", "lgs_mesh_channel_send", 0, 255, 1, container_right)
        add_slider("LGS Recv-Kanal", "lgs_mesh_channel_recv", 0, 255, 1, container_right)

        # --- Zusätzliche Controls (unten links/rechts verteilen) ---
        
        # Temperature Unit (Links) - label and selected value above compact buttons
        unit_block = BoxLayout(orientation="vertical", size_hint_y=None, height=dp_scaled(72), spacing=dp_scaled(6))
        unit_top = BoxLayout(size_hint_y=None, height=dp_scaled(26))
        unit_label = Label(text=f"{I18N.t('settings.temperature_unit')}:", size_hint=(0.6,1), font_size=sp_scaled(18), halign='left', valign='middle')
        self.temp_unit = self.cfg.get("temperature_unit","C")
        self.temp_unit_label = Label(text=self.temp_unit, size_hint=(0.4,1), font_size=sp_scaled(18), halign='right', valign='middle')
        unit_top.add_widget(unit_label)
        unit_top.add_widget(self.temp_unit_label)

        btn_row_unit = BoxLayout(size_hint_y=None, height=dp_scaled(36), spacing=dp_scaled(8))
        self.btn_C = Button(text="°C", background_color=(0.4,0.7,1,1) if self.temp_unit=="C" else (0.3,0.3,0.3,1))
        self.btn_F = Button(text="°F", background_color=(0.4,0.7,1,1) if self.temp_unit=="F" else (0.3,0.3,0.3,1))
        self.btn_C.bind(on_release=lambda *_: self._set_unit("C"))
        self.btn_F.bind(on_release=lambda *_: self._set_unit("F"))
        btn_row_unit.add_widget(self.btn_C)
        btn_row_unit.add_widget(self.btn_F)

        unit_block.add_widget(unit_top)
        unit_block.add_widget(btn_row_unit)
        container_left.add_widget(unit_block)

        # Language Row (Rechts) - label and selected value above compact buttons
        lang_block = BoxLayout(orientation="vertical", size_hint_y=None, height=dp_scaled(72), spacing=dp_scaled(6))
        lang_top = BoxLayout(size_hint_y=None, height=dp_scaled(26))
        lang_label = Label(text=f"{I18N.t('settings.language')}:", size_hint=(0.6,1), font_size=sp_scaled(18), halign='left', valign='middle')
        self.lang_selected_label = Label(text=(self.cfg.get("language","en") or "").upper(), size_hint=(0.4,1), font_size=sp_scaled(18), halign='right', valign='middle')
        lang_top.add_widget(lang_label)
        lang_top.add_widget(self.lang_selected_label)

        btn_row_lang = BoxLayout(size_hint_y=None, height=dp_scaled(36), spacing=dp_scaled(8))
        self.lang_buttons = {}
        for code, label in [("en","EN"),("de","DE"),("es","ES")]:
            btn = Button(text=label, background_color=(0.4,0.7,1,1) if self.cfg.get("language","en")==code else (0.3,0.3,0.3,1))
            btn.bind(on_release=lambda inst, c=code: self._set_language(c))
            self.lang_buttons[code] = btn
            btn_row_lang.add_widget(btn)
        lang_block.add_widget(lang_top)
        lang_block.add_widget(btn_row_lang)
        container_right.add_widget(lang_block)

        # Zusammenbau
        scroll_left.add_widget(container_left)
        scroll_right.add_widget(container_right)
        content_layout.add_widget(scroll_left)
        content_layout.add_widget(scroll_right)
        
        self.add_widget(content_layout) # Das fügt die zwei Spalten dem Hauptpanel hinzu
        # --- Bottom Buttons ---
        btn_row = BoxLayout(size_hint_y=None, height=dp_scaled(36), spacing=dp_scaled(10))
        btn_reset = Button(text=I18N.t("settings.reset_defaults"), font_size=sp_scaled(18), background_color=(0.45,0.45,0.45,1))
        btn_reset.bind(on_release=lambda *_: self._reset_defaults())
        btn_save = Button(text=I18N.t("settings.save"), font_size=sp_scaled(18), background_color=(0.2,0.55,0.2,1))
        btn_save.bind(on_release=lambda *_: self.on_save(self._collect()))
        btn_cancel = Button(text=I18N.t("settings.cancel"), font_size=sp_scaled(18), background_color=(0.55,0.2,0.2,1))
        btn_cancel.bind(on_release=lambda *_: self.on_cancel())
        btn_row.add_widget(btn_reset)
        btn_row.add_widget(btn_save)
        btn_row.add_widget(btn_cancel)
        self.add_widget(btn_row)

    # -----------------------------
    # Helper Methods
    # -----------------------------
    def _set_unit(self, u):
        self.temp_unit = u
        self.btn_C.background_color = (0.4,0.7,1,1) if u=="C" else (0.3,0.3,0.3,1)
        self.btn_F.background_color = (0.4,0.7,1,1) if u=="F" else (0.3,0.3,0.3,1)
        try:
            self.temp_unit_label.text = u
        except Exception:
            pass

    def _reset_defaults(self):
        now = time.time()
       

        defaults = {
            "refresh_interval":0.1,
            "graph_resolution":10.0,
            "stale_timeout":15.0,
            "tile_graph_window":850,
            "temperature_offset":0.0,
            "humidity_offset":0.0,
            "leaf_offset":0.0,
            "temperature_unit":"C",
            "graph_smoothing_factor":1.0,
        }

        for k,v in defaults.items():
            if k=="temperature_unit":
                self._set_unit(v)
            elif k in self.inputs:
                self.inputs[k].value = v


    def _update_bg(self, *_):
        self.bg.size = self.size
        self.bg.pos = self.pos
    def _collect(self):
        out = {k: v.value for k, v in self.inputs.items()}
        out["temperature_unit"] = self.temp_unit
        out["theme"] = config.get_theme()
        # Die Kanäle sind durch add_slider bereits in self.inputs[key].value
        return out

    def _update_dev_visibility(self):
        self.is_dev = config.is_developer_mode()
        for key in ("refresh_interval","graph_resolution","stale_timeout","tile_graph_window"):

            slider = self.inputs.get(key)
            if not slider:
                continue
            row = slider.parent
            if self.is_dev:
                row.disabled = False
                row.opacity = 1
                # restore the height we stored when creating the row (fallback to 48)
                row.height = getattr(row, "_visible_height", dp_scaled(48))
            else:
                row.disabled = True
                row.opacity = 0
                row.height = 0

    def _set_theme(self, theme):
        import config
        cfg = config._init()
        cfg["theme"] = theme
        config.save(cfg)
    
        for t, btn in self.theme_buttons.items():
            btn.background_color = (0.4,0.7,1,1) if t==theme else (0.3,0.3,0.3,1)
    
        print(f"[SETTINGS] Theme switched to {theme}")
    
    
    def _show_dev_popup(self, enabled: bool):
        icon = "[font=FA]\uf023[/font]"  # lock icon
        text = "Developer Mode ON" if enabled else "Developer Mode OFF"

        content = BoxLayout(orientation="horizontal", padding=10, spacing=10)

        lbl_icon = Label(
            text=icon,
            markup=True,
            font_size=28,
            size_hint=(None, 1),
            width=40
        )

        lbl_text = Label(
            text=text,
            valign="middle"
        )

        content.add_widget(lbl_icon)
        content.add_widget(lbl_text)

        popup = Popup(
            content=content,
            size_hint=(None, None),
            size=(260, 80),
            auto_dismiss=True
        )

        popup.open()

        # auto close nach 1.2s
        Clock.schedule_once(lambda dt: popup.dismiss(), 3)

    def _set_language(self, code):
        import config
        import time
    
        now = time.time()
    
        # --- DEV TOGGLE nur bei DE ---
        if code == "de":
            if now - self._last_lang_ts > 2.5:
                self._lang_clicks = 0
            self._last_lang_ts = now
            self._lang_clicks += 1
    
            if self._lang_clicks == 7:
                new_state = not config.is_developer_mode()
                config.set_developer_mode(new_state)
                self._lang_clicks = 0
                self._update_dev_visibility()

                print("[DEV] Developer Mode", "activated" if new_state else "deactivated")

                # 👉 Popup hier
                self._show_dev_popup(new_state)

                return
    
        # --- normale Sprachumschaltung ---
        cfg = config._init()
        cfg["language"] = code
        config.save(cfg)
    
        I18N.set_language(code)
    
        for c, btn in self.lang_buttons.items():
            btn.background_color = (0.4,0.7,1,1) if c==code else (0.3,0.3,0.3,1)

        try:
            self.lang_selected_label.text = code.upper()
        except Exception:
            pass
    
        print(f"[SETTINGS] Language switched to {code}")
