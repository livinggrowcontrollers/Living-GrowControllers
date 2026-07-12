///////////////////////////////////////////////////////////////////////////////
// !!! ABSOLUTES GESETZ: DAS TARGET-REVISION-PRINZIP (C++ / ESP32) !!!
// -------------------------------------------------------------------------
// 1. HARDWARE FOLGT TARGET: Die Loop darf NIEMALS direkt auf UI-Inputs reagieren.
//    Sie vergleicht permanent: 'target_val' vs 'effective_val'.
//
// 2. REVISION-CONFIRMATION: Der ESP32 bestätigt eine Änderung NUR, indem er 
//    die empfangene 'rev' (Revision) im Status-Paket unverändert zurücksendet.
//
// 3. KEINE LÜGEN: Der Status 'Synced' (Grün in der App) darf NUR dann entstehen,
//    wenn 'esp32_rev' == 'ui_target_rev'.
//
// 4. ATOMARE UPDATES: Bei Empfang eines neuen Targets wird die 'rev' sofort 
//    gespeichert, aber der 'effective_val' zieht (ggf. über Rampen) stur nach.
//
// JEDE KI-ÄNDERUNG MUSS DIESE ASYNCHRONE LOGIK WAHREN. DIREKTES ÜBERSCHREIBEN
// VON PINS OHNE TARGET-ABGLEICH IST EIN SYSTEMFEHLER!
///////////////////////////////////////////////////////////////////////////////

#ifndef LIGHT_CONTROL_H
#define LIGHT_CONTROL_H

#include <Arduino.h>
#include <ArduinoJson.h> // WICHTIG: Für den Postboten-Modus

extern bool light_climate_override;
extern float light_current_temp;
extern float light_current_humidity;

void light_control_set_temperature(float temperature);

enum LightPhase {
    LIGHT_PHASE_NIGHT = 0,
    LIGHT_PHASE_SUNRISE,
    LIGHT_PHASE_DAY,
    LIGHT_PHASE_SUNSET
};
enum PlantPhase {
    DAY_TRANSPIRE,
    SUNSET_TRANSITION,
    NIGHT_RECOVERY,
    SUNRISE_WAKEUP
};
enum LightMode {
    LIGHT_MODE_OFF_LOCKED = 0,
    LIGHT_MODE_MANUAL = 1,
    LIGHT_MODE_TIMER = 2
};
void light_control_get_status(JsonObject &doc);
// Modul-Funktionen
void light_init(); 
void light_reconfigure();
void light_update();
void light_set_brightness(int percent);
void light_set_mode(LightMode mode);
void light_set_timer(int h, int m, int dur);
void light_control_set_humidity(float humidity);
void light_reconfigure();

int light_get_start_h();
int light_get_start_m();
int light_get_duration_min();
int light_get_sunrise_min();
int light_get_sunset_min();
// GETTER
int light_get_minutes_to_next_change(); 
int light_get_effective_brightness();

// DER NEUE POSTBOTE
void light_control_process_json(JsonObject &doc);

// Externs (für handleData im Webserver)
extern int target_brightness; 
extern LightMode current_light_mode;
extern uint32_t sunrise_offset_sec;
extern int light_target_humidity_min;
extern int light_target_humidity_max;
int light_get_effective_brightness();
bool light_is_on();
float light_get_phase_progress(); // 0.0 → 1.0 innerhalb aktueller Phase
LightPhase light_get_current_phase();
PlantPhase getPlantPhase();
#endif