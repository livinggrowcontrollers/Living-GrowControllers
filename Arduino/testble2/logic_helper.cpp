#include "logic_helper.h"
#include <math.h>

// Variablen-Initialisierung
float minTemp = 99.0;
float maxTemp = -99.0;
float lastStableTemp = 0.0;
float currentHumid = 0.0;

float currentVPD     = 0.0; 
float currentVPDLeaf = 0.0; 
float currentVPDIn   = 0.0;

// Interne Hilfsfunktion für die VPD Physik
float _calculate_vpd(float T, float RH) {
    if (RH <= 0) return 0.0f;
    // Sättigungsdampfdruck (es)
    float es = 0.61078f * expf((17.27f * T) / (T + 237.3f));
    // Tatsächlicher Dampfdruck (ea)
    float ea = es * (RH / 100.0f);
    float vpd = es - ea;
    return (vpd > 0) ? vpd : 0.0f;
}

// DIE HAUPTFUNKTION (Passend zum UI-Block)
void update_sensor_logic(float temp_ext, float temp_int, float humid_ext) {
    
    // 1. Min/Max Statistik (JETZT BASIEREND AUF INTERNEM NTC FÜR MAIN TILE)
    if (temp_int > -40.0f && temp_int < 120.0f) {
        if (temp_int < minTemp) minTemp = temp_int;
        if (temp_int > maxTemp) maxTemp = temp_int;
    }

    // 2. Feuchtigkeit global zwischenspeichern
    currentHumid = humid_ext;

    // 3. VPD BERECHNUNGEN (EXTERN - SHT31)
    if (humid_ext > 0.0f && temp_ext > -40.0f) {
        // ext (Außen am SHT31)
        currentVPD = _calculate_vpd(temp_ext, humid_ext);

        // LEAF (Außen - 2 Grad Offset)
        currentVPDLeaf = _calculate_vpd(temp_ext - 2.0f, humid_ext);
    } else {
        currentVPD = 0.0f;
        currentVPDLeaf = 0.0f;
    }

    // 4. VPD BERECHNUNG (INTERN - NTC + 40% FIX)
    // Dies versorgt dein ui_vpd_label im Main Tile
    currentVPDIn = _calculate_vpd(temp_int, 40.0f);

    lastStableTemp = temp_int;
}

void reset_min_max() {
    minTemp = 99.0;
    maxTemp = -99.0;
}