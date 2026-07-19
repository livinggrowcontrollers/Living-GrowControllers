// plant_planner.cpp

#include "plant_planner.h"
#include <LittleFS.h>

// Interne Modul-Variablen
static uint32_t plant_planner_rev = 0;
static Plant system_plants[PLANT_PLANNER_MAX_SLOTS];  // Festes Array mit 10 Slots

// Dateipfad für die Persistierung im Flash
static const char* STORAGE_PATH = "/plant_planner.json";

void plant_planner_init() {
    // true bedeutet: Wenn die Partition gefunden wird, aber unformatiert ist, formatiere sie einmalig sauber.
    // Der zweite Parameter ist der Mount-Pfad, der dritte die maximale Anzahl offener Dateien.
    // Der vierte Parameter ist der Partitions-Label-Name (Standard ist "spiffs").
    if (!LittleFS.begin(true, "/littlefs", 10, "spiffs")) {
        Serial.println("[Plant Planner] CRITICAL: LittleFS Mount fehlgeschlagen! Partition 'spiffs' fehlt oder defekt.");
        return;
    }
    
    plant_planner_load_state();
    Serial.println("[Plant Planner] Modul erfolgreich aus funktionierendem LittleFS geladen.");
}

void plant_planner_process_json(JsonObject doc) {
    bool flash_changed = false;

    // 1. Daten-Revision (Flash relevant)
    if (doc.containsKey("rev_plant_planner")) {
        uint32_t received_rev = doc["rev_plant_planner"];
        
        if (received_rev > plant_planner_rev) {
            plant_planner_rev = received_rev;

            // Prüfen, ob das "plant_planner" Wrapper-Objekt existiert
            if (doc.containsKey("plant_planner")) {
                JsonObject ppObj = doc["plant_planner"];

                // ============================================================
                // PLANT UPDATES (Nur einzelne Felder über Slot aktualisieren)
                // ============================================================
                if (ppObj.containsKey("plant_updates")) {
                    JsonArray updateArr = ppObj["plant_updates"];
                    for (JsonObject updateObj : updateArr) {
                        // WICHTIG: Slot-basierte Identifikation (nicht mehr Name!)
                        uint8_t slot = updateObj["slot"] | 255;
                        
                        if (slot >= PLANT_PLANNER_MAX_SLOTS) {
                            continue;  // Ungültiger Slot
                        }

                        Plant& p = system_plants[slot];

                        // Update einzelne Felder, falls vorhanden
                        if (updateObj.containsKey("last_watered")) {
                            p.last_watered = updateObj["last_watered"] | p.last_watered;
                        }
                        if (updateObj.containsKey("last_fertilized")) {
                            p.last_fertilized = updateObj["last_fertilized"] | p.last_fertilized;
                        }
                    }
                    flash_changed = true;
                }
                
                // ============================================================
                // KOMPLETTER PLANTS-ARRAY (Bei Bulk-Update)
                // ============================================================
                if (ppObj.containsKey("plants")) {
                    JsonArray plantsArr = ppObj["plants"];
                    
                    // Alle Slots löschen/reset
                    for (int i = 0; i < PLANT_PLANNER_MAX_SLOTS; i++) {
                        system_plants[i].used = false;
                    }

                    // Neue Pflanzen aus dem Update laden (mit Slot-Information)
                    for (JsonObject pObj : plantsArr) {
                        uint8_t slot = pObj["slot"] | 255;
                        
                        if (slot >= PLANT_PLANNER_MAX_SLOTS) {
                            continue;  // Ungültiger Slot
                        }

                        Plant& p = system_plants[slot];
                        
                        p.used = pObj["used"] | false;
                        p.name = pObj["name"] | "";
                        p.strain = pObj["strain"] | "";
                        p.breeder = pObj["breeder"] | "";
                        p.phenotype = pObj["phenotype"] | "";
                        p.pot_size = pObj["pot_size"] | "";
                        p.medium = pObj["medium"] | "";
                        p.light = pObj["light"] | "";
                        p.location = pObj["location"] | "";
                        p.notes = pObj["notes"] | "";
                        p.tags = pObj["tags"] | "";
                        p.harvest_weight = pObj["harvest_weight"] | "";
                        p.dry_weight = pObj["dry_weight"] | "";
                        p.favorite = pObj["favorite"] | false;
                        p.picture = pObj["picture"] | 1;
                        p.last_watered = pObj["last_watered"] | 0;
                        p.last_fertilized = pObj["last_fertilized"] | 0;
                        p.estimated_veg_days = pObj["estimated_veg_days"] | 30;
                        p.estimated_flower_days = pObj["estimated_flower_days"] | 60;
                        p.harvest_date = pObj["harvest_date"] | "";
                        p.germination_start = pObj["germination_start"] | "";
                        p.seedling_start = pObj["seedling_start"] | "";
                        p.vegetative_start = pObj["vegetative_start"] | "";
                        p.flowering_start = pObj["flowering_start"] | "";
                        p.drying_start = pObj["drying_start"] | "";
                        p.curing_start = pObj["curing_start"] | "";
                    }
                    flash_changed = true;
                }
            }
        }
    }

    if (flash_changed) {
        plant_planner_save_state();
    }
}

