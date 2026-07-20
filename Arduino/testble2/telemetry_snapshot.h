#ifndef TELEMETRY_SNAPSHOT_H
#define TELEMETRY_SNAPSHOT_H

#include <Arduino.h>
#include <ArduinoJson.h>

void telemetry_snapshot_fill(JsonObject target, const String& hostname);

#endif
