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
///////////////////////////////////////////////////////////////////////////////
// !!! ERWEITERUNG: ZEITKONSISTENZ-PRINZIP (RTC / NTP / REBOOT) !!!
// -------------------------------------------------------------------------
// 5. ZEIT IST EINE KONTINUIERLICHE ACHSE:
//    Zeit wird als fortlaufend betrachtet – unabhängig von Reboots,
//    Internetverbindung oder Synchronisationsereignissen.
//
// 6. KEINE VERGANGENHEIT, KEIN RESET:
//    Timer-Startpunkte (z. B. light_start_unix) werden NIEMALS relativ zum
//    Boot interpretiert, sondern immer absolut zur aktuellen Uhrzeit.
//
//    Ein Reboot darf NIEMALS dazu führen, dass:
//    - Timer neu bei 0 starten
//    - vergangene Zeit ignoriert wird
//    - ein künstlicher Startpunkt erzeugt wird
//
// 7. VERGANGENE TIMER SIND REAL:
//    Liegt der aktuelle Zeitpunkt innerhalb eines bereits gestarteten
//    Timerfensters (auch wenn der Start vor dem Boot lag),
//    MUSS das System sofort den korrekten Zustand berechnen:
//
//    → elapsed_in_window = now - start
//    → Zustand ergibt sich deterministisch aus aktueller Zeit
//
//    Es gibt KEIN „Nachholen“, KEIN „Neustart“, KEIN „Reset“.
//
// 8. ZEITQUELLE IST AUSTAUSCHBAR, LOGIK NICHT:
//    Die Quelle der Zeit (RTC wie DS3231 RTC Module,
//    NTP oder Systemzeit) ist austauschbar,
//    ABER die Timer-Logik basiert IMMER auf absoluter Zeit.
//
// 9. SYNCHRONISATION IST EIN SPRUNG, KEIN NEUSTART:
//    Wenn sich die Zeitquelle ändert (z. B. von RTC → NTP),
//    darf KEIN Timer neu initialisiert werden.
//
//    Stattdessen gilt:
//    → Der neue Zeitwert ersetzt sofort 'now'
//    → Alle Zustände werden daraus NEU BERECHNET
//
//    Es erfolgt KEINE Anpassung von:
//    - light_start_unix
//    - Timer-Dauer
//
// 10. SYSTEM IST JEDERZEIT REKONSTRUIERBAR:
//     Der komplette Zustand (AN/AUS, Rampenphase, Restzeit)
//     muss ausschließlich aus folgenden Werten bestimmbar sein:
//
//     - aktuelle Zeit (now)
//     - gespeicherte Targets (Startzeit, Dauer, Parameter)
//
//     → Keine versteckten Zustände
//     → Keine Abhängigkeit von Laufzeit-Historie
//
// JEDE KI-ÄNDERUNG MUSS DIESES ZEITMODELL EINHALTEN.
// EIN TIMER, DER VOM BOOT ABHÄNGT, IST EIN SYSTEMFEHLER.
///////////////////////////////////////////////////////////////////////////////
#include "light_control.h"
#include <time.h>
#include <Preferences.h>
#include "sys_config.h"



time_t light_start_unix = 0;
uint32_t light_duration_sec = 43200;  // Sekunden
int target_brightness = 0;
int effective_brightness = 0;
static bool light_climate_override = false;
static float climate_brightness_factor = 1.0f;
String light_state_reason = "manual";

// ===== 15-MINUTEN-RASTER (ab jetzt) =====
int l_target_h = 8;         // Stunden (0-23)
int l_target_m = 0;         // Minuten (0, 15, 30, 45 ONLY)
int l_target_dur = 720;     // MINUTEN (nicht Stunden!) --> 720 min = 12h
int l_target_sunrise = 60;  // MINUTEN (15er-Raster)
int l_target_sunset = 60;   // MINUTEN (15er-Raster)
LightMode current_light_mode = LIGHT_MODE_MANUAL;
static uint32_t light_rev = 0;              // ← NEU: Eigenes Revision für das Licht-Modul

static bool light_module_enabled = true;

// 🔥 TRACKER FÜR HARDWARE-PIN (Runtime GPIO Fix)
static int current_light_pin = -1; 

