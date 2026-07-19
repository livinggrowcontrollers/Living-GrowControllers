// !!! ABSOLUTES GESETZ: DAS TARGET-REVISION-PRINZIP (v2.0) !!!
// -------------------------------------------------------------------------
// 1. HARDWARE FOLGT TARGET: Loop reagiert nur auf target_val vs effective_val.
//    Direktes Pin-Schreiben durch UI-Input ist streng verboten!
//

//
// 3. REVISION-CONFIRMATION (rev): Der ESP bestätigt ECHTE Änderungen (Werte),
//    indem er die rev spiegelt. Erst dann wird der Flash-Speicher (Save) aktiv.
//
// 4. KEINE LÜGEN: Das UI zeigt "Synced" (Grün) NUR, wenn:
//    (ui_init == esp_init) UND (ui_rev == esp_rev).
//
// 5. ATOMARE UPDATES: Neue Revisionen werden sofort übernommen, die Hardware
//    (effective_val) zieht asynchron (ggf. über Rampen) nach.
//
// JEDE KI-ÄNDERUNG MUSS DIESE TRENNUNG VON RAM-PING (INIT) UND FLASH-DATA (REV)
// WAHREN. WERTE OHNE REVISIONS-SPIEGELUNG SIND REINE LÜGEN!
///////////////////////////////////////////////////////////////////////////////

#include "circulation_fan3.h"
#include <Preferences.h> // NEU: Für persistente Speicherung
#include "sys_config.h"
#include "hardware_init.h"


static bool circulation_fan3_enabled = true;
// Variablen mit sicheren Startwerten
static int _circulation_fan3_pin = -1;
static int _tacho3_pin = -1;

// 🔥 TRACKER FÜR HARDWARE-PINS (Runtime GPIO Fix)
static int current_circ_fan3_pin = -1;
static int current_circ_tacho3_pin = -1;

Preferences circulation_fan3Prefs;
static int current_circulation_fan3_speed = 10;
static circulation_fan3Mode current_circulation_fan3_mode = circulation_fan3_MODE_NATURAL;
static int current_circulation_fan3_min_speed = 0;
static int effective_circulation_fan3_speed = 0;
static float circulation_fan3_climate_factor = 1.0f;
volatile uint32_t circulation_fan3_pulse_count = 0;
static uint32_t last_circulation_fan3_rpm_check = 0;
static int current_circulation_fan3_rpm = 0;
// Zeitstempel für Entprellung
static uint32_t last_circulation_fan3_pulse_time = 0;
static uint32_t circulation_fan3_rev = 0;     // ← NEU: Eigenes Revision für dieses Modul

static void circulation_fan3_set_speed(int percent);
static void circulation_fan3_set_mode(circulation_fan3Mode mode);

// Hilfsfunktion: Speichern
static void circulation_fan3_save_state() {
    circulation_fan3Prefs.putInt("speed", current_circulation_fan3_speed);
    circulation_fan3Prefs.putInt("mode", (int)current_circulation_fan3_mode);
    circulation_fan3Prefs.putInt("min_speed", current_circulation_fan3_min_speed);
}

void IRAM_ATTR count_circ_fan3_pulse() {
    uint32_t now = micros();
    // Nutze den korrekten Namen: last_circulation_fan3_pulse_time
    if (now - last_circulation_fan3_pulse_time > 800) { 
        circulation_fan3_pulse_count = circulation_fan3_pulse_count + 1;
        last_circulation_fan3_pulse_time = now;
    }
}

