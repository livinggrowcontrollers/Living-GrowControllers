#include "cloud_logging.h"

#include "firmware_version.h"
#include "telemetry_snapshot.h"
#include <Arduino.h>
#include <HTTPClient.h>
#include <NetworkClientSecure.h>
#include <Preferences.h>
#include <WiFi.h>
#include <esp_mac.h>
#include <math.h>
#include <time.h>

namespace {
constexpr const char* PREF_NAMESPACE = "cloudlog";
constexpr const char* PREF_ENABLED = "enabled";
constexpr const char* PREF_ENDPOINT = "endpoint";
constexpr const char* PREF_DEVICE_ID = "device_id";
constexpr const char* PREF_TOKEN = "token";
constexpr const char* PREF_INTERVAL = "interval";
constexpr const char* PREF_TIMEOUT = "timeout";
constexpr uint16_t DEFAULT_INTERVAL_MINUTES = 15;
constexpr uint16_t DEFAULT_TIMEOUT_SECONDS = 10;
constexpr size_t MAX_SERIAL_COMMAND = 1024;

struct CloudConfig {
    bool enabled = false;
    String endpoint;
    String device_id;
    String token;
    uint16_t interval_minutes = DEFAULT_INTERVAL_MINUTES;
    uint16_t timeout_seconds = DEFAULT_TIMEOUT_SECONDS;
};

struct UploadJob {
    String endpoint;
    String token;
    String payload;
    uint16_t timeout_seconds = DEFAULT_TIMEOUT_SECONDS;
};

CloudConfig active_config;
UploadJob pending_job;
SemaphoreHandle_t job_mutex = nullptr;
TaskHandle_t upload_task_handle = nullptr;
uint32_t last_queue_ms = 0;
uint32_t packet_counter = 0;
int last_http_status = 0;
String serial_line;

bool valid_device_id(const String& value) {
    if (!value.startsWith("growmaster-") || value.length() < 12 || value.length() > 58) {
        return false;
    }
    for (size_t index = 11; index < value.length(); ++index) {
        const char character = value[index];
        const bool valid = (character >= 'a' && character <= 'z')
            || (character >= '0' && character <= '9')
            || character == '-';
        if (!valid) return false;
    }
    return value[value.length() - 1] != '-';
}

bool valid_endpoint(const String& value) {
    return value.startsWith("https://")
        && value.length() <= 200
        && value.indexOf(' ') < 0
        && value.indexOf('?') < 0
        && value.indexOf('#') < 0;
}

String normalized_endpoint(String value) {
    value.trim();
    while (value.endsWith("/")) value.remove(value.length() - 1);
    if (value.endsWith("/snapshot")) value.remove(value.length() - 9);
    return value;
}

String default_device_id() {
    uint8_t mac[6] = {};
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    char suffix[5];
    snprintf(suffix, sizeof(suffix), "%02x%02x", mac[4], mac[5]);
    return String("growmaster-") + suffix;
}

bool save_config(const CloudConfig& candidate, bool write_token) {
    Preferences preferences;
    if (!preferences.begin(PREF_NAMESPACE, false)) return false;

    bool ok = preferences.putBool(PREF_ENABLED, candidate.enabled) == 1;
    ok = preferences.putString(PREF_ENDPOINT, candidate.endpoint) == candidate.endpoint.length() && ok;
    ok = preferences.putString(PREF_DEVICE_ID, candidate.device_id) == candidate.device_id.length() && ok;
    ok = preferences.putUShort(PREF_INTERVAL, candidate.interval_minutes) == sizeof(uint16_t) && ok;
    ok = preferences.putUShort(PREF_TIMEOUT, candidate.timeout_seconds) == sizeof(uint16_t) && ok;
    if (write_token) {
        ok = preferences.putString(PREF_TOKEN, candidate.token) == candidate.token.length() && ok;
    }
    preferences.end();
    if (ok) active_config = candidate;
    return ok;
}

bool apply_config(JsonObject source, bool allow_token) {
    const bool has_cloud_field = source.containsKey("cloud_enabled")
        || source.containsKey("cloud_endpoint")
        || source.containsKey("cloud_device_id")
        || source.containsKey("cloud_upload_interval_minutes")
        || source.containsKey("cloud_timeout_seconds")
        || (allow_token && source.containsKey("cloud_upload_token"));
    if (!has_cloud_field) return true;

    CloudConfig candidate = active_config;
    if (source.containsKey("cloud_enabled")) {
        candidate.enabled = source["cloud_enabled"].as<bool>();
    }
    if (source.containsKey("cloud_endpoint")) {
        candidate.endpoint = normalized_endpoint(source["cloud_endpoint"].as<String>());
    }
    if (source.containsKey("cloud_device_id")) {
        candidate.device_id = source["cloud_device_id"].as<String>();
        candidate.device_id.trim();
        candidate.device_id.toLowerCase();
    }
    if (source.containsKey("cloud_upload_interval_minutes")) {
        candidate.interval_minutes = source["cloud_upload_interval_minutes"].as<uint16_t>();
    }
    if (source.containsKey("cloud_timeout_seconds")) {
        candidate.timeout_seconds = source["cloud_timeout_seconds"].as<uint16_t>();
    }
    const bool writes_token = allow_token && source.containsKey("cloud_upload_token");
    if (writes_token) {
        candidate.token = source["cloud_upload_token"].as<String>();
        candidate.token.trim();
    }

    if ((!candidate.endpoint.isEmpty() && !valid_endpoint(candidate.endpoint))
        || !valid_device_id(candidate.device_id)
        || candidate.interval_minutes < 5
        || candidate.interval_minutes > 1440
        || candidate.timeout_seconds < 3
        || candidate.timeout_seconds > 15
        || (writes_token && (candidate.token.length() < 32 || candidate.token.length() > 256))) {
        return false;
    }
    if (candidate.enabled && (!valid_endpoint(candidate.endpoint) || candidate.token.length() < 32)) return false;
    return save_config(candidate, writes_token);
}

void add_metric(
    JsonObject metrics,
    const char* key,
    JsonVariantConst source,
    double minimum,
    double maximum
) {
    if (source.isNull()) return;
    const double value = source.as<double>();
    if (!isfinite(value) || value < minimum || value > maximum) return;
    metrics[key] = value;
}

bool build_payload(String& payload) {
    static DynamicJsonDocument telemetry(6144);
    telemetry.clear();
    telemetry_snapshot_fill(telemetry.to<JsonObject>(), active_config.device_id);
    if (telemetry.overflowed()) return false;

    StaticJsonDocument<3072> upload;
    upload["schema_version"] = 1;
    upload["device_id"] = active_config.device_id;
    upload["firmware"] = FIRMWARE_VERSION;
    upload["uptime_s"] = millis() / 1000;
    upload["packet_counter"] = packet_counter++;
    JsonObject metrics = upload.createNestedObject("metrics");

    add_metric(metrics, "temp_in", telemetry["temp_in"], -50, 100);
    add_metric(metrics, "humid_in", telemetry["humid_in"], 0, 100);
    add_metric(metrics, "temp_ext", telemetry["temp_ext"], -50, 100);
    add_metric(metrics, "humid_ext", telemetry["humid_ext"], 0, 100);
    add_metric(metrics, "vbat", telemetry["vbat"], 0, 30);
    add_metric(metrics, "rssi", telemetry["rssi"], -127, 0);
    add_metric(metrics, "exhaust_fan_rpm", telemetry["exhaust_fan_rpm"], 0, 100000);
    add_metric(metrics, "circulation_fan_rpm", telemetry["circulation_fan_rpm"], 0, 100000);
    add_metric(metrics, "circulation_fan2_rpm", telemetry["circulation_fan2_rpm"], 0, 100000);
    add_metric(metrics, "circulation_fan3_rpm", telemetry["circulation_fan3_rpm"], 0, 100000);
    add_metric(metrics, "light_pct", telemetry["light_pct"], 0, 100);
    add_metric(metrics, "humidifier_speed_now", telemetry["humidifier_speed_now"], 0, 100);

    JsonObjectConst ble = telemetry["ble_sensors"].as<JsonObjectConst>();
    JsonObjectConst outside = ble["outside"].as<JsonObjectConst>();
    JsonObjectConst inside = ble["inside"].as<JsonObjectConst>();
    if (outside["online"].as<bool>()) {
        add_metric(metrics, "ble_temp_outside", outside["ble_temp_outside"], -50, 100);
        add_metric(metrics, "ble_hum_outside", outside["ble_humid_outside"], 0, 100);
    }
    if (inside["online"].as<bool>()) {
        add_metric(metrics, "ble_temp_inside", inside["ble_temp_inside"], -50, 100);
        add_metric(metrics, "ble_hum_inside", inside["ble_hum_inside"], 0, 100);
    }

    if (metrics.size() == 0 || upload.overflowed()) return false;
    payload = "";
    serializeJson(upload, payload);
    return payload.length() > 0 && payload.length() <= 16 * 1024;
}

void upload_task(void*) {
    for (;;) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);

