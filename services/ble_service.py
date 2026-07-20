from jnius import autoclass
from bridge_manager import get_bridge
from time import sleep

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

        # Der Service wurde bereits durch core.py als Foreground Service gestartet.
        # Ein erneutes start() auf sich selbst ist weder fuer die Notification noch
        # fuer das Keep-alive erforderlich und erzeugt nur einen zweiten Start-Intent.
        print(f"[Service] Foreground Service aktiv: {service.getClass().getName()}")

        # --- 2. BRIDGE INITIALISIERUNG ---
        _bridge = get_bridge(context=service)
        _bridge.start()             # ADV + GATT
        _bridge.start_broadcast()   # Dein Custom Java Broadcast
        print("[Service] Alle Bridges aktiv")

        # --- 3. KEEP ALIVE LOOP ---
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
