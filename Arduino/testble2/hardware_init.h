// hardware_init.h - Alle Funktionen zur Initialisierung der Hardware (I2C, Sensoren, etc.)
#ifndef HARDWARE_INIT_H
#define HARDWARE_INIT_H

#include <Arduino.h>

#include <Wire.h>
void init_hardware();
void init_sensor_bus();
void scan_i2c_devices();
void recoverI2C(TwoWire &bus, int sda, int scl);

uint8_t get_pull_mode(int pull);
void hardware_reconfigure();

#endif