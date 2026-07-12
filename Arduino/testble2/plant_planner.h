// plant_planner.h


#ifndef PLANT_PLANNER_H
#define PLANT_PLANNER_H

#include <Arduino.h>
#include <ArduinoJson.h>

#define PLANT_PLANNER_MAX_SLOTS 10

// Struktur für ein einzelnes Pflanzen-Profil (mit eindeutigem Slot)
struct Plant {
    bool used = false;  // Slot-Status: true = belegt, false = frei

    String name;
    String strain;
    String breeder;
    String phenotype;
    String pot_size;
    String medium;
    String light;
    String location;
    String notes;
    String tags;
    String harvest_weight;
    String dry_weight;
    bool favorite;
    uint8_t picture = 1;
    uint32_t last_watered = 0;
    uint32_t last_fertilized = 0;
    // NEU
    uint16_t estimated_veg_days = 30;
    uint16_t estimated_flower_days = 60;
    // Phasen- und Datumsfelder
    String harvest_date;
    String germination_start;
    String seedling_start;
    String vegetative_start;
    String flowering_start;
    String drying_start;
    String curing_start;
};

// Modul-Schnittstellen
void plant_planner_init();
void plant_planner_process_json(JsonObject doc);
void plant_planner_get_status(JsonObject doc);
void plant_planner_save_state();
void plant_planner_load_state();

// Revisions-Getter
uint32_t get_plant_planner_rev();

// Hilfsfunktionen für Slot-basierte Operationen
int8_t plant_planner_find_free_slot();
Plant* plant_planner_get_slot(uint8_t slot);

#endif // PLANT_PLANNER_H