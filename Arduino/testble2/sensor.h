// sensor.h - Alle Funktionen rund um die Sensoren (SHT31)
#ifndef SENSOR_H
#define SENSOR_H

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_SHT31.h>

// I2C Busse
extern TwoWire I2C_Sensor;
extern TwoWire I2C_RTC;

// SHT31 Instanzen
extern Adafruit_SHT31 sht31_ext;   // Bus 0 (extern)
extern Adafruit_SHT31 sht31_int;   // Bus 1 (intern)

// Status
extern bool externalSensorFound;
extern bool internalSensorFound;

// INIT
bool initExternalSensor();
bool initInternalSensor();

// READ
float getTempExt();
float getExternalHumidity();

float getTempIn();
float getInternalHumidity();

// Helper: validate sensor value sentinel/NaN
bool is_sensor_value_valid(float val);

#endif