        UploadJob job;
        if (xSemaphoreTake(job_mutex, pdMS_TO_TICKS(100)) != pdTRUE) continue;
        job = pending_job;
        pending_job = UploadJob();
        xSemaphoreGive(job_mutex);
        if (job.payload.isEmpty()) continue;

        NetworkClientSecure tls_client;
        extern const uint8_t x509_crt_bundle[] asm("_binary_x509_crt_bundle_start");
        extern const uint8_t x509_crt_bundle_end[] asm("_binary_x509_crt_bundle_end");
        tls_client.setCACertBundle(x509_crt_bundle, x509_crt_bundle_end - x509_crt_bundle);
        tls_client.setTimeout(job.timeout_seconds * 1000UL);
        tls_client.setHandshakeTimeout(job.timeout_seconds);

        HTTPClient https;
        https.setConnectTimeout(job.timeout_seconds * 1000UL);
        https.setTimeout(job.timeout_seconds * 1000UL);
        const String url = job.endpoint + "/snapshot";
        if (!https.begin(tls_client, url)) {
            last_http_status = -1;
            continue;
        }
        https.addHeader("Authorization", String("Bearer ") + job.token);
        https.addHeader("Content-Type", "application/json");
        https.addHeader("Accept", "application/json");
        last_http_status = https.POST(job.payload);
        https.end();
        tls_client.stop();
        Serial.printf("[CLOUD] Upload abgeschlossen, HTTP-Status=%d\n", last_http_status);
    }
}

