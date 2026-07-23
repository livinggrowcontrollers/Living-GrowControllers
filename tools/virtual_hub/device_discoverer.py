from kivy.clock import Clock
from zeroconf import Zeroconf


class PopupDiscoverer:
    def __init__(self, callback, timeout=5.0):
        self.callback = callback
        self.found_devices = {}

        self.fallback_trigger = Clock.schedule_once(
            self._offer_ap_fallback,
            timeout
        )

    def add_service(self, zc: Zeroconf, type_, name):
        self.update_service(zc, type_, name)

    def update_service(self, zc: Zeroconf, type_, name):
        info = zc.get_service_info(type_, name)

        if not info:
            return

        hostname = info.server.rstrip(".").lower()

        if "growmaster-" not in hostname:
            return

        if self.fallback_trigger:
            Clock.unschedule(self.fallback_trigger)
            self.fallback_trigger = None

        addresses = info.parsed_addresses()

        ip = addresses[0] if addresses else ""

        mac = hostname.replace("growmaster-", "").replace(".local", "")

        if mac in self.found_devices:
            return

        device = {
            "hostname": hostname.replace(".local", ""),
            "ip_address": ip,
        }

        self.found_devices[mac] = device

        Clock.schedule_once(
            lambda dt: self.callback(mac, device)
        )

    def remove_service(self, *args):
        pass

    def _offer_ap_fallback(self, dt):
        if self.found_devices:
            return

        self.callback(
            "ap_fallback",
            {
                "hostname": "Growmaster AP",
                "ip_address": "192.168.4.1",
            },
        )