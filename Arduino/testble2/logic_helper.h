#ifndef LOGIC_HELPER_H
#define LOGIC_HELPER_H

#include <Arduino.h>

// Variablen für andere Dateien (extern)
extern float minTemp;
extern float maxTemp;
extern float lastStableTemp;
extern float currentHumid;

extern float currentVPD;     // ext
extern float currentVPDLeaf; // LEAF
extern float currentVPDIn;   // INTERN

// DIE KORREKTE FUNKTIONS-SIGNATUR (Wichtig für den Fehler!)
void update_sensor_logic(float temp_ext, float temp_int, float humid_ext);
void reset_min_max();

#endif