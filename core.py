# core.py – FINAL (stabil)
# © 2025 Dominik Rosenthal

import os
from platform_utils import is_android as _platform_is_android

import os
import sys
from kivy.app import App
import config
from bridge_manager import get_bridge
from ble_watchdog_manager import BleDumpWatchdog
from decoder import start_decoder_thread, stop_decoder_thread, update_bridge_state, step_decode
from web_client import WebClientThread
# ------------------------------------------------------------
# 🔥 100 % zuverlässige Android-Erkennung
# ------------------------------------------------------------
def is_android():
    # Delegate to the centralized helper
    return _platform_is_android()


# globale Instanzen
_bridge = None
_ble_watchdog = None
_web_client = None

# ------------------------------------------------------------
# Watchdog Callback
# ------------------------------------------------------------
def _wd_callback(status):
    print(f"[Core] Watchdog: {status['status']} | alive={status['alive']} | last_seen={status['last_seen']}")

    update_bridge_state(
        alive=status["alive"],
        status=status["status"],
        last_seen=status["last_seen"]
    )
# ------------------------------------------------------------
# decoded.json löschen
# ------------------------------------------------------------
def _cleanup_decoded():
    try:
        path = os.path.join(config.DATA, "decoded.json")
        if os.path.exists(path):
            os.remove(path)
            print("[Core] decoded.json entfernt")
    except:
        pass
# ------------------------------------------------------------
# web_dump.json löschen / clean
# ------------------------------------------------------------
def _cleanup_web_dump():
    try:
        import json
        path = os.path.join(config.DATA, "web_dump.json")

        with open(path, "w", encoding="utf-8") as f:
            json.dump({}, f)  # ⚠️ WICHTIG: dict, nicht Liste!

        print(f"[Core] web_dump.json geleert: {path}")

    except Exception as e:
        print("[Core] web_dump cleanup failed:", e)
# ------------------------------------------------------------
# ble_log_dump.json löschen / clean
# ------------------------------------------------------------
def _cleanup_ble_log_dump():
    try:
        import json
        path = os.path.join(config.DATA, "ble_log_dump.json")

        with open(path, "w", encoding="utf-8") as f:
            json.dump([], f)

        print(f"[Core] ble_log_dump.json geleert: {path}")

    except Exception as e:
        print("[Core] ble_log_dump cleanup failed:", e)


def _cleanup_ble_dump():
    try:
        import json
        path = os.path.join(config.DATA, "ble_dump.json")

        with open(path, "w", encoding="utf-8") as f:
            json.dump([], f)

        print(f"[Core] ble_dump.json geleert: {path}")

    except Exception as e:
        print("[Core] ble_dump cleanup failed:", e)
