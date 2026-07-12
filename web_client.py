# web_client.py
import threading
import time
import config
from concurrent.futures import ThreadPoolExecutor, as_completed

# Alle Netzwerk- und Storage-Module aus dem network-Ordner importieren
from network import client_storage
from network import network_worker
from network import client_discovery
from network.registry import DeviceRegistry
class WebClientThread(threading.Thread):
    """
    WebClientThread: Orchestrator und Manager für die zyklischen Daten-Abfragen.
    Steuert das Timing, den ThreadPoolExecutor und koordiniert Speicher- und Netzwerk-Worker.
    """

    def __init__(self, interval=1.5):
        super().__init__(daemon=True)
        self.interval = interval
        
        # Ablaufsteuerung
        self._stop_event = threading.Event()
        self.ready = False

        # Status & Caches (RAM)
        self.current_data = {}
        self._last_disk_write = 0.0
        self._disk_interval = 60.0

        # Boot-Load via Storage-Modul auslagern
        self._local_plants_cache, self._local_plant_revs = client_storage.load_plants_at_boot()

        # Instanziierung der Kernkomponenten
        self.registry = DeviceRegistry()
        self._executor = ThreadPoolExecutor(max_workers=20)
        
        # Nutzt den Discovery-Dienst aus dem network-Package
        self._discovery = client_discovery.MDNSDiscoveryService(self.registry)
    def run(self):
        # Autarken mDNS-Dienst starten
        try:
            self._discovery.start()
        except Exception as e:
            print(f"[WebClient] mDNS Dienst Start fehlgeschlagen: {e}")

        while not self._stop_event.is_set():
            t_start = time.time()
            try:
                changed = self.fetch_all_web_data()

                # Zyklisches Speichern auf HDD via Storage-Modul
                now = time.time()
                if (now - self._last_disk_write) >= self._disk_interval:
                    client_storage.save_web_dump(self.current_data)
                    self._last_disk_write = now

                elapsed = time.time() - t_start
                sleep_time = max(0.1, self.interval - elapsed)
                self._stop_event.wait(sleep_time)
            except Exception as e:
                print(f"[WebClient] Main Loop Error: {e}")
                time.sleep(1)

    def fetch_all_web_data(self):
        changed = False
        cfg = config._init()
        devices = cfg.get("devices", {})
        if not devices:
            return False  

        now = time.time()
        active = set(devices.keys())
        
        # RAM-Cache-Bereinigung von veralteten/gelöschten MACs
        for mac in list(self.current_data.keys()):
            if mac not in active: self.current_data.pop(mac, None)
        for mac in list(self._local_plants_cache.keys()):
            if mac not in active: self._local_plants_cache.pop(mac, None)
        for mac in list(self._local_plant_revs.keys()):
            if mac not in active: self._local_plant_revs.pop(mac, None)
        for mac in active:
            if mac not in active:
                self.registry.remove_device(mac)

        try:
            from decoder import inject_web_data
        except ImportError:
            return False

        future_to_mac = {}
        for mac, dev_cfg in devices.items():
            # Circuit Breaker Check via Registry
            if self.registry.is_cooldown(mac):
                continue
            
            # Target-Routenauflösung über Registry anfordern
            targets = self.registry.build_targets(mac, dev_cfg)
            if not targets:
                continue

            # NetworkWorker im ThreadPool ausführen
            job = self._executor.submit(
                network_worker.fetch_single_device, 
                mac, dev_cfg, targets, self.registry, 
                self._local_plants_cache, self._local_plant_revs
            )
            future_to_mac[job] = mac

        # Ergebnisse verarbeiten, sobald sie eintreffen
        if future_to_mac:
            for future in as_completed(future_to_mac):
                res = future.result()
                if res is None:
                    continue
                
                mac, payload, is_ap = res
                if payload:
                    payload["timestamp"] = now
                    inject_web_data(mac, payload)
                    self.current_data[mac] = payload
                    changed = True

        self.ready = True
        return changed    



    def send_control(self, mac, payload):
        """Übergibt die Control-Payload asynchron an den Network-Worker."""
        if "rev" in payload:
            client_storage.save_settings_rev(mac, payload["rev"])

        def _async_send():
            cfg = config._init()
            dev_cfg = cfg.get("devices", {}).get(mac, {})
            # Respect circuit breaker: skip sending if device is on cooldown
            if self.registry.is_cooldown(mac):
                return
            targets = self.registry.build_targets(mac, dev_cfg)
            user, pw = config.get_device_auth(mac)

            if not targets:
                return

            for base_url in targets:
                if network_worker.send_control_request(base_url, payload, user, pw):
                    break # Erfolg, weiteren Loop abbrechen

        threading.Thread(target=_async_send, daemon=True).start()

    def is_synced(self, mac, rev_key):
        if mac not in self.current_data:
            return False

        local_rev = client_storage.get_local_settings_rev(mac, rev_key)
        server_rev = int(self.current_data[mac].get(rev_key, -1))

        return server_rev == int(local_rev)
    def stop(self):
        self._stop_event.set()
        self._discovery.stop()
        self._executor.shutdown(wait=False)

# Singleton Instanz für die App bereitstellen
WEB_CLIENT = WebClientThread()