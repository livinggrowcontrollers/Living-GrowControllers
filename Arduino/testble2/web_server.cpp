//  web_server.cpp
#include "web_server.h"
#include "sensor.h"
// PATCHER BEGIN: CIRCULATION_INCLUDE
#include "circulation_fan.h"
// PATCHER END: CIRCULATION_INCLUDE
#include "exhaust_fan.h"
#include "light_control.h"
#include "power_manager.h"
#include "logic_helper.h"
#include <WiFi.h>
#include "esp_wifi.h"
#include <ArduinoJson.h>
#include "web_server_browser.h"
#include "esp_watch.h"
#include "ble_scanner.h"
#include "plant_planner.h"
#include <ESPmDNS.h>
#include "ota_manager.h"
#include <Update.h>

extern ESPWatch watch; 

#include "grow_controller.h" 
extern WebServer server;
extern String get_current_time_str();

extern int current_rev;
extern float currentVPD;      
extern float currentVPDIn;    
extern float currentVPDLeaf;
// Die alten festen Zugänge fliegen raus. Wir holen die dynamischen Variablen:
extern String _web_username;
extern String _web_password;
static bool mdns_started = false;
static String mdns_hostname = "";
void sendStandardHeaders() {
    // Keep connections alive to allow client-side connection pooling and
    // avoid constant TCP handshake churn. Do NOT force Connection: close.
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.sendHeader("Connection", "keep-alive");
}

// 1. DATA ENDPUNKT
void handleData() {
    if (!server.authenticate(_web_username.c_str(), _web_password.c_str())) return server.requestAuthentication();
    sendStandardHeaders();

    // STATIC statt DYNAMIC verhindert das Zerstückeln des Speichers
    static DynamicJsonDocument doc(6144);
    doc.clear(); // WICHTIG: Vor jeder Nutzung leeren!
    JsonObject obj = doc.to<JsonObject>();
    
    JsonObject health = obj.createNestedObject("health");
    JsonObject signal = health.createNestedObject("signal");
    
    if (WiFi.status() == WL_CONNECTED) {
        signal["rssi"] = WiFi.RSSI();
    } else {
        signal["rssi"] = -256; 
    }

    bool isRtcOk = watch.isRTCHealthy();
    obj["rtc_found"] = isRtcOk;

    if (isRtcOk) {
        time_t now;
        struct tm timeinfo;
        time(&now);
        localtime_r(&now, &timeinfo);
        char timeBuf[20]; // Puffer vergrößert (von 10 auf 20), um Platz für Sekunden zu haben
        
        // Geändert auf "%02d:%02d:%02d" und timeinfo.tm_sec hinzugefügt:
        sprintf(timeBuf, "%02d:%02d:%02d", timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec);
        
        obj["rtc_time"] = String(timeBuf);
    } else {
        obj["rtc_time"] = "offline";
    }

    // =================================================================
    // NEU: Echte Systemzeit (System-Uhrzeit) ausgeben für Boot-Abgleich
    // =================================================================
    time_t sysNow = time(nullptr);
    struct tm sysTimeinfo;
    localtime_r(&sysNow, &sysTimeinfo);
    char sysTimeBuf[20];
    // Option A: "HH:MM" -> "%02d:%02d"
    // Option B: "HH:MM:SS" (besser für Boot-Analysen) -> "%02d:%02d:%02d"
    sprintf(sysTimeBuf, "%02d:%02d:%02d", sysTimeinfo.tm_hour, sysTimeinfo.tm_min, sysTimeinfo.tm_sec);
    obj["system_time"] = String(sysTimeBuf);
    // =================================================================

 

    obj["temp_in"] = getTempIn();
    obj["temp_ext"] = getTempExt();
    obj["humid_ext"] = getExternalHumidity();
    obj["humid_in"] = getInternalHumidity();
    obj["leaf_temp"] = -256.0f; // Leaf-Temp nicht verfügbar
    obj["vbat"] = get_battery_voltage_now();
    obj["rev"] = current_rev;
    // Zusätzliche Geräte-Informationen für automatische Discovery
    obj["hostname"] = mdns_hostname;
    // NACHHER: Wenn im AP-Modus, liefere die korrekte Hotspot-IP, sonst die WLAN-IP
    if (WiFi.getMode() == WIFI_AP) {
        obj["ip_address"] = WiFi.softAPIP().toString(); // Liefert sauber "192.168.4.1"
    } else {
        obj["ip_address"] = WiFi.localIP().toString();  // Liefert die Heim-WLAN-IP (z.B. 192.168.2.20)
    }
    obj["mac"] = WiFi.macAddress();
    
    exhaust_fan_get_status(obj);

    // PATCHER BEGIN: CIRCULATION_GET_STATUS
    circulation_fan_get_status(obj);
// PATCHER END: CIRCULATION_GET_STATUS
    
    // Aufruf matcht jetzt exakt mit dem Prototyp aus plant_planner.h
    obj["rev_plant_planner"] = get_plant_planner_rev();

    light_control_get_status(obj);
    grow_controller_get_status(obj); 
    BLEScanner::get_status(obj);
    ota_manager_get_status(obj);
    String response;
    serializeJson(doc, response);
    server.send(200, "application/json", response);
}

