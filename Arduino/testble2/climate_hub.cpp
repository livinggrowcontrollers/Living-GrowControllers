#include "climate_hub.h"

#include <Preferences.h>
#include <math.h>

#include "ble_scanner.h"

// PATCHER BEGIN: CIRCULATION_INCLUDE
#include "circulation_fan.h"
#include "circulation_fan2.h"
#include "circulation_fan3.h"
// PATCHER END: CIRCULATION_INCLUDE

#include "exhaust_fan.h"
#include "humidifier.h"
#include "light_control.h"
#include "sensor.h"

namespace {

constexpr uint8_t CLIMATE_SCHEMA_VERSION = 1;
constexpr int EXHAUST_FAILSAFE_MIN_PCT = 33;
constexpr uint32_t POLICY_INTERVAL_MS = 1500;

enum PlantPhase : uint8_t {
    DAY_TRANSPIRE = 0,
    SUNSET_TRANSITION = 1,
    NIGHT_RECOVERY = 2,
    SUNRISE_WAKEUP = 3,
};

struct ClimateTargets {
    float temp_min;
    float temp_max;
    int humidity_min;
    int humidity_max;
    float vpd_min;
    float vpd_max;
};

Preferences climatePrefs;
bool preferencesReady = false;

ClimateTargets targets = {22.0f, 28.0f, 40, 70, 0.8f, 1.5f};
bool nightPolicyEnabled = true;
uint32_t climateHubRevision = 0;
PlantPhase currentPhase = DAY_TRANSPIRE;

uint32_t lastPolicyUpdate = 0;
uint32_t lastRevisionSeen = 0;
uint32_t lastOutsideWarning = 0;
uint32_t failsafePhase = 0;

struct ClimateSnapshot {
    float indoor_temp;
    float indoor_humidity;
    float indoor_vpd;
    bool indoor_valid;
    float outside_temp;
    float outside_humidity;
    bool outside_valid;
};

struct ExhaustDecision {
    float target_pct;
    const char* primary_reason;
    const char* secondary_reason;
    uint32_t next_failsafe_phase;
};

struct HumidifierDecision {
    float factor;
    const char* reason;
};

bool has_json_key(JsonObject doc, const char* key) {
    return !doc[key].isNull();
}

void normalize_targets(ClimateTargets& value) {
    value.temp_min = constrain(value.temp_min, 15.0f, 35.0f);
    value.temp_max = constrain(value.temp_max, 15.0f, 35.0f);
    value.humidity_min = constrain(value.humidity_min, 0, 100);
    value.humidity_max = constrain(value.humidity_max, 0, 100);
    value.vpd_min = constrain(value.vpd_min, 0.0f, 3.0f);
    value.vpd_max = constrain(value.vpd_max, 0.0f, 3.0f);

    if (value.temp_min > value.temp_max) {
        const float swap = value.temp_min;
        value.temp_min = value.temp_max;
        value.temp_max = swap;
    }
    if (value.humidity_min > value.humidity_max) {
        const int swap = value.humidity_min;
        value.humidity_min = value.humidity_max;
        value.humidity_max = swap;
    }
    if (value.vpd_min > value.vpd_max) {
        const float swap = value.vpd_min;
        value.vpd_min = value.vpd_max;
        value.vpd_max = swap;
    }
}

bool save_state() {
    if (!preferencesReady) return false;

    bool ok = true;
    ok = climatePrefs.putFloat("t_min", targets.temp_min) > 0 && ok;
    ok = climatePrefs.putFloat("t_max", targets.temp_max) > 0 && ok;
    ok = climatePrefs.putInt("h_min", targets.humidity_min) > 0 && ok;
    ok = climatePrefs.putInt("h_max", targets.humidity_max) > 0 && ok;
    ok = climatePrefs.putFloat("vpd_min", targets.vpd_min) > 0 && ok;
    ok = climatePrefs.putFloat("vpd_max", targets.vpd_max) > 0 && ok;
    ok = climatePrefs.putBool("night", nightPolicyEnabled) > 0 && ok;
    ok = climatePrefs.putUInt("rev", climateHubRevision) > 0 && ok;
    ok = climatePrefs.putUChar("schema", CLIMATE_SCHEMA_VERSION) > 0 && ok;
    return ok;
}

void migrate_legacy_exhaust_targets() {
    Preferences legacy;
    if (!legacy.begin("exhaust_fan", false)) {
        save_state();
        return;
    }

    targets.temp_min = legacy.getFloat("t_min", targets.temp_min);
    targets.temp_max = legacy.getFloat("t_max", targets.temp_max);
    targets.humidity_min = legacy.getInt("h_min", targets.humidity_min);
    targets.humidity_max = legacy.getInt("h_max", targets.humidity_max);
    targets.vpd_min = legacy.getFloat("vpd_min", targets.vpd_min);
    targets.vpd_max = legacy.getFloat("vpd_max", targets.vpd_max);
    nightPolicyEnabled = legacy.getBool("night_red", nightPolicyEnabled);
    normalize_targets(targets);

    if (save_state()) {
        legacy.remove("t_min");
        legacy.remove("t_max");
        legacy.remove("h_min");
        legacy.remove("h_max");
        legacy.remove("vpd_min");
        legacy.remove("vpd_max");
        legacy.remove("night_red");
        Serial.println("Climate Hub migrated legacy Exhaust climate targets.");
    } else {
        Serial.println("Climate Hub migration failed; legacy targets were preserved.");
    }
    legacy.end();
}

float calculate_vpd(float temperature, float humidity) {
    if (!is_sensor_value_valid(temperature) || !is_sensor_value_valid(humidity)) {
        return -256.0f;
    }
    const float saturation = 0.61078f * expf((17.27f * temperature) / (temperature + 237.3f));
    const float actual = saturation * (humidity / 100.0f);
    return max(0.0f, saturation - actual);
}

float estimate_refined_humidity(float outside_temp, float outside_humidity, float target_temp) {
    if (outside_temp >= target_temp) return outside_humidity;
    const float temperatureDifference = target_temp - outside_temp;
    return constrain(outside_humidity * powf(0.945f, temperatureDifference), 0.0f, 100.0f);
}

PlantPhase phase_from_light() {
    switch (light_get_current_phase()) {
        case LIGHT_PHASE_SUNRISE:
            return SUNRISE_WAKEUP;
        case LIGHT_PHASE_SUNSET:
            return SUNSET_TRANSITION;
        case LIGHT_PHASE_NIGHT:
            return NIGHT_RECOVERY;
        case LIGHT_PHASE_DAY:
        default:
            return DAY_TRANSPIRE;
    }
}

ClimateSnapshot read_snapshot() {
    ClimateSnapshot snapshot;
    snapshot.indoor_temp = getTempIn();
    snapshot.indoor_humidity = getInternalHumidity();
    snapshot.indoor_valid = is_sensor_value_valid(snapshot.indoor_temp)
        && is_sensor_value_valid(snapshot.indoor_humidity);
    snapshot.indoor_vpd = snapshot.indoor_valid
        ? calculate_vpd(snapshot.indoor_temp, snapshot.indoor_humidity)
        : -256.0f;

    BLEScanner::BLESnapshot bleSnapshot;
    BLEScanner::get_snapshot(bleSnapshot);
    snapshot.outside_temp = bleSnapshot.outside_temp;
    snapshot.outside_humidity = bleSnapshot.outside_hum;
    snapshot.outside_valid = bleSnapshot.outside_online
        && is_sensor_value_valid(snapshot.outside_temp)
        && is_sensor_value_valid(snapshot.outside_humidity);
    return snapshot;
}

float light_climate_factor(const ClimateSnapshot& snapshot) {
    if (!light_climate_override_enabled() || !snapshot.indoor_valid) {
        return 1.0f;
    }

    float factor = 1.0f;
    if (snapshot.indoor_temp > targets.temp_max) {
        factor = min(factor, 0.85f);
    }
    if (snapshot.indoor_humidity < static_cast<float>(targets.humidity_min)) {
        factor = min(factor, 0.90f);
    }
    if (snapshot.indoor_humidity > static_cast<float>(targets.humidity_max)) {
        factor = min(factor, 0.95f);
    }
    return constrain(factor, 0.75f, 1.0f);
}

HumidifierDecision compute_humidifier_decision(const ClimateSnapshot& snapshot) {
    if (!snapshot.indoor_valid) {
        return {0.0f, "sensor_fail"};
    }

    const float humidityFactor = constrain(
        (static_cast<float>(targets.humidity_min) - snapshot.indoor_humidity) / 10.0f,
        0.0f,
        1.0f
    );
    const float vpdFactor = constrain(
        (snapshot.indoor_vpd - targets.vpd_max) / 0.5f,
        0.0f,
        1.0f
    );

    float factor = max(humidityFactor, vpdFactor);
    const bool humidityDominates = humidityFactor >= vpdFactor;
    const char* reason = factor <= 0.01f
        ? "balanced"
        : (humidityDominates ? "humidity_low" : "vpd_high");

    if (factor > 0.0f && nightPolicyEnabled && currentPhase == NIGHT_RECOVERY) {
        factor *= 0.5f;
        reason = humidityDominates ? "humidity_low_night" : "vpd_high_night";
    }

    return {constrain(factor, 0.0f, 1.0f), reason};
}

ExhaustDecision compute_exhaust_decision(
    const ClimateSnapshot& snapshot,
    const ExhaustFanConfig& fan
) {
    ExhaustDecision decision = {
        static_cast<float>(fan.min_pct),
        "idle_balanced",
        "",
        failsafePhase,
    };

    if (!snapshot.indoor_valid) {
        decision.target_pct = fan.max_pct;
        decision.primary_reason = "sensor_fail";
        decision.secondary_reason = "crit_sensor_timeout";
    } else if (fan.mode == exhaust_fan_MODE_MANUAL) {
        decision.target_pct = fan.max_pct;
        decision.primary_reason = "manual";
        if (nightPolicyEnabled && currentPhase == NIGHT_RECOVERY) {
            decision.target_pct *= 0.5f;
            decision.primary_reason = "night_manual";
        }
    } else {
        const float temperatureFactor = constrain(
            (snapshot.indoor_temp - targets.temp_max) / 3.0f,
            0.0f,
            1.0f
        );
        const float humidityFactor = constrain(
            (snapshot.indoor_humidity - static_cast<float>(targets.humidity_max)) / 10.0f,
            0.0f,
            1.0f
        );
        float vpdFactor = 0.0f;

        const bool vpdHigh = snapshot.indoor_vpd > targets.vpd_max;
        const bool vpdLow = snapshot.indoor_vpd < targets.vpd_min;
        const bool temperatureHigh = snapshot.indoor_temp > targets.temp_max;
        const bool temperatureLow = snapshot.indoor_temp < targets.temp_min;
        const bool humidityHigh = snapshot.indoor_humidity > targets.humidity_max;
        const bool humidityLow = snapshot.indoor_humidity < targets.humidity_min;

        if (currentPhase != NIGHT_RECOVERY) {
            if (vpdLow) {
                vpdFactor = constrain((targets.vpd_min - snapshot.indoor_vpd) / 0.3f, 0.0f, 1.0f);
            } else if (vpdHigh) {
                vpdFactor = constrain((snapshot.indoor_vpd - targets.vpd_max) / 0.5f, 0.0f, 1.0f);
            }
        }

        float mixFactor = max(temperatureFactor, max(humidityFactor, vpdFactor));
        if (currentPhase == NIGHT_RECOVERY && nightPolicyEnabled) {
            mixFactor *= 0.5f;
        } else if (currentPhase == SUNSET_TRANSITION) {
            mixFactor *= 0.75f;
        } else if (currentPhase == SUNRISE_WAKEUP) {
            mixFactor *= 1.1f;
        }

        const float dominant = max(temperatureFactor, max(humidityFactor, vpdFactor));
        if (dominant <= 0.01f) {
            decision.primary_reason = "idle_balanced";
        } else if (vpdFactor >= temperatureFactor && vpdFactor >= humidityFactor) {
            decision.primary_reason = vpdHigh ? "vpd_high" : (vpdLow ? "vpd_low" : "idle_balanced");
        } else if (temperatureFactor >= humidityFactor) {
            decision.primary_reason = temperatureHigh
                ? "temp_high"
                : (temperatureLow ? "temp_low" : "idle_balanced");
        } else {
            decision.primary_reason = humidityHigh
                ? "hum_high"
                : (humidityLow ? "hum_low" : "idle_balanced");
        }

        decision.target_pct = fan.min_pct + ((fan.max_pct - fan.min_pct) * mixFactor);
        bool failsafeActive = false;
        bool refinedAirActive = false;

        if (snapshot.outside_valid) {
            const bool valuesTooHigh = temperatureHigh || humidityHigh;
            const bool outsideIsBad = snapshot.outside_temp > snapshot.indoor_temp + 0.2f
                || snapshot.outside_humidity > snapshot.indoor_humidity + 2.0f;
            bool airCanBeRefined = false;

            if (snapshot.outside_temp < targets.temp_max) {
                const float potentialHumidity = estimate_refined_humidity(
                    snapshot.outside_temp,
                    snapshot.outside_humidity,
                    targets.temp_max
                );
                airCanBeRefined = potentialHumidity <= static_cast<float>(targets.humidity_max);
            }

            if (valuesTooHigh && outsideIsBad && !airCanBeRefined) {
                failsafeActive = true;
                decision.next_failsafe_phase++;
                const float pulse = sinf(decision.next_failsafe_phase * 0.15f) * 0.5f + 0.5f;
                const int failsafeMin = max(EXHAUST_FAILSAFE_MIN_PCT, fan.min_pct);
                decision.target_pct = failsafeMin + ((fan.max_pct - failsafeMin) * pulse);
                decision.primary_reason = "failsafe_unrefinable";
            } else if (valuesTooHigh && airCanBeRefined) {
                refinedAirActive = true;
                decision.primary_reason = "refined_air";
            }
        }

        if (!snapshot.outside_valid) {
            decision.secondary_reason = "out_sensor_offline";
        } else if (failsafeActive) {
            decision.secondary_reason = "outside_air_bad";
        } else if (refinedAirActive) {
            decision.secondary_reason = "outside_air_refinable";
        } else if (currentPhase == NIGHT_RECOVERY && nightPolicyEnabled) {
            decision.secondary_reason = "night_reduction";
        } else if (currentPhase == SUNSET_TRANSITION) {
            decision.secondary_reason = "sunset_phase";
        } else if (currentPhase == SUNRISE_WAKEUP) {
            decision.secondary_reason = "sunrise_phase";
        } else if (fan.chaos_active) {
            decision.secondary_reason = "chaos_mode_active";
        }
    }

    if (fan.chaos_active) {
        decision.target_pct += static_cast<float>(random(-80, 81)) / 10.0f;
        if (fan.mode == exhaust_fan_MODE_MANUAL) {
            decision.secondary_reason = "chaos_mode_active";
        }
    }

    const int lower = min(fan.min_pct, fan.max_pct);
    const int upper = max(fan.min_pct, fan.max_pct);
    decision.target_pct = constrain(
        decision.target_pct,
        static_cast<float>(lower),
        static_cast<float>(upper)
    );
    return decision;
}

void reset_policy_state() {
    failsafePhase = 0;
    lastPolicyUpdate = 0;
}

}  // namespace