void print_status() {
    Serial.printf(
        "[CLOUD] enabled=%s configured=%s device_id=%s interval=%u last_http=%d\n",
        active_config.enabled ? "true" : "false",
        (valid_endpoint(active_config.endpoint) && active_config.token.length() >= 32) ? "true" : "false",
        active_config.device_id.c_str(),
        active_config.interval_minutes,
        last_http_status
    );
}

void process_serial_line(const String& line) {
    if (line == "CLOUD_STATUS") {
        print_status();
        return;
    }
    if (line == "CLOUD_DISABLE") {
        CloudConfig candidate = active_config;
        candidate.enabled = false;
        Serial.println(save_config(candidate, false) ? "[CLOUD] Deaktiviert." : "[CLOUD] NVS-Fehler.");
        return;
    }
    constexpr const char* prefix = "CLOUD_PROVISION ";
    if (!line.startsWith(prefix)) return;

    StaticJsonDocument<768> document;
    const DeserializationError error = deserializeJson(document, line.substring(strlen(prefix)));
    if (error || !document.is<JsonObject>()) {
        Serial.println("[CLOUD] Ungültige Provisionierungsdaten.");
        return;
    }

    JsonObject source = document.as<JsonObject>();
    StaticJsonDocument<768> normalized;
    normalized["cloud_enabled"] = source["enabled"] | false;
    normalized["cloud_endpoint"] = source["endpoint"] | "";
    normalized["cloud_device_id"] = source["device_id"] | "";
    normalized["cloud_upload_token"] = source["token"] | "";
    normalized["cloud_upload_interval_minutes"] = source["interval_minutes"] | DEFAULT_INTERVAL_MINUTES;
    normalized["cloud_timeout_seconds"] = source["timeout_seconds"] | DEFAULT_TIMEOUT_SECONDS;
    if (apply_config(normalized.as<JsonObject>(), true)) {
        last_queue_ms = 0;
        Serial.println("[CLOUD] Provisionierung sicher in NVS gespeichert.");
    } else {
        Serial.println("[CLOUD] Provisionierung abgewiesen.");
    }
}

