import ipywidgets as widgets
from IPython.display import display, Javascript
import os

file_content = """
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# gatt_ui.py – Monolithische Desktop-GATT-Bridge (UI + Engine)
# - Liest einmal data/ble_dump.json (ADV)
# - Spinner: Device wählen (Name [Address])
# - Spinner: Bridge-Profil (aus data/bridge_profiles)
# - Speichert gatt_config.json (lokal im gatt_bridge-Ordner)
# - Start/Stop steuert interne GattEngine
#
# WICHTIG:
#  - ble_dump.json bleibt bestehen
#  - GATT-Bridge schreibt NUR "gatt_raw" für das gewählte Device
#  - adv_raw / log_raw / andere Devices bleiben unberührt

import os
import json
import asyncio
from datetime import datetime, timezone
from threading import Thread

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.clock import Clock

from bleak import BleakScanner, BleakClient

# ---------------------------------------------------------
# Pfade / Projektstruktur
# ---------------------------------------------------------

# gatt_bridge Ordner
# In Colab, __file__ is not defined. Use os.getcwd() as a workaround.
BRIDGE_DIR = os.getcwd()

# Projekt-Root: eine Ebene über blebridge_desktop/
PROJECT_ROOT = os.path.abspath(os.path.join(BRIDGE_DIR, "..", ".."))

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
OUTFILE = os.path.join(DATA_DIR, "ble_dump.json")

# Bridge-Profile: data/bridge_profiles
PROFILE_DIR = os.path.join(DATA_DIR, "bridge_profiles")

# GATT-Konfig (lokal für die Desktop-Bridge)
CONFIG_PATH = os.path.join(BRIDGE_DIR, "gatt_config.json")


# ---------------------------------------------------------
# Helper
# ---------------------------------------------------------

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _safe_load_dump():
    """




def _safe_write_dump(devices: dict):
    tmp = OUTFILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(list(devices.values()), f, indent=2, ensure_ascii=False)
    os.replace(tmp, OUTFILE)


# ---------------------------------------------------------
# GATT ENGINE (Monolithisch)
# ---------------------------------------------------------

