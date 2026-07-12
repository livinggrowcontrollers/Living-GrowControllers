#ifndef POWER_MANAGER_H
#define POWER_MANAGER_H

#include <Arduino.h>


float get_battery_voltage_now();
void power_manager_init();
void power_manager_update();
void update_battery_ui();

#endif