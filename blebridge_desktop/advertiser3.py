import os
import time

def cmd(c):
    os.system(f"bluetoothctl {c}")

def start_linux_advertising():
    print("Starte Advertising via bluetoothctl…")

    cmd("power on")
    cmd("discoverable on")
    cmd("pairable off")
    cmd("system-alias LivingNode")

    # sicherstellen, dass nix anderes wirbt
    cmd("advertise off")
    time.sleep(0.5)

    cmd("advertise on")
    print(">>> SENDET JETZT: LivingNode <<<")

if __name__ == "__main__":
    try:
        start_linux_advertising()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        cmd("advertise off")
        print("\nGestoppt.")

