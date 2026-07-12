from jnius import autoclass
from bridge_manager import get_bridge
from time import sleep
import os

# --- Globale Referenzen (Überlebenswichtig für JNI/Garbage Collection) ---
_wakelock = None
_bridge = None

def run_service():
    global _wakelock, _bridge
    
    try:
        # Java Klassen laden
        PythonService = autoclass('org.kivy.android.PythonService')
        Context = autoclass('android.content.Context')
        PowerManager = autoclass('android.os.PowerManager')
        
        service = PythonService.mService
        if not service:
            print("[Service] Error: mService context is None!")
            return

        # --- 1. WAKELOCK FIX ---
        pm = service.getSystemService(Context.POWER_SERVICE)
        # Wir nutzen einen sehr spezifischen Tag für das Debugging
        _wakelock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "LGS:PermanentWakeLock")
        
        # SetReferenceCounted(False) sorgt dafür, dass ein acquire() reicht, 
        # egal wie oft release() gerufen wurde (und umgekehrt)
        _wakelock.setReferenceCounted(False)
        
        if not _wakelock.isHeld():
            # Acquire mit extrem langem Timeout (ca. 10 Jahre), 
            # das ist stabiler als die No-Args Version auf manchen Android 13 Geräten
            _wakelock.acquire(10 * 365 * 24 * 60 * 60 * 1000) 
            print("[Service] WakeLock dauerhaft akquiriert")

        # --- 2. FOREGROUND NOTIFICATION ---
        # Wichtig: Der String-Klassenname muss exakt zu deiner buildozer.spec passen
        try:
            ServiceClass = autoclass("org.hackintosh1980.espgrowcontroller.ServiceBle_service")
            # Wir nutzen den Service selbst als Kontext
            ServiceClass.start(service, "BLE Bridge: Aktiv im Hintergrund")
            print("[Service] Foreground Service Notification gestartet")
        except Exception as e:
            print(f"[Service] Notification konnte nicht gestartet werden: {e}")

        # --- 3. BRIDGE INITIALISIERUNG ---
        _bridge = get_bridge()
        _bridge.start()             # ADV + GATT
        _bridge.start_broadcast()   # Dein Custom Java Broadcast
        print("[Service] Alle Bridges aktiv")

        # --- 4. KEEP ALIVE LOOP ---
        # Diese Loop hält den Python-Interpreter Prozess am Leben
        print("[Service] Starte Main-Loop (Heartbeat alle 30s)")
        while True:
            # Hier nur schlafen, die Arbeit passiert in den Java-Threads der Bridge
            sleep(30)
            
    except Exception as e:
        print(f"[Service] FATAL ERROR: {e}")
    finally:
        cleanup()

def cleanup():
    global _wakelock, _bridge
    print("[Service] Cleanup eingeleitet...")
    try:
        if _bridge:
            _bridge.stop()
    except:
        pass
    try:
        if _wakelock and _wakelock.isHeld():
            _wakelock.release()
            print("[Service] WakeLock freigegeben")
    except:
        pass

if __name__ == '__main__':
    run_service()