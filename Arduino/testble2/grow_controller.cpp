//grow_controller.cpp - Hauptsteuerung für das Grow-Controller-Projekt
///////////////////////////////////////////////////////////////////////////////
// !!! ABSOLUTES GESETZ: DAS TARGET-REVISION-PRINZIP (C++ / ESP32) !!!
// -------------------------------------------------------------------------
// 1. HARDWARE FOLGT TARGET: Die Loop darf NIEMALS direkt auf UI-Inputs reagieren.
//    Sie vergleicht permanent: 'target_val' vs 'effective_val'.
//
// 2. REVISION-CONFIRMATION: Der ESP32 bestätigt eine Änderung NUR, indem er 
//    die empfangene 'rev' (Revision) im Status-Paket unverändert zurücksendet.
//


#include "grow_controller.h"
#include <WiFi.h>
#include <rom/rtc.h>
#include "ble_scanner.h"
#include "ble_bridge.h"
#include "sys_config.h"
#include "hardware_init.h"
#include "circulation_fan.h"
#include "exhaust_fan.h"
#include "light_control.h"
// 1. GLOBALE DEFINITION (Ohne static!)
extern int current_rev;
Preferences growPrefs;
String _device_name = "GrowBox-Alpha";
String _wifi_ssid = "";
String _wifi_password = "";


String _web_username = "admin";
String _web_password = "1234";

// 2. MODUL-INTERNE VARIABLEN

static int _log_level = 2;
static int _wifi_mode = 1; 
static uint32_t grow_controller_rev = 0;
static bool _ble_bridge_enabled = true;
static bool _ble_scan_enabled = true;



void grow_controller_init() {
    growPrefs.begin("grow", false);
    _wifi_mode = growPrefs.getInt("wifi_mode", 1);
    _wifi_ssid = growPrefs.getString("ssid", ""); 
    _wifi_password = growPrefs.getString("password", "");
    _device_name = growPrefs.getString("dev_name", "LGS_Grow_Master");
    
    // NEU: Werte aus dem NVS laden, falls leer -> Defaults ("admin" / "1234")
    _web_username = growPrefs.getString("web_user", "admin");
    _web_password = growPrefs.getString("web_pass", "1234");
    
    // GPIOs aus den Preferences laden (Fallbacks sind die sysConfig Defaults)
    sysConfig.pin_reset_button = growPrefs.getInt("p_reset", sysConfig.pin_reset_button);
    sysConfig.pin_circ_fan     = growPrefs.getInt("p_c_fan", sysConfig.pin_circ_fan);
    sysConfig.pin_circ_tacho   = growPrefs.getInt("p_c_tac", sysConfig.pin_circ_tacho);
    sysConfig.pin_circ_tacho_pull = growPrefs.getInt("p_c_tac_pull", 1);
    sysConfig.pin_exh_fan      = growPrefs.getInt("p_e_fan", sysConfig.pin_exh_fan);
    sysConfig.pin_exh_tacho    = growPrefs.getInt("p_e_tac", sysConfig.pin_exh_tacho);
    sysConfig.pin_exh_tacho_pull = growPrefs.getInt("p_e_tac_pull", 1);
    sysConfig.pin_light        = growPrefs.getInt("p_light", sysConfig.pin_light);
    sysConfig.i2c_sda          = growPrefs.getInt("p_i2c_sda", sysConfig.i2c_sda);
    sysConfig.i2c_scl          = growPrefs.getInt("p_i2c_scl", sysConfig.i2c_scl);
    sysConfig.rtc_sda          = growPrefs.getInt("p_rtc_sda", sysConfig.rtc_sda);
    sysConfig.rtc_scl          = growPrefs.getInt("p_rtc_scl", sysConfig.rtc_scl);
    sysConfig.pin_bat          = growPrefs.getInt("p_bat", sysConfig.pin_bat);
    sysConfig.pin_bat_pull     = growPrefs.getInt("p_bat_pull", sysConfig.pin_bat_pull);
    grow_controller_rev = growPrefs.getUInt("rev_grow", 0);

    // BLE enabled flags (defaults true)
    _ble_bridge_enabled = growPrefs.getBool("ble_bridge_enabled", true);
    _ble_scan_enabled = growPrefs.getBool("ble_scan_enabled", true);
    // NEU: Den geladenen Zustand direkt an das BLE-Subsystem übergeben!
    BLEScanner::init();

    if (_ble_scan_enabled)
        BLEScanner::enable();
    else
        BLEScanner::disable();
    
}