// 2. CONTROL ENDPUNKT
void handleControlJSON() {
    if (!server.authenticate(_web_username.c_str(), _web_password.c_str())) return server.requestAuthentication();
    
    sendStandardHeaders();

    if (server.hasArg("plain")) {
        StaticJsonDocument<1024> doc;
        DeserializationError error = deserializeJson(doc, server.arg("plain"));
        if (error) return;

        JsonObject obj = doc.as<JsonObject>();

        if (obj.containsKey("rev")) {
            current_rev = obj["rev"]; 
        }

        exhaust_fan_process_json(obj); 
        // PATCHER BEGIN: CIRCULATION_JSON_UPDATE
        circulation_fan_process_json(obj);
// PATCHER END: CIRCULATION_JSON_UPDATE
        plant_planner_process_json(obj);
        light_control_process_json(obj);            
        grow_controller_process_json(obj);       
        ota_manager_process_json(obj);
        
        StaticJsonDocument<128> res;
        res["status"] = "ok";
        res["rev"] = current_rev; 
        
        String response;
        serializeJson(res, response);
        server.send(200, "application/json", response);
    }
}

void handleGetPlants() {
    if (!server.authenticate(_web_username.c_str(), _web_password.c_str())) return server.requestAuthentication();
    sendStandardHeaders();
// STATIC statt DYNAMIC verhindert das Zerstückeln des Speichers
    static DynamicJsonDocument doc(6144);
    doc.clear(); // WICHTIG: Vor jeder Nutzung leeren!
    JsonObject obj = doc.to<JsonObject>();

    plant_planner_get_status(obj); 

    String response;
    serializeJson(doc, response);
    server.send(200, "application/json", response);
}

void handleControlPlantsJSON() {
    if (!server.authenticate(_web_username.c_str(), _web_password.c_str())) return server.requestAuthentication();
    sendStandardHeaders();

    if (server.hasArg("plain")) {
        DynamicJsonDocument doc(8192);
        DeserializationError error = deserializeJson(doc, server.arg("plain"));
        if (error) return;

        JsonObject obj = doc.as<JsonObject>();

        plant_planner_process_json(obj); 

        StaticJsonDocument<128> res;
        res["status"] = "ok";
        
        String response;
        serializeJson(res, response);
        server.send(200, "application/json", response);
    }
}

namespace WebModule {
    // 🔥 NEU: Hilfs-Handler für den Datei-Upload über den synchronen Webserver
    void handleOtaUpload() {
        if (!server.authenticate(_web_username.c_str(), _web_password.c_str())) return server.requestAuthentication();
        
        HTTPUpload& upload = server.upload();
        
        if (upload.status == UPLOAD_FILE_START) {
            Serial.printf("[HTTP-OTA] Start: %s\n", upload.filename.c_str());
            // Da der synchrone Server die Gesamtgröße im Header mitsendet, holen wir uns diese
            size_t total_size = 0;
            if (server.hasHeader("Content-Length")) {
                total_size = server.header("Content-Length").toInt();
            } else {
                // Fallback falls kein Header: Wir schätzen großzügig oder nutzen das Maximum der Partition
                total_size = UPDATE_SIZE_UNKNOWN; 
            }
            
            if (!ota_manager_start(total_size)) {
                Serial.println("[HTTP-OTA] Fehler beim Initialisieren!");
            }
        } 
        else if (upload.status == UPLOAD_FILE_WRITE) {
            if (!ota_manager_write(upload.buf, upload.currentSize)) {
                Serial.println("[HTTP-OTA] Fehler beim Schreiben des Chunks!");
            }
        } 
        else if (upload.status == UPLOAD_FILE_END) {
            if (ota_manager_end()) {
                sendStandardHeaders();
                server.send(200, "text/plain", "OTA SUCCESS. Rebooting...");
            } else {
                sendStandardHeaders();
                server.send(500, "text/plain", "OTA FAILED!");
            }
        }
    }

