#bridgemanager
from platform_utils import is_android, is_windows, is_linux, is_macos
import os
import config
print("BLE DESKTOP MODULE IMPORTIERT")
# Absolute Singleton-Instanz
_bridge_instance = None

class BleBridgeAndroid:
    def __init__(self, context=None):
        from jnius import autoclass
        self.AdvBridge = autoclass("org.hackintosh1980.blebridge.AdvBridge")
        self.GattBridge = autoclass("org.hackintosh1980.blebridge.GattBridge")
        self.BroadcastBridge = autoclass("org.hackintosh1980.blebridge.BroadcastBridge")
        self.LogBridge = autoclass("org.hackintosh1980.blebridge.LogBridge")
        if context is None:
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            context = PythonActivity.mActivity
        if context is None:
            raise RuntimeError("Android context ist nicht verfügbar")
        self.ctx = context.getApplicationContext()

    def start(self):
        self.start_adv()
        
    def start_adv(self):
        self.AdvBridge.start(self.ctx)

    def stop_adv(self):
        self.AdvBridge.stop()
    def start_gatt(self):
        gatt_cfg = os.path.join(config.DATA, "gatt_config.json")
        self.GattBridge.start(self.ctx, gatt_cfg)

    def stop_gatt(self):
        self.GattBridge.stop()

    def start_broadcast(self):
        mixed_path = os.path.join(config.DATA, "mixed.json")
        self.BroadcastBridge.start(self.ctx, mixed_path)

    def stop_broadcast(self):
        self.BroadcastBridge.stop()

    def start_log(self):
        self.LogBridge.start(self.ctx, "ble_log_dump.json")

    def stop_log(self):
        self.LogBridge.stop()

    def stop(self):
        self.stop_adv()
        self.stop_gatt()
        self.stop_broadcast()

def get_bridge(prefer_mock=False, context=None):
    global _bridge_instance
    if _bridge_instance is None:
        if is_android():
            _bridge_instance = BleBridgeAndroid(context=context)


        elif is_windows() or is_linux():
            try:
                from blebridge_desktop import blebridge_linux as desktop_bridge

                class DesktopBridgeAdapter:
                    def __init__(self, mod):
                        self._mod = mod
                        self._thread = None

                    def start(self):
                        import threading

                        if self._thread and self._thread.is_alive():
                            return

                        self._thread = threading.Thread(
                            target=self._mod.main,
                            daemon=True
                        )
                        self._thread.start()

                    def stop(self):
                        pass

                _bridge_instance = DesktopBridgeAdapter(desktop_bridge)

            except Exception as e:
                print("[BridgeManager] Linux/Windows bridge load failed:", e)

                class Dummy:
                    def __getattr__(self, name):
                        return lambda *a, **k: None

                _bridge_instance = Dummy()

        elif is_macos():
            try:
                from blebridge_desktop import blebridge_desktop_smooth as desktop_bridge

                class DesktopBridgeAdapter:
                    def __init__(self, mod):
                        self._mod = mod
                        self._thread = None

                    def start(self):
                        import threading

                        if self._thread and self._thread.is_alive():
                            return

                        self._thread = threading.Thread(
                            target=self._mod.main,
                            daemon=True
                        )
                        self._thread.start()

                    def stop(self):
                        pass

                _bridge_instance = DesktopBridgeAdapter(desktop_bridge)

            except Exception as e:
                print("[BridgeManager] macOS bridge load failed:", e)

                class Dummy:
                    def __getattr__(self, name):
                        return lambda *a, **k: None

                _bridge_instance = Dummy()
        else:
            # Fallback / unsupported platforms
            class Dummy:
                def __getattr__(self, name): return lambda *a, **k: None
            _bridge_instance = Dummy()
    return _bridge_instance
