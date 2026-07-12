#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import kivy
kivy.require("2.3.0")

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.core.window import Window
from kivy.core.clipboard import Clipboard


class IndentTool(BoxLayout):

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", spacing=10, padding=10, **kwargs)

        # -------- TEXT INPUT --------
        self.text_in = TextInput(
            hint_text="Code hier einfügen…",
            multiline=True,
            font_size=16,
            size_hint=(1, 0.6)
        )
        self.add_widget(self.text_in)

        # -------- TEXT OUTPUT --------
        self.text_out = TextInput(
            hint_text="Ergebnis…",
            multiline=True,
            readonly=True,
            font_size=16,
            size_hint=(1, 0.6)
        )
        self.add_widget(self.text_out)

        # -------- CONTROL BAR --------
        ctrl = BoxLayout(orientation="horizontal", spacing=10, size_hint=(1, 0.15))

        # Dropdown für Schrittweite
        self.indent_size = 4
        self.spinner = Spinner(
            text="4",
            values=("2", "4", "8", "16", "32"),
            size_hint=(None, None),
            size=(90, 40)
        )
        self.spinner.bind(text=self.on_indent_change)

        # Buttons
        btn_left = Button(
            text="<", font_size=22,
            on_press=lambda *_: self.do_indent(-self.indent_size)
        )
        btn_right = Button(
            text=">", font_size=22,
            on_press=lambda *_: self.do_indent(self.indent_size)
        )

        # --- COPY BUTTON ---
        btn_copy = Button(
            text="COPY",
            font_size=16,
            on_press=lambda *_: self.copy_output()
        )

        ctrl.add_widget(self.spinner)
        ctrl.add_widget(btn_left)
        ctrl.add_widget(btn_right)
        ctrl.add_widget(btn_copy)

        self.add_widget(ctrl)

    # -------- CALLBACK --------

    def on_indent_change(self, instance, value):
        self.indent_size = int(value)

    # -------- COPY FEATURE --------
    def copy_output(self):
        Clipboard.copy(self.text_out.text)

    # -------- INDENT ENGINE --------

    def do_indent(self, spaces):
        raw = self.text_in.text.splitlines()
        out = []

        indent = " " * abs(spaces)
        remove = abs(spaces)

        if spaces > 0:
            # EINRÜCKEN
            for line in raw:
                out.append(indent + line)
        else:
            # AUSRÜCKEN
            for line in raw:
                if line.startswith(" " * remove):
                    out.append(line[remove:])
                else:
                    out.append(line)

        self.text_out.text = "\n".join(out)


class IndentApp(App):
    def build(self):
        Window.size = (900, 650)
        return IndentTool()


if __name__ == "__main__":
    IndentApp().run()
