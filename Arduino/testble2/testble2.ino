// main.ino

#include "power_manager.h"
#include "sensor.h"
#include "ble_bridge.h"
#include "logic_helper.h"
#include "hardware_init.h"
#include "ota_manager.h"

// PATCHER BEGIN: CIRCULATION_INCLUDE
#include "circulation_fan.h"
#include "circulation_fan2.h"
#include "circulation_fan3.h"
// PATCHER END: CIRCULATION_INCLUDE

#include "exhaust_fan.h" 
#include "sys_config.h"
#include "web_server.h" 
#include "light_control.h"
#include "grow_controller.h"
#include "esp_watch.h"
#include "esp_sntp.h"
#include "ble_scanner.h"
#include "esp_sntp.h" 
#include "system_reset.h" 
#include "plant_planner.h" 
ESPWatch watch;
BLEBridge bleBridge;
uint32_t device_confirmed_rev = 0;



// DIE EINZIGE DEFINITION DES SERVERS
WebServer server(80); 

// Hardware & Sensoren
TwoWire I2C_Sensor = TwoWire(0); // Bus 0 für Sensoren            
TwoWire I2C_RTC    = TwoWire(1); // Bus 1 für RTC (Eigener Bus!)

extern Adafruit_SHT31 sht31_ext;
extern Adafruit_SHT31 sht31_int;

extern bool externalSensorFound;
extern bool internalSensorFound;
int current_rev = 0; // Die aktuelle Revisionsnummer auf dem Gerät


// --- HILFSFUNKTION FÜR DIE UHRZEIT ---
String get_current_time_str() {
    struct tm timeinfo;
    if (!getLocalTime(&timeinfo)) {
        return "--:--"; // Zeigt das an, wenn noch kein WLAN/Sync da ist
    }
    char timeStr[10];
    // Format: HH:MM (z.B. 14:30)
    strftime(timeStr, sizeof(timeStr), "%H:%M", &timeinfo);
    return String(timeStr);
}
void setup() {
    // 1. System-Basis
    setCpuFrequencyMhz(240);
    Serial.begin(115200);

    // Wichtig: Zuerst die gespeicherten System-Configs laden (NVS → sysConfig)
    // damit Hardware-Initialisierung die richtigen, vom User gesetzten Pins nutzt.
    BLEDevice::init("LGS_Grow_Master");

    grow_controller_init();
    ota_manager_init();
    // Hardware danach initialisieren (nutzt jetzt aktualisierte sysConfig)
    init_hardware();

    if (sysConfig.pin_reset_button == -1) {
        Serial.println("SystemReset disabled (sysConfig).");
    } else {
        SystemReset::init(sysConfig.pin_reset_button);
    }

    // ==============================
    // 🔥 ZEITBASIS: NUR 1 MASTER
    // ==============================

    // 1. TZ zuerst setzen (WICHTIG!)
    configTzTime("CET-1CEST,M3.5.0/2,M10.5.0/3", "pool.ntp.org", "time.nist.gov");
    tzset();

    // 2. RTC NUR STARTEN, WENN AKTIVIERT!
    // ✔️ REPARIERT: Wenn Pins auf -1 stehen, wird die RTC-Hardware komplett ignoriert
    if (sysConfig.rtc_sda == -1 || sysConfig.rtc_scl == -1) {
        Serial.println("RTC im sysConfig DEAKTIVIERT. Überspringe RTC-Init.");
    } else {
        if (watch.begin(I2C_RTC)) {
            Serial.println("RTC Hardware gefunden.");
            if (watch.isRTCSet()) {
                Serial.println("RTC OK → nutze als Backup falls NTP fehlt");
                if (sntp_get_sync_status() != SNTP_SYNC_STATUS_COMPLETED) {
                    watch.syncFromRTC();  
                }
            } else {
                Serial.println("RTC ungesetzt → warte auf NTP");
            }
        } else {
            Serial.println("CRITICAL: RTC konfiguriert, fehlt aber physisch!");
        }
    }

    // 3. Licht NACH stabiler Zeitbasis
    light_init();

    Serial.println(">>> Hardware läuft (TIMEBASE STABIL) <<<");

    // 4. INFRA

    int wifi_mode = grow_controller_get_wifi_mode();
    if (wifi_mode == 0 || _wifi_ssid == "" || _wifi_ssid == "NULL") {
        WebModule::init_ap(_device_name.c_str());
    } else {
        WebModule::init(_wifi_ssid.c_str(), _wifi_password.c_str());
    }

    // 5. BACKGROUND
    // PATCHER BEGIN: CIRCULATION_INIT
    if (sysConfig.pin_circ_fan == -1 || sysConfig.pin_circ_tacho == -1) {
        Serial.println("Circulation Fan1 disabled (sysConfig). ");
    } else {
        circulation_fan_init(sysConfig.pin_circ_fan, sysConfig.pin_circ_tacho);
    }
    if (sysConfig.pin_circ_fan2 == -1 || sysConfig.pin_circ_tacho2 == -1) {
        Serial.println("Circulation Fan2 disabled (sysConfig). ");
    } else {
        circulation_fan2_init(sysConfig.pin_circ_fan2, sysConfig.pin_circ_tacho2);
    }
    if (sysConfig.pin_circ_fan3 == -1 || sysConfig.pin_circ_tacho3 == -1) {
        Serial.println("Circulation Fan3 disabled (sysConfig). ");
    } else {
        circulation_fan3_init(sysConfig.pin_circ_fan3, sysConfig.pin_circ_tacho3);
    }
// PATCHER END: CIRCULATION_INIT

    if (sysConfig.pin_exh_fan == -1 || sysConfig.pin_exh_tacho == -1) {
        Serial.println("Exhaust Fan disabled (sysConfig).");
    } else {
        exhaust_fan_init((uint8_t)sysConfig.pin_exh_fan, (uint8_t)sysConfig.pin_exh_tacho);
    }
    plant_planner_init();

    // ============================================================
    // ✔️ REPARIERT: SHT31 SENSOR-INITIALISIERUNG CODESCHUTZ
    // ============================================================
    if (sysConfig.i2c_sda == -1 || sysConfig.i2c_scl == -1) {
        Serial.println("Sensor-Bus deaktivert. Sensoren werden nicht gestartet.");
        externalSensorFound = false;
        internalSensorFound = false;
    } else {
        // Nur wenn Pins gültig sind, hängst du die Sensoren an den Bus
        externalSensorFound = sht31_ext.begin(0x44);
        internalSensorFound = sht31_int.begin(0x44);
        Serial.printf("Sensoren initialisiert. Ext: %s, Int: %s\n", 
                      externalSensorFound ? "OK" : "FEHLT", 
                      internalSensorFound ? "OK" : "FEHLT");
    }

    power_manager_init();

    // Initialize BLE subsystems according to persisted NVS values (authoritative)
    {
        Preferences p;
        p.begin("grow", false);
        bool bleScanPref = p.getBool("ble_scan_enabled", true);
        bool bleBridgePref = p.getBool("ble_bridge_enabled", true);
        p.end();

        Serial.printf("Boot (NVS): BLEScanner enabled = %d | BLEBridge enabled = %d\n", bleScanPref ? 1 : 0, bleBridgePref ? 1 : 0);

        // init scanner always (prepare), enforce enabled/disabled according to persisted flag
        BLEScanner::init();
        if (bleScanPref) {
            BLEScanner::enable();
        } else {
            BLEScanner::disable();
            Serial.println("BLE Scanner bleibt nach Boot deaktiviert (NVS)");
        }

        // init bridge and enforce
        bleBridge.begin();
        if (bleBridgePref) {
            bleBridge.enable();
        } else {
            bleBridge.disable();
            Serial.println("BLE Bridge bleibt nach Boot deaktiviert (NVS)");
        }
    }
}    
// ---------- LOOP ----------
// ---------- LOOP ----------

