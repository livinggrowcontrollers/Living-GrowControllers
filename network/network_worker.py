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

                # Der ESP ist die autoritative Quelle. Auch nach einem Reset
                # (ESP-Revision kleiner als Cache) muss der Heavy-Cache ersetzt
                # werden, sonst bleibt der Client dauerhaft auf Geisterdaten.
                if esp_plant_rev != local_rev:
                    fetch_heavy_plant_data(
                        mac, base_url, user, pw,
                        local_plants_cache, local_plant_revs,
                    )

                cached = local_plants_cache.get(mac, {}).get("plant_planner", {})
                cached_rev = int(cached.get("rev_plant_planner", -1)) if isinstance(cached, dict) else -1
                if cached_rev == int(esp_plant_rev):
                    payload["plant_planner"] = cached

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

def send_control_request(base_url, payload, user, pw, endpoint="/control"):
    """Sendet Steuerbefehle synchron ab (wird asynchron aufgerufen)."""
    try:
        response = requests.post(
            f"{base_url}{endpoint}",
            json=payload,
            timeout=2.0,
            auth=(user, pw) if user else None,
            headers={'Connection': 'close'}
        )
        return 200 <= response.status_code < 300
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
