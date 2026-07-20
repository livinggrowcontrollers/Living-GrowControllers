#include "telemetry_snapshot.h"

#include "ble_scanner.h"
#include "circulation_fan.h"
#include "circulation_fan2.h"
#include "circulation_fan3.h"
#include "climate_hub.h"
#include "esp_watch.h"
#include "exhaust_fan.h"
#include "grow_controller.h"
#include "humidifier.h"
#include "light_control.h"
#include "ota_manager.h"
#include "plant_planner.h"
#include "power_manager.h"
#include "sensor.h"
#include <WiFi.h>
#include <time.h>

extern ESPWatch watch;
extern int current_rev;

void telemetry_snapshot_fill(JsonObject target, const String& hostname) {
    JsonObject health = target.createNestedObject("health");
    JsonObject signal = health.createNestedObject("signal");
    signal["rssi"] = WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : -256;

    const bool rtc_ok = watch.isRTCHealthy();
    target["rtc_found"] = rtc_ok;
    if (rtc_ok) {
        time_t now;
        struct tm timeinfo;
        time(&now);
        localtime_r(&now, &timeinfo);
        char time_buffer[20];
        snprintf(
            time_buffer,
            sizeof(time_buffer),
            "%02d:%02d:%02d",
            timeinfo.tm_hour,
            timeinfo.tm_min,
            timeinfo.tm_sec
        );
        target["rtc_time"] = time_buffer;
    } else {
        target["rtc_time"] = "offline";
    }

    const time_t system_now = time(nullptr);
    struct tm system_time;
    localtime_r(&system_now, &system_time);
    char system_time_buffer[20];
    snprintf(
        system_time_buffer,
        sizeof(system_time_buffer),
        "%02d:%02d:%02d",
        system_time.tm_hour,
        system_time.tm_min,
        system_time.tm_sec
    );
    target["system_time"] = system_time_buffer;

    target["temp_in"] = getTempIn();
    target["temp_ext"] = getTempExt();
    target["humid_ext"] = getExternalHumidity();
    target["humid_in"] = getInternalHumidity();
    target["leaf_temp"] = -256.0f;
    target["vbat"] = get_battery_voltage_now();
    target["rev"] = current_rev;
    target["hostname"] = hostname;
    target["ip_address"] = WiFi.getMode() == WIFI_AP
        ? WiFi.softAPIP().toString()
        : WiFi.localIP().toString();
    target["mac"] = WiFi.macAddress();

    exhaust_fan_get_status(target);
    humidifier_get_status(target);
    climate_hub_get_status(target);
    circulation_fan_get_status(target);
    circulation_fan2_get_status(target);
    circulation_fan3_get_status(target);
    target["rev_plant_planner"] = get_plant_planner_rev();
    light_control_get_status(target);
    grow_controller_get_status(target);
    BLEScanner::get_status(target);
    ota_manager_get_status(target);
}
