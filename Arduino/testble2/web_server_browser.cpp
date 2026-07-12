#include "web_server_browser.h"
#include <ArduinoJson.h>
#include <WiFi.h>

extern WebServer server;
extern String _web_username;
extern String _web_password;


// Großes, Smartphone-optimiertes UI mit Passwort-Auge (Zurück zur stabilen Version 1)
const char WIFI_CONFIG_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>GrowMaster WiFi Setup</title>
    <style>
        :root {
            --bg-main: #0f0f14;
            --bg-card: #181822;
            --bg-input: #242432;
            --accent-green: #2ecc71;
            --accent-orange: #e67e22;
            --accent-red: #e74c3c;
            --text-main: #f1f2f6;
            --text-muted: #a4b0be;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background-color: var(--bg-main); color: var(--text-main); padding: 20px; display: flex; flex-direction: column; align-items: center; }
        .container { width: 100%; max-width: 500px; }
        
        .status-card { background: var(--bg-card); border-radius: 16px; padding: 20px; margin-bottom: 20px; border: 1px solid #2d2d3d; display: flex; align-items: center; justify-content: space-between; }
        .status-info { display: flex; flex-direction: column; }
        .status-title { font-size: 1.1rem; font-weight: bold; }
        .status-subtitle { font-size: 0.85rem; color: var(--text-muted); margin-top: 4px; }
        .indicator { width: 24px; height: 24px; border-radius: 50%; background-color: var(--accent-orange); box-shadow: 0 0 12px var(--accent-orange); transition: all 0.3s ease; }
        .indicator.green { background-color: var(--accent-green); box-shadow: 0 0 12px var(--accent-green); }
        .indicator.orange { background-color: var(--accent-orange); box-shadow: 0 0 12px var(--accent-orange); }
        .indicator.red { background-color: var(--accent-red); box-shadow: 0 0 12px var(--accent-red); }
        
        .card { background: var(--bg-card); border-radius: 16px; padding: 24px; border: 1px solid #2d2d3d; box-shadow: 0 8px 24px rgba(0,0,0,0.3); }
        h2 { margin-bottom: 20px; font-size: 1.4rem; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 8px; color: var(--text-muted); font-size: 0.95rem; font-weight: 500; }
        
        .password-wrapper { position: relative; width: 100%; }
        
        input[type="text"], input[type="password"] {
            width: 100%; padding: 16px; background-color: var(--bg-input); border: 2px solid #3d3d52; border-radius: 12px;
            color: var(--text-main); font-size: 1.1rem; outline: none; transition: border-color 0.2s;
        }
        input[type="text"]:focus, input[type="password"]:focus { border-color: var(--accent-green); }
        
        .toggle-password {
            position: absolute; right: 14px; top: 50%; transform: translateY(-50%);
            cursor: pointer; color: var(--text-muted); font-size: 1.4rem; padding: 8px; user-select: none;
        }
        
        .btn {
            width: 100%; padding: 18px; background-color: var(--accent-green); border: none; border-radius: 12px;
            color: #000; font-size: 1.2rem; font-weight: bold; cursor: pointer; transition: transform 0.1s, opacity 0.2s;
            margin-top: 10px; display: flex; justify-content: center; align-items: center;
        }
        .btn:active { transform: scale(0.98); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        
        .log-box { background: #000; border-radius: 8px; padding: 12px; font-family: monospace; font-size: 0.8rem; color: #00ff00; height: 140px; overflow-y: auto; margin-top: 20px; border: 1px solid #222; }
    </style>
</head>
<body>

<div class="container">
    <div class="status-card">
        <div class="status-info">
            <span class="status-title" id="status-text">Initialisiere...</span>
            <span class="status-subtitle" id="net-info">Suche Verbindung zum GrowMaster</span>
        </div>
        <div class="indicator orange" id="sync-indicator"></div>
    </div>

    <div class="card">
        <h2>WLAN-Überführung</h2>
        <div class="form-group">
            <label for="ssid">WLAN Name (SSID)</label>
            <input type="text" id="ssid" placeholder="z.B. FritzBox_Heimnetz" autocomplete="off" autocapitalize="none">
        </div>
        <div class="form-group">
            <label for="password">WLAN Passwort</label>
            <div class="password-wrapper">
                <input type="password" id="password" placeholder="••••••••" autocomplete="off" autocapitalize="none">
                <span class="toggle-password" id="eye-icon" onclick="togglePasswordVisibility()">👁️</span>
            </div>
        </div>
        <button class="btn" id="submit-btn" onclick="sendWifiConfig()">In Router-Modus überführen</button>
    </div>

    <div class="log-box" id="log">Console gestartet...</div>
</div>

<script>
    let state = {
        lastSentRev: 0,
        lastSendTime: 0,
        retryCount: 0,
        maxRetries: 30, 
        currentServerRev: 0,
        isPending: false,
        lastUserActionTime: 0,
        currentIp: window.location.hostname || "192.168.4.1",
        fallbackIp: "192.168.4.1"
    };

    function log(msg) {
        const lb = document.getElementById('log');
        lb.innerHTML += "<br>> " + msg;
        lb.scrollTop = lb.scrollHeight;
    }

    function togglePasswordVisibility() {
        const passwordInput = document.getElementById("password");
        const eyeIcon = document.getElementById("eye-icon");
        if (passwordInput.type === "password") {
            passwordInput.type = "text";
            eyeIcon.innerText = "🔒";
        } else {
            passwordInput.type = "password";
            eyeIcon.innerText = "👁️";
        }
    }

    async function updateLoop() {
        try {
            const response = await fetch(`http://${state.currentIp}/data`, { 
                method: 'GET',
                headers: { 'Authorization': 'Basic ' + btoa('admin:1234') }
            });
            
            if (response.ok) {
                const data = await response.json();
                state.currentServerRev = data.rev_grow || 0;
                
                if (data.ip_address && data.ip_address !== "192.168.4.1" && state.currentIp === "192.168.4.1") {
                    log("Mögliche neue IP erkannt: " + data.ip_address);
                    state.currentIp = data.ip_address;
                }
                
                evaluateSyncState();
            } else {
                handleNetworkFailure();
            }
        } catch (e) {
            handleNetworkFailure();
        }
        setTimeout(updateLoop, 2000);
    }

    function handleNetworkFailure() {
        if (state.isPending) {
            state.retryCount++;
            log(`Warte auf ESP-Reboot & Router-Anmeldung... (Versuch ${state.retryCount}/${state.maxRetries})`);
            
            if (state.retryCount % 3 === 0) {
                state.currentIp = (state.currentIp === state.fallbackIp) ? "growmaster.local" : state.fallbackIp;
            }
            
            if (state.retryCount >= state.maxRetries) {
                setUIState("red", "Timeout!", "ESP reagiert nicht. Bitte Verbindung prüfen.");
                state.isPending = false;
            } else {
                setUIState("orange", "Umschalten...", "Suche ESP im Netzwerk...");
            }
        } else {
            setUIState("red", "Offline", "Keine Verbindung zum GrowMaster");
        }
    }

    function evaluateSyncState() {
        if (state.isPending && state.currentServerRev >= state.lastSentRev) {
            log(`🎯 SYNC ERFOLGREICH! Revision ${state.currentServerRev} bestätigt.`);
            state.isPending = false;
            state.retryCount = 0;
            setUIState("green", "Synchronisiert", "Erfolgreich mit Router verbunden!");
            document.getElementById("submit-btn").disabled = false;
            return;
        }

        if (state.isPending) {
            setUIState("orange", "Übertrage...", `Warte auf Quittung für Rev ${state.lastSentRev}`);
        } else {
            setUIState("green", "Bereit", `Verbunden. ESP Rev: ${state.currentServerRev}`);
        }
    }

    function setUIState(color, title, subtitle) {
        const ind = document.getElementById("sync-indicator");
        ind.className = "indicator " + color;
        document.getElementById("status-text").innerText = title;
        document.getElementById("net-info").innerText = subtitle;
    }

    async function sendWifiConfig() {
        const ssid = document.getElementById("ssid").value;
        const pw = document.getElementById("password").value;

        if(!ssid) { alert("Bitte SSID angeben!"); return; }

        document.getElementById("submit-btn").disabled = true;
        state.lastUserActionTime = Date.now();
        
        state.lastSentRev = state.currentServerRev + 1;
        state.isPending = true;
        state.retryCount = 0;

        log(`Sende neue Ziel-Revision: ${state.lastSentRev}`);

        const payload = {
            "rev_grow": state.lastSentRev,
            "wifi_ssid": ssid,
            "wifi_pw": pw,
            "wifi_mode": 1 
        };

        try {
            const response = await fetch(`http://${state.currentIp}/control`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Basic ' + btoa('admin:1234')
                },
                body: JSON.stringify(payload)
            });

            if(response.ok) {
                log("Daten übertragen. Warte auf Revision-Quittung...");
            } else {
                log("Fehler beim Senden des JSON-Payloads.");
                state.isPending = false;
                document.getElementById("submit-btn").disabled = false;
            }
        } catch(e) {
            log("Netzwerkfehler beim Absenden. Poller läuft weiter...");
        }
    }

    window.onload = () => {
        log("Client initialisiert auf IP: " + state.currentIp);
        updateLoop();
    };
</script>
</body>
</html>
)rawliteral";


namespace WebServerBrowser {
    void handleRoot() {
        // Liefert das oben definierte optimierte HTML aus
        server.send(200, "text/html", WIFI_CONFIG_HTML);
    }

    void registerRoutes(WebServer& serverRef) {
        serverRef.on("/", HTTP_GET, handleRoot);
    }
}