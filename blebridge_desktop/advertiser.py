import os
import time

def start_linux_advertising():
    print("Konfiguriere Bluetooth Advertising...")
    
    # 1. Bluetooth sicherstellen
    os.system("bluetoothctl power on")
    
    # 2. Altes Advertising stoppen, falls noch was läuft
    os.system("bluetoothctl advertise off > /dev/null 2>&1")
    
    # 3. Ein strukturiertes Advertising-Paket definieren
    # Wir nutzen 'manufacturer' für Raw Data (Beispiel: 0xffff ist Test-ID, dann 0x12 0x34)
    # 'name' setzt den Local Name
    cmd = (
        "bluetoothctl << EOF\n"
        "menu advertising\n"
        "clear\n"
        "name MAC-BLE\n"
        "manufacturer 0xffff 0x12 0x34 0x56\n" 
        "back\n"
        "advertise on\n"
        "exit\n"
        "EOF"
    )
    
    os.system(cmd)
    print(">>> SENDET JETZT: Name 'MAC-BLE' & Raw Data (123456) <<<")

if __name__ == "__main__":
    try:
        start_linux_advertising()
        print("Drücke Strg+C zum Beenden.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStoppe Advertising...")
        os.system("bluetoothctl advertise off")
        print("Gestoppt.")/home/domi/vivosun-setup/blebridge_desktop/advertiser.py
