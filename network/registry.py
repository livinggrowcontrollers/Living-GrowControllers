from ipaddress import IPv4Address
import threading
import time


def _is_valid_ip(ip):
    try:
        IPv4Address(str(ip or ""))
        return True
    except ValueError:
        return False


def _is_valid_hostname(host):
    return bool(host) and len(host) > 3


def _append_unique(targets, target):
    normalized = str(target or "").rstrip("/")
    if normalized and normalized not in targets:
        targets.append(normalized)


class DeviceRegistry:
    def __init__(self):
        self._lock = threading.Lock()

        # Laufzeitinformationen bleiben von der persistenten Config getrennt.
        self._devices = {}

        # Die kurzen Pausen bleiben deutlich unter dem Dashboard-Stale-Timeout.
        self._circuit_breakers = {}

    def update_device(self, mac, ip=None, hostname=None, source="mdns"):
        """Aktualisiert Laufzeitdaten eines Geräts thread-sicher."""
        with self._lock:
            entry = self._devices.setdefault(mac, {})
            if ip:
                if source == "runtime":
                    entry["runtime_ip"] = ip
                    if not entry.get("ip"):
                        entry["ip"] = ip
                        entry["source"] = source
                else:
                    entry["ip"] = ip
                    entry["source"] = source
                entry["last_seen"] = time.time()
            if hostname:
                entry["hostname"] = hostname

    def get_device(self, mac):
        with self._lock:
            return self._devices.get(mac, {}).copy()

    def remove_device(self, mac):
        with self._lock:
            self._devices.pop(mac, None)
            self._circuit_breakers.pop(mac, None)

    def remove_inactive(self, active_devices):
        active = set(active_devices)
        with self._lock:
            known_devices = set(self._devices) | set(self._circuit_breakers)
            for mac in known_devices:
                if mac not in active:
                    self._devices.pop(mac, None)
                    self._circuit_breakers.pop(mac, None)

    def build_targets(self, mac, dev_cfg):
        ip_cfg = (dev_cfg.get("ip_address") or "").strip()
        hostname = (dev_cfg.get("hostname") or "").strip().lower()

        # Explizite Hub-/Cloudflare-URLs bleiben allein autoritativ.
        if ip_cfg.startswith(("http://", "https://")):
            return [ip_cfg.rstrip("/")]

        entry = self.get_device(mac)
        targets = []
        configured_target = (
            f"http://{ip_cfg}" if _is_valid_ip(ip_cfg) else None
        )
        discovered_ip = entry.get("ip")
        discovered_target = (
            f"http://{discovered_ip}"
            if _is_valid_ip(discovered_ip)
            else None
        )
        hostname_target = (
            f"http://{hostname}.local"
            if _is_valid_hostname(hostname)
            else None
        )

        candidates = {
            configured_target,
            discovered_target,
            hostname_target,
        }
        preferred_target = entry.get("preferred_target")
        if preferred_target in candidates:
            _append_unique(targets, preferred_target)

        _append_unique(targets, configured_target)
        _append_unique(targets, discovered_target)
        _append_unique(targets, hostname_target)
        return targets

    def is_cooldown(self, mac):
        with self._lock:
            breaker = self._circuit_breakers.get(mac)
            if not breaker:
                return False
            now = time.monotonic()
            if now >= breaker["cooldown_until"]:
                breaker["cooldown_until"] = 0.0
                return False
            return True

    def handle_success(self, mac, target=None):
        with self._lock:
            self._circuit_breakers.pop(mac, None)
            if target:
                entry = self._devices.setdefault(mac, {})
                entry["preferred_target"] = str(target).rstrip("/")
                entry["last_success"] = time.time()

    def handle_failure(
        self,
        mac,
        max_fails=5,
        cooldown_base=1.0,
        cooldown_max=6.0,
    ):
        """Aktiviert nach mehreren Fehlern eine kurze progressive Probe-Pause."""
        with self._lock:
            breaker = self._circuit_breakers.setdefault(
                mac,
                {"fail_count": 0, "cooldown_until": 0.0},
            )
            breaker["fail_count"] += 1
            fail_count = breaker["fail_count"]
            if fail_count < max_fails:
                return 0.0

            cooldown = min(
                float(cooldown_max),
                float(cooldown_base) * (2 ** (fail_count - max_fails)),
            )
            breaker["cooldown_until"] = time.monotonic() + cooldown

        print(
            f"[CircuitBreaker] {mac}: kurze Wiederverbindungs-Pause "
            f"von {cooldown:.1f}s nach {fail_count} Fehlern."
        )
        return cooldown
