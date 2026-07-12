# network/client_storage.py
import os
import json
import config

PATH_WEB_DUMP = os.path.join(config.DATA, "web_dump.json")
PATH_PLANTS_STORE = os.path.join(config.DATA, "plants_store.json")
PATH_SETTINGS_SYNC = os.path.join(config.DATA, "settings_sync.json")

def load_plants_at_boot():
    """Lädt die lokalen Pflanzen-Daten beim Booten in den RAM-Cache."""
    cache = {}
    revs = {}
    if os.path.exists(PATH_PLANTS_STORE):
        try:
            with open(PATH_PLANTS_STORE, "r", encoding="utf-8") as f:
                cache = json.load(f)
                for mac, content in cache.items():
                    if "plant_planner" in content:
                        revs[mac] = content["plant_planner"].get("rev_plant_planner", 0)
            print("[Storage] RAM-Cache für Pflanzen erfolgreich geladen.")
        except Exception as e:
            print(f"[Storage] Boot-Load Fehler: {e}")
    return cache, revs

def save_web_dump(current_data):
    """Speichert die aktuellen Live-Daten atomar auf die Festplatte."""
    tmp_path = PATH_WEB_DUMP + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(current_data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, PATH_WEB_DUMP)
    except Exception as e:
        print(f"[Storage] Fehler beim Schreiben des Web-Dumps: {e}")

def save_heavy_plant_data(mac, plant_payload, local_plants_cache):
    """Speichert empfangene Heavy-Plant-Daten ab."""
    local_plants_cache[mac] = plant_payload
    tmp_path = PATH_PLANTS_STORE + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(local_plants_cache, f, indent=2)
        os.replace(tmp_path, PATH_PLANTS_STORE)
    except Exception as e:
        print(f"[Storage] Fehler beim Speichern der Heavy-Plant-Daten für {mac}: {e}")

def save_settings_rev(mac, rev):
    """Speichert eine neue Revisionsnummer in die settings_sync.json."""
    try:
        data = {}
        if os.path.exists(PATH_SETTINGS_SYNC):
            with open(PATH_SETTINGS_SYNC, "r") as f:
                data = json.load(f)
        
        data[mac] = data.get(mac, {})
        data[mac]["rev"] = int(rev)

        with open(PATH_SETTINGS_SYNC, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[Storage] Fehler beim Speichern der Settings-Rev für {mac}: {e}")

def get_local_settings_rev(mac):
    """Liest die lokale Revisionsnummer für den Abgleich aus."""
    if not os.path.exists(PATH_SETTINGS_SYNC):
        return 0
    try:
        with open(PATH_SETTINGS_SYNC, "r") as f:
            return json.load(f).get(mac, {}).get("rev", 0)
    except:
        return 0