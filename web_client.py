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
        self._stop_lock = threading.Lock()
        self._stopped = False
        self.ready = False

        # Status & Caches (RAM)
        self.current_data = {}
        self._last_disk_write = 0.0
        self._disk_interval = 60.0
        self._storage_future = None

        # Boot-Load via Storage-Modul auslagern
        (
            self._local_plants_cache,
            self._local_plant_revs,
        ) = client_storage.load_plants_at_boot()

        # Instanziierung der Kernkomponenten
        self.registry = DeviceRegistry()
        self._transport = network_worker.PersistentHTTPTransport()
        self._executor = ThreadPoolExecutor(
            max_workers=8,
            thread_name_prefix="web-poll",
        )
        self._heavy_executor = ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="web-heavy",
        )
        self._control_executor = ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="web-control",
        )
        self._history_executor = ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="web-history",
        )
        self._storage_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="web-storage",
        )
        self._heavy_lock = threading.Lock()
        self._heavy_inflight = set()
        self._heavy_failures = {}
        self._heavy_retry_after = {}

        # Nutzt den Discovery-Dienst aus dem network-Package
        self._discovery = client_discovery.MDNSDiscoveryService(self.registry)

    def run(self):
        # Autarken mDNS-Dienst starten
        try:
            self._discovery.start()
        except Exception as e:
            print(f"[WebClient] mDNS Dienst Start fehlgeschlagen: {e}")

        try:
            while not self._stop_event.is_set():
                cycle_started = time.monotonic()
                try:
                    self.fetch_all_web_data()

                    now = time.monotonic()
                    if now - self._last_disk_write >= self._disk_interval:
                        self._schedule_web_dump()
                        self._last_disk_write = now

                    elapsed = time.monotonic() - cycle_started
                    sleep_time = max(0.1, self.interval - elapsed)
                    self._stop_event.wait(sleep_time)
                except Exception as exc:
                    print(f"[WebClient] Main Loop Error: {exc}")
                    self._stop_event.wait(1.0)
        finally:
            self._discovery.stop()

    def fetch_all_web_data(self):
        changed = False
        cfg = config._init()
        devices = cfg.get("devices", {})
        active = set(devices.keys())
        
        # RAM-Cache-Bereinigung von veralteten/gelöschten MACs
        for mac in list(self.current_data.keys()):
            if mac not in active: self.current_data.pop(mac, None)
        for mac in list(self._local_plants_cache.keys()):
            if mac not in active: self._local_plants_cache.pop(mac, None)
        for mac in list(self._local_plant_revs.keys()):
            if mac not in active: self._local_plant_revs.pop(mac, None)
        self.registry.remove_inactive(active)
        self._transport.retain_devices(active)
        with self._heavy_lock:
            for mac in tuple(self._heavy_failures):
                if mac not in active:
                    self._heavy_failures.pop(mac, None)
                    self._heavy_retry_after.pop(mac, None)

        if not devices:
            return False

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
                self._local_plants_cache, self._local_plant_revs,
                self._transport,
                self._schedule_heavy_fetch,
            )
            future_to_mac[job] = mac

        # Ergebnisse verarbeiten, sobald sie eintreffen
        if future_to_mac:
            for future in as_completed(future_to_mac):
                try:
                    res = future.result()
                except Exception as exc:
                    mac = future_to_mac[future]
                    print(f"[WebClient] Worker-Fehler für {mac}: {exc}")
                    continue
                if res is None:
                    continue
                
                mac, payload, is_ap = res
                if payload:
                    payload["timestamp"] = time.time()
                    inject_web_data(mac, payload)
                    self.current_data[mac] = payload
                    changed = True

        self.ready = True
        return changed

    def _schedule_web_dump(self):
        if self._stop_event.is_set():
            return
        if self._storage_future and not self._storage_future.done():
            return

        snapshot = dict(self.current_data)
        self._storage_future = self._storage_executor.submit(
            client_storage.save_web_dump,
            snapshot,
        )

    def _schedule_heavy_fetch(self, mac, base_url, user, pw):
        now = time.monotonic()
        with self._heavy_lock:
            if mac in self._heavy_inflight:
                return
            if now < self._heavy_retry_after.get(mac, 0.0):
                return
            self._heavy_inflight.add(mac)

        try:
            self._heavy_executor.submit(
                self._run_heavy_fetch,
                mac,
                base_url,
                user,
                pw,
            )
        except RuntimeError:
            with self._heavy_lock:
                self._heavy_inflight.discard(mac)

    def _run_heavy_fetch(self, mac, base_url, user, pw):
        succeeded = False
        try:
            succeeded = network_worker.fetch_heavy_plant_data(
                mac,
                base_url,
                user,
                pw,
                self._local_plants_cache,
                self._local_plant_revs,
                transport=self._transport,
            )
        finally:
            with self._heavy_lock:
                self._heavy_inflight.discard(mac)
                if succeeded:
                    self._heavy_failures.pop(mac, None)
                    self._heavy_retry_after.pop(mac, None)
                else:
                    failures = self._heavy_failures.get(mac, 0) + 1
                    self._heavy_failures[mac] = failures
                    delay = min(30.0, 2.0 ** min(failures, 5))
                    self._heavy_retry_after[mac] = (
                        time.monotonic() + delay
                    )



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

            endpoint = (
                "/control/plants"
                if "rev_plant_planner" in payload
                else "/control"
            )
            network_worker.send_control_request(
                targets[0],
                payload,
                user,
                pw,
                endpoint=endpoint,
                mac=mac,
                transport=self._transport,
            )

        try:
            self._control_executor.submit(_async_send)
        except RuntimeError:
            return

    def send_history_command(self, mac, params, on_done):
        """Resolve the current route and send one History target."""
        command_params = dict(params)

        def finish(payload, error):
            if callable(on_done):
                on_done(payload, error)

        def _async_send():
            cfg = config._init()
            dev_cfg = cfg.get("devices", {}).get(mac, {})
            if self.registry.is_cooldown(mac):
                finish(
                    None,
                    "Aktuelle Geräteroute ist vorübergehend gesperrt.",
                )
                return

            targets = self.registry.build_targets(mac, dev_cfg)
            if not targets:
                finish(None, "Keine aktuelle Geräteroute verfügbar.")
                return

            user, pw = config.get_device_auth(mac)
            last_error = "History-Ziel konnte nicht erreicht werden."
            for base_url in targets:
                transport = getattr(self, "_transport", None)
                if transport is None:
                    acknowledgement, error = network_worker.send_history_request(
                        base_url,
                        command_params,
                        user,
                        pw,
                    )
                else:
                    acknowledgement, error = network_worker.send_history_request(
                        base_url,
                        command_params,
                        user,
                        pw,
                        mac=mac,
                        transport=transport,
                    )
                if acknowledgement is not None:
                    finish(acknowledgement, error)
                    return
                if error:
                    last_error = error

            finish(None, last_error)

        history_executor = getattr(self, "_history_executor", None)
        if history_executor is None:
            threading.Thread(
                target=_async_send,
                daemon=True,
                name="history-command",
            ).start()
            return
        try:
            history_executor.submit(_async_send)
        except RuntimeError:
            finish(None, "History-Worker ist bereits beendet.")

    def is_synced(self, mac, rev_key):
        if mac not in self.current_data:
            return False

        local_rev = client_storage.get_local_settings_rev(mac)
        server_rev = int(self.current_data[mac].get(rev_key, -1))

        return server_rev == int(local_rev)
    def stop(self):
        with self._stop_lock:
            if self._stopped:
                return
            self._stopped = True

        self._stop_event.set()
        self._discovery.stop()
        for executor in (
            self._executor,
            self._heavy_executor,
            self._control_executor,
            self._history_executor,
            self._storage_executor,
        ):
            executor.shutdown(wait=False, cancel_futures=True)
        self._transport.close()


    def start_ota_update(self, mac, file_path, on_progress_callback=None, on_done_callback=None):
        """
        Startet den asynchronen OTA-Upload im Hintergrund.
        """
        import os
        import threading
        import time
        import urllib.parse
        import http.client

        def _async_upload():
            conn = None
            cfg = config._init()
            dev_cfg = cfg.get("devices", {}).get(mac, {})
            targets = self.registry.build_targets(mac, dev_cfg)
            user, pw = config.get_device_auth(mac)

            if not targets:
                if on_done_callback: on_done_callback(False, "Keine Ziel-IP fuer Device gefunden.")
                return

            base_url = targets[0]
            url = f"{base_url.rstrip('/')}/update"

            try:
                file_size = os.path.getsize(file_path)
                filename = os.path.basename(file_path)
                
                boundary = '----GrowmasterOtaBoundary' + str(int(time.time()))
                
                header = (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="update"; filename="{filename}"\r\n'
                    f"Content-Type: application/octet-stream\r\n\r\n"
                ).encode('utf-8')
                
                footer = f"\r\n--{boundary}--\r\n".encode('utf-8')
                total_length = len(header) + file_size + len(footer)

                parsed_url = urllib.parse.urlparse(url)
                
                if parsed_url.scheme == "https":
                    conn = http.client.HTTPSConnection(parsed_url.netloc, timeout=30)
                else:
                    conn = http.client.HTTPConnection(parsed_url.netloc, timeout=30)
                    
                conn.putrequest("POST", parsed_url.path)
                conn.putheader('Content-Type', f'multipart/form-data; boundary={boundary}')
                conn.putheader('Content-Length', str(total_length))
                if user and pw:
                    import base64
                    auth_str = base64.b64encode(f"{user}:{pw}".encode('utf-8')).decode('utf-8')
                    conn.putheader('Authorization', f'Basic {auth_str}')
                conn.endheaders()

                conn.send(header)
                bytes_sent = len(header)

                chunk_size = 16384
                with open(file_path, 'rb') as f:
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        conn.send(chunk)
                        bytes_sent += len(chunk)
                        if on_progress_callback:
                            file_progress = bytes_sent - len(header)
                            on_progress_callback(min(file_progress, file_size), file_size)

                conn.send(footer)
                
                response = conn.getresponse()
                response.read()
                
                if response.status == 200:
                    if on_done_callback: on_done_callback(True, "Erfolgreich übertragen!")
                else:
                    if on_done_callback: on_done_callback(False, f"ESP-Fehler: {response.status}")

            except Exception as e:
                if on_done_callback: on_done_callback(False, str(e))
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass

        threading.Thread(target=_async_upload, daemon=True).start()
# Singleton Instanz für die App bereitstellen
WEB_CLIENT = WebClientThread()
