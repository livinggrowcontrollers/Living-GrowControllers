import os

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.label import Label
from kivy.graphics import Rectangle, Color

from dashboard_gui.ui.common.header_online import HeaderBar
from dashboard_gui.ui.i18n import I18N
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled

from dashboard_gui.ui.grow_overview_content.exhaust_tile import ExhaustTile
from dashboard_gui.ui.grow_overview_content.circulation_tile import CirculationTile
from dashboard_gui.ui.grow_overview_content.light_tile import LightTile
from dashboard_gui.ui.grow_overview_content.esp32_tile import ESP32Tile
from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.grow_overview_content.sensor_internal_sht31_tile import SensorInternalSHT31Tile
from dashboard_gui.ui.grow_overview_content.sensor_external_sht31_tile import SensorExternalSHT31Tile
from dashboard_gui.ui.grow_overview_content.ble_inside_tile import SensorBLE_InsideTile
from dashboard_gui.ui.grow_overview_content.ble_outside_tile import SensorBLEOutsideTile
from dashboard_gui.ui.grow_overview_content.mlx90614_tile import SensorExternalMLX90614Tile  # ← NEU
from dashboard_gui.ui.grow_overview_content.rtc_tile import RTCTile
from dashboard_gui.ui.grow_overview_content.humidifier_tile import HumidifierTile
from dashboard_gui.ui.grow_overview_content.scd41_tile import SensorSCD41Tile
from dashboard_gui.ui.grow_overview_content.tapo_tile import TapoTile
ASSET_ROOT = os.path.join("dashboard_gui", "assets")


