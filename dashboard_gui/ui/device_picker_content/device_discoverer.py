# dashboard_gui/ui/device_picker_content/device_discoverer.py
from kivy.clock import Clock
from zeroconf import ServiceBrowser, Zeroconf
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.global_state_manager import GLOBAL_STATE
from kivy.uix.gridlayout import GridLayout 

# --- INTEGRIRTER MDNS DISCOVERER FOR POPUP ---
class PopupDiscoverer:
    def __init__(self, callback, timeout=5.0):
        self.callback = callback
        self.found_devices = {}
        
        # Timer starten: Wenn nach 'timeout' Sekunden nix gefunden wurde -> AP-Modus IP anbieten
        self.fallback_trigger = Clock.schedule_once(self._offer_ap_fallback, timeout)

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info:
            hostname = info.server.rstrip('.').lower()
            if "growmaster-" in hostname:
                # Da wir ein echtes Gerät gefunden haben, brechen wir den AP-Fallback ab
                if self.fallback_trigger:
                    Clock.unschedule(self.fallback_trigger)
                    self.fallback_trigger = None

                addresses = [str(ip) for ip in info.parsed_addresses()]
                ip_address = addresses[0] if addresses else ""
                mac_id = hostname.split("growmaster-")[-1].replace(".local", "")
                
                device_data = {
                    "hostname": hostname.replace(".local", ""),
                    "ip_address": ip_address
                }
                
                if mac_id not in self.found_devices:
                    self.found_devices[mac_id] = device_data
                    Clock.schedule_once(lambda dt: self.callback(mac_id, device_data))

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self.update_service(zc, type_, name)

    def _offer_ap_fallback(self, dt):
        """Wird aufgerufen, wenn der Timeout abläuft und kein mDNS-Gerät gefunden wurde."""
        if not self.found_devices:
            fallback_data = {
                "hostname": "Growmaster-AP-Mode",
                "ip_address": "192.168.4.1"
            }
            # 'ap_fallback' als ID nutzen, damit die GUI weiß, dass es der AP-Modus ist
            self.found_devices["ap_fallback"] = fallback_data
            self.callback("ap_fallback", fallback_data)