# network_worker.py
import requests
import config
import network.client_storage
def fetch_single_device(mac, dev_cfg, targets, registry, local_plants_cache, local_plant_revs):
    """
    Führt den HTTP-Request für ein einzelnes Gerät aus.
    Gibt (mac, payload, is_ap) zurück oder (mac, None, False) im Fehlerfall.
    """
    if not targets:
        return mac, None, False

    user, pw = config.get_device_auth(mac)

    for base_url in targets:
        is_ap = "192.168.4." in base_url
        current_timeout = 6.0 if is_ap else 1.5
        
        try:
            # Im AP-Modus Session komplett umgehen (frischer Socket)
            if is_ap:
                r = requests.get(
                    f"{base_url}/data",
                    timeout=current_timeout,
                    auth=(user, pw) if user else None,
                    headers={'Connection': 'close', 'Accept': 'application/json'}
                )
            else:
                # Schneller LAN-Request ohne Session-Pool-Zwang (Keep-Alive explizit deaktiviert)
                r = requests.get(
                    f"{base_url}/data",
                    timeout=current_timeout,
                    auth=(user, pw) if user else None,
                    headers={'Connection': 'close', 'Accept': 'application/json'}
                )

            if r.status_code == 200:
                payload = r.json()
                
                # mDNS / IP Updates übergeben wir direkt zurück an den Core
                # oder triggern hier ein schnelles Config-Update bei IP-Wechsel
                _update_runtime_ip(mac, payload, registry)
                _update_config_ip_if_needed(mac, payload)
                
                # Heavy-Fetch Prüfung
                esp_plant_rev = payload.get("rev_plant_planner", 0)
                local_rev = local_plant_revs.get(mac, -1)

                if esp_plant_rev > local_rev:
                    fetch_heavy_plant_data(mac, base_url, user, pw, local_plants_cache, local_plant_revs)

                if mac in local_plants_cache:
                    payload["plant_planner"] = local_plants_cache[mac].get("plant_planner", {})

                registry.handle_success(mac)
                return mac, payload, is_ap
            
        except Exception as e:
            if is_ap:
                print(f"[NetworkWorker AP-Debug] Fehler bei {base_url}: {e}")
            continue
            
    registry.handle_failure(mac)
    return mac, None, False

def fetch_heavy_plant_data(mac, base_url, user, pw, local_plants_cache, local_plant_revs):
    """Holt die erweiterten Pflanzendaten ab und sichert sie über client_storage."""
    try:
        r = requests.get(
            f"{base_url}/data/plants",
            timeout=2.5,
            auth=(user, pw) if user else None,
            headers={'Connection': 'close'}
        )
        if r.status_code == 200:
            plant_payload = r.json()
            network.client_storage.save_heavy_plant_data(mac, plant_payload, local_plants_cache)
            if "plant_planner" in plant_payload:
                local_plant_revs[mac] = plant_payload["plant_planner"].get("rev_plant_planner", 0)
    except Exception as e:
        print(f"[NetworkWorker] Heavy Plant Fetch Error für {mac}: {e}")

def send_control_request(base_url, payload, user, pw):
    """Sendet Steuerbefehle synchron ab (wird asynchron aufgerufen)."""
    try:
        requests.post(
            f"{base_url}/control",
            json=payload,
            timeout=2.0,
            auth=(user, pw) if user else None,
            headers={'Connection': 'close'}
        )
        return True
    except:
        return False

def _update_runtime_ip(mac, payload, registry):
    ip = payload.get("ip") or payload.get("ip_address")
    if not ip:
        return

    registry.update_device(mac, ip=ip, source="runtime")


def _update_config_ip_if_needed(mac, payload):
    """Setzt die `ip_address` in der Config, aber NUR wenn dort bisher kein Wert steht."""
    ip = payload.get("ip") or payload.get("ip_address")
    if not ip:
        return

    try:
        cfg = config._init()
    except Exception:
        return

    devices = cfg.get("devices", {})
    if mac not in devices:
        return

    dev = devices[mac]
    current_ip = (dev.get("ip_address") or "").strip()
    if not current_ip:
        print(f"[NetworkWorker] Setze initiale IP für {mac}: {ip}")
        dev["ip_address"] = ip
        try:
            config.save(cfg)
        except Exception as e:
            print(f"[NetworkWorker] Fehler beim Schreiben der initialen IP: {e}")