# ------------------------------------------------------------
# START – von main.py
# ------------------------------------------------------------
def start():
    """
    Startet das Core-System im Foreground Service Modus auf Android:
    - Entfernt alte Dumps (decoded.json, ble_dump.json, ble_log_dump.json)
    - Startet Foreground BLE Service via PythonService
    - Initialisiert Bridges (ADV + GATT + Broadcast)
    - Startet Decoder-Thread
    - Startet Watchdog
    """
    global _bridge, _ble_watchdog

    print("[Core] Starte Core (Foreground Service Mode)…")
    print("[Core] is_android():", is_android())

    # -----------------------------------------------------
    # Alte Daten sauber entfernen
    # -----------------------------------------------------
    _cleanup_decoded()
    _cleanup_ble_dump()
    _cleanup_ble_log_dump() 
    _cleanup_web_dump()   # 🔥 NEU
    # -----------------------------------------------------
    # Android Foreground Service starten
    # -----------------------------------------------------
    if is_android():


        from jnius import autoclass

        # Activity & Service holen
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        activity = PythonActivity.mActivity

        # PythonService starten (Foreground)
        ServiceBle = autoclass("org.hackintosh1980.espgrowcontroller.ServiceBle_service")
        ServiceBle.start(activity, "BLE service running")
        print("[Core] BLE Python Service gestartet (Foreground)")

        # -------------------------------------------------
        # Bridges initialisieren (ADV/GATT + Broadcast)
        # -------------------------------------------------
        try:
            _bridge = get_bridge(prefer_mock=False)
            _bridge.start()             # ADV + GATT starten
            _bridge.start_broadcast()   # Broadcast starten
            print("[Core] Android-Bridges gestartet (ADV + GATT + BROADCAST)")
        except Exception as e:
            print("[Core] Bridge start failed:", e)


    elif not is_android():
        try:
            _bridge = get_bridge(prefer_mock=False)
            _bridge.start()
            print("[Core] Desktop Bridge gestartet")
        except Exception as e:
            print("[Core] Desktop Bridge start failed:", e)


    # -----------------------------------------------------
    # WebClient starten (Die neue Datenquelle)
    # -----------------------------------------------------
    global _web_client
    try:
        _web_client = WebClientThread(interval=config.get_refresh_interval())
        _web_client.start()
        print("[Core] WebClient-Thread gestartet")
    except Exception as e:
        print("[Core] WebClient start failed:", e)    
        
    # -----------------------------------------------------
    # Decoder starten (liefert decoded.json)
    # -----------------------------------------------------
    try:
        start_decoder_thread(config.get_refresh_interval())
        step_decode()  # 🔥 EINMAL SOFORT
        print("[Core] Decoder-Thread gestartet")
    except Exception as e:
        print("[Core] Decoder-Thread start failed:", e)

    # -----------------------------------------------------
    # Watchdog starten
    # -----------------------------------------------------
    try:
        _ble_watchdog = BleDumpWatchdog(
            timeout=config.get_stale_timeout(),
            interval=config.get_refresh_interval(),
            callback=_wd_callback
        )
        _ble_watchdog.start()
        print("[Core] Watchdog gestartet")
    except Exception as e:
        print("[Core] Watchdog start failed:", e)

    print("[Core] System läuft stabil im Hintergrund (Foreground Service Active).")
def is_broadcast_active():
    return _broadcast_active

def toggle_broadcast():
    global _broadcast_active
    if _broadcast_active:
        stop_broadcast_bridge()
        _broadcast_active = False
    else:
        start_broadcast_bridge()
        _broadcast_active = True
    return _broadcast_active
# ------------------------------------------------------------
# ADV ONLY
# ------------------------------------------------------------
def restart_adv_bridge():
    from kivy.clock import Clock
    if not is_android():
        return
    Clock.schedule_once(_restart_adv_safe, 0)

def _restart_adv_safe(dt):
    global _bridge
    try:
        _bridge = get_bridge()        # 🔒 IMMER neu holen
        try:
            _bridge.stop_adv()        # darf scheitern
        except Exception:
            pass

        _bridge.start_adv()           # MUSS laufen
        print("[Core] ADV Bridge restarted")

    except Exception as e:
        print("[Core] ADV restart failed:", e)

# LogBridge

def start_log_bridge():
    from kivy.clock import Clock
    if not is_android():
        return
    Clock.schedule_once(_start_log_safe, 0)

def _start_log_safe(dt):
    global _bridge
    try:
        _bridge = get_bridge()
        _bridge.start_log()
        print("[Core] LOG Bridge started")
    except Exception as e:
        print("[Core] LOG start failed:", e)




def _stop_log_safe(dt):
    global _bridge
    try:
        _bridge = get_bridge()
        _bridge.stop_log()
        print("[Core] LOG Bridge stopped")
    except Exception as e:
        print("[Core] LOG stop failed:", e)



# ------------------------------------------------------------
# GATT ONLY – Stop
# ------------------------------------------------------------
def stop_gatt_bridge():
    from kivy.clock import Clock
    if not is_android():
        return
    Clock.schedule_once(_stop_gatt_safe, 0)

def _stop_gatt_safe(dt):
    global _bridge
    try:
        _bridge = get_bridge()        # 🔒 Immer frische Instanz
        _bridge.stop_gatt()
        print("[Core] GATT Bridge stopped")
    except Exception as e:
        print("[Core] GATT stop failed:", e)
# ------------------------------------------------------------
# GATT ONLY
# ------------------------------------------------------------
def restart_gatt_bridge():
    from kivy.clock import Clock
    if not is_android():
        return
    Clock.schedule_once(_restart_gatt_safe, 0)

def _restart_gatt_safe(dt):
    global _bridge
    try:
        _bridge = get_bridge()        # 🔒 IMMER neu holen
        try:
            _bridge.stop_gatt()
        except Exception:
            pass

        _bridge.start_gatt()
        print("[Core] GATT Bridge restarted")

    except Exception as e:
        print("[Core] GATT restart failed:", e)
