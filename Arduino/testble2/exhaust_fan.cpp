#include "exhaust_fan.h"

#include <Preferences.h>

#include "hardware_init.h"
#include "sys_config.h"

namespace {

Preferences exhaustPrefs;
bool preferencesReady = false;
bool moduleEnabled = false;

int exhaustPin = -1;
int tachoPin = -1;
int attachedExhaustPin = -1;
int attachedTachoPin = -1;

int configuredMaxPct = 25;
int configuredMinPct = 20;
exhaust_fanMode configuredMode = exhaust_fan_MODE_MANUAL;
bool chaosActive = false;

int effectiveSpeedPct = 0;
String primaryReason = "idle_balanced";
String secondaryReason = "";

volatile uint32_t pulseCount = 0;
uint32_t lastPulseTime = 0;
uint32_t lastRpmCheck = 0;
int currentRpm = 0;

void IRAM_ATTR count_exhaust_pulse() {
    const uint32_t now = micros();
    if (now - lastPulseTime > 2500) {
        pulseCount = pulseCount + 1;
        lastPulseTime = now;
    }
}

bool ensure_preferences() {
    if (!preferencesReady) {
        preferencesReady = exhaustPrefs.begin("exhaust_fan", false);
    }
    return preferencesReady;
}

void load_config() {
    if (!ensure_preferences()) return;
    configuredMinPct = constrain(exhaustPrefs.getInt("min_p", 20), 0, 100);
    configuredMaxPct = constrain(exhaustPrefs.getInt("max_p", 25), 0, 100);
    configuredMode = static_cast<exhaust_fanMode>(
        exhaustPrefs.getInt("mode", exhaust_fan_MODE_MANUAL)
    );
    if (configuredMode != exhaust_fan_MODE_AUTOMATIC) {
        configuredMode = exhaust_fan_MODE_MANUAL;
    }
    chaosActive = exhaustPrefs.getBool("chao_active", false);
}

void save_config() {
    if (!ensure_preferences()) return;
    exhaustPrefs.putInt("min_p", configuredMinPct);
    exhaustPrefs.putInt("max_p", configuredMaxPct);
    exhaustPrefs.putInt("mode", static_cast<int>(configuredMode));
    exhaustPrefs.putBool("chao_active", chaosActive);
}

void detach_hardware() {
    if (attachedTachoPin != -1 && attachedTachoPin != 255) {
        detachInterrupt(digitalPinToInterrupt(attachedTachoPin));
        pinMode(attachedTachoPin, INPUT);
    }
    if (attachedExhaustPin != -1) {
        ledcDetach(attachedExhaustPin);
        pinMode(attachedExhaustPin, INPUT);
    }
    attachedExhaustPin = -1;
    attachedTachoPin = -1;
}

void attach_hardware() {
    ledcAttach(exhaustPin, 5000, 8);
    attachedExhaustPin = exhaustPin;

    if (tachoPin != 255) {
        pinMode(tachoPin, get_pull_mode(sysConfig.pin_exh_tacho_pull));
        attachInterrupt(digitalPinToInterrupt(tachoPin), count_exhaust_pulse, RISING);
    }
    attachedTachoPin = tachoPin;
}

}  // namespace

void exhaust_fan_init(int pin, int tacho_pin) {
    load_config();

    exhaustPin = pin;
    tachoPin = tacho_pin;

    if (exhaustPin == -1 || tachoPin == -1) {
        moduleEnabled = false;
        effectiveSpeedPct = -256;
        currentRpm = -256;
        Serial.println("Exhaust Fan disabled (sysConfig). Initialization skipped.");
        return;
    }

    moduleEnabled = true;
    effectiveSpeedPct = configuredMaxPct;
    currentRpm = 0;
    attach_hardware();
    exhaust_fan_update();
}

void exhaust_fan_reconfigure() {
    const int nextExhaustPin = sysConfig.pin_exh_fan;
    const int nextTachoPin = sysConfig.pin_exh_tacho;

    if (attachedExhaustPin != nextExhaustPin || attachedTachoPin != nextTachoPin) {
        detach_hardware();
    }

    exhaustPin = nextExhaustPin;
    tachoPin = nextTachoPin;

    if (exhaustPin == -1 || tachoPin == -1) {
        moduleEnabled = false;
        effectiveSpeedPct = -256;
        currentRpm = -256;
        primaryReason = "off";
        secondaryReason = "disabled";
        Serial.println("Exhaust Fan permanently disabled (pins = -1).");
        return;
    }

    moduleEnabled = true;
    if (attachedExhaustPin == -1) {
        attach_hardware();
    }
    if (effectiveSpeedPct < 0) {
        effectiveSpeedPct = configuredMaxPct;
    }
    if (currentRpm < 0) {
        currentRpm = 0;
        pulseCount = 0;
        lastRpmCheck = millis();
    }
    exhaust_fan_update();
    Serial.printf(
        "Exhaust Fan reconfigured -> PWM GPIO %d, tacho GPIO %d\n",
        exhaustPin,
        tachoPin
    );
}