void circulation_fan3_init(int pin, int tacho_pin) {
    circulation_fan3Prefs.begin("circ_fan_3", false);
    current_circulation_fan3_speed = circulation_fan3Prefs.getInt("speed", 60);
    current_circulation_fan3_mode = (circulation_fan3Mode)circulation_fan3Prefs.getInt("mode", 1);
    current_circulation_fan3_min_speed = circulation_fan3Prefs.getInt("min_speed", 20);

    // Runtime-Check: Pin -1 deaktiviert Modul
    if (pin == -1 || tacho_pin == -1) {
        Serial.println("circulation_fan3_init: Pin = -1 -> Modul deaktiviert.");
        circulation_fan3_enabled = false;
        current_circ_fan3_pin = -1;
        current_circ_tacho3_pin = -1;
        current_circulation_fan3_rpm = -256;
        effective_circulation_fan3_speed = -256;
        return;
    }

    _circulation_fan3_pin = pin;
    _tacho3_pin = tacho_pin;
    
    // Initialisiere Tracker für den allerersten Start
    current_circ_fan3_pin = _circulation_fan3_pin;
    current_circ_tacho3_pin = _tacho3_pin;
    
    ledcAttach(_circulation_fan3_pin, 25000, 8);
    
    // 3. Tacho Setup
    if (tacho_pin != 255) {
            
            pinMode(
                tacho_pin,
                get_pull_mode(sysConfig.pin_circ_tacho3_pull)
            );


            int irq = digitalPinToInterrupt(tacho_pin);
            // Hier muss der Name der Funktion oben stehen: count_circ_fan3_pulse
            attachInterrupt(irq, count_circ_fan3_pulse, FALLING); 
        }
    

    // INITIALER SETTER FIX:
    // Wir rufen circulation_fan3_set_mode auf, damit die Logik sofort greift
    circulation_fan3_rev = millis();
    circulation_fan3_set_mode(current_circulation_fan3_mode);
    circulation_fan3_set_speed(current_circulation_fan3_speed);

}
void circulation_fan3_reconfigure() {
    Serial.println("Runtime-Reconfigure: Circulation Fan");

    // 1. SCHRITT: Alten Tacho-Interrupt sauber lösen
    if (current_circ_tacho3_pin != -1 && current_circ_tacho3_pin != 255 && current_circ_tacho3_pin != sysConfig.pin_circ_tacho3) {
        Serial.printf("Löse alten Umluft-Tacho-Interrupt auf Pin: %d\n", current_circ_tacho3_pin);
        detachInterrupt(digitalPinToInterrupt(current_circ_tacho3_pin));
        pinMode(current_circ_tacho3_pin, INPUT);
    }

    // 2. SCHRITT: Alten PWM Pin sauber detachen
    if (current_circ_fan3_pin != -1 && current_circ_fan3_pin != sysConfig.pin_circ_fan3) {
        Serial.printf("Löse alten Umluft-PWM Pin: %d\n", current_circ_fan3_pin);
        ledcDetach(current_circ_fan3_pin);
        pinMode(current_circ_fan3_pin, INPUT);
    }

    // Neue Pins aus der Konfiguration übernehmen
    _circulation_fan3_pin = sysConfig.pin_circ_fan3;
    _tacho3_pin = sysConfig.pin_circ_tacho3;

    // 3. SCHRITT: Modul-Deaktivierung (HÄRTUNG)
    if (_circulation_fan3_pin == -1 || _tacho3_pin == -1) {
        circulation_fan3_enabled = false;
        current_circ_fan3_pin = -1;   // ⚡ FIX: Tracker explizit auf -1 setzen!
        current_circ_tacho3_pin = -1; // ⚡ FIX: Tracker explizit auf -1 setzen!
        current_circulation_fan3_rpm = -256; // ⚡ Daten-Zombies eliminieren
        effective_circulation_fan3_speed = -256;
        Serial.println("Circulation Fan dauerhaft deaktiviert (Pins = -1).");
        return; 
    }

    circulation_fan3_enabled = true;
    if (current_circulation_fan3_rpm < 0) {
        current_circulation_fan3_rpm = 0;
        circulation_fan3_pulse_count = 0;
        last_circulation_fan3_rpm_check = millis();
    }

    // 4. SCHRITT: PWM neu binden
    if (current_circ_fan3_pin != _circulation_fan3_pin) {
        ledcAttach(_circulation_fan3_pin, 25000, 8);
        current_circ_fan3_pin = _circulation_fan3_pin;
    }

    // 5. SCHRITT: Tacho neu binden
    if (current_circ_tacho3_pin != _tacho3_pin) {
        if (_tacho3_pin != 255) {
            pinMode(_tacho3_pin, get_pull_mode(sysConfig.pin_circ_tacho3_pull));
            attachInterrupt(digitalPinToInterrupt(_tacho3_pin), count_circ_fan3_pulse, FALLING);
        }
        current_circ_tacho3_pin = _tacho3_pin;
    }

    circulation_fan3_update();
    Serial.printf("Circulation Fan aktiv -> PWM GPIO %d, Tacho GPIO %d\n", _circulation_fan3_pin, _tacho3_pin);
}

