# network/client_discovery.py
import threading

import config
from network.registry import DeviceRegistry
from platform_utils import is_android


def _select_ipv4(addresses):
    return next(
        (address for address in addresses if "." in str(address)),
        None,
    )


def _normalize_identity(value):
    return str(value or "").strip().lower().replace("-", ":")


def _acquire_android_multicast_lock():
    if not is_android():
        return None

    try:
        from jnius import autoclass

        Context = autoclass("android.content.Context")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        app_context = activity.getApplicationContext()
        wifi_manager = app_context.getSystemService(Context.WIFI_SERVICE)
        multicast_lock = wifi_manager.createMulticastLock(
            "LGS:WebClientMDNS"
        )
        multicast_lock.setReferenceCounted(False)
        multicast_lock.acquire()
        print("[Discovery] Android MulticastLock aktiv.")
        return multicast_lock
    except Exception as exc:
        print(
            "[Discovery] Android MulticastLock nicht verfügbar: "
            f"{exc}"
        )
        return None


def _release_multicast_lock(multicast_lock):
    if multicast_lock is None:
        return
    try:
        if multicast_lock.isHeld():
            multicast_lock.release()
            print("[Discovery] Android MulticastLock freigegeben.")
    except Exception as exc:
        print(f"[Discovery] MulticastLock-Freigabe fehlgeschlagen: {exc}")

class MDNSDiscoveryService:
    def __init__(self, registry: DeviceRegistry):
        self.registry = registry
        self._mdns_thread = None
        self._mdns_stop = threading.Event()

    def start(self):
        if self._mdns_thread and self._mdns_thread.is_alive():
            return

        self._mdns_stop.clear()
        self._mdns_thread = threading.Thread(
            target=self._mdns_worker,
            name="mdns-discovery",
            daemon=True,
        )
        self._mdns_thread.start()

    def stop(self):
        self._mdns_stop.set()
        if self._mdns_thread and self._mdns_thread.is_alive():
            self._mdns_thread.join(timeout=2.0)

    def _mdns_worker(self):
        try:
            from zeroconf import ServiceBrowser, Zeroconf
        except ImportError:
            print(
                "[Discovery] zeroconf Bibliothek nicht installiert. "
                "mDNS übersprungen."
            )
            return

        multicast_lock = _acquire_android_multicast_lock()
        zc = None
        try:
            zc = Zeroconf()

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

                        ip = _select_ipv4(info.parsed_addresses())
                        if not ip:
                            return
                        hostname = (info.server or "").rstrip(".")

                        mac_from_txt = None
                        if info.properties:
                            encoded_mac = (
                                info.properties.get(b"mac")
                                or info.properties.get(b"id")
                                or info.properties.get(b"device_id")
                            )
                            if encoded_mac:
                                mac_from_txt = _normalize_identity(
                                    encoded_mac.decode("utf-8")
                                )

                        cfg = config._init()
                        devices = cfg.get("devices", {})
                        for mac, dev in devices.items():
                            identities = {
                                _normalize_identity(mac),
                                _normalize_identity(dev.get("mac")),
                                _normalize_identity(dev.get("device_id")),
                            }
                            identities.discard("")

                            if mac_from_txt and mac_from_txt in identities:
                                self.registry.update_device(
                                    mac,
                                    ip=ip,
                                    hostname=hostname,
                                    source="mdns",
                                )
                                continue

                            dev_host = (
                                dev.get("hostname") or ""
                            ).lower().strip().rstrip(".")
                            if not dev_host:
                                continue

                            hostname_clean = hostname.lower().rstrip(".")
                            if hostname_clean in {
                                dev_host,
                                f"{dev_host}.local",
                            }:
                                current = self.registry.get_device(mac)
                                if current.get("ip") != ip:
                                    print(
                                        f"[Discovery] mDNS Match für "
                                        f"{mac}: {ip} ({hostname})"
                                    )
                                    self.registry.update_device(
                                        mac,
                                        ip=ip,
                                        hostname=hostname,
                                        source="mdns",
                                    )
                    except Exception as exc:
                        print(
                            "[Discovery] Fehler im mDNS Listener: "
                            f"{exc}"
                        )

                def update_service(self, zc, type_, name):
                    self.add_service(zc, type_, name)

            listener = DiscoveryListener(self.registry)
            browser = ServiceBrowser(
                zc,
                "_http._tcp.local.",
                listener,
            )

            while not self._mdns_stop.wait(1.0):
                pass

            _ = browser
        except Exception as exc:
            print(f"[Discovery] mDNS-Dienstfehler: {exc}")
        finally:
            if zc is not None:
                try:
                    zc.close()
                except Exception:
                    pass
            _release_multicast_lock(multicast_lock)