void plant_planner_get_status(JsonObject doc) {
    // Erzeugt exakt die gewünschte verschachtelte Struktur im globalen Webdump
    JsonObject ppObj = doc["plant_planner"].to<JsonObject>();
    
    ppObj["rev_plant_planner"] = plant_planner_rev;
    
    JsonArray plantsArr = ppObj["plants"].to<JsonArray>();
    
    // Zehn Slots sind nur die Kapazitaetsgrenze. Uebertragen werden
    // ausschliesslich tatsaechlich belegte Pflanzen.
    for (uint8_t slot = 0; slot < PLANT_PLANNER_MAX_SLOTS; slot++) {
        const Plant& p = system_plants[slot];
        if (!p.used) {
            continue;
        }
        JsonObject pObj = plantsArr.add<JsonObject>();
        
        pObj["slot"] = slot;  // WICHTIG: Slot-Index für Identifikation
        pObj["used"] = p.used;
        
        pObj["name"] = p.name;
        pObj["strain"] = p.strain;
        pObj["breeder"] = p.breeder;
        pObj["phenotype"] = p.phenotype;
        pObj["pot_size"] = p.pot_size;
        pObj["medium"] = p.medium;
        pObj["light"] = p.light;
        pObj["location"] = p.location;
        pObj["notes"] = p.notes;
        pObj["tags"] = p.tags;
        pObj["harvest_weight"] = p.harvest_weight;
        pObj["dry_weight"] = p.dry_weight;
        pObj["favorite"] = p.favorite;
        pObj["picture"] = p.picture;
        pObj["last_watered"] = p.last_watered;
        pObj["last_fertilized"] = p.last_fertilized;
        pObj["estimated_veg_days"] = p.estimated_veg_days;
        pObj["estimated_flower_days"] = p.estimated_flower_days;
        pObj["harvest_date"] = p.harvest_date;
        pObj["germination_start"] = p.germination_start;
        pObj["seedling_start"] = p.seedling_start;
        pObj["vegetative_start"] = p.vegetative_start;
        pObj["flowering_start"] = p.flowering_start;
        pObj["drying_start"] = p.drying_start;
        pObj["curing_start"] = p.curing_start;

    }
}

void plant_planner_save_state() {
    File file = LittleFS.open(STORAGE_PATH, "w");
    if (!file) {
        Serial.println("[Plant Planner] Fehler beim Öffnen der Speicherdatei zum Schreiben!");
        return;
    }

    // Temporäres Dokument zur Serialisierung
    JsonDocument tempDoc;
    tempDoc["rev"] = plant_planner_rev;
    JsonArray arr = tempDoc["plants"].to<JsonArray>();

    // Auch im Flash nur existierende Pflanzen speichern. Der Slot bleibt als
    // stabile Identitaet erhalten, obwohl das JSON-Array kompakt ist.
    for (uint8_t slot = 0; slot < PLANT_PLANNER_MAX_SLOTS; slot++) {
        const Plant& p = system_plants[slot];
        if (!p.used) {
            continue;
        }
        JsonObject pObj = arr.add<JsonObject>();
        
        pObj["slot"] = slot;
        pObj["used"] = p.used;
        
        pObj["name"] = p.name;
        pObj["strain"] = p.strain;
        pObj["breeder"] = p.breeder;
        pObj["phenotype"] = p.phenotype;
        pObj["pot_size"] = p.pot_size;
        pObj["medium"] = p.medium;
        pObj["light"] = p.light;
        pObj["location"] = p.location;
        pObj["notes"] = p.notes;
        pObj["tags"] = p.tags;
        pObj["harvest_weight"] = p.harvest_weight;
        pObj["dry_weight"] = p.dry_weight;
        pObj["favorite"] = p.favorite;
        pObj["picture"] = p.picture;
        pObj["last_watered"] = p.last_watered;
        pObj["last_fertilized"] = p.last_fertilized;
        pObj["harvest_date"] = p.harvest_date;
        pObj["germination_start"] = p.germination_start;
        pObj["seedling_start"] = p.seedling_start;
        pObj["vegetative_start"] = p.vegetative_start;
        pObj["flowering_start"] = p.flowering_start;
        pObj["drying_start"] = p.drying_start;
        pObj["curing_start"] = p.curing_start;
        pObj["estimated_veg_days"] = p.estimated_veg_days;
        pObj["estimated_flower_days"] = p.estimated_flower_days;
    
    
    }

    if (serializeJson(tempDoc, file) == 0) {
        Serial.println("[Plant Planner] Fehler beim Schreiben der JSON-Daten!");
    }
    file.flush(); // <--- ZWINGEND ERFORDERLICH FÜR HARTE REBOOTS
    file.close();
}