static void circulation_fan3_set_speed(int percent) {
    if (!circulation_fan3_enabled || _circulation_fan3_pin == 255 || current_circ_fan3_pin == -1) return;
    current_circulation_fan3_speed = constrain(percent, 0, 100);
    
    circulation_fan3_save_state();

    if(current_circulation_fan3_mode == circulation_fan3_MODE_MANUAL) {
        effective_circulation_fan3_speed = (int)(
            current_circulation_fan3_speed * circulation_fan3_climate_factor + 0.5f
        );
        uint32_t duty = 0;
        if (effective_circulation_fan3_speed > 0) {
            duty = map(effective_circulation_fan3_speed, 1, 100, 65, 255);
        }
        ledcWrite(_circulation_fan3_pin, duty);
    }
}

static void circulation_fan3_set_mode(circulation_fan3Mode mode) {
    if (!circulation_fan3_enabled) return;
    current_circulation_fan3_mode = mode;
    circulation_fan3_save_state(); // Modus speichern
}

void circulation_fan3_apply_climate_factor(float factor) {
    circulation_fan3_climate_factor = constrain(factor, 0.0f, 1.0f);
}




// 3. Die RPM-Abfrage (Reaktionsfreudige Glättung)
int circulation_fan3_get_rpm() {
    uint32_t now = millis();
    // Nutze den korrekten Namen: last_circulation_fan3_rpm_check
    if (now - last_circulation_fan3_rpm_check >= 1000) {
        noInterrupts();
        uint32_t pulses = circulation_fan3_pulse_count;
        circulation_fan3_pulse_count = 0;
        interrupts();

        // 2 Pulse pro Umdrehung
        int new_rpm = (pulses * 60) / 2; 

        // Schnelle Glättung (60% neu, 40% alt)
        if (current_circulation_fan3_rpm == 0) {
            current_circulation_fan3_rpm = new_rpm;
        } else {
            current_circulation_fan3_rpm = (current_circulation_fan3_rpm * 0.4f) + (new_rpm * 0.6f);
        }
        
        last_circulation_fan3_rpm_check = now;
    }
    return current_circulation_fan3_rpm;
}