void loop() {
    WebModule::update();           // Web-Server am Leben erhalten
    SystemReset::update();         // <--- 3. PERMANENT DEN KNOPF ÜBERWACHEN
    
        
    // PATCHER BEGIN: CIRCULATION_UPDATE
    circulation_fan_update();
    circulation_fan2_update();
    circulation_fan3_update();
// PATCHER END: CIRCULATION_UPDATE
        
    
    exhaust_fan_update(); 

    // Beide Klimawerte sauber an das Lichtmodul übergeben (Push-Prinzip)
    light_control_set_humidity(getInternalHumidity());
    light_control_set_temperature(getTempIn()); // <-- DIESE ZEILE HAT GEFEHLT!

    light_update();                // Berechnet stur den Lichtzustand anhand der Systemzeit
    power_manager_update();
    if (grow_controller_ble_scan_enabled()) {
        BLEScanner::update();
    }

    // ==================== ZEIT-MANAGEMENT (PROFI-VERSION) ====================
    static uint32_t last_rtc_sync = 0;
    
    // Bedingung für RTC-Update: 
    // Entweder es ist eine Stunde vergangen (Routine-Abgleich)
    // ODER wir haben Internetzeit und die RTC meldet hardwareseitig, dass sie ungesetzt ist (Sofort-Heilung!)
    if ((millis() - last_rtc_sync > 3600000) || (sntp_get_sync_status() == SNTP_SYNC_STATUS_COMPLETED && !watch.isRTCSet())) { 
        
        if (sntp_get_sync_status() == SNTP_SYNC_STATUS_COMPLETED) {
            Serial.println("Zeitmanagement: NTP-Zeit valide. Aktualisiere Hardware-RTC & lösche OSF...");
            watch.writeToRTC();       // Schreibt Internetzeit in DS3231 und löscht OSF-Flag
            last_rtc_sync = millis(); // Timer zurücksetzen
        }
    }

    // KRISENVORSORGE: Falls die Systemuhr im Betrieb durch einen Software-Glitch auf 1970 fällt,
    // holen wir uns die Rettung aus der RTC (aber nur, wenn die RTC auch gestellt ist!)
    static uint32_t last_backup_check = 0;
    if (millis() - last_backup_check > 60000) { 
        last_backup_check = millis();
        if (time(nullptr) < 946684800 && watch.isRTCHealthy() && watch.isRTCSet()) { 
            Serial.println("NOTFALL: Systemzeit korrupt! Synchronisiere sofort mit intakter RTC...");
            watch.syncFromRTC();
        }
    }
    
    // ==================== BLE SCANNER RESTART ====================
    static uint32_t lastBLErestart = 0;
    if (millis() - lastBLErestart > 2*3600*1000UL) {   // alle 2 Stunden
        lastBLErestart = millis();
        BLEScanner::restart();        
    }
    
    // ==================== BLE BROADCAST (alle 5 Sek) ====================
    static uint32_t last_ble_broadcast = 0;
    if (millis() - last_ble_broadcast > 5000) {
        last_ble_broadcast = millis();
        if (grow_controller_ble_bridge_enabled()) {
            bleBridge.updateBroadcast(
                getTempExt(),            
                getExternalHumidity(),   
                getTempIn(),             
                getInternalHumidity(),   
                -256.0f,                   
                get_battery_voltage_now(), 
                circulation_fan_get_rpm()
            );
        }
    }

    yield();
}