void climate_hub_init() {
    preferencesReady = climatePrefs.begin("climate_hub", false);
    if (!preferencesReady) {
        Serial.println("Climate Hub could not open its Preferences namespace.");
        return;
    }

    const uint8_t schema = climatePrefs.getUChar("schema", 0);
    if (schema < CLIMATE_SCHEMA_VERSION) {
        migrate_legacy_exhaust_targets();
    } else {
        targets.temp_min = climatePrefs.getFloat("t_min", targets.temp_min);
        targets.temp_max = climatePrefs.getFloat("t_max", targets.temp_max);
        targets.humidity_min = climatePrefs.getInt("h_min", targets.humidity_min);
        targets.humidity_max = climatePrefs.getInt("h_max", targets.humidity_max);
        targets.vpd_min = climatePrefs.getFloat("vpd_min", targets.vpd_min);
        targets.vpd_max = climatePrefs.getFloat("vpd_max", targets.vpd_max);
        nightPolicyEnabled = climatePrefs.getBool("night", nightPolicyEnabled);
        climateHubRevision = climatePrefs.getUInt("rev", 0);
        normalize_targets(targets);
    }

    currentPhase = phase_from_light();
    lastRevisionSeen = climateHubRevision;
    Serial.printf(
        "Climate Hub initialized | rev=%lu\n",
        static_cast<unsigned long>(climateHubRevision)
    );
}