class GrowOverviewScreen(Screen):

    def __init__(self, **kw):
        super().__init__(**kw)

        GLOBAL_STATE.ui_handler.attach_screen("grow_overview", self)

        # ---------------- ROOT ----------------
        root = BoxLayout(orientation="vertical")

        # ---------------- BACKGROUND ----------------
        with root.canvas.before:
            Color(1, 1, 1, 1)
            self.bg_rect = Rectangle(
                source=os.path.join(ASSET_ROOT, "background2.png"),
                pos=root.pos,
                size=root.size
            )

        root.bind(
            pos=lambda *_: setattr(self.bg_rect, "pos", root.pos),
            size=lambda *_: setattr(self.bg_rect, "size", root.size)
        )

        # ---------------- HEADER ----------------
        self.header = HeaderBar()
        root.add_widget(self.header)



        # ---------------- CONTENT AREA ----------------
        # Use a horizontal BoxLayout with three columns. Each column
        # contains a header label and a ScrollView holding a vertical
        # BoxLayout so unlimited items can be added.
        from kivy.uix.scrollview import ScrollView

        self.content = BoxLayout(orientation="horizontal", spacing=dp_scaled(0), padding=dp_scaled(2))

        # helper to create a column with header and scroll container
        def make_column(header_text):
            col = BoxLayout(orientation="vertical")
            hdr = Label(
                text=header_text,
                font_size=sp_scaled(14),
                bold=True,
                color=(1, 1, 1, 1),
                size_hint=(1, None),
                height=dp_scaled(16),
                halign="left",
                valign="middle"
            )
            # inner layout holds dynamic children
            inner = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp_scaled(1), padding=[0, dp_scaled(8), 0, dp_scaled(8)])
            inner.bind(minimum_height=inner.setter('height'))

            sv = ScrollView(size_hint=(1, 1))
            sv.add_widget(inner)

            col.add_widget(hdr)
            col.add_widget(sv)
            return col, inner

        # Create three columns
        col1, col1_inner = make_column("System Core")
        col2, col2_inner = make_column("Sensor Hub")
        col3, col3_inner = make_column("Actuators")

        # keep references so other code can add widgets dynamically
        self.col1_inner = col1_inner
        self.col2_inner = col2_inner
        self.col3_inner = col3_inner

        # ---------------- TILES ----------------
        # ---------------- TILES ----------------
        self.exhaust_tile = ExhaustTile()
        self.circ_tile = CirculationTile()
        self.light_tile = LightTile()
        self.esp32_tile = ESP32Tile()
        self.rtc_tile = RTCTile()
        self.tapo_tile = TapoTile()
        self.humidifier_tile = HumidifierTile()

        # Ändere das hier in Zeile 112:
        self.sht31_internal_tile = SensorInternalSHT31Tile(
            device_id="internal",     # ID des Geräts
            channel="ch1",            # Kanal/Channel
            tile_id="temp_in"         # Start-Tile ID aus deiner 'available_tiles' Liste
            
        )
        self.sht31_external_tile = SensorExternalSHT31Tile(
            device_id="external",
            channel="ch1",
            tile_id="temp_ex"
        )
        
        self.ble_inside_tile = SensorBLE_InsideTile(
            device_id="ble_inside",
            channel="ch1",
            tile_id="ble_temp_inside"
        )
        
        self.ble_outside_tile = SensorBLEOutsideTile(
            device_id="ble_outside",
            channel="ch1",
            tile_id="ble_temp_outside"
        )
        
        self.mlx90614_tile = SensorExternalMLX90614Tile(
            device_id="mlx90614",
            channel="ch1",
            tile_id="leaf_temp"
        )
        
        self.scd41_tile = SensorSCD41Tile()
        # ---------------- SENSOR SIZE SETTINGS ----------------
        self.sht31_internal_tile.size_hint_y = None
        self.sht31_internal_tile.height = dp_scaled(140)
        self.sht31_internal_tile.size_hint_x = 1
        
        self.sht31_external_tile.size_hint_y = None
        self.sht31_external_tile.height = dp_scaled(140)
        self.sht31_external_tile.size_hint_x = 1
        
        self.ble_inside_tile.size_hint_y = None
        self.ble_inside_tile.height = dp_scaled(140)
        self.ble_inside_tile.size_hint_x = 1
        
        self.ble_outside_tile.size_hint_y = None
        self.ble_outside_tile.height = dp_scaled(140)
        self.ble_outside_tile.size_hint_x = 1
        
        self.mlx90614_tile.size_hint_y = None
        self.mlx90614_tile.height = dp_scaled(110)
        self.mlx90614_tile.size_hint_x = 1

        self.scd41_tile.size_hint_y = None
        self.scd41_tile.height = dp_scaled(140)
        self.scd41_tile.size_hint_x = 1

        # their value box.
        self.exhaust_tile.size_hint_y = None
        self.exhaust_tile.height = dp_scaled(170)
        self.exhaust_tile.size_hint_x = 1

        self.humidifier_tile.size_hint_y = None
        self.humidifier_tile.height = dp_scaled(130)
        self.humidifier_tile.size_hint_x = 1

        self.circ_tile.size_hint_y = None
        self.circ_tile.height = dp_scaled(130)
        self.circ_tile.size_hint_x = 1

        self.light_tile.size_hint_y = None
        self.light_tile.height = dp_scaled(170)
        self.light_tile.size_hint_x = 1

        self.rtc_tile.size_hint_y = None
        self.rtc_tile.height = dp_scaled(130)
        self.rtc_tile.size_hint_x = 1
        
        self.tapo_tile.size_hint_y = None
        self.tapo_tile.height = dp_scaled(130)
        self.tapo_tile.size_hint_x = 1
        
        self.esp32_tile.size_hint_y = None
        self.esp32_tile.height = dp_scaled(600)  # Adjusted height to fit the content of the ESP32 tile
        self.esp32_tile.size_hint_x = 1

        # Place tiles into appropriate columns
        # Column 1: main panel / device overview
        col1_inner.add_widget(self.esp32_tile)
        col1_inner.add_widget(self.rtc_tile)
        col1_inner.add_widget(self.tapo_tile)

        # Column 2: sensors (currently empty by default)
        col2_inner.add_widget(self.sht31_internal_tile) # <--- DAS HAT GEFEHLT!
        col2_inner.add_widget(self.sht31_external_tile) # <--- DAS HAT GEFEHLT!
        col2_inner.add_widget(self.ble_inside_tile)
        col2_inner.add_widget(self.ble_outside_tile)
        col2_inner.add_widget(self.mlx90614_tile)          # ← NEU HIER
        col2_inner.add_widget(self.scd41_tile)            # ← NEU HIER
        # Column 3: actuators
        col3_inner.add_widget(self.light_tile)
        col3_inner.add_widget(self.circ_tile)
        col3_inner.add_widget(self.exhaust_tile)
        col3_inner.add_widget(self.humidifier_tile)
        # Add columns to content
        self.content.add_widget(col1)
        self.content.add_widget(col2)
        self.content.add_widget(col3)

        root.add_widget(self.content)
        self.add_widget(root)

    # ---------------- UPDATE ----------------
    # ---------------- UPDATE ----------------
    def update_from_global(self, d):
        self.header.update_from_global(d)

        mac = GLOBAL_STATE.get_active_device_id()
        
        # 1. Hol die echten Daten aus der Engine
        server_data = GLOBAL_STATE.overlay_engine.get_buffer_data(mac) if mac else None

        # 2. FALLBACK: Wenn keine Daten da sind (weil Gerät gelöscht oder Offline)
        if not server_data:
            # Wir nehmen das erste Element deines perfekten Null-Skeletts!
            server_data = {
                "exhaust_fan": {"exhaust_fan_rpm": 0},
                "exhaust_fan_speed_now": 0,
                "exhaust_fan_state_reason_1": "OFFLINE",
                "exhaust_fan_state_reason_2": "NO DEVICE",
                "circulation_fan": {"circulation_fan_rpm": 0},
                # Falls andere Tiles meckern, hier einfach erweitern
            }
            prefix_string = ""
        else:
            active_channel = GLOBAL_STATE.get_active_channel()
            prefix_string = f"{mac}_{active_channel}"

        # 3. JETZT ERST DIE TILES BESCHICKEN (Läuft somit IMMER durch!)
        self.exhaust_tile.update_values(server_data)
        self.circ_tile.update_values(server_data)
        self.light_tile.update_values(server_data)
        self.esp32_tile.update_values(server_data)
        self.humidifier_tile.update_values(server_data)
        
        self.sht31_internal_tile.update_values(server_data, prefix=prefix_string)
        self.sht31_external_tile.update_values(server_data, prefix=prefix_string)
        self.ble_inside_tile.update_values(server_data, prefix=prefix_string)
        self.ble_outside_tile.update_values(server_data, prefix=prefix_string)
        self.mlx90614_tile.update_values(server_data, prefix=prefix_string)
        self.rtc_tile.update_values(server_data)
        self.scd41_tile.update_values(server_data, prefix=prefix_string)
        self.tapo_tile.update_values(server_data)