void circulation_fan3_update() {
    // Strenger Schutz vor uninitialisierten Schreibzugriffen
    if (!circulation_fan3_enabled || current_circ_fan3_pin == -1) return;
    
    // Falls Manuell: Der effektive Wert ist einfach das Target
    if (current_circulation_fan3_mode == circulation_fan3_MODE_MANUAL) {
        effective_circulation_fan3_speed = (int)(
            current_circulation_fan3_speed * circulation_fan3_climate_factor + 0.5f
        );
        uint32_t duty = 0;
        if (effective_circulation_fan3_speed > 0) {
            duty = map(effective_circulation_fan3_speed, 1, 100, 65, 255);
        }
        ledcWrite(_circulation_fan3_pin, duty);
        return;
    }

    static uint32_t last_wind_change = 0;
    if (millis() - last_wind_change > 1500) {
        float mix_factor = 0;

        if (current_circulation_fan3_mode == circulation_fan3_MODE_NATURAL) {
            mix_factor = 0.5 + (sin(millis() / 3000.0) * 0.5);
        } 
        else if (current_circulation_fan3_mode == circulation_fan3_MODE_CHAOTIC) {
            mix_factor = random(0, 101) / 100.0;
        }

        int diff = current_circulation_fan3_speed - current_circulation_fan3_min_speed;
        if (diff < 0) diff = 0; 

        const int base_speed = current_circulation_fan3_min_speed + (int)(diff * mix_factor);
        effective_circulation_fan3_speed = (int)(
            base_speed * circulation_fan3_climate_factor + 0.5f
        );
        
        uint32_t duty = 0;
        if (effective_circulation_fan3_speed > 0) {
            duty = map(effective_circulation_fan3_speed, 1, 100, 65, 255);
        }
        
        ledcWrite(_circulation_fan3_pin, duty);
        last_wind_change = millis();
    }
}

void circulation_fan3_process_json(JsonObject doc) {
    bool flash_changed = false;


    // 2. Daten-Revision (Flash relevant)
    if (!doc["rev_circfan3"].isNull()) {
        uint32_t received_rev = doc["rev_circfan3"];
        if (received_rev > circulation_fan3_rev) {
            circulation_fan3_rev = received_rev;

            if (!doc["circulation_fan3_pct"].isNull()) {
                current_circulation_fan3_speed = constrain((int)doc["circulation_fan3_pct"], 0, 100);
                flash_changed = true;
            }
            if (!doc["circulation_fan3_min"].isNull()) {
                current_circulation_fan3_min_speed = constrain((int)doc["circulation_fan3_min"], 0, 100);
                flash_changed = true;
            }
            if (!doc["circulation_fan3_mode"].isNull()) {
                String m = doc["circulation_fan3_mode"];
                if (m == "nat") current_circulation_fan3_mode = circulation_fan3_MODE_NATURAL;
                else if (m == "chao") current_circulation_fan3_mode = circulation_fan3_MODE_CHAOTIC;
                else current_circulation_fan3_mode = circulation_fan3_MODE_MANUAL;
                flash_changed = true;
            }
        }
    }

    if (flash_changed) {
        // Logik anwenden & persistieren
        if (current_circulation_fan3_mode == circulation_fan3_MODE_MANUAL) {
            circulation_fan3_set_speed(current_circulation_fan3_speed);
        }
        circulation_fan3_save_state();
    }
}

void circulation_fan3_get_status(JsonObject doc) {
    // Doppelter Schutz: Entweder Flag false ODER GPIOs stehen im System auf -1
    if (!circulation_fan3_enabled || sysConfig.pin_circ_fan3 == -1 || sysConfig.pin_circ_tacho3 == -1) {
        doc["circulation_fan3_rpm"] = -256;
        doc["circulation_fan3_pct"] = -256;
        doc["circulation_fan3_speed_now"] = -256;
        doc["circulation_fan3_min"] = -256;
        doc["circulation_fan3_mode"] = "off";
        doc["rev_circfan3"] = circulation_fan3_rev;
        return; // Absolute Kapselung, keine Datenlecks danach!
    }

    doc["circulation_fan3_rpm"] = circulation_fan3_get_rpm();
    doc["circulation_fan3_pct"] = current_circulation_fan3_speed;
    doc["circulation_fan3_speed_now"] = effective_circulation_fan3_speed;
    doc["circulation_fan3_min"] = current_circulation_fan3_min_speed;

    doc["circulation_fan3_mode"] =
        (current_circulation_fan3_mode == circulation_fan3_MODE_NATURAL) ? "nat" :
        (current_circulation_fan3_mode == circulation_fan3_MODE_CHAOTIC) ? "chao" :
        "manual";

    doc["rev_circfan3"] = circulation_fan3_rev;
}
