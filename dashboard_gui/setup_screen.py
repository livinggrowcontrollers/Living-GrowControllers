import os
import json
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
import config
import core
from dashboard_gui.ui.setup_content.setup_main_panel import SetupMainPanel
from dashboard_gui.ui.common.header_online import HeaderBar
from dashboard_gui.global_state_manager import GLOBAL_STATE

_selected = {}      # mac -> { "adv": str, "gatt": str, "bridge": str }
_device_names = {}  # mac -> display name

def _raw_path():
    return os.path.join(config.DATA, "ble_dump.json")

class SetupScreen(Screen):

    def __init__(self, **kw):
        super().__init__(**kw)

        from dashboard_gui.global_state_manager import GLOBAL_STATE
        GLOBAL_STATE.ui_handler.attach_screen("setup", self)

        root = BoxLayout(orientation="vertical", spacing=0, padding=0)
        self.add_widget(root)

        self.header = HeaderBar()
        root.add_widget(self.header)

        content_box = BoxLayout(orientation="vertical", spacing=10, padding=10)        

        self.panel = SetupMainPanel(
            on_refresh=self.update_devices,
            on_save=self._save,
            on_back=self._back,
            on_profile_change=self._set_profile,
            on_device_toggle=self._toggle_device,
            on_adv=self.set_adv,
            on_gatt=self.set_gatt,
            on_bridge=self.set_bridge,
            on_restart_bridge=self._restart_bridge,
            on_restart_adv=self._restart_adv,
            on_restart_gatt=self._restart_gatt,
        )
        content_box.add_widget(self.panel)
        root.add_widget(content_box)

    def on_pre_enter(self, *_):

        Clock.schedule_once(self.update_devices, 0)

        Clock.schedule_once(
            lambda dt: self._restart_adv(),
            0.1
        )
    def _restart_adv(self, *_):
        try:
            import core
            core.restart_adv_bridge()
            print("[Setup] ADV Bridge neu gestartet")
        except Exception as e:
            print("[Setup] ADV restart FEHLER:", e)
    
    def _restart_gatt(self, *_):
        try:
            import core
            core.restart_gatt_bridge()
            print("[Setup] GATT Bridge neu gestartet")
        except Exception as e:
            print("[Setup] GATT restart FEHLER:", e)

    def _restart_bridge(self, *_):
        try:
            from bridge_manager import get_bridge
            bridge = get_bridge()
            bridge.stop()
            bridge.start()
            print("[Setup] ADV + GATT Bridges neu gestartet (Bridge-only)")
        except Exception as e:
            print("[Setup] Bridge-only Restart FEHLER:", e)

    def update_devices(self, *_):
        self.panel.clear_devices()
        path = _raw_path()
        if not os.path.exists(path):
            print("[Setup] dump fehlt")
            return
    
        try:
            with open(path, "r", encoding="utf-8") as f:
                arr = json.load(f)
        except Exception:
            print("[Setup] JSON Fehler")
            return
    
        is_dev = config.is_developer_mode()

        for e in arr:
            mac = e.get("address")
            raw = e.get("adv_raw") or e.get("gatt_raw") or e.get("log_raw")
            name = e.get("name") or mac
    
            if not mac or not raw:
                continue
    
            _device_names[mac] = name
    
            # -------------------------------
            # NON-DEVELOPER MODE
            # -------------------------------
            if not is_dev:
                lname = name.lower()
                if not (
                    "sps" in lname
                    or "thermobeacon" in lname
                    or "tp35" in lname
                    or "thermopro" in lname
                    or "growmaster" in lname
                    or "lgs_node" in lname
                ):
                    continue
    
                sel = _selected.get(mac, {
                    "adv": config.get_adv_decoder(mac),
                    "gatt": config.get_gatt_decoder(mac),
                    "bridge": config.get_bridge_profile(mac)
                })
                _selected[mac] = sel
    
                # 🛠️ Übergibt dev_mode=False -> Keine Spinner sichtbar

                self.panel.add_device(
                    name=name,
                    mac=mac,
                    adv=sel.get("adv"),
                    gatt=sel.get("gatt"),
                    bridge=sel.get("bridge"),
                    selected=True,
                    dev_mode=False,
                    image_file=self._get_image_for_device(name)
                )

            # -------------------------------
            # DEVELOPER MODE
            # -------------------------------
            else:
                if mac not in _selected:
                    lname = name.lower()
                    if "sps" in lname:
                        _selected[mac] = {"adv": "Inkbird_ADV_Desktop", "gatt": "Inkbird_GATT", "bridge": "Inkbird_Bridge"}
                    elif "thermobeacon" in lname:
                        _selected[mac] = {"adv": "ThermoBeacon2_ADV", "gatt": "ThermoBeacon2_GATT", "bridge": "ThermoBeacon2_Bridge"}
                    elif "tp35" in lname or "thermopro" in lname:
                        _selected[mac] = {"gatt": "ThermoPro_GATT", "bridge": "ThermoPro_Bridge"}
                    elif "growmaster" in lname:
                        _selected[mac] = {"adv": "LGS_SENSOR", "gatt": "", "bridge": ""}   
                    elif "lgs_node" in lname:
                        _selected[mac] = {"adv": "LGS_ADV", "gatt": "", "bridge": ""}
                    else:
                        _selected[mac] = {"adv": "", "gatt": "", "bridge": ""}
            
                sel = _selected[mac]
            
                # 🛠️ Übergibt dev_mode=True -> Spinner sind voll da
                self.panel.add_device(
                    name=name,
                    mac=mac,
                    adv=sel.get("adv"),
                    gatt=sel.get("gatt"),
                    bridge=sel.get("bridge"),
                    selected=True,
                    dev_mode=True,
                    image_file=self._get_image_for_device(name)
                )

    def _set_profile(self, mac, prof):
        _selected[mac] = {"profile": prof}


    def _get_image_for_device(self, name):
        lname = (name or "").lower()

        if "sps" in lname:
            return "inkbird.png"
        elif "thermobeacon" in lname:
            return "thermobeacon.png"
        elif "tp35" in lname or "thermopro" in lname:
            return "thermopro.png"
        elif "growmaster" in lname:
            return "esp32_s3.png"
        elif "lgs_node" in lname:
            return "unknown_device.png"
        else:
            return "unknown_device.png"

    def _save(self, *_):
        cfg = config._init()
        devices = {}

        for mac, sel in _selected.items():
            discovered_name = _device_names.get(mac, mac)
            existing_device = cfg.get("devices", {}).get(mac, {})
            # Discovery supplies the physical name.  A user-selected display
            # name must survive subsequent setup saves unchanged.
            name = existing_device.get("name") or discovered_name
            device_id = existing_device.get("device_id", "")
            img_file = ""
            
            # Standard-Felder vorbereiten
            auto_ip = None
            auto_hostname = ""
            is_growmaster = False

            # --------------------------------------------------------
            # 💥 DIE AUTOMATISCHE GROWMASTER-REGELUNG
            # --------------------------------------------------------
            lname = discovered_name.lower()
            if "growmaster" in lname:
                is_growmaster = True
                img_file = "esp32_s3.png"
                if not device_id:
                    device_id = discovered_name.strip()
                
                # Prüfen, ob wir im AP-Modus (-0000) sind
                if "-0000" in lname:
                    auto_ip = "192.168.4.1"
                    auto_hostname = "growmaster-0000"
                    print(f"[Setup] Growmaster im AP-Modus erkannt! IP: {auto_ip}")
                else:
                    # Router-Modus: Suffix nutzen, IP muss WEG!
                    # The hostname is a technical discovery value.  It must
                    # never be rebuilt from the user-editable display name.
                    auto_hostname = discovered_name.strip()
                    auto_ip = ""  # Explizit leeren String erzwingen!
                    print(f"[Setup] Growmaster im Router-Modus erkannt! IP wird zurückgesetzt.")

            # Non-Developer Standard-Decoder Profile zuweisen
            if not config.is_developer_mode():
                if "sps" in lname:
                    sel = {"adv": "Inkbird_ADV_Desktop", "gatt": "Inkbird_GATT", "bridge": "Inkbird_Bridge"}
                    img_file = "inkbird.png"
                elif "thermobeacon" in lname:
                    sel = {"adv": "ThermoBeacon2_ADV", "gatt": "ThermoBeacon2_GATT", "bridge": "ThermoBeacon2_Bridge"}
                    img_file = "thermobeacon.png"
                elif "tp35" in lname or "thermopro" in lname:
                    sel = {"gatt": "ThermoPro_GATT", "bridge": "ThermoPro_Bridge"}
                    img_file = "thermopro.png"
                elif "growmaster" in lname:
                    sel = {"adv": "LGS_SENSOR", "gatt": "", "bridge": ""}   
                    img_file = "esp32_s3.png"
                elif "lgs_node" in lname:
                    sel = {"adv": "LGS_ADV", "gatt": "", "bridge": ""}
                    img_file = "unknown_device.png"
                else:
                    img_file = "unknown_device.png"
                    continue
                _selected[mac] = sel
            else:
                # Bild-Fallback für den Dev-Mode
                if "sps" in lname: img_file = "inkbird.png"
                elif "thermobeacon" in lname: img_file = "thermobeacon.png"
                elif "tp35" in lname or "thermopro" in lname: img_file = "thermopro.png"
                elif "growmaster" in lname: img_file = "esp32_s3.png"
                elif "lgs_node" in lname: img_file = "unknown_device.png"
                else: img_file = "unknown_device.png"
            adv = sel.get("adv", "")
            gatt = sel.get("gatt", "")
            bridge = sel.get("bridge", "")

            if any([adv, gatt, bridge]):
                devices[mac] = {
                    "device_id": device_id,
                    "name": name,
                    "adv_decoder": adv,
                    "gatt_decoder": gatt,
                    "bridge_profile": bridge,
                    "image_file": img_file
                }
                
                if auto_hostname:
                    devices[mac]["hostname"] = auto_hostname
                
                if is_growmaster:
                    devices[mac]["ip_address"] = auto_ip

        if not devices:
            print("[Setup] Kein Device zum Speichern")
            return

        if "devices" not in cfg or not isinstance(cfg["devices"], dict):
            cfg["devices"] = {}

        # --------------------------------------------------------
        # 👑 DER SORTIER-PRIORITÄTS-TRAUM (Growmaster nach ganz oben)
        # --------------------------------------------------------
        sorted_devices = {}

        # Schritt 1: Erstmal alle neuen/aktualisierten Growmaster ganz oben einfügen
        for mac, dev in devices.items():
            if config.is_growmaster_device(dev):
                sorted_devices[mac] = dev

        # Schritt 2: Bestehende Growmaster aus der alten Config retten, falls nicht in den neuen
        for mac, old_dev in cfg["devices"].items():
            if config.is_growmaster_device(old_dev) and mac not in sorted_devices:
                sorted_devices[mac] = old_dev

        # Schritt 3: Alle anderen neuen Geräte (Inkbird, Thermopro, etc.) anhängen
        for mac, dev in devices.items():
            if mac not in sorted_devices:
                sorted_devices[mac] = dev

        # Schritt 4: Alle restlichen alten Geräte aus der Config anhängen
        for mac, old_dev in cfg["devices"].items():
            if mac not in sorted_devices:
                sorted_devices[mac] = old_dev

        # Jetzt das saubere, sortierte Wörterbuch zurück in die Config schreiben
        cfg["devices"] = sorted_devices

        # Daten-Updates und IP-Bereinigungen auf der finalen Struktur durchführen
        for mac, dev in devices.items():
            old_dev = cfg["devices"].get(mac, {})
            if old_dev.get("protected", False):
                continue
            
            if "ip_address" in dev:
                cfg["devices"][mac]["ip_address"] = dev["ip_address"]
                if dev["ip_address"] == "":
                    cfg["devices"][mac].pop("ip_address", None)

            cfg["devices"][mac].update(dev)

            if "auth" not in cfg["devices"][mac]:
                cfg["devices"][mac]["auth"] = {"user": "admin", "pass": "1234"}

        config.save(cfg)

        config.reload()
        print("[Setup] Config mit Growmaster-Priorität oben gespeichert!")

        GLOBAL_STATE.ui_handler.go_back()

    def _back(self, *_):
        from dashboard_gui.global_state_manager import GLOBAL_STATE
        GLOBAL_STATE.ui_handler.go_back()

    def set_adv(self, mac, val):
        if val == "---": _selected.setdefault(mac, {}).pop("adv", None)
        else: _selected.setdefault(mac, {})["adv"] = val

    def set_gatt(self, mac, val):
        if val == "---": _selected.setdefault(mac, {}).pop("gatt", None)
        else: _selected.setdefault(mac, {})["gatt"] = val

    def set_bridge(self, mac, val):
        if val == "---": _selected.setdefault(mac, {}).pop("bridge", None)
        else: _selected.setdefault(mac, {})["bridge"] = val

    def _toggle_device(self, mac, is_selected):
        if is_selected:
            _selected.setdefault(mac, {})["adv"] = config.get_adv_decoder(mac)
            _selected[mac]["gatt"] = config.get_gatt_decoder(mac)
            _selected[mac]["bridge"] = config.get_bridge_profile(mac)
        else:
            _selected.pop(mac, None)

    def update_from_global(self, d):
        self.header.update_from_global(d)
        self.header._last_frame = d
