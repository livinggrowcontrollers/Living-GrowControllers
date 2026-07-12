// exhaust_fan.cpp
// !!! ABSOLUTES GESETZ: DAS TARGET-REVISION-PRINZIP (v2.0) !!!
// -------------------------------------------------------------------------
// 1. HARDWARE FOLGT TARGET: Loop reagiert nur auf target_val vs effective_val.
//    Direktes Pin-Schreiben durch UI-Input ist streng verboten!
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
#include "exhaust_fan.h"
#include <Preferences.h>
#include "sensor.h"
#include <time.h>
#include "ble_scanner.h"
#include "light_control.h"
#include "sys_config.h"
#include "hardware_init.h"

static bool exhaust_fan_enabled = true;

static uint8_t _exhaust_fan_pin;
static uint8_t _tacho_pin; 
static uint32_t failsafe_phase = 0;
static PlantPhase current_phase = DAY_TRANSPIRE;
Preferences exhaust_fanPrefs;
#define EXHAUST_FAILSAFE_MIN 33

// Globale Variablen
int current_exhaust_fan_speed = 60;
exhaust_fanMode current_exhaust_fan_mode = exhaust_fan_MODE_MANUAL;

int exhaust_fan_pct = 25;
int target_exhaust_fan_pct = 60;
int exhaust_fan_min = 25;
float target_temp_min = 22.0f;
float target_temp_max = 28.0f;
int target_humidity_min = 40;
int target_humidity_max = 70;

float target_temp = 26.0;
float target_humidity = 60.0;
float target_vpd_min = 0.8f;
float target_vpd_max = 1.5f;

volatile int exhaust_fan_pulse_count = 0; 
static uint32_t last_exhaust_fan_rpm_check = 0;
static int current_exhaust_fan_rpm = 0;
static uint32_t last_exhaust_fan_pulse_time = 0;
static uint32_t exhaust_fan_rev = 0;     
static uint32_t target_over_threshold_start = 0; 
static float persistence_boost = 0.0f;           
static float temp_trend = 0.0f;
static float hum_trend = 0.0f;
static float last_temp_h = -255.0f;
static float last_hum_h = -255.0f;
static uint32_t last_trend_check = 0;
static uint32_t efficiency_test_start = 0;
static bool efficiency_test_active = false;
static float temp_before_test = 0.0f;
static uint32_t last_wind_change = 0;
static uint32_t last_rev_seen = 0;
static uint32_t last_warn_msg = 0; 

static String exhaust_fan_state_reason_1 = "idle_balanced";
static String exhaust_fan_state_reason_2 = "";

// 🔥 TRACKER FÜR HARDWARE-PINS (Runtime GPIO Fix)
static int current_exh_fan_pin = -1;
static int current_exh_tacho_pin = -1;
static bool vpd_control_enabled = true; 
bool exhaust_fan_chaos_active = false;
bool exhaust_fan_night_reduction = true;

// ============================================================
// HILFSFUNKTIONEN
// ============================================================

void IRAM_ATTR count_exhaust_fan_pulse() {
    uint32_t now = micros();
    uint32_t delta = now - last_exhaust_fan_pulse_time;
    if (delta > 2500) { 
        exhaust_fan_pulse_count++;
        last_exhaust_fan_pulse_time = now;
    }
}

float calculate_current_vpd(float temp, float hum) {
    if (temp < -50.0f || hum < 0.0f) return 1.0f; 
    float svp = 0.61078f * exp((17.27f * temp) / (temp + 237.3f));
    float avp = svp * (hum / 100.0f);
    return svp - avp;
}

float estimate_refined_humidity(float temp_out, float hum_out, float temp_target) {
    if (temp_out >= temp_target) return hum_out; 
    float temp_diff = temp_target - temp_out;
    float refined_hum = hum_out * pow(0.945f, temp_diff); 
    return constrain(refined_hum, 0.0f, 100.0f);
}

// ============================================================
// SYSTEM & PREFS
// ============================================================

