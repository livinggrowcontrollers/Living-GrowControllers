import json
import socket
import threading
from datetime import datetime
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

# ==============================================================================
# GLOBAL CONFIG & UTILS
# ==============================================================================
ESP_IP = "192.168.4.1"
HUB_PROXY_PORT = 80


def get_local_ip():
    """Ermittelt die lokale IP-Adresse des Rechners im Netzwerk."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"


# ==============================================================================
# KOMMUNIKATIONSLOGIK (Direct ESP Fetch)
# ==============================================================================
def fetch_esp_data(ip_address, username=None, password=None, timeout=2.0):
    ip_clean = ip_address.strip().replace("http://", "").replace("https://", "")
    if not ip_clean:
        return False, "Keine IP-Adresse eingegeben."

    base_url = f"http://{ip_clean}"
    endpoint = f"{base_url}/data"

    try:
        response = requests.get(
            endpoint,
            timeout=timeout,
            auth=(username, password) if username else None,
            headers={"Connection": "close", "Accept": "application/json"},
        )

        if response.status_code == 200:
            try:
                payload = response.json()
                return True, payload
            except json.JSONDecodeError:
                return (
                    False,
                    f"HTTP 200, aber ungültiges JSON empfangen:\n{response.text}",
                )
        else:
            return (
                False,
                f"HTTP-Fehler {response.status_code}: {response.reason}",
            )

    except requests.exceptions.Timeout:
        return False, f"Timeout beim Verbindungsaufbau zu {ip_clean} ({timeout}s)"
    except requests.exceptions.ConnectionError:
        return (
            False,
            f"Verbindung zu {ip_clean} fehlgeschlagen (Gerät nicht erreichbar).",
        )
    except Exception as e:
        return False, f"Unerwarteter Fehler: {str(e)}"


# ==============================================================================
# HTTP PROXY SERVER (Flask)
# ==============================================================================
proxy_app = Flask(__name__)
CORS(proxy_app)

log_callback = None


def forward_request_to_esp(path):
    target_url = f"http://{ESP_IP}/{path}"
    method = request.method
    timestamp = datetime.now().strftime("%H:%M:%S")

    try:
        resp = requests.request(
            method=method,
            url=target_url,
            headers={
                k: v for k, v in request.headers if k.lower() != "host"
            },
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            timeout=5.0,
        )

        log_msg = f"[{timestamp}] {method} /{path} -> ESP ({resp.status_code})"
        if log_callback:
            log_callback(log_msg)

        return (resp.content, resp.status_code, resp.headers.items())

    except requests.exceptions.Timeout:
        if log_callback:
            log_callback(f"[{timestamp}] {method} /{path} -> TIMEOUT ({ESP_IP})")
        return jsonify({"error": "Proxy Timeout", "target": ESP_IP}), 504
    except requests.exceptions.ConnectionError:
        if log_callback:
            log_callback(
                f"[{timestamp}] {method} /{path} -> NOT REACHABLE ({ESP_IP})"
            )
        return jsonify({"error": "Proxy Connection Error", "target": ESP_IP}), 502
    except Exception as e:
        if log_callback:
            log_callback(f"[{timestamp}] {method} /{path} -> ERROR: {str(e)}")
        return jsonify({"error": "Proxy Internal Error", "message": str(e)}), 500


# ==============================================================================
# HTTP PROXY SERVER (Flask mit Preflight FIX)
# ==============================================================================


@proxy_app.route(
    "/",
    defaults={"path": ""},
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)
@proxy_app.route(
    "/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
)
def proxy_handler(path):
    # PREFLIGHT FIX FOR BROWSERS:
    # Wenn der Browser (Webclient) fragt, ob er senden darf, antworten wir sofort mit JA!
    if request.method == "OPTIONS":
        response = proxy_app.make_default_options_response()
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, DELETE, OPTIONS"
        )
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, Authorization, X-Requested-With"
        )
        return response, 200

    # Alle normalen Requests (GET, POST, etc.) wie gehabt an den ESP weiterleiten
    return forward_request_to_esp(path)

def start_proxy_server():
    import logging

    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)
    proxy_app.run(host="0.0.0.0", port=HUB_PROXY_PORT, debug=False, use_reloader=False)


# ==============================================================================
# KIVY GUI SETUP (Scrollable Monolith)
# ==============================================================================
class VirtualHubWidget(BoxLayout):

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", spacing=8, padding=10, **kwargs)

        self.auto_refresh_event = None
        self.local_ip = get_local_ip()

        global log_callback
        log_callback = self.add_proxy_log

        # --- Haupt-Container in ScrollView einbetten ---
        main_scroll = ScrollView()
        content = BoxLayout(
            orientation="vertical",
            spacing=8,
            padding=5,
            size_hint_y=None,
        )
        content.bind(minimum_height=content.setter("height"))

        # --- 1. Header & Netzwerk-Informationen ---
        content.add_widget(
            Label(
                text="ESP Virtual Hub & Proxy",
                font_size="20sp",
                bold=True,
                size_hint_y=None,
                height=30,
            )
        )

        info_box = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=40,
        )
        self.hub_url_label = Label(
            text=f"📌 WEBCONTROLLER ZIEL-URL: http://{self.local_ip}:{HUB_PROXY_PORT}",
            font_size="15sp",
            bold=True,
            color=(0.2, 1, 0.4, 1),
        )
        info_box.add_widget(self.hub_url_label)
        content.add_widget(info_box)

        # --- 2. Eingabebereich für Ziel-ESP (IP, User, Pass) ---
        ip_layout = BoxLayout(
            orientation="horizontal", spacing=5, size_hint_y=None, height=35
        )
        ip_layout.add_widget(
            Label(text="Ziel ESP IP:", size_hint_x=None, width=90)
        )

        self.ip_input = TextInput(
            text=ESP_IP,
            multiline=False,
            font_size="14sp",
            write_tab=False,
        )
        self.ip_input.bind(text=self.on_esp_ip_change)
        ip_layout.add_widget(self.ip_input)
        content.add_widget(ip_layout)

        # Basic Auth Felder (Wieder da!)
        auth_layout = BoxLayout(
            orientation="horizontal", spacing=5, size_hint_y=None, height=35
        )
        auth_layout.add_widget(
            Label(text="User (opt):", size_hint_x=None, width=80)
        )
        self.user_input = TextInput(
            multiline=False, write_tab=False, font_size="14sp"
        )
        auth_layout.add_widget(self.user_input)

        auth_layout.add_widget(
            Label(text="Pass (opt):", size_hint_x=None, width=80)
        )
        self.pass_input = TextInput(
            multiline=False, password=True, write_tab=False, font_size="14sp"
        )
        auth_layout.add_widget(self.pass_input)
        content.add_widget(auth_layout)

        # --- 3. Steuerung / Buttons ---
        btn_layout = BoxLayout(
            orientation="horizontal", spacing=10, size_hint_y=None, height=40
        )

        self.btn_fetch = Button(
            text="Direkt-Test (GUI)",
            background_color=(0.2, 0.6, 1.0, 1.0),
            bold=True,
        )
        self.btn_fetch.bind(on_press=self.on_fetch_click)
        btn_layout.add_widget(self.btn_fetch)

        self.btn_auto = Button(
            text="Auto-Refresh: AUS", background_color=(0.5, 0.5, 0.5, 1.0)
        )
        self.btn_auto.bind(on_press=self.toggle_auto_refresh)
        btn_layout.add_widget(self.btn_auto)

        content.add_widget(btn_layout)

        # --- 4. Live Proxy-Log ---
        content.add_widget(
            Label(
                text="🔄 Live Proxy-Traffic (Webclient -> Hub -> ESP):",
                size_hint_y=None,
                height=25,
                halign="left",
                bold=True,
            )
        )

        self.proxy_log_output = TextInput(
            text="<Warte auf Requests vom Webclient...>\n",
            readonly=True,
            multiline=True,
            size_hint_y=None,
            height=120,
            font_size="12sp",
            background_color=(0.1, 0.1, 0.1, 1),
            foreground_color=(0.8, 0.8, 0.8, 1),
        )
        content.add_widget(self.proxy_log_output)

        # --- 5. Payload Output ---
        content.add_widget(
            Label(
                text="📄 Empfangene ESP-Daten (JSON):",
                size_hint_y=None,
                height=25,
                halign="left",
                bold=True,
            )
        )

        self.json_output = TextInput(
            text="<Keine Daten>",
            readonly=True,
            multiline=True,
            size_hint_y=None,
            height=200,
            font_size="12sp",
        )
        content.add_widget(self.json_output)

        main_scroll.add_widget(content)
        self.add_widget(main_scroll)

    def on_esp_ip_change(self, instance, value):
        global ESP_IP
        ESP_IP = value.strip()

    def add_proxy_log(self, log_line):
        Clock.schedule_once(lambda dt: self._append_log_text(log_line))

    def _append_log_text(self, log_line):
        self.proxy_log_output.text += log_line + "\n"

    def on_fetch_click(self, instance):
        self.btn_fetch.disabled = True
        ip = self.ip_input.text
        user = self.user_input.text.strip() or None
        password = self.pass_input.text.strip() or None

        threading.Thread(
            target=self._worker_thread,
            args=(ip, user, password),
            daemon=True,
        ).start()

    def _worker_thread(self, ip, user, password):
        success, response = fetch_esp_data(ip, user, password)
        Clock.schedule_once(
            lambda dt: self._update_ui_after_fetch(success, response)
        )

    def _update_ui_after_fetch(self, success, response):
        self.btn_fetch.disabled = False
        if success:
            pretty_json = json.dumps(response, indent=2, ensure_ascii=False)
            self.json_output.text = pretty_json
        else:
            self.json_output.text = f"FEHLER:\n{response}"

    def toggle_auto_refresh(self, instance):
        if self.auto_refresh_event:
            Clock.unschedule(self.auto_refresh_event)
            self.auto_refresh_event = None
            self.btn_auto.text = "Auto-Refresh: AUS"
            self.btn_auto.background_color = (0.5, 0.5, 0.5, 1.0)
        else:
            self.auto_refresh_event = Clock.schedule_interval(
                lambda dt: self.on_fetch_click(None), 2.0
            )
            self.btn_auto.text = "Auto-Refresh: AN (2s)"
            self.btn_auto.background_color = (0.2, 0.8, 0.2, 1.0)


class VirtualHubApp(App):

    def build(self):
        self.title = "ESP Virtual Hub & Proxy"
        proxy_thread = threading.Thread(target=start_proxy_server, daemon=True)
        proxy_thread.start()
        return VirtualHubWidget()


if __name__ == "__main__":
    VirtualHubApp().run()