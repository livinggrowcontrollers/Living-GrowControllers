#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sim_zombie_gui.py – GUI für sim_zombie.py
Start/Stop, sichtbarer Status, sauberer Prozess-Kill.
© 2025 Dominik Rosenthal
"""

import os
import subprocess
import signal
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock


# ------------------------------------------------------------
# Pfad zum Simulator
# ------------------------------------------------------------
BASE = os.path.dirname(os.path.abspath(__file__))
SIM_PATH = os.path.join(BASE, "sim_zombie.py")


class ZombieSimGUI(BoxLayout):

    def __init__(self, **kw):
        super().__init__(orientation="vertical", spacing=15, padding=15, **kw)

        self.proc = None

        # --------------------------------------------------------
        # STATUS
        # --------------------------------------------------------
        self.lbl_status = Label(
            text="[Stopped]",
            font_size="20sp",
            size_hint=(1, 0.3),
            markup=True
        )
        self.add_widget(self.lbl_status)

        # --------------------------------------------------------
        # BUTTON LEISTE
        # --------------------------------------------------------
        row = BoxLayout(size_hint=(1, 0.3), spacing=10)

        btn_start = Button(text="Simulator START", font_size="18sp")
        btn_start.bind(on_release=lambda *_: self.start_sim())
        row.add_widget(btn_start)

        btn_stop = Button(text="STOP", font_size="18sp")
        btn_stop.bind(on_release=lambda *_: self.stop_sim())
        row.add_widget(btn_stop)

        self.add_widget(row)

        # --------------------------------------------------------
        # INFO
        # --------------------------------------------------------
        self.lbl_info = Label(
            text=f"[code]{os.path.basename(SIM_PATH)}[/code]\n→ schreibt nach ../data/ble_dump.json",
            markup=True,
            font_size="12sp",
            size_hint=(1, 0.4)
        )
        self.add_widget(self.lbl_info)

        # Prozess überwachen
        Clock.schedule_interval(self._tick, 1)


    # --------------------------------------------------------
    # Simulator starten
    # --------------------------------------------------------
    def start_sim(self):
        if self.proc:
            return

        if not os.path.exists(SIM_PATH):
            self.lbl_status.text = "[b][color=#ff3333]Fehler: sim_zombie.py fehlt![/color][/b]"
            return

        self.proc = subprocess.Popen(
            ["python3", SIM_PATH],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        self.lbl_status.text = "[b][color=#33ff33]RUNNING – ZombieSim aktiv[/color][/b]"


    # --------------------------------------------------------
    # Stoppen
    # --------------------------------------------------------
    def stop_sim(self):
        if not self.proc:
            return

        try:
            os.kill(self.proc.pid, signal.SIGTERM)
        except:
            pass

        self.proc = None
        self.lbl_status.text = "[Stopped]"


    # --------------------------------------------------------
    # Prozess-Überwachung
    # --------------------------------------------------------
    def _tick(self, dt):
        if self.proc and self.proc.poll() is not None:
            self.proc = None
            self.lbl_status.text = "[Stopped]"

    # --------------------------------------------------------
    # Falls das Fenster geschlossen wird
    # --------------------------------------------------------
    def on_parent(self, widget, parent):
        if parent is None:
            self.stop_sim()


class ZombieSimApp(App):
    def build(self):
        return ZombieSimGUI()


if __name__ == "__main__":
    ZombieSimApp().run()