void grow_controller_save_state() {
    growPrefs.putInt("log_level", _log_level);
    growPrefs.putString("dev_name", _device_name);
    growPrefs.putInt("wifi_mode", _wifi_mode); // Modus sichern
    growPrefs.putString("wifi_ssid", _wifi_ssid);
    growPrefs.putString("wifi_pass", _wifi_password);
}

void grow_controller_process_json(JsonObject doc) {
    // Debug: show the full incoming JSON so we can see received keys/values
    Serial.println("JSON empfangen!");
    serializeJson(doc, Serial);
    Serial.println();
    bool gpio_changed = false;
    
    if (doc.containsKey("rev_grow")) {

        grow_controller_rev = doc["rev_grow"].as<uint32_t>();

        growPrefs.putUInt(
            "rev_grow",
            grow_controller_rev
        );

        Serial.print("[GROW] Neue Revision übernommen: ");
        Serial.println(grow_controller_rev);
    }    
    // ================= COMMAND HANDLING =================
    if (doc.containsKey("command")) {
        String cmd = doc["command"].as<String>();
    
        Serial.print("Command erhalten: ");
        Serial.println(cmd);
    
        if (cmd == "soft_reset") {
            Serial.println("Soft Reset...");
            delay(500);
            ESP.restart();
        }
    
        else if (cmd == "factory_reset") {
            Serial.println("Factory Reset...");
            // Erst BLE-spezifische gespeicherte MACs löschen, damit ein echter Factory-Reset erfolgt
            BLEScanner::clear_saved_macs();
            growPrefs.clear();   // 🔥 ALLES LÖSCHEN (Grow-Namespace)
            // Nach Factory-Reset: Standardmäßig BLE Bridge + Scanner wieder aktivieren
            growPrefs.putBool("ble_bridge_enabled", true);
            growPrefs.putBool("ble_scan_enabled", true);
            delay(500);
            ESP.restart();
        }
    
        else if (cmd == "sync_time") {
            Serial.println("Sync Time Trigger");
            // 👉 hier ggf. NTP oder RTC sync triggern
        }
    
        else if (cmd == "test") {
            Serial.println("Test Command OK");
        }
    }    
    // Falls neue WiFi Daten kommen
    if (doc.containsKey("wifi_ssid")) {
        String new_ssid = doc["wifi_ssid"].as<String>();
        growPrefs.putString("ssid", new_ssid);
        _wifi_ssid = new_ssid;
    }

    if (doc.containsKey("wifi_pw")) {
        String new_pw = doc["wifi_pw"].as<String>();
        growPrefs.putString("password", new_pw);
        _wifi_password = new_pw;
    }

    // ================= SECURITY / HTTP CREDENTIALS HANDLING =================
    if (doc.containsKey("sec_user")) {
        String new_user = doc["sec_user"].as<String>();
        // Nur speichern, wenn das Feld nicht komplett leer ist
        if (new_user.length() > 0) {
            growPrefs.putString("web_user", new_user);
            _web_username = new_user;
            Serial.print("Neuer HTTP-User empfangen: ");
            Serial.println(_web_username);
        }
    }

    if (doc.containsKey("sec_pw")) {
        String new_pw = doc["sec_pw"].as<String>();
        if (new_pw.length() > 0) {
            growPrefs.putString("web_pass", new_pw);
            _web_password = new_pw;
            Serial.println("Neues HTTP-Passwort empfangen und gespeichert.");
        }
    }    
    if (doc.containsKey("wifi_mode")) {
        int mode = doc["wifi_mode"];
        growPrefs.putInt("wifi_mode", mode);
        _wifi_mode = mode;   // 🔥 FEHLT BEI DIR
    }

    // ================= BLE SENSOR PAIRING HANDLING =================
    if (doc.containsKey("pair_outside")) {
        String mac_outside = doc["pair_outside"].as<String>();
        if (mac_outside.length() == 17) {
            // Wir reichen die MAC direkt an das BLE-Subsystem weiter
            BLEScanner::set_paired_mac("outside", mac_outside);
            Serial.print("Zentraler Controller: outside neu zugewiesen -> ");
            Serial.println(mac_outside);
            // Kein Reboot nötig! BLE zieht die neue Adresse im laufenden Betrieb
        }
    }

    if (doc.containsKey("pair_inside")) {
        String mac_inside = doc["pair_inside"].as<String>();
        if (mac_inside.length() == 17) {
            BLEScanner::set_paired_mac("inside", mac_inside);
            Serial.print("Zentraler Controller: inside neu zugewiesen -> ");
            Serial.println(mac_inside);
        }
    }

    // === BLE enable/disable via overlay ===
    if (doc.containsKey("ble_bridge")) {
        bool enable = doc["ble_bridge"];
        _ble_bridge_enabled = enable;                   
        
        Preferences p;
        p.begin("grow", false);
        p.putBool("ble_bridge_enabled", enable);
        p.end();
        
        if (enable) {
            bleBridge.enable();
            Serial.println("BLE Bridge aktiviert via Overlay.");
        } else {
            bleBridge.disable();
            Serial.println("BLE Bridge deaktiviert via Overlay.");
        }
    }

    // === BLE enable/disable via overlay ===
    if (doc.containsKey("ble_scan")) {
        bool enable = doc["ble_scan"].as<bool>();
        _ble_scan_enabled = enable;

        Preferences p;
        p.begin("grow", false);
        p.putBool("ble_scan_enabled", enable);
        p.end();

        if (enable) {
            BLEScanner::enable();
            Serial.println("✅ BLE Scanner AKTIVIERT via Overlay");
        } else {
            BLEScanner::disable();
            Serial.println("⛔ BLE Scanner DEAKTIVIERT via Overlay");
        }
    }

    // ---- GPIO EINSPEISUNG (Target-Revision-Prinzip) ----

    // ---- GPIO EINSPEISUNG (Target-Revision-Prinzip) ----

    if (doc.containsKey("p_reset")) {
        int v = doc["p_reset"];
        growPrefs.putInt("p_reset", v);
        sysConfig.pin_reset_button = v;
        gpio_changed = true;
    }

    if (doc.containsKey("p_c_fan")) {
        int v = doc["p_c_fan"];
        growPrefs.putInt("p_c_fan", v);
        sysConfig.pin_circ_fan = v;
        gpio_changed = true;
    }

    if (doc.containsKey("p_c_tac")) {
        int v = doc["p_c_tac"];
        growPrefs.putInt("p_c_tac", v);
        sysConfig.pin_circ_tacho = v;
        gpio_changed = true;
    }

    if (doc.containsKey("p_e_fan")) {
        int v = doc["p_e_fan"];
        growPrefs.putInt("p_e_fan", v);
        sysConfig.pin_exh_fan = v;
        gpio_changed = true;
    }

    if (doc.containsKey("p_e_tac")) {
        int v = doc["p_e_tac"];
        growPrefs.putInt("p_e_tac", v);
        sysConfig.pin_exh_tacho = v;
        gpio_changed = true;
    }

    if (doc.containsKey("p_light")) {
        int v = doc["p_light"];
        growPrefs.putInt("p_light", v);
        sysConfig.pin_light = v;
        gpio_changed = true;
    }

    if (doc.containsKey("p_i2c_sda")) {
        int v = doc["p_i2c_sda"];
        growPrefs.putInt("p_i2c_sda", v);
        sysConfig.i2c_sda = v;
        gpio_changed = true;
    }

    if (doc.containsKey("p_i2c_scl")) {
        int v = doc["p_i2c_scl"];
        growPrefs.putInt("p_i2c_scl", v);
        sysConfig.i2c_scl = v;
        gpio_changed = true;
    }

    if (doc.containsKey("p_rtc_sda")) {
        int v = doc["p_rtc_sda"];
        growPrefs.putInt("p_rtc_sda", v);
        sysConfig.rtc_sda = v;
        gpio_changed = true;
    }

    if (doc.containsKey("p_rtc_scl")) {
        int v = doc["p_rtc_scl"];
        growPrefs.putInt("p_rtc_scl", v);
        sysConfig.rtc_scl = v;
        gpio_changed = true;
    }

    if (doc.containsKey("p_bat")) {
        int v = doc["p_bat"];
        growPrefs.putInt("p_bat", v);
        sysConfig.pin_bat = v;
        gpio_changed = true;
    }

    if (doc.containsKey("p_c_tac_pull")) {
        int v = doc["p_c_tac_pull"];
        growPrefs.putInt("p_c_tac_pull", v);
        sysConfig.pin_circ_tacho_pull = v;
        gpio_changed = true;
    }

    if (doc.containsKey("p_e_tac_pull")) {
        int v = doc["p_e_tac_pull"];
        growPrefs.putInt("p_e_tac_pull", v);
        sysConfig.pin_exh_tacho_pull = v;
        gpio_changed = true;
    }

    if (doc.containsKey("p_bat_pull")) {
        int v = doc["p_bat_pull"];
        growPrefs.putInt("p_bat_pull", v);
        sysConfig.pin_bat_pull = v;
        gpio_changed = true;
    }
    if (gpio_changed) {
        Serial.println("GPIO-Konfiguration geändert -> Runtime-Reconfigure");

        hardware_reconfigure();
        circulation_fan_reconfigure();
        exhaust_fan_reconfigure();
        light_reconfigure();
    }
}
// Safe accessors for other modules
bool grow_controller_ble_scan_enabled() {
    return _ble_scan_enabled;
}
bool grow_controller_ble_bridge_enabled() {
    return _ble_bridge_enabled;
}