void climate_hub_update() {
    currentPhase = phase_from_light();

    const uint32_t now = millis();
    if (lastRevisionSeen != climateHubRevision) {
        lastRevisionSeen = climateHubRevision;
        reset_policy_state();
    }
    if (lastPolicyUpdate != 0 && now - lastPolicyUpdate < POLICY_INTERVAL_MS) {
        return;
    }
    lastPolicyUpdate = now;

    const ClimateSnapshot snapshot = read_snapshot();
    light_apply_climate_factor(light_climate_factor(snapshot));

    const HumidifierDecision humidifier = compute_humidifier_decision(snapshot);
    humidifier_apply_climate_factor(humidifier.factor, humidifier.reason);

    // Climate Hub owns the runtime path for every generated fan instance.
    // A factor of 1.0 intentionally preserves today's circulation behavior;
    // a concrete Night policy can later change this single value.
    const float circulationFactor = 1.0f;
    // PATCHER BEGIN: CIRCULATION_CLIMATE_APPLY
    circulation_fan_apply_climate_factor(circulationFactor);
    circulation_fan2_apply_climate_factor(circulationFactor);
    circulation_fan3_apply_climate_factor(circulationFactor);
    // PATCHER END: CIRCULATION_CLIMATE_APPLY

    const ExhaustFanConfig fan = exhaust_fan_get_config();
    if (fan.enabled) {
        const ExhaustDecision decision = compute_exhaust_decision(snapshot, fan);
        failsafePhase = decision.next_failsafe_phase;
        exhaust_fan_apply_climate_target(
            decision.target_pct,
            decision.primary_reason,
            decision.secondary_reason
        );
    }

    if (!snapshot.outside_valid && now - lastOutsideWarning > 10000) {
        Serial.println("Warning: outside BLE sensor offline; outside-air refinement disabled.");
        lastOutsideWarning = now;
    }
}

