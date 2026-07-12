

#ifndef SYSTEM_RESET_H
#define SYSTEM_RESET_H

#include <Arduino.h>

// Idiotensicheres Reset-Modul
namespace SystemReset {
    // Initialisiert den Reset-Button-Pin
    void init(int pin);

    // Muss in der Haupt-loop() permanent aufgerufen werden
    void update();

    // Zentrale Funktion, die ALLES löscht und neu startet
    void perform_factory_reset();
}

#endif // SYSTEM_RESET_H