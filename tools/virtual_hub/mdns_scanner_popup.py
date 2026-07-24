import threading

from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView

from zeroconf import ServiceBrowser, Zeroconf

from device_discoverer import PopupDiscoverer
from kivy.metrics import dp, sp


def open_mdns_scanner_popup(
    target_mac,
    ip_input_field,
    hostname_input_field,
    save_callback,
):
    """
    Öffnet ein modales Popup,
    scannt das Netzwerk nach Growmastern
    und übernimmt die Auswahl direkt
    in die Eingabefelder.
    """

    popup_layout = BoxLayout(
        orientation="vertical",
        padding=dp(15),
        spacing=dp(10)
    )

    with popup_layout.canvas.before:
        Color(0, 0, 0, 0.6)
        bg_rect = RoundedRectangle(
            pos=popup_layout.pos,
            size=popup_layout.size,
            radius=[dp(18)]
        )

    popup_layout.bind(
        pos=lambda *_: setattr(bg_rect, "pos", popup_layout.pos),
        size=lambda *_: setattr(bg_rect, "size", popup_layout.size)
    )

    status_lbl = Label(
        text="Suche aktive Growmaster im Netzwerk (4s)...",
        size_hint_y=None,
        height=dp(30),
        font_size=sp(14)
    )

    popup_layout.add_widget(status_lbl)

    scroll = ScrollView()

    result_grid = GridLayout(
        cols=1,
        spacing=dp(8),
        size_hint_y=None
    )

    result_grid.bind(
        minimum_height=result_grid.setter("height")
    )

    scroll.add_widget(result_grid)

    popup_layout.add_widget(scroll)

    close_btn = Button(
        text="Abbrechen",
        size_hint_y=None,
        height=dp(40),
        background_down="",
        background_color=(0.3, 0.3, 0.3, 1)
    )

    popup_layout.add_widget(close_btn)

    popup = ModalView(
        size_hint=(0.85, 0.7),
        auto_dismiss=True,
        background="",
        background_color=(0, 0, 0, 0.72)
    )

    popup.add_widget(popup_layout)

    close_btn.bind(on_release=popup.dismiss)

    scan_cancelled = threading.Event()
    discoverer_holder = []

    def cancel_scan(*_):
        scan_cancelled.set()
        if discoverer_holder:
            discoverer_holder[0].cancel()

    popup.bind(on_dismiss=cancel_scan)
    popup.open()

    def on_device_discovered(mac_id, data):
        if scan_cancelled.is_set():
            return

        btn_text = (
            f"ID: {mac_id}  |  "
            f"IP: {data['ip_address']}  |  "
            f"{data['hostname']}.local"
        )

        dev_btn = Button(
            text=btn_text,
            size_hint_y=None,
            height=dp(45),
            background_down="",
            background_color=(0.15, 0.4, 0.7, 1)
        )

        def select_this_device(*_):
            if scan_cancelled.is_set():
                return

            ip_input_field.text = data["ip_address"]

            popup.dismiss()

            if save_callback:
                Clock.schedule_once(
                    lambda dt: save_callback(),
                    0.1
                )

        dev_btn.bind(
            on_release=select_this_device
        )

        result_grid.add_widget(dev_btn)

    def run_network_scan():
        zc = None
        browser = None
        try:
            if scan_cancelled.is_set():
                return

            zc = Zeroconf()
            discoverer = PopupDiscoverer(on_device_discovered)
            discoverer_holder.append(discoverer)

            if scan_cancelled.is_set():
                discoverer.cancel()
                return

            browser = ServiceBrowser(
                zc,
                "_http._tcp.local.",
                discoverer
            )
            scan_cancelled.wait(4.0)
        finally:
            if zc is not None:
                zc.close()

        def finish_status(*_):
            if scan_cancelled.is_set():
                return

            if not result_grid.children:

                status_lbl.text = (
                    "Keine mDNS Geräte gefunden. "
                    "Stelle sicher, dass du im selben WLAN bist."
                )

            else:

                status_lbl.text = (
                    "Scan abgeschlossen. "
                    "Wähle das passende Gerät für das Autofill aus:"
                )

        if not scan_cancelled.is_set():
            Clock.schedule_once(finish_status)

    threading.Thread(
        target=run_network_scan,
        daemon=True
    ).start()