void climate_hub_process_json(JsonObject doc) {
    if (!has_json_key(doc, "rev_exhaust")) return;

    const uint32_t receivedRevision = doc["rev_exhaust"].as<uint32_t>();
    if (receivedRevision <= climateHubRevision) return;

    ClimateTargets candidate = targets;
    if (has_json_key(doc, "target_temp_min")) candidate.temp_min = doc["target_temp_min"];
    if (has_json_key(doc, "target_temp_max")) candidate.temp_max = doc["target_temp_max"];
    if (has_json_key(doc, "target_humidity_min")) candidate.humidity_min = doc["target_humidity_min"];
    if (has_json_key(doc, "target_humidity_max")) candidate.humidity_max = doc["target_humidity_max"];
    if (has_json_key(doc, "target_vpd_min")) candidate.vpd_min = doc["target_vpd_min"];
    if (has_json_key(doc, "target_vpd_max")) candidate.vpd_max = doc["target_vpd_max"];
    normalize_targets(candidate);

    bool candidateNightPolicy = nightPolicyEnabled;
    if (has_json_key(doc, "exhaust_fan_night_reduction")) {
        candidateNightPolicy = doc["exhaust_fan_night_reduction"];
    }

    ExhaustFanConfig fan = exhaust_fan_get_config();
    const bool hasFanConfig = has_json_key(doc, "exhaust_fan_min")
        || has_json_key(doc, "exhaust_fan_pct")
        || has_json_key(doc, "exhaust_fan_chaos")
        || has_json_key(doc, "exhaust_fan_mode");
    if (has_json_key(doc, "exhaust_fan_min")) {
        fan.min_pct = constrain(doc["exhaust_fan_min"].as<int>(), 0, 100);
    }
    if (has_json_key(doc, "exhaust_fan_pct")) {
        fan.max_pct = constrain(doc["exhaust_fan_pct"].as<int>(), 0, 100);
    }
    if (has_json_key(doc, "exhaust_fan_chaos")) {
        fan.chaos_active = doc["exhaust_fan_chaos"];
    }
    if (has_json_key(doc, "exhaust_fan_mode")) {
        const String mode = doc["exhaust_fan_mode"].as<String>();
        if (mode == "auto") fan.mode = exhaust_fan_MODE_AUTOMATIC;
        if (mode == "manual") fan.mode = exhaust_fan_MODE_MANUAL;
    }

    targets = candidate;
    nightPolicyEnabled = candidateNightPolicy;
    if (hasFanConfig) {
        exhaust_fan_apply_config(fan);
    }
    climateHubRevision = receivedRevision;
    save_state();
    reset_policy_state();

    Serial.printf(
        "Climate Hub accepted rev=%lu\n",
        static_cast<unsigned long>(climateHubRevision)
    );
}

void climate_hub_get_status(JsonObject doc) {
    doc["target_temp_min"] = targets.temp_min;
    doc["target_temp_max"] = targets.temp_max;
    doc["target_humidity_min"] = targets.humidity_min;
    doc["target_humidity_max"] = targets.humidity_max;
    doc["target_vpd_min"] = targets.vpd_min;
    doc["target_vpd_max"] = targets.vpd_max;
    doc["rev_exhaust"] = climateHubRevision;
    doc["plant_phase"] = static_cast<int>(currentPhase);
    doc["exhaust_fan_night_reduction"] = nightPolicyEnabled;
}