# ------------------------------------------------------------
# LEGACY / BOTH
# ------------------------------------------------------------
def restart_bridge():
    from kivy.clock import Clock
    if not is_android():
        return
    Clock.schedule_once(_restart_bridge_safe, 0)

def _restart_bridge_safe(dt):
    global _bridge
    try:
        _bridge = get_bridge()        # 🔒 neu holen

        try:
            _bridge.stop()
        except Exception:
            pass

        _bridge.start()
        print("[Core] ADV + GATT Bridges restarted")

    except Exception as e:
        print("[Core] Bridge restart failed:", e)

# ------------------------------------------------------------
# LOG ONLY – Restart Semantik
# ------------------------------------------------------------
def restart_log_bridge():
    from kivy.clock import Clock
    if not is_android():
        return
    Clock.schedule_once(_restart_log_safe, 0)

def _restart_log_safe(dt):
    global _bridge
    try:
        _bridge = get_bridge()  # 🔒 Immer neu holen

        try:
            _bridge.stop_log()  # darf fehlschlagen, wenn nicht läuft
        except Exception:
            pass

        _bridge.start_log()  # MUSS laufen
        print("[Core] LOG Bridge restarted")

    except Exception as e:
        print("[Core] LOG restart failed:", e)
# ------------------------------------------------------------
# LOG ONLY – Stop
# ------------------------------------------------------------
def stop_log_bridge():
    from kivy.clock import Clock
    if not is_android():
        return
    Clock.schedule_once(_stop_log_safe, 0)

def _stop_log_safe(dt):
    global _bridge
    try:
        _bridge = get_bridge()        # 🔒 Immer frische Instanz
        _bridge.stop_log()
        print("[Core] LOG Bridge stopped")
    except Exception as e:
        print("[Core] LOG stop failed:", e)
# ------------------------------------------------------------
# ADV ONLY – Stop
# ------------------------------------------------------------
def stop_adv_bridge():
    from kivy.clock import Clock
    if not is_android():
        return
    Clock.schedule_once(_stop_adv_safe, 0)

def _stop_adv_safe(dt):
    global _bridge
    try:
        _bridge = get_bridge()        # 🔒 Immer frische Instanz
        _bridge.stop_adv()
        print("[Core] ADV Bridge stopped")
    except Exception as e:
        print("[Core] ADV stop failed:", e)

# ------------------------------------------------------------
# BROADCAST ONLY – Start / Stop / Restart
# ------------------------------------------------------------

def start_broadcast_bridge():
    from kivy.clock import Clock
    if not is_android():
        return
    Clock.schedule_once(_start_broadcast_safe, 0)

def _start_broadcast_safe(dt):
    global _bridge
    try:
        _bridge = get_bridge()
        _bridge.start_broadcast()
        print("[Core] BROADCAST Bridge started")
    except Exception as e:
        print("[Core] BROADCAST start failed:", e)


def stop_broadcast_bridge():
    from kivy.clock import Clock
    if not is_android():
        return
    Clock.schedule_once(_stop_broadcast_safe, 0)

def _stop_broadcast_safe(dt):
    global _bridge
    try:
        _bridge = get_bridge()
        _bridge.stop_broadcast()
        print("[Core] BROADCAST Bridge stopped")
    except Exception as e:
        print("[Core] BROADCAST stop failed:", e)


def restart_broadcast_bridge():
    from kivy.clock import Clock
    if not is_android():
        return
    Clock.schedule_once(_restart_broadcast_safe, 0)

def _restart_broadcast_safe(dt):
    global _bridge
    try:
        _bridge = get_bridge()
        try:
            _bridge.stop_broadcast()
        except:
            pass
        _bridge.start_broadcast()
        print("[Core] BROADCAST Bridge restarted")
    except Exception as e:
        print("[Core] BROADCAST restart failed:", e)