void plant_planner_load_state() {
    if (!LittleFS.exists(STORAGE_PATH)) {
        Serial.println("[Plant Planner] Keine Profildatei gefunden. Starte leer.");
        // Initialisiere alle Slots als unbelegte Array
        for (int i = 0; i < PLANT_PLANNER_MAX_SLOTS; i++) {
            system_plants[i].used = false;
        }
        return;
    }

    File file = LittleFS.open(STORAGE_PATH, "r");
    if (!file) return;

    JsonDocument tempDoc;
    DeserializationError error = deserializeJson(tempDoc, file);
    file.close();

    if (error) {
        Serial.println("[Plant Planner] Deserialisierungsfehler beim Laden!");
        return;
    }

    plant_planner_rev = tempDoc["rev"] | 0;
    JsonArray arr = tempDoc["plants"];
    
    // Initialisiere alle Slots als unbelegte
    for (int i = 0; i < PLANT_PLANNER_MAX_SLOTS; i++) {
        system_plants[i].used = false;
    }

    // Lade Daten aus dem JSON Array
    for (JsonObject pObj : arr) {
        uint8_t slot = pObj["slot"] | 255;
        
        if (slot >= PLANT_PLANNER_MAX_SLOTS) {
            continue;  // Ungültiger Slot
        }

        Plant& p = system_plants[slot];
        
        p.used = pObj["used"] | false;
        p.name = pObj["name"] | "";
        p.strain = pObj["strain"] | "";
        p.breeder = pObj["breeder"] | "";
        p.phenotype = pObj["phenotype"] | "";
        p.pot_size = pObj["pot_size"] | "";
        p.medium = pObj["medium"] | "";
        p.light = pObj["light"] | "";
        p.location = pObj["location"] | "";
        p.notes = pObj["notes"] | "";
        p.tags = pObj["tags"] | "";
        p.harvest_weight = pObj["harvest_weight"] | "";
        p.dry_weight = pObj["dry_weight"] | "";
        p.favorite = pObj["favorite"] | false;
        p.picture = pObj["picture"] | 1;
        p.last_watered = pObj["last_watered"] | 0;
        p.last_fertilized = pObj["last_fertilized"] | 0;
        p.estimated_veg_days = pObj["estimated_veg_days"] | 30;
        p.estimated_flower_days = pObj["estimated_flower_days"] | 60;
        p.harvest_date = pObj["harvest_date"] | "";
        p.germination_start = pObj["germination_start"] | "";
        p.seedling_start = pObj["seedling_start"] | "";
        p.vegetative_start = pObj["vegetative_start"] | "";
        p.flowering_start = pObj["flowering_start"] | "";
        p.drying_start = pObj["drying_start"] | "";
        p.curing_start = pObj["curing_start"] | "";
    }
}

// FIX: Name auf get_plant_planner_rev() geändert
uint32_t get_plant_planner_rev() {
    return plant_planner_rev;
}

// ============================================================================
// HILFSFUNKTIONEN FÜR SLOT-BASIERTE OPERATIONEN
// ============================================================================

/**
 * Findet den ersten freien Slot
 * Rückgabe: Slot-Index (0-9), oder -1 falls alle Slots belegt
 */
int8_t plant_planner_find_free_slot() {
    for (uint8_t i = 0; i < PLANT_PLANNER_MAX_SLOTS; i++) {
        if (!system_plants[i].used) {
            return i;
        }
    }
    return -1;  // Alle Slots belegt
}

/**
 * Liefert Zeiger auf Pflanze an Slot, oder nullptr falls ungültig
 */
Plant* plant_planner_get_slot(uint8_t slot) {
    if (slot >= PLANT_PLANNER_MAX_SLOTS) {
        return nullptr;
    }
    return &system_plants[slot];
}
