#include "system_reset.h"
#include <Preferences.h>

static int _reset_pin = -1;
static uint32_t _button_pressed_time = 0;
static bool _is_pressing = false;

// Konstante für die Haltezeit (10 Sekunden)
const uint32_t RESET_HOLD_TIME_MS = 10000; 

void SystemReset::init(int pin) {
    if (pin == -1) {
        _reset_pin = -1;
        Serial.println("SystemReset: disabled via sysConfig (pin=-1)");
        return;
    }

    _reset_pin = pin;
    // INPUT_PULLUP bedeutet: Knopf schaltet gegen GND (0V -> gedrückt)
    pinMode(_reset_pin, INPUT_PULLUP);
    Serial.printf("[RESET] Modul aktiv auf Pin %d (10s Hold für Factory Reset)\n", _reset_pin);
}

void SystemReset::perform_factory_reset() {
    Serial.println("");
    Serial.println("=================================");
    Serial.println("FACTORY RESET");
    Serial.println("=================================");

    Preferences prefs;

    // Grow
    prefs.begin("grow", false);
    prefs.clear();
    prefs.end();

    // Gespeicherte BLE-Sensor-Zuordnungen gehören ebenfalls zum Werkszustand.
    prefs.begin("blescan", false);
    prefs.clear();
    prefs.end();

    // Licht
    prefs.begin("light", false);
    prefs.clear();
    prefs.end();

    // Climate policy and Exhaust hardware configuration
    prefs.begin("climate_hub", false);
    prefs.clear();
    prefs.end();

    prefs.begin("exhaust_fan", false);
    prefs.clear();
    prefs.end();

    prefs.begin("humidifier", false);
    prefs.clear();
    prefs.end();

    prefs.begin("circulation_fan", false);
    prefs.clear();
    prefs.end();

    prefs.begin("circ_fan_2", false);
    prefs.clear();
    prefs.end();

    prefs.begin("circ_fan_3", false);
    prefs.clear();
    prefs.end();

    Serial.println("[RESET] grow gelöscht");
    Serial.println("[RESET] BLE-Sensor-Zuordnungen gelöscht");
    Serial.println("[RESET] light gelöscht");
    Serial.println("[RESET] climate_hub gelöscht");
    Serial.println("[RESET] exhaust_fan gelöscht");
    Serial.println("[RESET] humidifier gelöscht");
    Serial.println("[RESET] circulation fans gelöscht");

    delay(2000);

    ESP.restart();
}

void SystemReset::update() {
    if (_reset_pin == -1) return;

    // Da INPUT_PULLUP: LOW (0) = Gedrückt, HIGH (1) = Losgelassen
    bool current_state = (digitalRead(_reset_pin) == LOW);

    if (current_state) {
        // Knopf wurde GERADE EBEN gedrückt
        if (!_is_pressing) {
            _is_pressing = true;
            _button_pressed_time = millis();
            Serial.println("[RESET] Knopf gedrückt... Halten für Factory Reset!");
        } 
        // Knopf WIRD BEREITS gehalten
        else {
            uint32_t elapsed = millis() - _button_pressed_time;
            
            // Jede Sekunde ein Lebenszeichen im Seriellen Monitor ausgeben
            static uint32_t last_ticker = 0;
            if (millis() - last_ticker > 1000) {
                last_ticker = millis();
                Serial.printf(
                    "[RESET] Haltedauer: %lu / 10 Sekunden...\n",
                    static_cast<unsigned long>(elapsed / 1000)
                );
            }

            // 10 Sekunden erreicht?
            if (elapsed >= RESET_HOLD_TIME_MS) {
                perform_factory_reset(); // Führt Reset aus und startet ESP neu
            }
        }
    } else {
        // Knopf wurde losgelassen, bevor die 10 Sekunden um waren
        if (_is_pressing) {
            _is_pressing = false;
            Serial.println("[RESET] Abgebrochen. Knopf zu früh losgelassen.");
        }
    }
}