    void _startServerCommon() {
        server.on("/data", handleData);                         
        server.on("/control", HTTP_POST, handleControlJSON);     
        
        server.on("/data/plants", handleGetPlants);              
        server.on("/control/plants", HTTP_POST, handleControlPlantsJSON); 
        
        // 🔥 NEU: Registrierung der OTA-Route für Datei-Uploads
        // Wir nutzen denselben Handler sowohl für den Request-Abschluss als auch für den Stream-Erhalt
        server.on("/update", HTTP_POST, [](){}, handleOtaUpload);
        
        WebServerBrowser::registerRoutes(server);
        
        // Da wir mDNS/Uploads machen, erlauben wir dem Server Header zu lesen
        const char * headerkeys[] = {"Content-Length"} ;
        size_t headerkeyssize = sizeof(headerkeys)/sizeof(char*);
        server.collectHeaders(headerkeys, headerkeyssize);

        server.begin();
        Serial.println("Webserver gestartet.");
    }

    void init(const char* ssid, const char* password) {
        WiFi.mode(WIFI_STA);
        WiFi.begin(ssid, password);
        esp_wifi_set_ps(WIFI_PS_NONE);

        Serial.println("WLAN Station Mode -> Warte auf Verbindung & NTP...");

        configTzTime("CET-1CEST,M3.5.0/2,M10.5.0/3", 
                     "de.pool.ntp.org", 
                     "pool.ntp.org", 
                     "time.nist.gov");

        _startServerCommon();
    }

    // Erstelle eine Hilfsfunktion, um den Hostnamen einmalig zu generieren
    void ensure_hostname_generated() {
        if (mdns_hostname.length() > 0) return;

        String macStr = WiFi.macAddress();
        macStr.replace(":", "");
        String suffix = macStr.substring(macStr.length() - 4);
        mdns_hostname = "growmaster-" + suffix;
        mdns_hostname.toLowerCase();
    }

    void start_mdns_if_needed() {
        // Nur im Station-Mode mDNS nutzen
        if (WiFi.getMode() & WIFI_AP) {
            return;
        }

        if (mdns_started) return;
        if (WiFi.status() != WL_CONNECTED) return;

        ensure_hostname_generated(); // Sicherstellen, dass Name existiert

        if (MDNS.begin(mdns_hostname.c_str())) {
            MDNS.addService("http", "tcp", 80);
            Serial.printf("[mDNS] Aktiv: http://%s.local\n", mdns_hostname.c_str());
            mdns_started = true;
        } else {
            Serial.println("[mDNS] Fehler beim Start.");
        }
    }

    void init_ap(const char* ap_name) {
        WiFi.mode(WIFI_AP);
        WiFi.softAP(ap_name, ""); 
        esp_wifi_set_ps(WIFI_PS_NONE);

        ensure_hostname_generated(); // <--- WICHTIG: Damit "hostname" im JSON nicht leer ist!

        Serial.printf("Hotspot aktiv: %s | IP: 192.168.4.1\n", ap_name);
        _startServerCommon();
    }

void update() {
        // Diese zwei Zeilen sind neu (erstellen den Timer):
        static uint32_t lastCheck = 0;
        uint32_t now = millis();

        // Diese Zeile sorgt dafür, dass der mDNS-Kram nur alle 5000ms (5 Sek) läuft:
        if (now - lastCheck > 5000) {
            lastCheck = now;

            if (WiFi.status() == WL_CONNECTED) {
                start_mdns_if_needed();
            } else {
                if (mdns_started) {
                    MDNS.end();
                    mdns_started = false;
                }
            }
        } // Hier endet der 5-Sekunden-Timer

        // Das hier läuft weiterhin im Dauertakt, damit Anfragen sofort durchgehen:
        if (WiFi.status() == WL_CONNECTED ||
            (WiFi.getMode() & WIFI_AP)) {

            server.handleClient();
        }
    }
}