void exhaust_fan_save_state() {
    if (!exhaust_fan_enabled) return;
    exhaust_fanPrefs.putInt("min_p", exhaust_fan_min);
    exhaust_fanPrefs.putInt("max_p", exhaust_fan_pct);
    exhaust_fanPrefs.putInt("mode", (int)current_exhaust_fan_mode);
    exhaust_fanPrefs.putFloat("t_min", target_temp_min);
    exhaust_fanPrefs.putFloat("t_max", target_temp_max);
    exhaust_fanPrefs.putInt("h_min", target_humidity_min);
    exhaust_fanPrefs.putInt("h_max", target_humidity_max);
    exhaust_fanPrefs.putFloat("vpd_min", target_vpd_min);
    exhaust_fanPrefs.putFloat("vpd_max", target_vpd_max);
    exhaust_fanPrefs.putBool("chao_active", exhaust_fan_chaos_active);
    exhaust_fanPrefs.putBool("night_red", exhaust_fan_night_reduction);    
}

void reset_exhaust_logic() {
    temp_trend = 0.0f;
    hum_trend = 0.0f;
    last_temp_h = -255.0f;
    last_hum_h  = -255.0f;
    last_trend_check = 0;
    target_over_threshold_start = 0;
    persistence_boost = 0.0f;
    efficiency_test_active = false;
    efficiency_test_start = 0;
    temp_before_test = 0.0f;
}

void exhaust_fan_init(uint8_t pin, uint8_t tacho_pin) {
    if ((int)pin == -1 || (int)tacho_pin == -1) {
        Serial.println("Exhaust Fan disabled (sysConfig). Initialization skipped.");
        exhaust_fan_enabled = false;
        current_exh_fan_pin = -1;
        current_exh_tacho_pin = -1;
        current_exhaust_fan_rpm = -256;
        current_exhaust_fan_speed = -256;
        return;
    }

    _exhaust_fan_pin = pin;
    _tacho_pin = tacho_pin;
    
    current_exh_fan_pin = _exhaust_fan_pin;
    current_exh_tacho_pin = _tacho_pin;

    ledcAttach(_exhaust_fan_pin, 5000, 8);
    
    exhaust_fanPrefs.begin("exhaust_fan", false);
    exhaust_fan_min = exhaust_fanPrefs.getInt("min_p", 20);
    exhaust_fan_pct = exhaust_fanPrefs.getInt("max_p", 25);
    current_exhaust_fan_mode = (exhaust_fanMode)exhaust_fanPrefs.getInt("mode", exhaust_fan_MODE_MANUAL);
    
    target_temp_min = exhaust_fanPrefs.getFloat("t_min", 22.0f);
    target_temp_max = exhaust_fanPrefs.getFloat("t_max", 28.0f);
    target_humidity_min = exhaust_fanPrefs.getInt("h_min", 40);
    target_humidity_max = exhaust_fanPrefs.getInt("h_max", 70);
    target_vpd_min = exhaust_fanPrefs.getFloat("vpd_min", 0.8f);
    target_vpd_max = exhaust_fanPrefs.getFloat("vpd_max", 1.5f);

    if (_tacho_pin != 255) {
        pinMode(_tacho_pin, get_pull_mode(sysConfig.pin_exh_tacho_pull));
        attachInterrupt(digitalPinToInterrupt(_tacho_pin), count_exhaust_fan_pulse, RISING);
    }
    
    exhaust_fan_chaos_active = exhaust_fanPrefs.getBool("chao_active", false);
    exhaust_fan_set_mode(current_exhaust_fan_mode);
    exhaust_fan_rev = millis();
    exhaust_fan_night_reduction = exhaust_fanPrefs.getBool("night_red", true);    
}

