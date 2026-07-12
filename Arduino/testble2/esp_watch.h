// ESPWatch - Einfache RTC-Integration für ESP32-Uhren
#ifndef ESP_WATCH_H
#define ESP_WATCH_H

#include <Arduino.h>
#include <Wire.h>

class ESPWatch {
public:
    bool begin(TwoWire &wire, uint8_t addr = 0x68);
    bool isRTCHealthy();
    bool syncFromRTC();        // <--- muss genau so heißen
    bool writeToRTC();
    bool isRTCSet();
    void forceRTCAsTimebase();

    void writeBackupU32(uint16_t memAddr, uint32_t value);
    uint32_t readBackupU32(uint16_t memAddr);
    void markBoot(uint32_t rev);
    uint32_t getBootCounter();

private:
    TwoWire *bus = nullptr;
    uint8_t _addr = 0x68;
};

extern ESPWatch watch;

#endif