ExhaustFanConfig exhaust_fan_get_config() {
    return {
        moduleEnabled,
        configuredMode,
        chaosActive,
        configuredMinPct,
        configuredMaxPct,
    };
}

void exhaust_fan_apply_config(const ExhaustFanConfig& config) {
    const int nextMinPct = constrain(config.min_pct, 0, 100);
    const int nextMaxPct = constrain(config.max_pct, 0, 100);
    const exhaust_fanMode nextMode = config.mode == exhaust_fan_MODE_AUTOMATIC
        ? exhaust_fan_MODE_AUTOMATIC
        : exhaust_fan_MODE_MANUAL;

    const bool changed = nextMinPct != configuredMinPct
        || nextMaxPct != configuredMaxPct
        || nextMode != configuredMode
        || config.chaos_active != chaosActive;
    if (!changed) return;

    configuredMinPct = nextMinPct;
    configuredMaxPct = nextMaxPct;
    configuredMode = nextMode;
    chaosActive = config.chaos_active;
    save_config();
}

void exhaust_fan_apply_climate_target(
    float target_pct,
    const char* primary_reason,
    const char* secondary_reason
) {
    if (!moduleEnabled) {
        effectiveSpeedPct = -256;
        return;
    }

    const int lower = min(configuredMinPct, configuredMaxPct);
    const int upper = max(configuredMinPct, configuredMaxPct);
    effectiveSpeedPct = static_cast<int>(
        constrain(target_pct, static_cast<float>(lower), static_cast<float>(upper)) + 0.5f
    );
    primaryReason = primary_reason ? primary_reason : "idle_balanced";
    secondaryReason = secondary_reason ? secondary_reason : "";
}

void exhaust_fan_update() {
    if (!moduleEnabled || attachedExhaustPin == -1 || effectiveSpeedPct < 0) return;
    ledcWrite(attachedExhaustPin, map(effectiveSpeedPct, 0, 100, 0, 255));
}

int exhaust_fan_get_rpm() {
    if (!moduleEnabled || attachedTachoPin == -1) return -256;
    if (attachedTachoPin == 255) return 0;

    const uint32_t now = millis();
    const uint32_t elapsed = now - lastRpmCheck;
    if (elapsed >= 1000) {
        noInterrupts();
        const uint32_t pulses = pulseCount;
        pulseCount = 0;
        interrupts();

        int measuredRpm = static_cast<int>((pulses / 4.0f) * (60000.0f / elapsed));
        if (currentRpm > 500 && measuredRpm > currentRpm * 1.5f) {
            measuredRpm = currentRpm + 50;
        }
        currentRpm = static_cast<int>((currentRpm * 0.8f) + (measuredRpm * 0.2f));
        lastRpmCheck = now;
    }
    return currentRpm;
}

void exhaust_fan_get_status(JsonObject doc) {
    if (!moduleEnabled || sysConfig.pin_exh_fan == -1 || sysConfig.pin_exh_tacho == -1) {
        doc["exhaust_fan_rpm"] = -256;
        doc["exhaust_fan_pct"] = -256;
        doc["exhaust_fan_min"] = -256;
        doc["exhaust_fan_speed_now"] = -256;
        doc["exhaust_fan_mode"] = "off";
        doc["exhaust_fan_chaos_active"] = false;
        doc["exhaust_fan_state_reason_1"] = "off";
        doc["exhaust_fan_state_reason_2"] = "disabled";
        return;
    }

    doc["exhaust_fan_rpm"] = exhaust_fan_get_rpm();
    doc["exhaust_fan_pct"] = configuredMaxPct;
    doc["exhaust_fan_min"] = configuredMinPct;
    doc["exhaust_fan_speed_now"] = effectiveSpeedPct;
    doc["exhaust_fan_mode"] = configuredMode == exhaust_fan_MODE_AUTOMATIC ? "auto" : "manual";
    doc["exhaust_fan_chaos_active"] = chaosActive;
    doc["exhaust_fan_state_reason_1"] = primaryReason;
    doc["exhaust_fan_state_reason_2"] = secondaryReason;
}