void grow_controller_get_status(JsonObject doc) {
    // System Infos
    doc["dev_name"] = _device_name;
    doc["log_level"] = _log_level;
    
    doc["uptime_esp_s"] = millis() / 1000;
    doc["fw_ver"] = "v2.8.6-beta";
    
    // IP + WLAN
    
    
    if (WiFi.status() == WL_CONNECTED) {
        doc["ip"] = WiFi.localIP().toString();
        doc["ssid"] = WiFi.SSID();
        doc["rssi"] = WiFi.RSSI();
    } else {
        doc["ip"] = "192.168.4.1";
        doc["ssid"] = "";
        doc["rssi"] = -256.0f;
    }

    // Heap Monitoring
    doc["free_heap"]   = ESP.getFreeHeap();
    doc["max_alloc"]   = ESP.getMaxAllocHeap();
    doc["heap_usage"]  = ESP.getHeapSize() - ESP.getFreeHeap();

    // Boot Cause
    int reason = (int)rtc_get_reset_reason(0);
    if (reason == 1)      doc["boot_cause"] = "Power Cut / Hard Reset";
    else if (reason == 12) doc["boot_cause"] = "Software Reboot";
    else if (reason == 3)  doc["boot_cause"] = "Software Crash (Watchdog)";
    else                   doc["boot_cause"] = "Other: " + String(reason);

    // === REVISIONEN ZURÜCKSENDEN (genau wie bei circfan) ===
    doc["rev_grow"] = grow_controller_rev;           // <--- Modulspezifisch
    doc["wifi_mode"] = _wifi_mode;

    // Aktuelle Live-Pins in den Status-Payload für die Kivy-UI packen
    JsonObject gpios = doc.createNestedObject("gpios");
    gpios["p_reset"] = sysConfig.pin_reset_button;
    gpios["p_c_fan"] = sysConfig.pin_circ_fan;
    gpios["p_c_tac"] = sysConfig.pin_circ_tacho;
    gpios["p_e_fan"] = sysConfig.pin_exh_fan;
    gpios["p_e_tac"] = sysConfig.pin_exh_tacho;
    gpios["p_light"] = sysConfig.pin_light;
    gpios["p_i2c_sda"] = sysConfig.i2c_sda;
    gpios["p_i2c_scl"] = sysConfig.i2c_scl;
    gpios["p_rtc_sda"] = sysConfig.rtc_sda;
    gpios["p_rtc_scl"] = sysConfig.rtc_scl;
    gpios["p_bat"]   = sysConfig.pin_bat;

    // BLE enablement flags (exposed to UI)
    // BLE enablement flags (live RAM state + persisted)
    doc["ble_bridge_enabled"] = _ble_bridge_enabled;   // statt prefs
    doc["ble_scan_enabled"]   = _ble_scan_enabled;     // statt prefs
    gpios["p_c_tac_pull"] = sysConfig.pin_circ_tacho_pull;
    gpios["p_e_tac_pull"] = sysConfig.pin_exh_tacho_pull;
    gpios["p_bat_pull"]   = sysConfig.pin_bat_pull;

}
int grow_controller_get_wifi_mode() {
    // Standardmäßig 0 (AP), wenn nichts gespeichert ist
    return growPrefs.getInt("wifi_mode", 0); 
}