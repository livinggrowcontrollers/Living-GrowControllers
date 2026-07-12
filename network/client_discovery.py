# network/client_discovery.py
import threading
import time
import config
from network.registry import DeviceRegistry

class MDNSDiscoveryService:
    def __init__(self, registry: DeviceRegistry):
        self.registry = registry
        self._mdns_thread = None
        self._mdns_stop = threading.Event()

    def start(self):
        if self._mdns_thread and self._mdns_thread.is_alive():
            return

        self._mdns_stop.clear()
        self._mdns_thread = threading.Thread(target=self._mdns_worker, daemon=True)
        self._mdns_thread.start()

    def stop(self):
        self._mdns_stop.set()
        if self._mdns_thread and self._mdns_thread.is_alive():
            self._mdns_thread.join(timeout=2.0)

    def _mdns_worker(self):
        try:
            from zeroconf import Zeroconf, ServiceBrowser
        except ImportError:
            print("[Discovery] zeroconf Bibliothek nicht installiert. mDNS übersprungen.")
            return

        try:
            zc = Zeroconf()
        except Exception as e:
            print(f"[Discovery] Zeroconf konnte nicht initialisiert werden: {e}")
            return

        class DiscoveryListener:
            def __init__(self, registry):
                self.registry = registry

            def remove_service(self, zc, type_, name):
                pass

            def add_service(self, zc, type_, name):
                try:
                    info = zc.get_service_info(type_, name)
                    if not info:
                        return
                    addresses = info.parsed_addresses()
                    ip = addresses[0] if addresses else None
                    hostname = (info.server or "").rstrip('.')
                    
                    # Bessere Erkennung via TXT-Record falls vorhanden (z.B. mac=A1:B2:C3...)
                    mac_from_txt = None
                    if info.properties:
                        # Versuche 'mac' aus den mDNS-Properties zu lesen
                        encoded_mac = info.properties.get(b'mac') or info.properties.get(b'id')
                        if encoded_mac:
                            mac_from_txt = encoded_mac.decode('utf-8').strip().lower().replace("-", ":")

                    cfg = config._init()
                    devices = cfg.get('devices', {})
                    
                    for mac, dev in devices.items():
                        mac_clean = mac.strip().lower()
                        
                        # Höchste Priorität: Eindeutiger TXT-Record Match
                        if mac_from_txt and mac_from_txt == mac_clean:
                            self.registry.update_device(mac, ip=ip, hostname=hostname, source="mdns")
                            continue
                            
                        dev_host = (dev.get('hostname') or '').lower().strip()
                        dev_ip = (dev.get('ip_address') or '').strip()
                        
                        if not dev_host:
                            continue

                        # Schärferer Match: Hostname muss exakt übereinstimmen, nicht nur starten mit!
                        # Oder die IP muss exakt passen.
                        hostname_clean = hostname.lower()
                        if (hostname_clean == dev_host or hostname_clean == f"{dev_host}.local"):
                            # Verhindere, dass eine IP doppelt zugewiesen wird (Konflikt-Vermeidung)
                            current_reg = self.registry.get_device(mac)
                            if current_reg.get("ip") != ip:
                                print(f"[Discovery] mDNS Match für {mac}: {ip} ({hostname})")
                                self.registry.update_device(mac, ip=ip, hostname=hostname, source="mdns")
                                
                except Exception as e:
                    print(f"[Discovery] Fehler im mDNS Listener: {e}")
            def update_service(self, zc, type_, name):
                self.add_service(zc, type_, name)

        listener = DiscoveryListener(self.registry)
        browser = ServiceBrowser(zc, '_http._tcp.local.', listener)

        while not self._mdns_stop.is_set():
            self._mdns_stop.wait(1.0)

        try:
            zc.close()
        except:
            pass