// web_server.h
#ifndef WEB_SERVER_H
#define WEB_SERVER_H

#include <WiFi.h>
#include <WebServer.h>

// Wir machen den Server extern verfügbar, falls andere Module ihn brauchen
extern WebServer server;

namespace WebModule {
    void init(const char* ssid, const char* password);
    void init_ap(const char* ap_name);   // ← DAS HIER FEHLT
    void update();
    bool isConnected();
}

#endif