void exhaust_fan_reconfigure()
{
    Serial.println("Exhaust Fan Runtime Reconfigure");

    // 1. SCHRITT: Tacho-Interrupt lösen
    if (current_exh_tacho_pin != -1 && current_exh_tacho_pin != 255 && current_exh_tacho_pin != sysConfig.pin_exh_tacho) {
        Serial.printf("Löse alten Tacho-Interrupt auf Pin: %d\n", current_exh_tacho_pin);
        detachInterrupt(digitalPinToInterrupt(current_exh_tacho_pin));
        pinMode(current_exh_tacho_pin, INPUT);
    }

    // 2. SCHRITT: PWM Pin detachen
    if (current_exh_fan_pin != -1 && current_exh_fan_pin != sysConfig.pin_exh_fan) {
        Serial.printf("Löse alten Abluft-PWM Pin: %d\n", current_exh_fan_pin);
        ledcDetach(current_exh_fan_pin);
        pinMode(current_exh_fan_pin, INPUT);
        current_exh_fan_pin = -1;
    }

    _exhaust_fan_pin = sysConfig.pin_exh_fan;
    _tacho_pin = sysConfig.pin_exh_tacho;

    // 3. SCHRITT: Modul-Deaktivierungs-Check (FIX: Härtung)
    if ((int)_exhaust_fan_pin == -1 || (int)_tacho_pin == -1) {
        exhaust_fan_enabled = false;
        current_exh_fan_pin = -1;   
        current_exh_tacho_pin = -1; 
        current_exhaust_fan_rpm = -256;
        current_exhaust_fan_speed = -256;
        Serial.println("Exhaust Fan dauerhaft deaktiviert (Pins = -1).");
        return;
    }

    exhaust_fan_enabled = true;

    // 4. SCHRITT: PWM neu binden
    if (current_exh_fan_pin != _exhaust_fan_pin) {
        ledcAttach(_exhaust_fan_pin, 5000, 8);
        current_exh_fan_pin = _exhaust_fan_pin;
    }

    // 5. SCHRITT: Tacho neu binden
    if (current_exh_tacho_pin != _tacho_pin) {
        if (_tacho_pin != 255) {
            pinMode(_tacho_pin, get_pull_mode(sysConfig.pin_exh_tacho_pull));
            attachInterrupt(digitalPinToInterrupt(_tacho_pin), count_exhaust_fan_pulse, RISING);
        }
        current_exh_tacho_pin = _tacho_pin;
    }

    // 6. SCHRITT: PWM direkt schreiben
    ledcWrite(_exhaust_fan_pin, map(exhaust_fan_pct, 0, 100, 0, 255));

    Serial.printf("Exhaust Fan Runtime Reconfigure Done -> PWM GPIO %d, Tacho GPIO %d\n", _exhaust_fan_pin, _tacho_pin);
}

void exhaust_fan_set_speed(int percent) {
    if (!exhaust_fan_enabled || current_exh_fan_pin == -1) return;
    exhaust_fan_pct = constrain(percent, 0, 100);
    exhaust_fan_save_state();
}

void exhaust_fan_set_mode(exhaust_fanMode mode) {
    if (!exhaust_fan_enabled) return;
    current_exhaust_fan_mode = mode;
    exhaust_fan_save_state();
}

void exhaust_fan_set_min_speed(int percent) {
    if (!exhaust_fan_enabled) return;
    exhaust_fan_min = constrain(percent, 0, 100);
    exhaust_fan_save_state();
}

int exhaust_fan_get_rpm() {
    if (!exhaust_fan_enabled || current_exh_tacho_pin == -1) return -256;
    uint32_t now = millis();
    uint32_t elapsed = now - last_exhaust_fan_rpm_check;

    if (elapsed >= 1000) {
        noInterrupts();
        uint32_t pulses = exhaust_fan_pulse_count;
        exhaust_fan_pulse_count = 0;
        interrupts();

        float pulses_per_rev = 4.0f;
        int calculated_rpm = (int)((pulses / pulses_per_rev) * (60000.0f / elapsed));

        if (current_exhaust_fan_rpm > 500 && calculated_rpm > current_exhaust_fan_rpm * 1.5f) {
            calculated_rpm = current_exhaust_fan_rpm + 50; 
        }
        current_exhaust_fan_rpm = (current_exhaust_fan_rpm * 0.8f) + (calculated_rpm * 0.2f);
        last_exhaust_fan_rpm_check = now;
    }
    return current_exhaust_fan_rpm;
}

// ============================================================
// 🟨 DECISION LAYER (Single Source of Truth)
// ============================================================

struct ExhaustInputs {
    bool is_manual;
    PlantPhase phase;
    float in_temp, in_hum;
    float out_temp, out_hum;
    bool out_ok;
    bool sensors_valid;
    bool night_reduction;
    bool chaos_active;
    int max_pct, min_pct;
    uint32_t current_failsafe_phase;
};

struct ExhaustDecision {
    float target_pct;
    String reason_1;
    String reason_2;
    uint32_t new_failsafe_phase;
};

