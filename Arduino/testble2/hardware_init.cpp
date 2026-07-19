// hardware_init.cpp - Alle Funktionen zur Initialisierung der Hardware (I2C, Sensoren, etc.)
#include "hardware_init.h"
#include "sensor.h"
#include "sys_config.h"
extern TwoWire I2C_Sensor;
extern TwoWire I2C_RTC;

#define LEDC_FREQ 5000
#define LEDC_TIMER_10_BIT 10


void recoverI2C(TwoWire &bus, int sda, int scl) {
    bus.end();
    delay(10);
    bus.begin(sda, scl, 50000);
    delay(10);
}

void init_sensor_bus()
{
    // Prüfen, ob Sensor-I2C aktiviert ist
    if (sysConfig.i2c_sda == -1 || sysConfig.i2c_scl == -1) {
        Serial.println("I2C Sensor Bus deaktiviert (sysConfig). Skipping init.");
        return;
    }

    I2C_Sensor.end(); 
    delay(50); 
    
    // ✔️ REPARIERT: Nutzt jetzt die dynamischen Pins aus sysConfig
    I2C_Sensor.begin(sysConfig.i2c_sda, sysConfig.i2c_scl, 50000);
    I2C_Sensor.setTimeOut(20);
    
    // ✔️ REPARIERT: Dynamische Log-Ausgabe statt Hardcoded Text
    Serial.printf("Sensor-Bus (Extern) mit Pins SDA:%d / SCL:%d gestartet.\n", sysConfig.i2c_sda, sysConfig.i2c_scl);
}

void scan_i2c_devices()
{
    Serial.printf("\n--- I2C SCAN GPIO %d / %d ---\n", sysConfig.i2c_sda, sysConfig.i2c_scl);

    byte error, address;
    int nDevices = 0;

    for (address = 1; address < 127; address++)
    {
        I2C_Sensor.beginTransmission(address);
        error = I2C_Sensor.endTransmission();

        if (error == 0)
        {
            Serial.print("Gerät gefunden: 0x");
            if (address < 16) Serial.print("0");
            Serial.println(address, HEX);
            nDevices++;
        }
    }

    if (nDevices == 0)
        Serial.println("Kein I2C Gerät gefunden.");
    else
        Serial.printf("Scan fertig: %d Geräte\n", nDevices);
}

void init_hardware() {
    if (sysConfig.pin_bat != -1) {
        pinMode(sysConfig.pin_bat, INPUT);
    } else {
        Serial.println("PIN_BAT disabled (sysConfig).");
    }

    // Sensor Bus starten
    if (sysConfig.i2c_sda == -1 || sysConfig.i2c_scl == -1) {
        Serial.println("Sensor I2C deaktiviert (sysConfig). Skipping I2C_Sensor init.");
    } else {
        // ✔️ REPARIERT: Pins übergeben!
        I2C_Sensor.begin(sysConfig.i2c_sda, sysConfig.i2c_scl, 50000);
    }

    // RTC Bus starten
    if (sysConfig.rtc_sda == -1 || sysConfig.rtc_scl == -1) {
        Serial.println("RTC I2C deaktiviert (sysConfig). Skipping I2C_RTC init.");
    } else {
        // ✔️ REPARIERT: Pins übergeben!
        I2C_RTC.begin(sysConfig.rtc_sda, sysConfig.rtc_scl, 100000);
    }

    Serial.println("I2C Busse mit dynamischen sysConfig-Pins initialisiert.");
}

void hardware_reconfigure()
{
    Serial.println("========== Hardware Runtime Reconfigure ==========");
    Serial.println("========== Hardware Reconfigure Done ==========");
}
