# tools/virtual_hub/esp_virtual_hub.py

import json
import socket
import threading
from datetime import datetime
from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from bounded_log import BoundedLogBuffer
from history_routes import (
    HistoryPipelineStore,
    create_history_blueprint,
)
from cloudflare_tunnel_manager import CloudflareTunnelManager
from email_sender import EmailSender
from mdns_scanner_popup import open_mdns_scanner_popup
# ==============================================================================
# GLOBAL CONFIG & UTILS
# ==============================================================================
ESP_IP = "192.168.2.20"
HUB_PROXY_PORT = 80
USER = "admin"
PASSWORD = "1234"
PROXY_LOG_MAX_LINES = 300
TUNNEL_LOG_MAX_LINES = 200
LOG_FLUSH_INTERVAL = 0.1


def get_local_ip():
    """Ermittelt die lokale IP-Adresse des Rechners im Netzwerk."""
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        if sock is not None:
            sock.close()


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

        try:
            if response.status_code == 200:
                try:
                    payload = response.json()
                    return True, payload
                except json.JSONDecodeError:
                    return (
                        False,
                        f"HTTP 200, aber ungültiges JSON empfangen:\n{response.text}",
                    )
            return (
                False,
                f"HTTP-Fehler {response.status_code}: {response.reason}",
            )
        finally:
            response.close()

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


def _history_log(message):
    if log_callback:
        log_callback(message)


history_pipeline_store = HistoryPipelineStore(
    csv_file=None,
    log_cb=_history_log,
)