ExhaustDecision compute_exhaust_decision(const ExhaustInputs& in) {
    ExhaustDecision out;
    out.reason_1 = "idle_balanced";
    out.reason_2 = "";
    out.target_pct = in.min_pct;
    out.new_failsafe_phase = in.current_failsafe_phase;

    if (!in.sensors_valid) {
        out.target_pct = in.max_pct;
        out.reason_1 = "sensor_fail";
        out.reason_2 = "crit_sensor_timeout";
        return out; 
    }

    if (in.is_manual) {
        out.target_pct = in.max_pct;
        out.reason_1 = "manual";
        if (in.night_reduction && in.phase == NIGHT_RECOVERY) {
            out.target_pct *= 0.5f;
            out.reason_1 = "night_manual";
        }
    } 
    else {
        float t_f = constrain((in.in_temp - target_temp_max) / 3.0f, 0.0f, 1.0f);
        float h_f = constrain((in.in_hum - (float)target_humidity_max) / 10.0f, 0.0f, 1.0f);
        float vpd_f = 0.0f;
        
        float current_vpd = calculate_current_vpd(in.in_temp, in.in_hum);
        bool vpd_high = current_vpd > target_vpd_max;
        bool vpd_low  = current_vpd < target_vpd_min;
        bool temp_high = in.in_temp > target_temp_max;
        bool temp_low  = in.in_temp < target_temp_min;
        bool hum_high = in.in_hum > target_humidity_max;
        bool hum_low  = in.in_hum < target_humidity_min;

        if (in.phase == DAY_TRANSPIRE || in.phase == SUNRISE_WAKEUP || in.phase == SUNSET_TRANSITION) {
            if (current_vpd < target_vpd_min) vpd_f = constrain((target_vpd_min - current_vpd) / 0.3f, 0.0f, 1.0f);
            else if (current_vpd > target_vpd_max) vpd_f = constrain((current_vpd - target_vpd_max) / 0.5f, 0.0f, 1.0f);
        }

        float mix_factor = max({t_f, h_f, vpd_f});

        if (in.phase == NIGHT_RECOVERY && in.night_reduction) {
            mix_factor *= 0.5f;
        } else if (in.phase == SUNSET_TRANSITION) {
            mix_factor *= 0.75f;
        } else if (in.phase == SUNRISE_WAKEUP) {
            mix_factor *= 1.1f;
        }

        float dominant = max({t_f, h_f, vpd_f});
        if (dominant <= 0.01f) out.reason_1 = "idle_balanced";
        else if (vpd_f >= t_f && vpd_f >= h_f) out.reason_1 = vpd_high ? "vpd_high" : (vpd_low ? "vpd_low" : "idle_balanced");
        else if (t_f >= h_f) out.reason_1 = temp_high ? "temp_high" : (temp_low ? "temp_low" : "idle_balanced");
        else out.reason_1 = hum_high ? "hum_high" : (hum_low ? "hum_low" : "idle_balanced");

        out.target_pct = (float)in.min_pct + ((in.max_pct - in.min_pct) * mix_factor);

        bool is_failsafe_active = false;
        bool is_refined_active = false;

        if (in.out_ok) {
            bool values_too_high = (in.in_temp > target_temp_max || in.in_hum > target_humidity_max);
            bool outside_is_bad = (in.out_temp > in.in_temp + 0.2f || in.out_hum > in.in_hum + 2.0f);
            bool air_can_be_refined = false;

            if (in.out_temp < target_temp_max) {
                float potential_hum = estimate_refined_humidity(in.out_temp, in.out_hum, target_temp_max);
                if (potential_hum <= (float)target_humidity_max) air_can_be_refined = true;
            }

            if (values_too_high && outside_is_bad && !air_can_be_refined) {
                is_failsafe_active = true;
                out.new_failsafe_phase += 1;
                float pulse = (sin(out.new_failsafe_phase * 0.15f) * 0.5f + 0.5f);
                int fs_min = max((int)EXHAUST_FAILSAFE_MIN, in.min_pct);
                
                out.target_pct = fs_min + ((in.max_pct - fs_min) * pulse);
                out.reason_1 = "failsafe_unrefinable";
            } else if (values_too_high && air_can_be_refined) {
                is_refined_active = true;
                out.reason_1 = "refined_air";
            }
        }

        if (!in.out_ok) {
            out.reason_2 = "out_sensor_offline"; 
        } else {
            if (is_failsafe_active)                                    out.reason_2 = "outside_air_bad";
            else if (is_refined_active)                                out.reason_2 = "outside_air_refinable";
            else if (in.phase == NIGHT_RECOVERY && in.night_reduction) out.reason_2 = "night_reduction";
            else if (in.phase == SUNSET_TRANSITION)                    out.reason_2 = "sunset_phase";
            else if (in.phase == SUNRISE_WAKEUP)                       out.reason_2 = "sunrise_phase"; 
            else if (in.chaos_active)                                  out.reason_2 = "chaos_mode_active";
        }
    }

    if (in.chaos_active) {
        float wobble = (float)random(-80, 81) / 10.0f;
        out.target_pct += wobble;
        if (in.is_manual) out.reason_2 = "chaos_mode_active";
    }

    int real_min = min(in.min_pct, in.max_pct);
    int real_max = max(in.min_pct, in.max_pct);
    out.target_pct = constrain(out.target_pct, (float)real_min, (float)real_max);

    return out;
}

