#include "humidifier.h"

#include <Preferences.h>

#include "sys_config.h"

namespace {

constexpr uint32_t PWM_FREQUENCY_HZ = 25000;
constexpr uint8_t PWM_RESOLUTION_BITS = 8;
constexpr uint8_t PWM_MIN_ACTIVE_DUTY = 65;
constexpr int DEFAULT_TARGET_PCT = 60;
constexpr const char* PREFERENCES_NAMESPACE = "humidifier";
constexpr const char* TARGET_PREF_KEY = "pct";
constexpr const char* REVISION_PREF_KEY = "rev";

Preferences humidifierPrefs;
bool preferencesReady = false;
bool humidifierEnabled = false;
int configuredPin = -1;
int currentPin = -1;
int targetPct = DEFAULT_TARGET_PCT;
int effectivePct = 0;
float climateFactor = 0.0f;
uint32_t humidifierRevision = 0;
char climateReason[32] = "waiting_for_climate";

uint32_t duty_for_percent(int percent) {
    const int constrained = constrain(percent, 0, 100);
    if (constrained == 0) return 0;
    return map(constrained, 1, 100, PWM_MIN_ACTIVE_DUTY, 255);
}

void set_reason(const char* reason) {
    strlcpy(
        climateReason,
        (reason && reason[0] != '\0') ? reason : "balanced",
        sizeof(climateReason)
    );
}

bool save_state() {
    if (!preferencesReady) return false;

    bool ok = true;
    ok = humidifierPrefs.putInt(TARGET_PREF_KEY, targetPct) == sizeof(int32_t) && ok;
    ok = humidifierPrefs.putUInt(REVISION_PREF_KEY, humidifierRevision) == sizeof(uint32_t) && ok;
    if (!ok) {
        Serial.println("Humidifier: state could not be persisted completely.");
    }
    return ok;
}

void stop_and_detach_current_pin() {
    if (currentPin < 0) return;
    ledcWrite(currentPin, 0);
    ledcDetach(currentPin);
    pinMode(currentPin, INPUT);
    currentPin = -1;
}

void attach_configured_pin() {
    if (configuredPin < 0) {
        humidifierEnabled = false;
        effectivePct = -256;
        set_reason("disabled");
        return;
    }

    if (!ledcAttach(configuredPin, PWM_FREQUENCY_HZ, PWM_RESOLUTION_BITS)) {
        humidifierEnabled = false;
        effectivePct = -256;
        set_reason("pwm_attach_failed");
        Serial.printf("Humidifier: PWM attach failed on GPIO %d.\n", configuredPin);
        return;
    }

    currentPin = configuredPin;
    humidifierEnabled = true;
    effectivePct = 0;
    ledcWrite(currentPin, 0);
    Serial.printf("Humidifier active on PWM GPIO %d.\n", currentPin);
}

}  // namespace

void humidifier_init(int pin) {
    preferencesReady = humidifierPrefs.begin(PREFERENCES_NAMESPACE, false);
    if (!preferencesReady) {
        Serial.println("Humidifier: Preferences namespace could not be opened.");
    } else {
        targetPct = constrain(humidifierPrefs.getInt(TARGET_PREF_KEY, DEFAULT_TARGET_PCT), 0, 100);
        humidifierRevision = humidifierPrefs.getUInt(REVISION_PREF_KEY, 0);
    }

    configuredPin = pin;
    attach_configured_pin();
}

void humidifier_reconfigure() {
    const int nextPin = sysConfig.pin_humidifier;
    if (nextPin == currentPin && humidifierEnabled) return;

    stop_and_detach_current_pin();
    configuredPin = nextPin;
    attach_configured_pin();
    humidifier_update();
}

void humidifier_apply_climate_factor(float factor, const char* reason) {
    climateFactor = constrain(factor, 0.0f, 1.0f);
    set_reason(reason);
}

void humidifier_update() {
    if (!humidifierEnabled || currentPin < 0) return;

    effectivePct = constrain(
        static_cast<int>(targetPct * climateFactor + 0.5f),
        0,
        100
    );
    ledcWrite(currentPin, duty_for_percent(effectivePct));
}

void humidifier_process_json(JsonObject doc) {
    if (doc["rev_humidifier"].isNull()) return;

    const uint32_t receivedRevision = doc["rev_humidifier"].as<uint32_t>();
    if (receivedRevision <= humidifierRevision) return;

    if (!doc["humidifier_pct"].isNull()) {
        targetPct = constrain(doc["humidifier_pct"].as<int>(), 0, 100);
    }
    humidifierRevision = receivedRevision;
    save_state();
    humidifier_update();

    Serial.printf(
        "Humidifier accepted rev=%lu | target=%d%%\n",
        static_cast<unsigned long>(humidifierRevision),
        targetPct
    );
}

void humidifier_get_status(JsonObject doc) {
    if (!humidifierEnabled || sysConfig.pin_humidifier < 0) {
        doc["humidifier_pct"] = -256;
        doc["humidifier_speed_now"] = -256;
        doc["humidifier_status"] = "disabled";
        doc["rev_humidifier"] = humidifierRevision;
        return;
    }

    doc["humidifier_pct"] = targetPct;
    doc["humidifier_speed_now"] = effectivePct;
    doc["humidifier_status"] = climateReason;
    doc["rev_humidifier"] = humidifierRevision;
}