proxy_app.register_blueprint(
    create_history_blueprint(
        pipeline_store=history_pipeline_store,
        log_cb=_history_log,
    )
)


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

        try:
            log_msg = (
                f"[{timestamp}] {method} /{path} -> ESP ({resp.status_code})"
            )
            if log_callback:
                log_callback(log_msg)

            # Die History bleibt ausschließlich Teil des /data-Webkanals.
            if path.strip("/") == "data" and resp.status_code == 200:
                try:
                    esp_payload = resp.json()
                    esp_payload["history"] = (
                        history_pipeline_store.get_pipeline_payload(
                            copy_payload=False,
                        )
                    )
                    return (
                        jsonify(esp_payload),
                        200,
                        {"Content-Type": "application/json"},
                    )
                except Exception as metadata_error:
                    if log_callback:
                        log_callback(
                            f"[{timestamp}] History-Pipeline konnte nicht "
                            f"eingespeist werden: {metadata_error}"
                        )
                    return (
                        resp.content,
                        resp.status_code,
                        list(resp.headers.items()),
                    )

            return (
                resp.content,
                resp.status_code,
                list(resp.headers.items()),
            )
        finally:
            resp.close()

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
        self.last_notified_tunnel_url = None
        self.device_id = "unknown"
        self._fetch_lock = threading.Lock()
        self._fetch_in_progress = False
        self._tunnel_action_lock = threading.Lock()
        self._shutting_down = False
        self._proxy_log_buffer = BoundedLogBuffer(
            PROXY_LOG_MAX_LINES,
            initial_lines=("<Warte auf Requests vom Webclient...>",),
        )
        self._tunnel_log_buffer = BoundedLogBuffer(
            TUNNEL_LOG_MAX_LINES,
            initial_lines=("<Tunnel Log...>",),
        )
        self._proxy_log_trigger = Clock.create_trigger(
            self._flush_proxy_log_ui,
            LOG_FLUSH_INTERVAL,
        )
        self._tunnel_log_trigger = Clock.create_trigger(
            self._flush_tunnel_log_ui,
            LOG_FLUSH_INTERVAL,
        )
        self._tunnel_start_event = None

        global log_callback
        log_callback = self.add_proxy_log

        # Initialize Email Sender Component
        self.email_sender = EmailSender(log_callback=self.on_tunnel_log)

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

        # ======================================================================
        # --- CLOUDFLARE QUICK TUNNEL BEREICH ---
        # ======================================================================
        content.add_widget(
            Label(
                text="☁️ Cloudflare Quick Tunnel",
                font_size="16sp",
                bold=True,
                size_hint_y=None,
                height=25,
                halign="left",
            )
        )

        tunnel_box = BoxLayout(
            orientation="vertical",
            spacing=6,
            padding=8,
            size_hint_y=None,
            height=250,
        )

        self.tunnel_status_label = Label(
            text="Cloudflare Tunnel: Gestoppt",
            font_size="14sp",
            bold=True,
            color=(0.8, 0.8, 0.8, 1),
            size_hint_y=None,
            height=20,
        )
        tunnel_box.add_widget(self.tunnel_status_label)

        url_layout = BoxLayout(
            orientation="horizontal", spacing=5, size_hint_y=None, height=35
        )
        url_layout.add_widget(
            Label(text="Öffentliche URL:", size_hint_x=None, width=110)
        )
        self.tunnel_url_input = TextInput(
            text="",
            readonly=True,
            multiline=False,
            font_size="13sp",
            background_color=(0.15, 0.15, 0.15, 1),
            foreground_color=(0.2, 1, 0.4, 1),
        )
        url_layout.add_widget(self.tunnel_url_input)

        self.btn_copy_url = Button(
            text="Adresse kopieren",
            size_hint_x=None,
            width=130,
            background_color=(0.2, 0.6, 1.0, 1.0),
            bold=True,
        )
        self.btn_copy_url.bind(on_press=self.copy_tunnel_url)
        url_layout.add_widget(self.btn_copy_url)
        tunnel_box.add_widget(url_layout)

        tunnel_btn_layout = BoxLayout(
            orientation="horizontal", spacing=10, size_hint_y=None, height=35
        )
        self.btn_restart_tunnel = Button(
            text="Tunnel neu starten",
            background_color=(0.9, 0.6, 0.2, 1.0),
        )
        self.btn_restart_tunnel.bind(on_press=self.on_restart_tunnel_click)
        tunnel_btn_layout.add_widget(self.btn_restart_tunnel)

        self.btn_stop_tunnel = Button(
            text="Tunnel stoppen",
            background_color=(0.8, 0.3, 0.3, 1.0),
        )
        self.btn_stop_tunnel.bind(on_press=self.on_stop_tunnel_click)
        tunnel_btn_layout.add_widget(self.btn_stop_tunnel)
        tunnel_box.add_widget(tunnel_btn_layout)

        self.tunnel_log_output = TextInput(
            text="\n".join(self._tunnel_log_buffer.snapshot()) + "\n",
            readonly=True,
            multiline=True,
            size_hint_y=None,
            height=100,
            font_size="11sp",
            background_color=(0.08, 0.08, 0.08, 1),
            foreground_color=(0.7, 0.7, 0.7, 1),
        )
        tunnel_box.add_widget(self.tunnel_log_output)

        content.add_widget(tunnel_box)

        # Tunnel Manager initialisieren
        self.tunnel_manager = CloudflareTunnelManager(
            local_url=f"http://127.0.0.1:{HUB_PROXY_PORT}",
            on_status=self.on_tunnel_status,
            on_url=self.on_tunnel_url,
            on_log=self.on_tunnel_log,
        )

        # --- 2. Eingabebereich für Ziel-ESP (IP, User, Pass) ---
        ip_layout = BoxLayout(
            orientation="horizontal",
            spacing=5,
            size_hint_y=None,
            height=35,
        )

        ip_layout.add_widget(
            Label(text="Ziel ESP IP:", size_hint_x=None, width=90)
        )

        # Textfeld + Suchbutton nebeneinander
        ip_box = BoxLayout(
            orientation="horizontal",
            spacing=5,
        )

        self.ip_input = TextInput(
            text=ESP_IP,
            multiline=False,
            font_size="14sp",
            write_tab=False,
        )

        self.ip_input.bind(text=self.on_esp_ip_change)

        ip_box.add_widget(self.ip_input)

        self.scan_btn = Button(
            text="🔍",
            size_hint_x=None,
            width=45,
        )

        self.scan_btn.bind(on_release=self.on_scan_devices)

        ip_box.add_widget(self.scan_btn)

        ip_layout.add_widget(ip_box)

        content.add_widget(ip_layout)

        # Basic Auth Felder
        auth_layout = BoxLayout(
            orientation="horizontal", spacing=5, size_hint_y=None, height=35
        )
        auth_layout.add_widget(
            Label(text="User (opt):", size_hint_x=None, width=80)
        )
        self.user_input = TextInput(
            text=USER,
            multiline=False,
            write_tab=False,
            font_size="14sp",
        )
        auth_layout.add_widget(self.user_input)

        auth_layout.add_widget(
            Label(text="Pass (opt):", size_hint_x=None, width=80)
        )
        self.pass_input = TextInput(
            text=PASSWORD,
            multiline=False,
            password=True,
            write_tab=False,
            font_size="14sp",
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
            text="\n".join(self._proxy_log_buffer.snapshot()) + "\n",
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

        # Tunnel direkt beim Start der UI anwerfen
        self._tunnel_start_event = Clock.schedule_once(
            self._start_tunnel,
            0.5,
        )

    def on_scan_devices(self, instance):
        open_mdns_scanner_popup(
            target_mac=None,
            ip_input_field=self.ip_input,
            hostname_input_field=None,
            save_callback=lambda: None,
        )

    def _start_tunnel(self, _dt):
        self._tunnel_start_event = None
        if not self._shutting_down:
            self.tunnel_manager.start()
    # --------------------------------------------------------------------------
    # Cloudflare Tunnel Handlers (Thread-sicher via Clock)
    # --------------------------------------------------------------------------
    def on_tunnel_status(self, status):
        if self._shutting_down:
            return
        Clock.schedule_once(lambda dt: self._update_tunnel_status_ui(status))

    def _update_tunnel_status_ui(self, status):
        if status == "starting":
            self.tunnel_status_label.text = "Cloudflare Tunnel: Wird gestartet …"
            self.tunnel_status_label.color = (1, 0.8, 0.2, 1)
        elif status == "online":
            self.tunnel_status_label.text = "Cloudflare Tunnel: Online"
            self.tunnel_status_label.color = (0.2, 1, 0.4, 1)
        elif status == "error":
            self.tunnel_status_label.text = "Cloudflare Tunnel: Fehler"
            self.tunnel_status_label.color = (1, 0.3, 0.3, 1)
        else:
            self.tunnel_status_label.text = "Cloudflare Tunnel: Gestoppt"
            self.tunnel_status_label.color = (0.7, 0.7, 0.7, 1)

    def on_tunnel_url(self, url):
        if self._shutting_down:
            return
        Clock.schedule_once(lambda dt: self._update_tunnel_url_ui(url))

    def _update_tunnel_url_ui(self, url):
        self.tunnel_url_input.text = url
        
        # Trigger email dispatch only for valid, new trycloudflare.com URLs
        clean_url = url.strip()
        if clean_url and "trycloudflare.com" in clean_url and clean_url != self.last_notified_tunnel_url:
            self.last_notified_tunnel_url = clean_url
            threading.Thread(
                target=self.email_sender.send_tunnel_notification,
                kwargs={"tunnel_url": clean_url, "device_id": self.device_id},
                daemon=True
            ).start()

    def on_tunnel_log(self, message):
        if self._shutting_down:
            return
        self._tunnel_log_buffer.append(message)
        self._tunnel_log_trigger()

    def _flush_tunnel_log_ui(self, _dt):
        text = self._tunnel_log_buffer.drain_text()
        if text is not None and not self._shutting_down:
            self.tunnel_log_output.text = text

    def copy_tunnel_url(self, instance):
        url = self.tunnel_url_input.text.strip()
        if url:
            Clipboard.copy(url)
            self.btn_copy_url.text = "Kopiert!"
            Clock.schedule_once(self._reset_copy_btn, 1.5)

    def _reset_copy_btn(self, dt):
        self.btn_copy_url.text = "Adresse kopieren"

    def on_restart_tunnel_click(self, instance):
        self._start_tunnel_action(self.tunnel_manager.restart)

    def on_stop_tunnel_click(self, instance):
        self._start_tunnel_action(self.tunnel_manager.stop)

    def _start_tunnel_action(self, action):
        if self._shutting_down:
            return

        def run_action():
            if not self._tunnel_action_lock.acquire(blocking=False):
                return
            try:
                if not self._shutting_down:
                    action()
            finally:
                self._tunnel_action_lock.release()

        threading.Thread(
            target=run_action,
            daemon=True,
            name="virtual-hub-tunnel-action",
        ).start()

    # --------------------------------------------------------------------------
    # Bestehende Handlers
    # --------------------------------------------------------------------------
    def on_esp_ip_change(self, instance, value):
        global ESP_IP
        ESP_IP = value.strip()

    def add_proxy_log(self, log_line):
        if self._shutting_down:
            return
        self._proxy_log_buffer.append(log_line)
        self._proxy_log_trigger()

    def _flush_proxy_log_ui(self, _dt):
        text = self._proxy_log_buffer.drain_text()
        if text is not None and not self._shutting_down:
            self.proxy_log_output.text = text

    def on_fetch_click(self, instance):
        with self._fetch_lock:
            if self._fetch_in_progress or self._shutting_down:
                return
            self._fetch_in_progress = True

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
        try:
            success, response = fetch_esp_data(ip, user, password)
        except Exception as exc:
            success, response = False, f"Unerwarteter Fehler: {exc}"

        if self._shutting_down:
            with self._fetch_lock:
                self._fetch_in_progress = False
            return

        Clock.schedule_once(
            lambda dt: self._update_ui_after_fetch(success, response)
        )

    def _update_ui_after_fetch(self, success, response):
        try:
            self.btn_fetch.disabled = False
            if success:
                pretty_json = json.dumps(response, indent=2, ensure_ascii=False)
                self.json_output.text = pretty_json
                if isinstance(response, dict):
                    dev_id = (
                        response.get("device_id")
                        or response.get("id")
                        or response.get("mac")
                    )
                    if dev_id:
                        self.device_id = str(dev_id)
            else:
                self.json_output.text = f"FEHLER:\n{response}"
        finally:
            with self._fetch_lock:
                self._fetch_in_progress = False

    def toggle_auto_refresh(self, instance):
        if self.auto_refresh_event:
            Clock.unschedule(self.auto_refresh_event)
            self.auto_refresh_event = None
            self.btn_auto.text = "Auto-Refresh: AUS"
            self.btn_auto.background_color = (0.5, 0.5, 0.5, 1.0)
        else:
            self.auto_refresh_event = Clock.schedule_interval(
                self._auto_refresh_tick,
                2.0,
            )
            self.btn_auto.text = "Auto-Refresh: AN (2s)"
            self.btn_auto.background_color = (0.2, 0.8, 0.2, 1.0)

    def _auto_refresh_tick(self, _dt):
        self.on_fetch_click(None)

    def shutdown(self):
        self._shutting_down = True

        if self._tunnel_start_event:
            self._tunnel_start_event.cancel()
            self._tunnel_start_event = None
        if self.auto_refresh_event:
            self.auto_refresh_event.cancel()
            self.auto_refresh_event = None

        self._proxy_log_trigger.cancel()
        self._tunnel_log_trigger.cancel()

        global log_callback
        if getattr(log_callback, "__self__", None) is self:
            log_callback = None

        self.tunnel_manager.stop()


class VirtualHubApp(App):

    def build(self):
        self.title = "ESP Virtual Hub & Proxy"
        proxy_thread = threading.Thread(target=start_proxy_server, daemon=True)
        proxy_thread.start()
        history_pipeline_store.start_auto_refresh()
        self.hub_widget = VirtualHubWidget()
        return self.hub_widget

    def on_stop(self):
        history_pipeline_store.stop_auto_refresh()
        if hasattr(self, "hub_widget"):
            self.hub_widget.shutdown()


if __name__ == "__main__":
    VirtualHubApp().run()