class GattEngine:
    """
    Desktop-GATT-Engine:
      - liest gatt_config.json
      - lädt bridge_profile (UUIDs, Command)
      - scannt nach Geräten (Name-Match)
      - verbindet, hört Notify
      - schreibt GATT-RAW in ble_dump.json[device]["gatt_raw"]
    """

    def __init__(self):
        self.running = False
        self.thread: Thread | None = None
        self.log_cb = None
        self.packet_counter = {}  # key: address → int
    # -----------------------------------------------------
    # Public API
    # -----------------------------------------------------
    def start(self, log_cb):
        """
        Startet Engine (asynchron in eigenem Thread).
        """
        self.log_cb = log_cb

        if self.running:
            self._log("[ENGINE] Bereits aktiv.")
            return

        self.running = True
        self.thread = Thread(target=self._run_thread, daemon=True)
        self.thread.start()

    def stop(self):
        """
        Stop-Signal setzen, Loop in _run_async beendet sich.
        """
        if not self.running:
            self._log("[ENGINE] War nicht aktiv.")
            return
        self._log("[ENGINE] Stop gesetzt.")
        self.running = False

    # -----------------------------------------------------
    # Intern
    # -----------------------------------------------------
    def _log(self, msg: str):
        if self.log_cb:
            self.log_cb(msg)

    def _run_thread(self):
        try:
            asyncio.run(self._run_async())
        except Exception as e:
            self._log(f"[ENGINE] Fehler: {e!r}")
        finally:
            self.running = False

    async def _run_async(self):
        # -------------------------------
        # CONFIG LADEN (gatt_config.json)
        # -------------------------------
        if not os.path.exists(CONFIG_PATH):
            self._log("[ENGINE] gatt_config.json fehlt.")
            return

        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            self._log(f"[ENGINE] Fehler beim Lesen von gatt_config.json: {e!r}")
            return

        devices_cfg = cfg.get("devices", [])
        if not devices_cfg:
            self._log("[ENGINE] Keine Devices in gatt_config.json.")
            return

        # Aktuell ein Zielgerät
        target = devices_cfg[0]
        target_name = (target.get("name") or "").strip()
        profile_name = (target.get("profile") or "").strip()

        if not target_name or not profile_name:
            self._log("[ENGINE] Config unvollständig (name/profile fehlt).")
            return

        self._log(f"[ENGINE] Zielgerät: '{target_name}' mit Profil '{profile_name}'")

        # -------------------------------
        # BRIDGE-PROFIL LADEN
        # -------------------------------
        prof_path = os.path.join(PROFILE_DIR, f"{profile_name}.json")
        if not os.path.exists(prof_path):
            self._log(f"[ENGINE] Bridge-Profil nicht gefunden: {prof_path}")
            return

        try:
            with open(prof_path, "r", encoding="utf-8") as f:
                profile = json.load(f)
        except Exception as e:
            self._log(f"[ENGINE] Fehler beim Laden Bridge-Profil: {e!r}")
            return

        # --- Bridge Profile Data ---
        notify_uuid = profile.get("notify_uuid") # UUID for data characteristic (can be notified or polled)
        cmd_uuid = profile.get("command_uuid")
        cmd_hex = profile.get("command")

        read_mode = profile.get("read_mode", "notify") # Default to notify
        read_interval_ms = profile.get("read_interval_ms", 1500) # Default for poll
        notify_active = profile.get("notify", True) # Explicitly allow disabling notify

        # Use notify_uuid as the data_char_uuid, assuming it's the characteristic for data.
        data_char_uuid = notify_uuid

        self._log(f"[ENGINE] Datencharakteristik UUID: {data_char_uuid}")
        self._log(f"[ENGINE] Datenakquise: {'Notify' if notify_active and data_char_uuid else 'Poll' if read_mode == 'poll' and data_char_uuid else 'None'}")
        if read_mode == "poll":
            self._log(f"[ENGINE] Poll Intervall: {read_interval_ms}ms")

        # convert_to_adv ignorieren – wir fahren nur ORIG-VENDOR-RAW
        cmd_bytes = None
        if cmd_hex:
            try:
                cmd_bytes = bytes.fromhex(cmd_hex)
            except Exception as e:
                self._log(f"[ENGINE] WARN: Ungültiger Command-HEX: {e!r}")
                cmd_bytes = None

        # -------------------------------
        # SCAN: Name-Matching
        # -------------------------------
        self._log("[ENGINE] Scanne 10 Sekunden nach passendem Gerät…")
        target_name_l = target_name.lower()
        matched_dev = None

        try:
            scan_list = await BleakScanner.discover(timeout=10.0)
        except Exception as e:
            self._log(f"[ENGINE] Scan-Fehler: {e!r}")
            return

        for dev in scan_list:
            dname_l = (dev.name or "").lower()

            # 1) Exakter Name
            if dname_l == target_name_l:
                matched_dev = dev
                break

            # 2) Substring
            if target_name_l in dname_l:
                matched_dev = dev
                break

        if not matched_dev:
            self._log("[ENGINE] KEIN passendes Gerät im Scan gefunden.")
            return

        self._log(f"[ENGINE] Gerät gefunden: {matched_dev.address} ({matched_dev.name})")

        # -------------------------------
        # VERBINDUNG & DATENAKQUISE
        # -------------------------------
        try:
            async with BleakClient(matched_dev) as client:
                self._log("[ENGINE] Verbunden ✔")

                # Unified handler for incoming GATT data (from notify or read)
                async def _handle_gatt_data(_, data: bytearray):
                    raw = data.hex().upper()
                    addr_key = matched_dev.address

                    # ANDROID-LIKE PACKET COUNTER (pro Device / GATT)
                    cnt = self.packet_counter.get(addr_key, 0) + 1
                    self.packet_counter[addr_key] = cnt

                    devices = _safe_load_dump()
                    dev_entry = devices.get(addr_key, {
                        "timestamp": now_iso(),
                        "name": matched_dev.name or target_name,
                        "address": addr_key,
                        "rssi": 0,
                        "adv_raw": "",
                        "gatt_raw": None,
                        "packet_counter": 0,
                        "log_raw": "",
                    })
                    dev_entry["timestamp"] = now_iso()
                    dev_entry["gatt_raw"] = raw
                    dev_entry["packet_counter"] = cnt
                    devices[addr_key] = dev_entry

                    try:
                        _safe_write_dump(devices)
                        self._log(f"[RAW] {raw}  packet_counter={cnt}")
                    except Exception as e:
                        self._log(f"[ENGINE] Write-Fehler: {e!r}")

                # Conditionally start notify or prepare for polling
                if notify_active and data_char_uuid:
                    self._log(f"[ENGINE] Aktiviere Notifications auf {data_char_uuid}")
                    await client.start_notify(data_char_uuid, _handle_gatt_data)
                elif read_mode == "poll" and data_char_uuid:
                    self._log(f"[ENGINE] Poll Read für {data_char_uuid} wird gestartet.")
                else:
                    self._log("[ENGINE] KEINE Datenakquise (Notify oder Poll) konfiguriert für dieses Profil.")

                # Initialer Command (EINMAL)
                if cmd_uuid and cmd_bytes:
                    try:
                        await client.write_gatt_char(cmd_uuid, cmd_bytes)
                        self._log("[ENGINE] Initialer Command gesendet.")
                    except Exception as e:
                        self._log(f"[ENGINE] Initialer Command-Fehler: {e!r}")

                self._log("[ENGINE] Lausche auf Daten & Commands…")

                poll_tick_counter = 0 # Universal tick counter
                # Calculate how many 0.2s ticks make up the poll interval
                # Only if read_mode is poll, otherwise set to -1 to disable timed polling
                poll_interval_ticks = max(1, int(read_interval_ms / 200)) if read_mode == "poll" else -1

                while self.running:
                    await asyncio.sleep(0.2) # Base sleep for loop iteration
                    poll_tick_counter += 1

                    # Send command periodically (e.g., every 5 ticks = 1 second)
                    if cmd_uuid and cmd_bytes and poll_tick_counter % 5 == 0:
                        try:
                            await client.write_gatt_char(cmd_uuid, cmd_bytes)
                        except Exception as e:
                            self._log(f"[ENGINE] Fehler beim Senden periodischer Commands: {e!r}")

                    # Perform poll read if configured and it's time
                    if read_mode == "poll" and data_char_uuid and poll_interval_ticks > 0 and poll_tick_counter % poll_interval_ticks == 0:
                        try:
                            # Use read_gatt_char to get data
                            data = await client.read_gatt_char(data_char_uuid)
                            await _handle_gatt_data(None, data) # Call unified handler, first arg (sender) is None for poll read
                        except Exception as e:
                            self._log(f"[ENGINE] Fehler beim Poll Read von {data_char_uuid}: {e!r}")

                # Cleanup
                if notify_active and data_char_uuid: # Only stop notify if it was started
                    self._log("[ENGINE] Stop – Notify aus.")
                    try:
                        await client.stop_notify(data_char_uuid)
                    except Exception: # Ignore if already stopped or failed to start
                        pass
        except Exception as e:
            self._log(f"[ENGINE] Verbindungsfehler: {e!r}")
