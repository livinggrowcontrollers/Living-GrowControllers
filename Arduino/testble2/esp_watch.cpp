// ESPWatch - Einfache RTC-Integration für ESP32-Uhren
#include "esp_watch.h"
#include "hardware_init.h"   // für recoverI2C()
#include <time.h>
#include <sys/time.h>

#define DS3231_TIME_REG   0x00
#define DS3231_STATUS_REG 0x0F
#define EEPROM_ADDR       0x57

// Hilfsfunktionen
static uint8_t dec2bcd(uint8_t val) { return ((val / 10 * 16) + (val % 10)); }
static uint8_t bcd2dec(uint8_t val) { return ((val / 16 * 10) + (val % 16)); }

bool ESPWatch::begin(TwoWire &wire, uint8_t addr) {
    bus = &wire;
    _addr = addr;
    bus->beginTransmission(_addr);
    return (bus->endTransmission() == 0);
}

bool ESPWatch::isRTCHealthy() {
    if (!bus) return false;
    bus->beginTransmission(_addr);
    return (bus->endTransmission() == 0);
}

// ==================== NEU: HARDWARE-STATUS ABFRAGEN ====================
bool ESPWatch::isRTCSet() {
    if (!bus) return false;

    // Status-Register 0x0F ansteuern
    bus->beginTransmission(_addr);
    bus->write(DS3231_STATUS_REG); 
    if (bus->endTransmission() != 0) return false;

    bus->requestFrom(_addr, (uint8_t)1);
    if (bus->available() < 1) return false;

    uint8_t statusReg = bus->read();
    
    // Bit 7 (OSF) ist 1, wenn der Oszillator gestoppt war (Stromausfall ohne Batterie)
    // Wenn Bit 7 also 1 ist, ist die Uhr UNGESETZT / UNGÜLTIG.
    if (statusReg & 0x80) {
        return false; 
    }
    return true;
}

// ==================== SYNC FROM RTC ====================
bool ESPWatch::syncFromRTC() {
    if (!bus) return false;

    bus->beginTransmission(_addr);
    bus->write(DS3231_TIME_REG); // Start-Register
    if (bus->endTransmission() != 0) return false;

    bus->requestFrom(_addr, (uint8_t)7);
    if (bus->available() < 7) return false;

    uint8_t sec   = bcd2dec(bus->read() & 0x7F);
    uint8_t min   = bcd2dec(bus->read());
    uint8_t hour  = bcd2dec(bus->read());
    bus->read(); // weekday ignorieren
    uint8_t day   = bcd2dec(bus->read());
    uint8_t month = bcd2dec(bus->read());
    uint8_t year  = bcd2dec(bus->read());

    struct tm t = {};
    t.tm_sec   = sec;
    t.tm_min   = min;
    t.tm_hour  = hour;
    t.tm_mday  = day;
    t.tm_mon   = month - 1;
    t.tm_year  = year + 100;
    
    // WICHTIG: Sommerzeit automatisch erkennen
    t.tm_isdst = -1;
    
    time_t epoch = mktime(&t);
    struct timeval tv = {epoch, 0};
    settimeofday(&tv, nullptr);

    Serial.printf("RTC Sync OK → %02d:%02d:%02d\n", hour, min, sec);
    return true;
}

// ==================== WRITE TO RTC ====================
bool ESPWatch::writeToRTC() {
    if (!bus) return false;

    struct tm ti;
    if (!getLocalTime(&ti)) {
        Serial.println("RTC Write: Fehler! Keine valide Systemzeit vorhanden.");
        return false;
    }

    // 1. Zeitdaten in die Register 0x00 bis 0x06 schreiben
    bus->beginTransmission(_addr);
    bus->write(DS3231_TIME_REG); 
    bus->write(dec2bcd(ti.tm_sec));
    bus->write(dec2bcd(ti.tm_min));
    bus->write(dec2bcd(ti.tm_hour));
    bus->write(dec2bcd(ti.tm_wday + 1)); 
    bus->write(dec2bcd(ti.tm_mday));
    bus->write(dec2bcd(ti.tm_mon + 1));  
    bus->write(dec2bcd(ti.tm_year - 100)); 
    if (bus->endTransmission() != 0) {
        Serial.println("RTC Write: I2C Fehler beim Zeitscheiben");
        return false;
    }

    // 2. STATUS-REGISTER (0x0F) AKTUALISIEREN: OSF-Bit (Bit 7) auf 0 löschen!
    bus->beginTransmission(_addr);
    bus->write(DS3231_STATUS_REG);
    bus->write(0x00); // Löscht das OSF Flag und setzt Alarme zurück
    if (bus->endTransmission() == 0) {
        Serial.printf("RTC Geheilt & Synchronisiert: %02d:%02d:%02d (OSF gelöscht)\n", ti.tm_hour, ti.tm_min, ti.tm_sec);
        return true;
    }
    
    Serial.println("RTC Write: I2C Fehler beim Löschen des OSF-Flags");
    return false;
}

void ESPWatch::forceRTCAsTimebase() { syncFromRTC(); }
void ESPWatch::writeBackupU32(uint16_t memAddr, uint32_t value) {}
uint32_t ESPWatch::readBackupU32(uint16_t memAddr) { return 0; }
void ESPWatch::markBoot(uint32_t rev) {}
uint32_t ESPWatch::getBootCounter() { return 0; }