// ============================================================
// MAIN UPDATE SCHLEIFE (Der Wrapper)
// ============================================================

void exhaust_fan_update() {
    // ⚡ FIX: Sofortiger Abbruch, wenn Hardware uninitialisiert oder deaktiviert ist
    if (!exhaust_fan_enabled || current_exh_fan_pin == -1) return;

    uint32_t now = millis();

    if (last_rev_seen != exhaust_fan_rev) {
        last_rev_seen = exhaust_fan_rev;
        last_wind_change = 0;
        reset_exhaust_logic();
    }
    if (now - last_wind_change < 1500 && last_wind_change != 0) return;
    last_wind_change = now;

    // 🟦 INPUT LAYER
    ExhaustInputs inputs;
    inputs.is_manual = (current_exhaust_fan_mode == exhaust_fan_MODE_MANUAL);
    inputs.phase = getPlantPhase();
    current_phase = inputs.phase; 
    inputs.in_temp = getTempExt();
    inputs.in_hum  = getExternalHumidity();
    inputs.out_temp = BLEScanner::get_outside_temp();
    inputs.out_hum  = BLEScanner::get_outside_hum();
    inputs.out_ok   = BLEScanner::is_outside_online();
    inputs.sensors_valid = (inputs.in_temp > -200.0f && inputs.in_hum > -200.0f);
    inputs.night_reduction = exhaust_fan_night_reduction;
    inputs.chaos_active = exhaust_fan_chaos_active;
    inputs.max_pct = exhaust_fan_pct;
    inputs.min_pct = exhaust_fan_min;
    inputs.current_failsafe_phase = failsafe_phase;

    // 🟨 DECISION LAYER
    ExhaustDecision decision = compute_exhaust_decision(inputs);

    // 🟩 OUTPUT LAYER
    failsafe_phase = decision.new_failsafe_phase;
    exhaust_fan_state_reason_1 = decision.reason_1;
    exhaust_fan_state_reason_2 = decision.reason_2;
    current_exhaust_fan_speed = (int)(decision.target_pct + 0.5f);
    
    if (!inputs.out_ok && (now - last_warn_msg > 10000)) {
        Serial.println("⚠️ WARNUNG: Außensensor (outside) ist OFFLINE! Veredelung deaktiviert.");
        last_warn_msg = now;
    }
    
    ledcWrite(_exhaust_fan_pin, map(current_exhaust_fan_speed, 0, 100, 0, 255));
}

// ============================================================
// JSON & KOMMUNIKATION
// ============================================================