# ---------------------------------------------------------
# UI – Kivy
# ---------------------------------------------------------

def load_profiles():
    """Lädt alle Bridge-Profilnamen aus data/bridge_profiles."""
    if not os.path.isdir(PROFILE_DIR):
        return ()
    return tuple(
        sorted(
            fn[:-5]
            for fn in os.listdir(PROFILE_DIR)
            if fn.endswith(".json")
        )
    )


def load_devices_from_dump():
    """
    Reads data/ble_dump.json once.
    Expects the new dict format (or converts the old list format).
    Returns a list of (label, address, name).
    """
    devices = _safe_load_dump()
    result = []

    for addr, entry in devices.items():
        name = entry.get("name") or "(unknown)"
        label = f"{name} [{addr}]"
        result.append((label, addr, name))

    # sortiert nach Label
    result.sort(key=lambda x: x[0])
    return result


class GattUI(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)

        self.engine = GattEngine()

        # --- Devices aus Dump laden ---
        self.device_entries = load_devices_from_dump()
        device_labels = tuple(label for (label, _, _) in self.device_entries)

        # --- Device-Spinner ---
        self.dev_spinner = Spinner(
            text="Device wählen",
            values=device_labels,
            size_hint=(1, 0.1),
        )
        self.add_widget(self.dev_spinner)

        # --- Profil-Spinner ---
        self.prof_spinner = Spinner(
            text="Profil wählen",
            values=load_profiles(),
            size_hint=(1, 0.1),
        )
        self.add_widget(self.prof_spinner)

        # --- Buttons ---
        btns = BoxLayout(size_hint=(1, 0.15))

        self.save_btn = Button(text="Config speichern")
        self.save_btn.bind(on_press=self.on_save)
        btns.add_widget(self.save_btn)

        self.start_btn = Button(text="START")
        self.start_btn.bind(on_press=self.on_start)
        btns.add_widget(self.start_btn)

        self.stop_btn = Button(text="STOP")
        self.stop_btn.bind(on_press=self.on_stop)
        btns.add_widget(self.stop_btn)

        self.add_widget(btns)

        # --- Log ---
        self.log_box = TextInput(
            readonly=True,
            size_hint=(1, 0.65),
        )
        self.add_widget(self.log_box)

        self.log("[UI] BLE-Dump einmalig gelesen.")
        if not self.device_entries:
            self.log("[UI] Keine Devices im Dump gefunden.")
        else:
            self.log(f"[UI] {len(self.device_entries)} Devices im Dump gefunden.")

    # --------------------------
    # Hilfsfunktionen
    # --------------------------
    def log(self, msg: str):
        Clock.schedule_once(lambda dt: self._append(msg))

    def _append(self, msg: str):
        self.log_box.text += msg + "\n"
        self.log_box.cursor = (0, len(self.log_box.text))

    def _get_selected_device(self):
        label = self.dev_spinner.text
        for lab, addr, name in self.device_entries:
            if lab == label:
                return addr, name
        return None, None

    # --------------------------
    # Actions
    # --------------------------
    def on_save(self, *_):
        addr, name = self._get_selected_device()
        prof = self.prof_spinner.text.strip()

        if not addr:
            self.log("[UI] Kein Device gewählt.")
            return
        if not prof or prof == "Profil wählen":
            self.log("[UI] Kein Profil gewählt.")
            return

        cfg = {
            "devices": [
                {
                    "address": addr,
                    "name": name,
                    "profile": prof,
                }
            ]
        }

        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            self.log(f"[UI] gatt_config.json gespeichert für {name} [{addr}] mit Profil '{prof}'.")
        except Exception as e:
            self.log(f"[UI] Fehler beim Schreiben von gatt_config.json: {e!r}")

    def on_start(self, *_):
        self.log("[UI] Starte GATT-Engine…")
        self.engine.start(self.log)

    def on_stop(self, *_):
        self.log("[UI] Stop angefordert.")
        self.engine.stop()


class GattUIApp(App):
    def build(self):
        return GattUI()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.kv_directory = None # Explicitly set kv_directory to None


if __name__ == "__main__":
    GattUIApp().run()

