# tools/virtual_hub/cloudflare_tunnel_manager.py

import os
import re
import sys
import subprocess
import threading
import time

class CloudflareTunnelManager:
    """
    Verwaltet den lokalen cloudflared Quick-Tunnel-Prozess.
    Liest den stdout/stderr-Stream zeilenweise aus, ermittelt die öffentliche URL
    und verwaltet den Prozessstatus thread-sicher.
    """

    def __init__(self, local_url="http://127.0.0.1:80", on_status=None, on_url=None, on_log=None):
        self.local_url = local_url
        self.on_status_cb = on_status
        self.on_url_cb = on_url
        self.on_log_cb = on_log

        self.process = None
        self.reader_thread = None
        self.stop_requested = False
        self._state_lock = threading.RLock()
        self._operation_lock = threading.Lock()
        
        self.status = "stopped"
        self.public_url = ""
        self.binary_path = self._get_binary_path()

    def _get_binary_path(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        if sys.platform.startswith("win"):
            binary_name = "cloudflared.exe"
        else:
            binary_name = "cloudflared"
        return os.path.join(base_dir, binary_name)

    def _update_status(self, new_status):
        with self._state_lock:
            self.status = new_status
            callback = self.on_status_cb
        if callback:
            callback(new_status)

    def _update_url(self, url):
        with self._state_lock:
            self.public_url = url
            callback = self.on_url_cb
        if callback:
            callback(url)

    def _log(self, message):
        with self._state_lock:
            callback = self.on_log_cb
        if callback:
            callback(message)

    def start(self):
        with self._operation_lock:
            self._start_locked()

    def _start_locked(self):
        with self._state_lock:
            process = self.process
        if process and process.poll() is None:
            self._log("[Tunnel] Tunnel läuft bereits.")
            return

        with self._state_lock:
            self.stop_requested = False
        self._update_url("")
        self._update_status("starting")

        # 1. Existenzprüfung der Binary
        if not os.path.exists(self.binary_path):
            error_msg = f"Datei gefehlt: '{os.path.basename(self.binary_path)}' wurde im Ordner nicht gefunden."
            self._log(f"[Tunnel Fehler] {error_msg}")
            self._update_status("error")
            return

        # 2. Prüfen auf Ausführbarkeit (macOS/Linux)
        if not sys.platform.startswith("win"):
            if not os.access(self.binary_path, os.X_OK):
                error_msg = f"Datei nicht ausführbar: Rechte für '{os.path.basename(self.binary_path)}' fehlen."
                self._log(f"[Tunnel Fehler] {error_msg}")
                self._update_status("error")
                return

        command = [
            self.binary_path,
            "tunnel",
            "--url",
            self.local_url
        ]

        try:
            self._log(f"[Tunnel] Starte cloudflared: {' '.join(command)}")
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
        except Exception as e:
            self._log(f"[Tunnel Fehler] Prozess konnte nicht gestartet werden: {str(e)}")
            self._update_status("error")
            return

        reader_thread = threading.Thread(
            target=self._read_output,
            args=(process,),
            daemon=True,
            name="cloudflared-output",
        )
        with self._state_lock:
            self.process = process
            self.reader_thread = reader_thread
        reader_thread.start()

    def _read_output(self, process):
        url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
        url_found = False

        while process.poll() is None:
            line = process.stdout.readline()
            if not line:
                break
            
            line_clean = line.strip()
            if line_clean:
                self._log(f"[cloudflared] {line_clean}")

                if not url_found:
                    match = url_pattern.search(line_clean)
                    if match:
                        found_url = match.group(0)
                        url_found = True
                        self._update_url(found_url)
                        self._update_status("online")

        # Prozess beendet
        exit_code = process.poll()
        with self._state_lock:
            is_current = self.process is process
            stop_requested = self.stop_requested
        if not is_current:
            return

        if not stop_requested:
            if not url_found and self.status == "starting":
                self._log("[Tunnel Fehler] Prozess beendet ohne eine URL zu erzeugen.")
                self._update_status("error")
            elif self.status == "online":
                self._log(f"[Tunnel] Cloudflare Tunnel wurde beendet (Exit Code: {exit_code}).")
                self._update_status("stopped")
            else:
                self._update_status("stopped")
        else:
            self._update_status("stopped")

    def stop(self):
        with self._operation_lock:
            self._stop_locked()

    def _stop_locked(self):
        with self._state_lock:
            self.stop_requested = True
            process = self.process
            reader_thread = self.reader_thread

        if process and process.poll() is None:
            self._log("[Tunnel] Stoppe cloudflared-Prozess...")
            try:
                process.terminate()
                try:
                    process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    self._log("[Tunnel] Prozess reagiert nicht auf terminate(), sende kill()...")
                    process.kill()
                    process.wait(timeout=1.0)
            except Exception as e:
                self._log(f"[Tunnel Fehler] Fehler beim Stoppen: {str(e)}")

        if process and process.stdout:
            try:
                process.stdout.close()
            except Exception:
                pass
        if (
            reader_thread
            and reader_thread is not threading.current_thread()
            and reader_thread.is_alive()
        ):
            reader_thread.join(timeout=1.0)

        with self._state_lock:
            if self.process is process:
                self.process = None
                self.reader_thread = None
        self._update_url("")
        self._update_status("stopped")
        self._log("[Tunnel] Gestoppt.")

    def restart(self):
        with self._operation_lock:
            self._log("[Tunnel] Neustart wird durchgeführt...")
            self._stop_locked()
            time.sleep(0.5)
            self._start_locked()