Preferences lightPrefs;

bool light_is_on() {
    return effective_brightness > 0;
}
void light_reconstruct_after_boot();

void light_reconfigure()
{
    // 1. SCHRITT: Alten Pin sauber detachen, falls er sich geändert hat oder deaktiviert wurde
    if (current_light_pin != -1 && current_light_pin != sysConfig.pin_light) {
        Serial.printf("Löse alten PWM Pin: %d\n", current_light_pin);
        ledcDetach(current_light_pin);
        pinMode(current_light_pin, INPUT); // Gibt die GPIO-Matrix komplett frei
        current_light_pin = -1;
    }

    // 2. SCHRITT: Prüfen, ob das Modul deaktiviert werden soll
    if (sysConfig.pin_light == -1) {
        Serial.println("Light Module deaktiviert (sysConfig).");
        light_module_enabled = false;
        effective_brightness = -256; 
        target_brightness = -256;    
        return;
    }
    light_module_enabled = true;

    // 3. SCHRITT: Neuen Pin anbinden (falls noch nicht geschehen)
    if (current_light_pin != sysConfig.pin_light) {
        ledcAttach(sysConfig.pin_light, 5000, 8);
        current_light_pin = sysConfig.pin_light; // Tracker aktualisieren
    }

    // Definierten Startzustand schreiben
    ledcWrite(sysConfig.pin_light, 0);

    light_update();

    Serial.printf("Light GPIO Runtime-Reconfigure -> GPIO %d\n", sysConfig.pin_light);
}

void light_save_state() {
    lightPrefs.putInt("l_h", l_target_h);
    lightPrefs.putInt("l_m", l_target_m);
    lightPrefs.putInt("l_dur", l_target_dur);        // Minuten
    lightPrefs.putInt("l_sunrise", l_target_sunrise); // Minuten (15-min Raster)
    lightPrefs.putInt("l_sunset", l_target_sunset);   // Minuten (15-min Raster)
    lightPrefs.putInt("mode", (int)current_light_mode);
    lightPrefs.putInt("target", target_brightness);
    lightPrefs.putBool("clim_ovr", light_climate_override);
    lightPrefs.putUInt("rev", light_rev);
}

// === REBOOT RECONSTRUCT ===
void light_reconstruct_after_boot() {
    // Mode wird schon in light_init() aus Preferences geladen → nichts machen
    
    if (current_light_mode == LIGHT_MODE_TIMER) {
        time_t now = time(nullptr);
        if (now > 946684800) {  // gültige Zeit
            struct tm ti;
            localtime_r(&now, &ti);
            ti.tm_hour = l_target_h;
            ti.tm_min = l_target_m;
            ti.tm_sec = 0;
            light_start_unix = mktime(&ti);
        }
    }
}

