# dashboard_gui/data_buffer.py
import os
import json
import time
import decoder  # <- wichtig
import config   # 💥 DAS IST DER FIX
class DataBuffer:
    def __init__(self):
        self.path = os.path.join("data", "decoded.json")
        # 💥 Sicherstellen, dass der "data" Ordner wirklich existiert
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        # Wir behalten 'self.data', damit kein AttributeError kommt
        self.data = [] 

        self.file_exists = False
        self.data_ok = False
        self.alive_flag = False

    def load(self):
        # 🔥 1. CONFIG CHECK (NEU, KRITISCH)
        cfg = config._init()
        devices = cfg.get("devices", {}) if cfg else {}

        # 💥 HARD RESET RULE: keine Devices = kein RAM, kein gar nichts
        if not devices:
            self.data = []
            self.data_ok = False
            self.alive_flag = False
            return self.data

        # 🔥 2. RAM FIRST
        ram_data = decoder.get_decoded_ram()

        if ram_data:
            # 💥 FILTER GHOST DEVICES OUT
            self.data = [
                d for d in ram_data
                if d.get("device_id") in devices
            ]

            self.data_ok = True

            if len(self.data) > 0:
                self.alive_flag = bool(self.data[0].get("alive", False))
            else:
                self.alive_flag = False

            return self.data

        # 🔥 3. FALLBACK NUR BEIM START
        self.file_exists = os.path.exists(self.path)

        if not self.file_exists:
            self.data = []
            return self.data

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                new_content = json.load(f)

            if isinstance(new_content, list):
                self.data = [
                    d for d in new_content
                    if d.get("device_id") in devices
                ]
                self.data_ok = True
            else:
                self.data = []
                self.data_ok = False

        except:
            self.data = []
            self.data_ok = False

        return self.data

    def get(self):
        return self.data

    def soft_reload(self):
        return self.load()

    def clear(self):
        self.data = []
        self.data_ok = False
        self.alive_flag = False
        if os.path.exists(self.path):
            try:
                with open(self.path, "w") as f:
                    f.write("[]") 
            except:
                pass

# global Singleton
BUFFER = DataBuffer()