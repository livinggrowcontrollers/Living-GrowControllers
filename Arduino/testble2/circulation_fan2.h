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


#ifndef circulation_fan2_H
#define circulation_fan2_H

#include <Arduino.h>
#include <ArduinoJson.h> // WICHTIG: Damit JsonObject bekannt ist
enum circulation_fan2Mode {
    circulation_fan2_MODE_MANUAL,
    circulation_fan2_MODE_NATURAL,
    circulation_fan2_MODE_CHAOTIC
};
void circulation_fan2_get_status(JsonObject doc);
// Modul-Funktionen
void circulation_fan2_init(int pin, int tacho_pin);
void circulation_fan2_update();
void circulation_fan2_apply_climate_factor(float factor);
void circulation_fan2_reconfigure();

int circulation_fan2_get_rpm();

// DER NEUE POSTBOTE:
void circulation_fan2_process_json(JsonObject doc);

#endif