void light_init() {

    lightPrefs.begin("light", false);

    l_target_h = lightPrefs.getInt("l_h", 8);
    l_target_m = lightPrefs.getInt("l_m", 0);
    l_target_dur = lightPrefs.getInt("l_dur", 720);
    l_target_sunrise = lightPrefs.getInt("l_sunrise", 60);
    l_target_sunset = lightPrefs.getInt("l_sunset", 60);
    current_light_mode = (LightMode)lightPrefs.getInt("mode", (int)LIGHT_MODE_MANUAL);
    target_brightness = lightPrefs.getInt("target", 0);
    light_climate_override = lightPrefs.getBool("clim_ovr", false);
    
    // Revision aus Flash laden
    light_rev = lightPrefs.getUInt("rev", 0);

    light_duration_sec = (uint32_t)l_target_dur * 60;
    
    // Berechnet Startzeit deterministisch (ersetzt den gelöschten Block)
    light_reconstruct_after_boot();
    
    light_reconfigure();

    Serial.println("Light Module initialisiert (stabiler Modus)");
}
void light_update() {
    // ⚡ Sofortiger Abbruch bei inaktivem Modul (HINZUFÜGEN)
    if (!light_module_enabled || sysConfig.pin_light == -1 || current_light_pin == -1) {
        return;
    }

    time_t now = time(nullptr);
    bool hasTime = (now >= 1000000);

    struct tm ti_now;
    int now_sec = 0;

    if (hasTime) {
        localtime_r(&now, &ti_now);
        now_sec =
            ti_now.tm_hour * 3600 +
            ti_now.tm_min * 60 +
            ti_now.tm_sec;
    }

    bool timer_should_be_on = false;

    uint32_t elapsed = 0;
    uint32_t remaining = 0;

    // =====================================================
    // TIMER MODUS
    // =====================================================

    if (current_light_mode == LIGHT_MODE_TIMER) {

        int start_sec =
            l_target_h * 3600 +
            l_target_m * 60;

        int dur_sec =
            l_target_dur * 60;

        int end_sec =
            start_sec + dur_sec;

        // -------------------------------------------------
        // MITTERNACHTSLOGIK
        // -------------------------------------------------

        if (end_sec <= 86400) {

            if (now_sec >= start_sec &&
                now_sec < end_sec) {

                timer_should_be_on = true;

                elapsed =
                    now_sec - start_sec;

                remaining =
                    end_sec - now_sec;
            }
        }
        else {

            int overflow =
                end_sec - 86400;

            if (now_sec >= start_sec ||
                now_sec < overflow) {

                timer_should_be_on = true;

                elapsed =
                    (now_sec >= start_sec)
                    ? (now_sec - start_sec)
                    : (86400 - start_sec + now_sec);

                remaining =
                    (now_sec >= start_sec)
                    ? (86400 - now_sec + overflow)
                    : (overflow - now_sec);
            }
        }

        // -------------------------------------------------
        // =====================================================
        // TIMER AKTIV
        // =====================================================
        
        if (timer_should_be_on) {
        
            uint32_t sunrise_sec =
                l_target_sunrise * 60;
        
            uint32_t sunset_sec =
                l_target_sunset * 60;
        
            // STANDARD
            effective_brightness =
                target_brightness;
        
            // DEFAULT STATE
            light_state_reason = "DAY";
        
            // =====================================================
            // 🌅 SUNRISE RAMP
            // =====================================================
        
            if (elapsed < sunrise_sec) {
                light_state_reason = "SUNRISE";
                
                // Mathematisch korrekte Rundung statt Abschneiden
                effective_brightness = ((target_brightness * elapsed) + (sunrise_sec / 2)) / sunrise_sec;
                
                // Hartes Minimum: Wenn die Rampe läuft, wollen wir MINDESTENS 1% sehen
                if (effective_brightness == 0 && elapsed > 0) {
                    effective_brightness = 1;
                }
            }
        
            // =====================================================
            // 🌇 SUNSET RAMP
            // =====================================================
        
            else if (remaining < sunset_sec) {
                light_state_reason = "SUNSET";
                
                // Mathematisch korrekte Rundung
                effective_brightness = ((target_brightness * remaining) + (sunset_sec / 2)) / sunset_sec;
                
                // Hartes Minimum: Wenn wir noch im Fenster sind, nicht vorzeitig komplett ausschalten
                if (effective_brightness == 0 && remaining > 0) {
                    effective_brightness = 1;
                }
            }
        
        }

        // -------------------------------------------------
        // TIMER AUS
        // -------------------------------------------------

        else {

            light_state_reason = "NIGHT";
            effective_brightness = 0;
        }
    }

    // =====================================================
    // MANUAL MODUS
    // =====================================================

    else if (current_light_mode == LIGHT_MODE_MANUAL) {
        
        light_state_reason = "MANUAL";

        effective_brightness =
            target_brightness;
    }

    // =====================================================
    // FALLBACK
    // =====================================================

    else {

        effective_brightness =
            target_brightness;
    }

    if (
        current_light_mode == LIGHT_MODE_TIMER
        && light_climate_override
        && effective_brightness > 0
    ) {
        effective_brightness = constrain(
            static_cast<int>(effective_brightness * climate_brightness_factor + 0.5f),
            0,
            100
        );
    }

    // =====================================================
    // PWM OUTPUT
    // =====================================================

    if (!light_module_enabled || sysConfig.pin_light == -1 || current_light_pin == -1) {
        return;
    }

    ledcWrite(
        sysConfig.pin_light,
        map(
            effective_brightness,
            0,
            100,
            0,
            255
        )
    );
}