void poll_serial() {
    while (Serial.available() > 0) {
        const char character = static_cast<char>(Serial.read());
        if (character == '\n' || character == '\r') {
            if (!serial_line.isEmpty()) process_serial_line(serial_line);
            serial_line = "";
            continue;
        }
        if (serial_line.length() >= MAX_SERIAL_COMMAND) {
            serial_line = "";
            continue;
        }
        serial_line += character;
    }
}
}

void cloud_logging_init() {
    Preferences preferences;
    if (preferences.begin(PREF_NAMESPACE, true)) {
        active_config.enabled = preferences.getBool(PREF_ENABLED, false);
        active_config.endpoint = preferences.getString(PREF_ENDPOINT, "");
        active_config.device_id = preferences.getString(PREF_DEVICE_ID, "");
        active_config.token = preferences.getString(PREF_TOKEN, "");
        active_config.interval_minutes = preferences.getUShort(PREF_INTERVAL, DEFAULT_INTERVAL_MINUTES);
        active_config.timeout_seconds = preferences.getUShort(PREF_TIMEOUT, DEFAULT_TIMEOUT_SECONDS);
        preferences.end();
    }
    if (!valid_device_id(active_config.device_id)) {
        active_config.device_id = default_device_id();
        save_config(active_config, false);
    }

    job_mutex = xSemaphoreCreateMutex();
    if (job_mutex == nullptr) {
        active_config.enabled = false;
        Serial.println("[CLOUD] Kein Mutex verfügbar; Upload deaktiviert.");
        return;
    }
    if (xTaskCreate(upload_task, "cloud_upload", 10240, nullptr, 1, &upload_task_handle) != pdPASS) {
        upload_task_handle = nullptr;
        active_config.enabled = false;
        Serial.println("[CLOUD] Upload-Task konnte nicht gestartet werden.");
    }
    print_status();
}

void cloud_logging_update() {
    poll_serial();
    if (!active_config.enabled || upload_task_handle == nullptr) return;
    if (WiFi.status() != WL_CONNECTED || (WiFi.getMode() & WIFI_AP)) return;
    if (time(nullptr) < 1704067200) return;

    const uint32_t now = millis();
    const uint32_t interval_ms = static_cast<uint32_t>(active_config.interval_minutes) * 60UL * 1000UL;
    if (last_queue_ms != 0 && now - last_queue_ms < interval_ms) return;
    last_queue_ms = now;

    String payload;
    if (!build_payload(payload)) {
        Serial.println("[CLOUD] Snapshot konnte nicht erstellt werden.");
        return;
    }

    if (xSemaphoreTake(job_mutex, 0) != pdTRUE) return;
    if (!pending_job.payload.isEmpty()) {
        xSemaphoreGive(job_mutex);
        return;
    }
    pending_job.endpoint = active_config.endpoint;
    pending_job.token = active_config.token;
    pending_job.payload = payload;
    pending_job.timeout_seconds = active_config.timeout_seconds;
    xSemaphoreGive(job_mutex);
    xTaskNotifyGive(upload_task_handle);
}

void cloud_logging_process_config(JsonObject config) {
    if (config.containsKey("cloud_upload_token")) {
        Serial.println("[CLOUD] Token-Änderung über HTTP blockiert; USB/Serial verwenden.");
    }
    if (!apply_config(config, false)) {
        Serial.println("[CLOUD] Ungültige Cloud-Konfiguration abgewiesen.");
    }
}

void cloud_logging_factory_reset() {
    Preferences preferences;
    if (preferences.begin(PREF_NAMESPACE, false)) {
        preferences.clear();
        preferences.end();
    }
    active_config = CloudConfig();
}
