//grow_controller.h - Hauptsteuerung für das Grow-Controller-Projekt
#ifndef GROW_CONTROLLER_H
#define GROW_CONTROLLER_H

#include <Arduino.h>
#include <ArduinoJson.h>
#include <Preferences.h>

// ANKÜNDIGUNG: Diese Variablen sind für ALLE Dateien sichtbar
extern Preferences growPrefs;
extern String _device_name;
#pragma once
#include <Arduino.h>

extern String _wifi_ssid;
extern String _wifi_password;
extern String _web_username;
extern String _web_password;

// Funktionen
void grow_controller_init();
void grow_controller_start_ble();
void grow_controller_process_json(JsonObject doc);
void grow_controller_get_status(JsonObject doc);
int grow_controller_get_wifi_mode();
// Safe accessors for BLE flags (read RAM state loaded at init)
bool grow_controller_ble_scan_enabled();
bool grow_controller_ble_bridge_enabled();

#endif
