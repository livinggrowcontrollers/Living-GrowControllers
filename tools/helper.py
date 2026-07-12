#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scrcpy + ADB Control Center
Dominik Edition 2025

Features:
- SCRCPY über TCP-IP starten
- APK auswählen & installieren
- ADB connect/disconnect/kill/start
- ADB devices anzeigen
- Live-LOGCAT Viewer mit Filter
"""

import subprocess
import threading
import os

from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.core.window import Window
from kivy.clock import Clock


DEFAULT_IP = "192.168.2.127:5555"


# =====================================================================
# ADB COMMAND HELPER
# =====================================================================

def run_cmd(cmd):
    """Führt einen Shell-Befehl aus und gibt stdout zurück."""
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode("utf-8", "ignore")
        return out
    except Exception as e:
        return f"[ERROR] {e}"


# =====================================================================
# MAIN APPLICATION
# =====================================================================

class ScrcpyADBHelper(App):

    def build(self):
        Window.size = (650, 700)
        Window.clearcolor = (0.08, 0.08, 0.08, 1)

        self.selected_apk = None
        self.log_running = False

        root = BoxLayout(orientation="vertical", padding=10, spacing=10)

        # ------------------------------------------------------------------
        # IP ADDRESS FIELD
        # ------------------------------------------------------------------
        self.ip_field = TextInput(
            text=DEFAULT_IP,
            multiline=False,
            font_size=20,
            size_hint=(1, 0.1),
            background_color=(0.15, 0.15, 0.15, 1),
            foreground_color=(1, 1, 1, 1),
        )
        root.add_widget(self.ip_field)

        # ------------------------------------------------------------------
        # SCRCPY BUTTON
        # ------------------------------------------------------------------
        btn_scrcpy = Button(
            text="📱 SCRCPY starten",
            font_size=22,
            background_color=(0.1, 0.6, 0.3, 1),
            color=(1, 1, 1, 1),
            size_hint=(1, 0.1)
        )
        btn_scrcpy.bind(on_release=self.start_scrcpy)
        root.add_widget(btn_scrcpy)

        # ==================================================================
        # ADB CONTROL BUTTONS
        # ==================================================================
        adb_row = BoxLayout(size_hint=(1, 0.1), spacing=10)

        btn_connect = Button(text="🔌 connect", on_release=self.adb_connect)
        btn_disc = Button(text="❌ disconnect", on_release=self.adb_disconnect)
        btn_kill = Button(text="💀 kill-server", on_release=self.adb_kill)
        btn_start = Button(text="▶ start-server", on_release=self.adb_start)

        adb_row.add_widget(btn_connect)
        adb_row.add_widget(btn_disc)
        adb_row.add_widget(btn_kill)
        adb_row.add_widget(btn_start)
        root.add_widget(adb_row)

        # ------------------------------------------------------------------
        # ADB DEVICES BUTTON
        # ------------------------------------------------------------------
        btn_devices = Button(
            text="📋 Geräte anzeigen (ADB devices)",
            size_hint=(1, 0.08),
            background_color=(0.2, 0.4, 0.6, 1)
        )
        btn_devices.bind(on_release=self.show_devices)
        root.add_widget(btn_devices)

        # ==================================================================
        # APK BEREICH
        # ==================================================================
        btn_choose = Button(
            text="📂 APK auswählen",
            size_hint=(1, 0.08),
            background_color=(0.4, 0.4, 0.8, 1)
        )
        btn_choose.bind(on_release=self.choose_apk)
        root.add_widget(btn_choose)

        btn_install = Button(
            text="⬆️ APK installieren",
            size_hint=(1, 0.08),
            background_color=(0.7, 0.2, 0.2, 1)
        )
        btn_install.bind(on_release=self.install_apk)
        root.add_widget(btn_install)

        # ==================================================================
        # LOGCAT VIEW
        # ==================================================================

        self.filter_field = TextInput(
            text="",
            hint_text="🔍 Logcat Filter (z.B. python, kivy, error)",
            multiline=False,
            size_hint=(1, 0.08),
            background_color=(0.15, 0.15, 0.15, 1),
            foreground_color=(1, 1, 1, 1),
        )
        root.add_widget(self.filter_field)

        log_controls = BoxLayout(size_hint=(1, 0.07), spacing=10)
        btn_log_start = Button(text="📡 Logcat starten", on_release=self.start_logcat)
        btn_log_stop = Button(text="🛑 Logcat stoppen", on_release=self.stop_logcat)
        log_controls.add_widget(btn_log_start)
        log_controls.add_widget(btn_log_stop)
        root.add_widget(log_controls)

        self.log_output = TextInput(
            text="",
            readonly=True,
            font_size=13,
            background_color=(0, 0, 0, 1),
            foreground_color=(0, 1, 0, 1)
        )
        scroll = ScrollView(size_hint=(1, 0.35))
        scroll.add_widget(self.log_output)
        root.add_widget(scroll)

        return root

    # ==================================================================
    # SCRCPY
    # ==================================================================
    def start_scrcpy(self, *args):
        ip = self.ip_field.text.strip()
        try:
            subprocess.Popen(["scrcpy", f"--tcpip={ip}"])
        except Exception as e:
            self.append_log(f"[SCRCPY ERROR] {e}")

    # ==================================================================
    # ADB CONTROLS
    # ==================================================================
    def adb_connect(self, *args):
        ip = self.ip_field.text.strip()
        out = run_cmd(["adb", "connect", ip])
        self.append_log(out)

    def adb_disconnect(self, *args):
        out = run_cmd(["adb", "disconnect"])
        self.append_log(out)

    def adb_kill(self, *args):
        out = run_cmd(["adb", "kill-server"])
        self.append_log(out)

    def adb_start(self, *args):
        out = run_cmd(["adb", "start-server"])
        self.append_log(out)

    def show_devices(self, *args):
        out = run_cmd(["adb", "devices"])
        self.append_log(out)

    # ==================================================================
    # APK AUSWÄHLEN
    # ==================================================================
    def choose_apk(self, *args):
        chooser = FileChooserIconView(filters=["*.apk"])

        popup = Popup(
            title="APK auswählen",
            content=chooser,
            size_hint=(0.9, 0.9)
        )

        def _on_select(instance, selection, touch):
            if selection:
                self.selected_apk = selection[0]
                self.append_log(f"[APK] gewählt: {self.selected_apk}")
                popup.dismiss()

        chooser.bind(on_submit=_on_select)
        popup.open()

    # ==================================================================
    # APK INSTALL
    # ==================================================================
    def install_apk(self, *args):
        if not self.selected_apk:
            self.append_log("[WARN] Keine APK gewählt!")
            return
        out = run_cmd(["adb", "install", "-r", self.selected_apk])
        self.append_log(out)

    # ==================================================================
    # LOGCAT
    # ==================================================================
    def start_logcat(self, *args):
        if self.log_running:
            return
        self.log_running = True
        self.log_output.text = ""

        def log_thread():
            proc = subprocess.Popen(["adb", "logcat"], stdout=subprocess.PIPE)
            while self.log_running:
                line = proc.stdout.readline().decode("utf-8", "ignore")
                if not line:
                    break
                filt = self.filter_field.text.strip().lower()
                if filt in line.lower():
                    Clock.schedule_once(lambda dt, l=line: self.append_log(l), 0)
            proc.kill()

        threading.Thread(target=log_thread, daemon=True).start()

    def stop_logcat(self, *args):
        self.log_running = False

    # ==================================================================
    # LOG HELPER
    # ==================================================================
    def append_log(self, text):
        self.log_output.text += text + "\n"
        self.log_output.cursor = (0, len(self.log_output.text.split("\n")))


# =====================================================================
# START APP
# =====================================================================
if __name__ == "__main__":
    ScrcpyADBHelper().run()
