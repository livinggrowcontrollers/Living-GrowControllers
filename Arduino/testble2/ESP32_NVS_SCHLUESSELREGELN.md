# ESP32-NVS: Namenslängen und persistente Einstellungen

## Die entscheidende Regel

Bei `Preferences` dürfen **Namespace und Schlüssel höchstens 15 Byte** lang sein.
Das ESP-IDF reserviert ein weiteres Byte für das abschließende Nullzeichen.

- Nur kurze ASCII-Namen verwenden. Umlaute können mehrere Byte belegen.
- Die Arduino-Kompilierung erkennt zu lange Namen nicht.
- JSON-/WebDoc-Feldnamen sind davon nicht betroffen und dürfen aussagekräftig bleiben.

## Warum dieser Fehler schwer zu erkennen ist

Ein zu langer Schlüssel erzeugt genau das beobachtete Fehlerbild:

1. Der neue Wert funktioniert im RAM bis zum Neustart.
2. `putBool()`, `putInt()` usw. können beim Speichern `0` zurückgeben.
3. Beim nächsten Boot findet `getBool()` oder `getInt()` keinen Wert und liefert unauffällig den angegebenen Standardwert.

Darum müssen Schreibvorgänge immer geprüft werden. Beispiel:

```cpp
constexpr const char* BLE_BRIDGE_PREF_KEY = "ble_bridge"; // 10 Byte

if (growPrefs.putBool(BLE_BRIDGE_PREF_KEY, enabled) == 0) {
    Serial.println("NVS-Speichern fehlgeschlagen");
    return false;
}
```

## Konkreter BLE-Fall

| Name | Länge | Ergebnis |
|---|---:|---|
| `ble_bridge_enabled` | 18 | ungültig |
| `ble_scan_enabled` | 16 | ungültig |
| `ble_bridge` | 10 | gültig |
| `ble_scan` | 8 | gültig |

Die externen JSON-Felder bleiben trotzdem unverändert:

- Eingang: `ble_bridge`, `ble_scan`
- Status: `ble_bridge_enabled`, `ble_scan_enabled`

Nur die internen NVS-Namen müssen kurz sein.

## Prüfliste für neue ESP-Einstellungen

1. Namespace und Schlüssel in **Byte** zählen: maximal 15.
2. Schlüssel einmal als Konstante am zuständigen Implementierungsort definieren.
3. Lesen und Schreiben müssen exakt dieselbe Konstante verwenden.
4. `Preferences::begin()` sowie jeden `put...()`-Rückgabewert prüfen.
5. Neustarttest durchführen: Wert ändern, Soft Reset, Strom aus/ein, Wert kontrollieren.
6. Factory Reset testen: gelöschte Werte müssen auf den bewusst festgelegten Standard fallen.
7. Keine zweite NVS-Lese- oder Speicherlogik in `testble2.ino` oder einem anderen Modul anlegen.

Hinweis: Der vorhandene Namespace `circulation_fan` besitzt exakt 15 Zeichen und liegt damit bereits an der erlaubten Grenze.

## Humidifier

Die neue Persistenz hält die Grenze ebenfalls bewusst ein:

| Verwendung | Name | Länge |
|---|---|---:|
| Modul-Namespace | `humidifier` | 10 |
| Sollwert | `pct` | 3 |
| Modul-Revision | `rev` | 3 |
| GPIO im Namespace `grow` | `p_humidifier` | 12 |
