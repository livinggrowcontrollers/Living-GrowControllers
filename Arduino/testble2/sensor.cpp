// sensor.cpp - Alle Funktionen rund um die Sensoren (SHT31)
#include "sensor.h"
#include "sys_config.h"
#include "hardware_init.h"
// Instanzen definieren (WICHTIG!)
Adafruit_SHT31 sht31_ext = Adafruit_SHT31(&I2C_Sensor);
Adafruit_SHT31 sht31_int = Adafruit_SHT31(&I2C_RTC);
float lastValidTempExt = -256.0;
float lastValidHumExt = -256.0;
unsigned long lastExternalSuccessUpdate = 0; 
const unsigned long SENSOR_TIMEOUT = 1000; // 1 Sekunde Dämpfung
bool externalSensorFound = false;
bool internalSensorFound = false;
extern bool externalSensorFound;


float getTempExt() {
    if (!externalSensorFound) return -256.0;

    float t = sht31_ext.readTemperature();

    if (!isnan(t) && t != -256.0) {
        // Alles okay, Zeitstempel und Wert merken
        lastValidTempExt = t;
        lastExternalSuccessUpdate = millis();
        return t;
    } else {
        // Fehler! Prüfen, ob wir noch innerhalb der 1s Toleranz sind
        if (millis() - lastExternalSuccessUpdate < SENSOR_TIMEOUT) {
            return lastValidTempExt; // "Lüge" und gib alten Wert aus
        } else {
            return -256.0; // Timeout abgelaufen, jetzt Fehler zeigen
        }
    }
}

float getExternalHumidity() {
    float h = sht31_ext.readHumidity();

    // Versuch 1: Normaler Read
    if (!isnan(h)) {
        lastValidHumExt = h;
        lastExternalSuccessUpdate = millis(); // Teilt sich den Timer mit Temp
        return h;
    }

    // Versuch 2: Kurze interne Wiederholung (hast du schon drin)
    for (int i = 0; i < 2; i++) {
        delay(20);
        h = sht31_ext.readHumidity();
        if (!isnan(h)) {
            lastValidHumExt = h;
            lastExternalSuccessUpdate = millis();
            return h;
        }
    }

    // Wenn hier gelandet -> Hardware-Fehler!
    recoverI2C(I2C_Sensor, sysConfig.i2c_sda, sysConfig.i2c_scl);
    sht31_ext.begin(0x44);

    // Watchdog-Check: Bevor wir -256 schicken, prüfen wir die Zeit
    if (millis() - lastExternalSuccessUpdate < SENSOR_TIMEOUT) {
        return lastValidHumExt; // Gib den letzten guten Wert zurück
    }

    return -256.0;
}

// Gleiches Spiel für Intern
float getInternalHumidity() {
    // 1. Sofort-Abbruch, wenn Sensor im Betrieb bereits als "verloren" markiert wurde
    if (!internalSensorFound) return -256.0;
    
    float h = sht31_int.readHumidity();
    
    // 2. Plausibilitäts-Check (SHT31 Feuchtigkeit ist physikalisch 0-100%)
    if (isnan(h) || h > 100.0f || h < 0.0f) {
        delay(20);
        h = sht31_int.readHumidity(); // Zweiter Versuch
        
        // Wenn immer noch Müll, ist der Sensor im Betrieb abgezogen worden!
        if (isnan(h) || h > 100.0f || h < 0.0f) {
            Serial.println("KRETIISCH: INT SHT31 SENSOR VERLOREN (Abgezogen?)");
            internalSensorFound = false; // Sensor für weitere Loops deaktivieren!
            return -256.0; 
        }
    }
    
    return h;
}

float getTempIn() {
    if (!internalSensorFound) return -256.0;
    
    float t = sht31_int.readTemperature();
    
    // SHT31 Range ist -40 bis +125 Grad. 
    // Wenn der Sensor abgezogen wird, liefert er oft +130°C oder NaN
    if (isnan(t) || t > 125.0f || t < -40.0f) {
        delay(20);
        t = sht31_int.readTemperature();
        
        if (isnan(t) || t > 125.0f || t < -40.0f) {
            Serial.println("KRITISCH: INT SHT31 TEMPERATUR FEHLER");
            internalSensorFound = false; // Sensor deaktivieren
            return -256.0;
        }
    }
    return t;
}

// Validate sensor values centrally to avoid sentinel inconsistencies
bool is_sensor_value_valid(float val) {
    if (isnan(val)) return false;
    // We use -256.0 as the sentinel for 'invalid' in this project
    if (val <= -250.0f) return false;
    return true;
}


bool initInternalSensor()
{
    if (!sht31_int.begin(0x44)) {
        Serial.println("INT SHT31 NICHT gefunden!");
        return false;
    }

    Serial.println("INT SHT31 gefunden");
    return true;
}
bool initExternalSensor()
{
    if (!sht31_ext.begin(0x44)) {
        Serial.println("EXT SHT31 NICHT gefunden!");
        return false;
    }

    Serial.println("EXT SHT31 gefunden");
    return true;
}