float light_get_phase_progress() {
    time_t now = time(nullptr);
    if (now < 946684800) return 0.0f;

    struct tm ti;
    localtime_r(&now, &ti);
    int now_sec = ti.tm_hour * 3600 + ti.tm_min * 60 + ti.tm_sec;

    int start_sec = l_target_h * 3600 + l_target_m * 60;
    int dur_sec = l_target_dur * 60;
    int end_sec = (start_sec + dur_sec); 

    // Prüfung: Sind wir aktuell innerhalb des Licht-Fensters?
    bool is_on = false;
    uint32_t elapsed = 0;
    if (end_sec <= 86400) {
        if (now_sec >= start_sec && now_sec < end_sec) {
            is_on = true;
            elapsed = now_sec - start_sec;
        }
    } else {
        if (now_sec >= start_sec || now_sec < (end_sec - 86400)) {
            is_on = true;
            elapsed = (now_sec >= start_sec) ? (now_sec - start_sec) : (86400 - start_sec + now_sec);
        }
    }

    if (!is_on) return -1.0f; // 🔥 WICHTIG: -1.0 signalisiert "ECHTE NACHT" ans UI

    uint32_t sunrise_sec = l_target_sunrise * 60;
    uint32_t sunset_sec = l_target_sunset * 60;

    // 🌅 SUNRISE
    if (elapsed < sunrise_sec) return (float)elapsed / sunrise_sec;
    
    // 🌇 SUNSET
    uint32_t remaining = dur_sec - elapsed;
    if (remaining < sunset_sec) return 1.0f - ((float)remaining / sunset_sec);

    // 🌞 DAY
    return 1.0f;
}


LightPhase light_get_current_phase() {

    time_t now = time(nullptr);

    if (now < 946684800) {
        return LIGHT_PHASE_DAY;
    }

    struct tm ti;
    localtime_r(&now, &ti);

    int now_sec =
        ti.tm_hour * 3600 +
        ti.tm_min * 60 +
        ti.tm_sec;

    int start_sec =
        l_target_h * 3600 +
        l_target_m * 60;

    int dur_sec =
        l_target_dur * 60;

    int end_sec =
        start_sec + dur_sec;

    uint32_t sunrise_sec =
        l_target_sunrise * 60;

    uint32_t sunset_sec =
        l_target_sunset * 60;

    bool is_on = false;
    uint32_t elapsed = 0;
    uint32_t remaining = 0;

    // =====================================================
    // MITTERNACHTSLOGIK
    // =====================================================

    if (end_sec <= 86400) {

        if (now_sec >= start_sec &&
            now_sec < end_sec) {

            is_on = true;

            elapsed =
                now_sec - start_sec;

            remaining =
                end_sec - now_sec;
        }
    }
    else {

        int overflow =
            end_sec - 86400;

        if (now_sec >= start_sec ||
            now_sec < overflow) {

            is_on = true;

            elapsed =
                (now_sec >= start_sec)
                ? (now_sec - start_sec)
                : (86400 - start_sec + now_sec);

            remaining =
                (now_sec >= start_sec)
                ? (86400 - now_sec + overflow)
                : (overflow - now_sec);
        }
    }

    // =====================================================
    // PHASEN
    // =====================================================

    if (!is_on) {
        return LIGHT_PHASE_NIGHT;
    }

    if (elapsed < sunrise_sec) {
        return LIGHT_PHASE_SUNRISE;
    }

    if (remaining < sunset_sec) {
        return LIGHT_PHASE_SUNSET;
    }

    return LIGHT_PHASE_DAY;
}

// DIESE BEIDEN HIER MÜSSEN UNBEDINGT UNTER DER UPDATE FUNKTION STEHEN:
int light_get_effective_brightness() {
    return effective_brightness;
}

