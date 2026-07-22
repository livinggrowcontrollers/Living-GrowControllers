# web_client/registry.py
import re
import threading
import time

# Modulweite Validierer
def _is_valid_ip(ip):
    return bool(re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip or ""))

def _is_valid_hostname(host):
    return bool(host) and len(host) > 3

class DeviceRegistry:
    def __init__(self):
        # Der Lock schützt alle darunter liegenden Dictionaries vor concurrent Zugriffen
        self._lock = threading.Lock()
        
        # Central device registry: { mac: {"ip": str, "hostname": str, "source": str, "last_seen": float} }
        self._devices = {}
        
        # Circuit Breaker Zustand: { mac: {"fail_count": int, "cooldown_until": float} }
        self._circuit_breakers = {}

    def update_device(self, mac, ip=None, hostname=None, source="mdns"):
        """Aktualisiert oder erstellt einen Eintrag in der Registry (Thread-sicher)."""
        with self._lock:
            entry = self._devices.setdefault(mac, {})
            if ip:
                entry["ip"] = ip
                entry["source"] = source
                entry["last_seen"] = time.time()
            if hostname:
                entry["hostname"] = hostname

    def get_device(self, mac):
        """Holt die Daten eines spezifischen Geräts."""
        with self._lock:
            return self._devices.get(mac, {}).copy()

    def remove_device(self, mac):
        """Entfernt ein Gerät aus der Registry (z.B. bei Bereinigung)."""
        with self._lock:
            self._devices.pop(mac, None)
            self._circuit_breakers.pop(mac, None)

    from urllib.parse import urlparse

    def build_targets(self, mac, dev_cfg):
        ip_cfg = (dev_cfg.get("ip_address") or "").strip()
        hostname = (dev_cfg.get("hostname") or "").strip().lower()

        targets = []

        # Vollständige URL eingetragen?
        if ip_cfg.startswith("http://") or ip_cfg.startswith("https://"):
            return [ip_cfg.rstrip("/")]

        # Normale IPv4
        if _is_valid_ip(ip_cfg):
            targets.append(f"http://{ip_cfg}")

        # mDNS
        if _is_valid_hostname(hostname):
            targets.append(f"http://{hostname}.local")

        return targets
    def is_cooldown(self, mac):
        """Prüft, ob ein Gerät aktuell wegen Fehlern blockiert ist."""
        with self._lock:
            breaker = self._circuit_breakers.get(mac)
            if not breaker:
                return False
            return time.time() < breaker["cooldown_until"]

    def handle_success(self, mac):
        """Setzt den Fehlerzähler bei erfolgreicher Verbindung zurück."""
        with self._lock:
            self._circuit_breakers.pop(mac, None)




    def handle_failure(self, mac, max_fails=5, cooldown_duration=20.0):
        """Registriert einen Fehler und aktiviert ggf. den Cooldown."""
        with self._lock:
            now = time.time()
            breaker = self._circuit_breakers.setdefault(mac, {"fail_count": 0, "cooldown_until": 0.0})
            breaker["fail_count"] += 1
            
            if breaker["fail_count"] >= max_fails:
                breaker["cooldown_until"] = now + cooldown_duration
                print(f"[CircuitBreaker] {mac} ist offline. Überspringe Anfragen für {cooldown_duration}s.")