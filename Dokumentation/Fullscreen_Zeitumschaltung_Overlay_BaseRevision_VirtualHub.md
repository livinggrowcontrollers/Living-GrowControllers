# Fullscreen-Zeitumschaltung, Base-Revision und Virtual Hub

## Zweck

Diese Dokumentation beschreibt die Semantik der Zeitumschaltung im
Fullscreen, den History-Befehlsweg im `OverlayCommandEngine`, das
`base_revision`-System und die Rolle des Virtual Hub.

Der wichtigste Grundsatz lautet:

> `/history` setzt nur den gewünschten Zustand. Die bestätigte Auswahl und
> die Messreihen kommen ausschließlich über die normale `/data`-Pipeline
> zurück.

## Zeitumschaltung im Fullscreen

Der Fullscreen bietet `LIVE`, `1H`, `2H`, `3H`, `6H`, `12H`, `24H`, `48H`,
`7D`, `30D`, `365D` und `ZEIT` an.

- `LIVE` setzt das aktive History-Fenster auf `None` und sendet
  `mode=live`.
- Eine feste Dauer erzeugt ein `HistoryWindow` von „jetzt minus Dauer“ bis
  „jetzt“ und sendet `mode=history`.
- `ZEIT` erzeugt ein absolutes benutzerdefiniertes Fenster mit festem
  Start- und Endzeitpunkt.
- Beim Umschalten werden alte Auswahl- und Render-Zwischenspeicher geleert,
  damit keine Daten des vorherigen Fensters angezeigt werden.
- Während der Bestätigung zeigt der Fullscreen einen Wartezustand. Das
  HTTP-ACK allein schaltet die Darstellung noch nicht verbindlich um.

Die eigentliche Bestätigung erfolgt erst, wenn der normale `/data`-Poll
dieselbe `selection_id` mit der erwarteten `rev_history` liefert. Erst dann
übernimmt die `GraphHistoryEngine` das Ziel, der Fullscreen rendert die Daten
und zeigt die Bestätigung an.

## Vollständiger Befehls- und Datenweg

```text
Benutzer wählt Zeitraum
        |
        v
FullscreenView
        |
        v
GlobalStateManager
        |
        v
OverlayCommandEngine
        |
        v
WEB_CLIENT -> aktuelle lokale/Cloudflare-Route -> Virtual Hub /history
        |                                      |
        |<----------- Steuer-ACK --------------|
        |
        |  nächster normaler /data-Poll
        v
DataFlowEngine -> GraphHistoryEngine -> Fullscreen/Dashboard
```

`WEB_CLIENT` bestimmt die aktuelle Route für jeden Befehl neu. Dadurch wird
keine veraltete lokale oder Cloudflare-Adresse im Fullscreen gespeichert.

## Aufgabe des OverlayCommandEngine

Der `OverlayCommandEngine` ist der zentrale Besitzer eines History-Befehls.
Er:

1. liest `history_session` und `rev_history` aus dem zuletzt bestätigten
   Zustand der `GraphHistoryEngine`,
2. erzeugt eine neue eindeutige `selection_id`,
3. ermittelt die stabile physische `device_id`,
4. registriert das gewünschte Ziel lokal in der `GraphHistoryEngine`,
5. sendet den Befehl über `WEB_CLIENT`,
6. prüft das ACK auf Gerät, Modus, Session, Auswahlkennung und Zielrevision.

Ein gültiges ACK muss genau zur laufenden Auswahl gehören und
`rev_history = base_revision + 1` enthalten. Fremde, alte oder verspätete
Antworten dürfen die aktuelle Fullscreen-Auswahl nicht bestätigen.

## Semantik des Base-Revision-Systems