int light_get_minutes_to_next_change() {
    time_t now = time(nullptr);
    if (now < 946684800) return -1; // Noch kein gültiger Zeit-Sync

    struct tm ti_now;
    localtime_r(&now, &ti_now);
    
    // Aktuelle Sekunden seit Mitternacht
    int now_sec = ti_now.tm_hour * 3600 + ti_now.tm_min * 60 + ti_now.tm_sec;
    
    // Timer-Daten
    int start_sec = l_target_h * 3600 + l_target_m * 60;
    int dur_sec = l_target_dur * 60;
    int end_sec = start_sec + dur_sec;

    // Modus Check
    if (current_light_mode != LIGHT_MODE_TIMER) return -1;

    // Fall A: Timer läuft innerhalb eines Tages (z.B. 08:00 - 20:00)
    if (end_sec <= 86400) {
        if (now_sec < start_sec) {
            // Licht noch aus -> Zeit bis AN
            return (start_sec - now_sec) / 60;
        } else if (now_sec < end_sec) {
            // Licht an -> Zeit bis AUS
            return (end_sec - now_sec) / 60;
        } else {
            // Licht bereits aus für heute -> Zeit bis morgen Start
            return (86400 - now_sec + start_sec) / 60;
        }
    } 
    // Fall B: Timer geht über Mitternacht (z.B. 20:00 - 04:00)
    else {
        int overflow_end_sec = end_sec - 86400;
        if (now_sec >= start_sec) {
            // Wir sind im ersten Teil der Nacht (vor Mitternacht) -> Zeit bis AUS
            return (end_sec - now_sec) / 60;
        } else if (now_sec < overflow_end_sec) {
            // Wir sind im zweiten Teil der Nacht (nach Mitternacht) -> Zeit bis AUS
            return (overflow_end_sec - now_sec) / 60;
        } else {
            // Wir sind im "Tag-Loch" (Licht aus) -> Zeit bis Start am Abend
            return (start_sec - now_sec) / 60;
        }
    }
}

void light_set_brightness(int p) {
    // Wir setzen nur den Zielwert. 
    // Der Modus (Timer oder Manuell) bleibt einfach so, wie er ist!
    target_brightness = constrain(p, 0, 100);
    
    // Preferences speichern, damit der Wert nach Reboot bleibt
    light_save_state();
    
    // Sofortiges Update der PWM-Ausgabe
    light_update();
}

void light_set_mode(LightMode m) {
    // Wir setzen den neuen Modus
    current_light_mode = m;
    

    
    light_save_state();
    light_update();
}

void light_apply_climate_factor(float factor) {
    climate_brightness_factor = constrain(factor, 0.0f, 1.0f);
}

bool light_climate_override_enabled() {
    return light_climate_override;
}
// 15-Minuten-Raster Validierung
int _round_to_15min(int minutes) {
    return ((minutes + 7) / 15) * 15;  // Rundet auf nächstes 15er-Vielfaches
}

// light_set_timer() - d = Minuten (nicht Stunden!)
void light_set_timer(int h, int m, int d) {
    l_target_h = constrain(h, 0, 23);
    l_target_m = _round_to_15min(m) % 60;
    l_target_dur = constrain(_round_to_15min(d), 15, 1440);
    light_duration_sec = (uint32_t)l_target_dur * 60;

    // Widget-Rettung: Wir bauen einen validen Timestamp für HEUTE
    time_t now = time(nullptr);
    struct tm ti;
    if (now > 1000000) {
        localtime_r(&now, &ti);
    } else {
        // Fallback falls Zeit noch auf 1970 steht
        ti.tm_year = 126; // 2026
        ti.tm_mon = 3;
        ti.tm_mday = 17;
    }
    ti.tm_hour = l_target_h;
    ti.tm_min = l_target_m;
    ti.tm_sec = 0;
    
    light_start_unix = mktime(&ti); 
    
    light_save_state();
    Serial.printf("RECOVERY: Timer auf %02d:%02d gesetzt.\n", l_target_h, l_target_m);
}


int light_get_start_h() {
    return l_target_h;
}

int light_get_start_m() {
    return l_target_m;
}

int light_get_duration_min() {
    return l_target_dur;
}

int light_get_sunrise_min() {
    return l_target_sunrise;
}