void exhaust_fan_process_json(JsonObject doc) {
    bool flash_changed = false;

    if (doc.containsKey("rev_exhaust")) {
        uint32_t received_rev = doc["rev_exhaust"];

        if (received_rev > exhaust_fan_rev) {
            exhaust_fan_rev = received_rev;

            if (doc.containsKey("exhaust_fan_chaos")) {
                exhaust_fan_chaos_active = doc["exhaust_fan_chaos"];
                flash_changed = true; 
            }
            if (doc.containsKey("exhaust_fan_night_reduction")) {
                exhaust_fan_night_reduction = doc["exhaust_fan_night_reduction"];
                flash_changed = true;
            }
            if (doc.containsKey("exhaust_fan_pct")) {
                exhaust_fan_pct = constrain((int)doc["exhaust_fan_pct"], 0, 100);
                flash_changed = true;
            }
            if (doc.containsKey("exhaust_fan_min")) {
                exhaust_fan_min = constrain((int)doc["exhaust_fan_min"], 0, 100);
                flash_changed = true;
            }
            if (doc.containsKey("exhaust_fan_mode")) {
                String m = doc["exhaust_fan_mode"];
                if (m == "auto") current_exhaust_fan_mode = exhaust_fan_MODE_AUTOMATIC;
                else if (m == "manual") current_exhaust_fan_mode = exhaust_fan_MODE_MANUAL;
                flash_changed = true;
            }
            if (doc.containsKey("target_temp_min")) { target_temp_min = constrain((float)doc["target_temp_min"], 15, 35); flash_changed = true; }
            if (doc.containsKey("target_temp_max")) { target_temp_max = constrain((float)doc["target_temp_max"], 15, 35); flash_changed = true; }
            if (doc.containsKey("target_humidity_min")) { target_humidity_min = constrain((int)doc["target_humidity_min"], 0, 100); flash_changed = true; }
            if (doc.containsKey("target_humidity_max")) { target_humidity_max = constrain((int)doc["target_humidity_max"], 0, 100); flash_changed = true; }
            if (doc.containsKey("target_vpd_min")) { target_vpd_min = constrain((float)doc["target_vpd_min"], 0.0f, 3.0f); flash_changed = true; }
            if (doc.containsKey("target_vpd_max")) { target_vpd_max = constrain((float)doc["target_vpd_max"], 0.0f, 3.0f); flash_changed = true; }
        }
    }

    if (flash_changed && exhaust_fan_enabled) {
        exhaust_fanPrefs.putBool("chao_active", exhaust_fan_chaos_active);
        exhaust_fan_save_state();
        reset_exhaust_logic(); 
        Serial.printf("Exhaust Update | Rev: %u | Chaos: %s\n", exhaust_fan_rev, exhaust_fan_chaos_active ? "ON" : "OFF");
    }
}

void exhaust_fan_get_status(JsonObject doc) {
    // ⚡ FIX: Absolute JSON-Kapselung bei inaktiver Hardware zur Eliminierung von Pseudodaten
    if (!exhaust_fan_enabled || sysConfig.pin_exh_fan == -1 || sysConfig.pin_exh_tacho == -1) {
        doc["exhaust_fan_rpm"] = -256;
        doc["exhaust_fan_pct"] = -256;
        doc["exhaust_fan_min"] = -256;
        doc["exhaust_fan_speed_now"] = -256;
        doc["exhaust_fan_mode"] = "off";
        doc["target_temp_min"] = -256;
        doc["target_temp_max"] = -256;
        doc["target_humidity_min"] = -256;
        doc["target_humidity_max"] = -256;
        doc["target_vpd_min"] = -256;
        doc["target_vpd_max"] = -256;
        doc["rev_exhaust"] = exhaust_fan_rev;        
        doc["plant_phase"] = -256;
        doc["exhaust_fan_chaos_active"] = false;
        doc["exhaust_fan_state_reason_1"] = "off";
        doc["exhaust_fan_state_reason_2"] = "disabled";
        doc["exhaust_fan_night_reduction"] = false;
        return; // Direkt abbrechen – keine alten RAM-Werte durchsickern lassen
    }

    doc["exhaust_fan_rpm"] = exhaust_fan_get_rpm();
    doc["exhaust_fan_pct"] = exhaust_fan_pct;
    doc["exhaust_fan_min"] = exhaust_fan_min;
    doc["exhaust_fan_speed_now"] = current_exhaust_fan_speed;
    doc["exhaust_fan_mode"] = (current_exhaust_fan_mode == exhaust_fan_MODE_AUTOMATIC) ? "auto" : "manual";
    doc["target_temp_min"] = target_temp_min;
    doc["target_temp_max"] = target_temp_max;
    doc["target_humidity_min"] = target_humidity_min;
    doc["target_humidity_max"] = target_humidity_max;
    doc["target_vpd_min"] = target_vpd_min;
    doc["target_vpd_max"] = target_vpd_max;
    doc["rev_exhaust"] = exhaust_fan_rev;        
    doc["plant_phase"] = (int)current_phase;
    doc["exhaust_fan_chaos_active"] = exhaust_fan_chaos_active;
    doc["exhaust_fan_state_reason_1"] = exhaust_fan_state_reason_1;
    doc["exhaust_fan_state_reason_2"] = exhaust_fan_state_reason_2;
    doc["exhaust_fan_night_reduction"] = exhaust_fan_night_reduction;
}