# ------------------------------------------------------------
# STOP – Bereinigt alle Threads, Hintergrund-Dienste und Bridges
# ------------------------------------------------------------
def stop():
    global _bridge, _ble_watchdog, _web_client

    print("[Core] Stoppe System vollständig…")

    # 1. WebClient-Thread beenden (Die Datenquelle)
    try:
        if _web_client:
            # Falls der WebClientThread eine eigene stop()-Methode hat
            if hasattr(_web_client, 'stop'):
                _web_client.stop()
            # Falls er via Event/Flag läuft (Standard-Thread-Pattern)
            elif hasattr(_web_client, 'running'):
                _web_client.running = False
            
            print("[Core] WebClient-Thread gestoppt")
    except Exception as e:
        print("[Core] WebClient-Thread stop failed:", e)

    # 2. Decoder-Thread stoppen
    try:
        # Importiert die Stop-Logik direkt aus deinem decoder-Modul
        import decoder

        decoder.stop_decoder_thread()
        print("[Core] Decoder-Thread gestoppt")
    except Exception as e:
        print("[Core] Decoder-Thread stop failed:", e)

    # 3. BLE Watchdog stoppen
    try:
        if _ble_watchdog:
            _ble_watchdog.stop()
            print("[Core] Watchdog gestoppt")
    except Exception as e:
        print("[Core] Watchdog stop failed:", e)

    # 4. Android-Bridges stoppen
    try:
        if is_android() and _bridge:
            _bridge.stop()
            print("[Core] Native Bridges gestoppt")
    except Exception as e:
        print("[Core] Bridge stop failed:", e)

    # 5. Android Foreground Service hart beenden
    try:
        if is_android():
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            activity = PythonActivity.mActivity
            
            ServiceBle = autoclass("org.hackintosh1980.espgrowcontroller.ServiceBle_service")
            # Stoppt den Service über die laufende Android-Activity
            ServiceBle.stop(activity)
            print("[Core] Android BLE Python Foreground Service gestoppt")
    except Exception as e:
        print("[Core] Foreground Service stop failed:", e)

    print("[Core] Shutdown komplett abgeschlossen.")

from kivy.app import App
import sys
import os

def restart_app():
    if is_android():
        from jnius import autoclass

        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Intent = autoclass('android.content.Intent')

        activity = PythonActivity.mActivity
        intent = activity.getPackageManager().getLaunchIntentForPackage(
            activity.getPackageName()
        )

        intent.addFlags(
            Intent.FLAG_ACTIVITY_CLEAR_TOP |
            Intent.FLAG_ACTIVITY_NEW_TASK
        )

        activity.startActivity(intent)
        activity.finish()

    else:
        app = App.get_running_app()
        if app:
            app.stop()

        os.execv(sys.executable, [sys.executable] + sys.argv)


# ------------------------------------------------------------
# WEBCLIENT ONLY – Start / Stop (Für Debug Buttons)
# ------------------------------------------------------------

def start_web_client_bridge():
    from kivy.clock import Clock
    Clock.schedule_once(_start_web_client_safe, 0)

def _start_web_client_safe(dt):
    global _web_client

    try:
        if _web_client and _web_client.is_alive():
            print("[Core] WebClient läuft bereits")
            return

        _web_client = WebClientThread(
            interval=config.get_refresh_interval()
        )
        _web_client.start()

        print("[Core] WebClient-Thread separat gestartet")

    except Exception as e:
        print("[Core] WebClient start failed:", e)

def stop_web_client_bridge():
    from kivy.clock import Clock
    Clock.schedule_once(_stop_web_client_safe, 0)

def _stop_web_client_safe(dt):
    global _web_client

    try:
        if _web_client and _web_client.is_alive():
            _web_client.stop()
            _web_client.join(timeout=3)

            _web_client = None

            print("[Core] WebClient-Thread separat gestoppt")
        else:
            print("[Core] WebClient war nicht aktiv")

    except Exception as e:
        print("[Core] WebClient stop failed:", e)


def start_decoder_bridge():
    from kivy.clock import Clock
    Clock.schedule_once(_start_decoder_safe, 0)


def _start_decoder_safe(dt):
    try:
        start_decoder_thread(config.get_refresh_interval())

        # Optional: einmal sofort dekodieren
        step_decode()

        print("[Core] Decoder separat gestartet")

    except Exception as e:
        print("[Core] Decoder start failed:", e)

def stop_decoder_bridge():
    from kivy.clock import Clock
    Clock.schedule_once(_stop_decoder_safe, 0)


def _stop_decoder_safe(dt):
    try:
        stop_decoder_thread()
        print("[Core] Decoder separat gestoppt")

    except Exception as e:
        print("[Core] Decoder stop failed:", e)