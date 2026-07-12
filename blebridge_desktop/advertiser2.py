import asyncio
from bleak import BleakScanner, BleakClient

# Hinweis: Bleak ist primär für Clients. 
# Für reines Advertising auf Linux ohne Kopfschmerzen 
# nutzt man oft das System-Tool 'bluetoothctl'.

import os

def start_linux_advertising():
    print("Starte Advertising auf Linux via bluetoothctl...")
    # Wir nutzen OS-Calls, da das stabiler ist als viele Python-Libs auf Linux
    os.system("bluetoothctl power on")
    os.system("bluetoothctl advertise on")
    print(">>> SENDET JETZT: Gerät ist sichtbar <<<")

if __name__ == "__main__":
    try:
        start_linux_advertising()
        # Loop um das Skript am Laufen zu halten
        while True:
            pass
    except KeyboardInterrupt:
        os.system("bluetoothctl advertise off")
        print("\nGestoppt.")