int light_get_sunset_min() {
    return l_target_sunset;
}
void light_control_process_json(JsonObject &doc) {
    if (doc.isNull()) {
        Serial.println("light_control: received NULL JsonObject in process_json");
        return;
    }
    if (!light_module_enabled) return; // ⚡ Updates blockieren (HINZUFÜGEN)
    bool flash_changed = false;



    // 2. REVISIONS-CHECK
    if (doc.containsKey("rev_light")) {
        uint32_t received_rev = doc["rev_light"];

        if (received_rev > light_rev) {
            light_rev = received_rev;

            // D: Modus-Wechsel
            if (doc.containsKey("light_mode")) {
                String lm = doc["light_mode"];

                if (lm == "time") {
                    light_set_mode(LIGHT_MODE_TIMER);
                }
                else {
                    light_set_mode(LIGHT_MODE_MANUAL);
                }

                flash_changed = true;
            }

            // B: Timer-Einstellungen
            if (doc.containsKey("l_start_h") || doc.containsKey("l_dur") || doc.containsKey("l_sunrise") || doc.containsKey("l_sunset")) {
                int h = doc.containsKey("l_start_h") ? (int)doc["l_start_h"] : l_target_h;
                int m = doc.containsKey("l_start_m") ? (int)doc["l_start_m"] : l_target_m;
                int d = doc.containsKey("l_dur") ? (int)doc["l_dur"] : l_target_dur;
                
                if (doc.containsKey("l_sunrise")) {
                    l_target_sunrise = _round_to_15min((int)doc["l_sunrise"]);
                }
                if (doc.containsKey("l_sunset")) {
                    l_target_sunset = _round_to_15min((int)doc["l_sunset"]);
                }
                light_set_timer(h, m, d);
                flash_changed = true;
            }

            // C: Helligkeit
            if (doc.containsKey("light_pct")) {
                light_set_brightness((int)doc["light_pct"]);
                flash_changed = true;
            }

            if (doc.containsKey("light_climate_override")) {
                light_climate_override =
                    (bool)doc["light_climate_override"];
            
                flash_changed = true;
            }


        } else {
            // Alte Revision -> Ignorieren (Verhindert Echo-Effekte)
            return;
        }
    }

    // 3. PERSISTIERUNG
    if (flash_changed) {
        light_save_state();
        light_update();
        //Serial.printf("Light Control Flash Update | Rev: %u\n", light_rev);
    }
}
void light_control_get_status(JsonObject &doc) {
    if (doc.isNull()) return;

    // ⚡ Zwangskapselung bei inaktiver Hardware (HINZUFÜGEN)
    if (!light_module_enabled || sysConfig.pin_light == -1 || current_light_pin == -1) {
        doc["light_pct"] = -256;
        doc["light_target"] = -256;
        doc["light_mode"] = "off";
        doc["l_start_h"] = -256;
        doc["l_start_m"] = -256;
        doc["l_dur"] = -256;          
        doc["l_sunrise"] = -256;  
        doc["l_sunset"] = -256;    
        doc["light_climate_override"] = false;
        doc["light_remaining"] = -256;
        doc["rev_light"] = light_rev;
        doc["light_state_reason"] = "disabled";
        return; 
    }
    doc["light_pct"] = light_get_effective_brightness();
    doc["light_target"] = target_brightness;

    // === WICHTIG: Immer den aktuellen gespeicherten Modus senden ===
    if (current_light_mode == LIGHT_MODE_TIMER) {
        doc["light_mode"] = "time";
    } else {
        doc["light_mode"] = "manual";
    }



    // Targets für UI (15-min Raster)
    doc["l_start_h"] = l_target_h;
    doc["l_start_m"] = l_target_m;
    doc["l_dur"] = l_target_dur;          // MINUTEN (nicht Stunden)
    doc["l_sunrise"] = l_target_sunrise;  // MINUTEN (15-min Raster)
    doc["l_sunset"] = l_target_sunset;    // MINUTEN (15-min Raster)
    
    if (current_light_mode == LIGHT_MODE_TIMER) {
        doc["light_mode"] = "time";
    } else {
        doc["light_mode"] = "manual";
    }
    doc["light_climate_override"] = light_climate_override;
    doc["light_remaining"] = light_get_minutes_to_next_change();
    doc["rev_light"] = light_rev;
    doc["light_state_reason"] = light_state_reason;
}