| Feld | Bedeutung |
|---|---|
| `history_session` | Eindeutige Lebenszeit des aktuell laufenden Virtual Hub. Ein Hub-Neustart erzeugt eine neue Session. |
| `rev_history` | Vom Hub vergebene Revision des gewählten Steuerzustands. |
| `base_session` | Session, auf deren bestätigtem Zustand der neue Befehl aufbaut. |
| `base_revision` | Zuletzt über `/data` bestätigte Revision, auf der der neue Befehl aufbaut. |
| `selection_id` | Eindeutige Kennung einer Benutzeraktion; dient zur Zuordnung und Idempotenz. |
| `history_generated_at` | Erzeugungszeit des Log-Inhalts; ist keine neue Steuerrevision. |

Der Virtual Hub akzeptiert einen Befehl nur, wenn `base_session` und
`base_revision` exakt seinem aktuellen Zustand entsprechen. Das entspricht
einem atomaren „Vergleichen und Setzen“:

```text
gesendet:    base_revision = 17
Hub aktuell: rev_history   = 17
Ergebnis:    akzeptiert, neue rev_history = 18
```

Ist der Hub bereits bei Revision 18, wird ein weiterer Befehl mit Basis 17
mit HTTP `409 Conflict` abgewiesen. Die Pipeline wird dabei nicht verändert.
Das Dashboard muss zuerst den neueren Zustand über `/data` übernehmen.

Eine wiederholte Anfrage mit derselben `selection_id` liefert dasselbe
Ergebnis zurück und erhöht die Revision nicht erneut. Dadurch bleiben
Wiederholungen über wechselnde oder kurz aussetzende Netzwerkwege sicher.

## Aufgabe des Virtual Hub

Der Virtual Hub ist die Source of Truth für den History-Zustand. Er besitzt
den lokalen `/history`-Endpunkt und hängt die History-Pipeline an erfolgreiche
ESP-Antworten von `/data` an.

Bei einer gültigen Auswahl führt er atomar aus:

- Basis-Session und Basisrevision prüfen,
- Logdaten aus `data/log.csv` für die stabile `device_id` komprimieren,
- `rev_history` genau einmal erhöhen,
- den Geräteblock samt `history_selection` veröffentlichen,
- andere Geräteblöcke unverändert erhalten,
- über `/history` nur Steuer-Metadaten als ACK zurückgeben.

Im `LIVE`-Modus bleibt die UI semantisch live. Der Hub liefert zusätzlich
einen passiven 6-Stunden-Verlauf über `/data`, damit passive Übersichten
weiterhin Verlaufsdaten besitzen.

Relative Fenster werden im Hub regelmäßig neu erzeugt. Dabei bleiben
`selection_id` und `rev_history` gleich; nur `history_generated_at` und der
Log-Inhalt werden erneuert. Benutzerdefinierte absolute Zeitfenster gleiten
nicht mit der Uhrzeit weiter.

## Unveränderliche Regeln

- Fullscreen und `GraphHistoryEngine` führen keine eigenen
  HTTP-History-Anfragen aus.
- `/history` ist ausschließlich der Steuer- und ACK-Kanal.
- `/data` ist der einzige Kanal für bestätigten Zustand und Messreihen.
- Nur die stabile physische `device_id` identifiziert ein Gerät.
- Eine Auswahl gilt erst nach passender `/data`-Spiegelung als bestätigt.
- Eine automatische Log-Aktualisierung darf `rev_history` nicht erhöhen.
- Eine alte Session oder Revision darf einen neueren Hub-Zustand niemals
  überschreiben.

## Zentrale Dateien

- `dashboard_gui/ui/fullscreen_content/fullscreen_view.py`
- `dashboard_gui/gsm_engines/overlay_command_engine.py`
- `dashboard_gui/gsm_engines/graph_history_engine.py`
- `dashboard_gui/gsm_engines/graph_engine.py`
- `dashboard_gui/gsm_engines/graph_models.py`
- `dashboard_gui/gsm_engines/data_flow_engine.py`
- `dashboard_gui/global_state_manager.py`
- `web_client.py`
- `network/network_worker.py`
- `tools/virtual_hub/history_routes.py`
- `tools/virtual_hub/esp_virtual_hub.py`
