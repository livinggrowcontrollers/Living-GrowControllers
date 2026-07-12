# dashboard_gui/ui/grow_controller_content/controller_command_status_popup.py

from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup

from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled


class GrowCommandStatusPopup:
    """Kleines Auto-Close Feedback fuer bestaetigte Grow-Controller Befehle."""

    _active_popup = None
    _dismiss_event = None

    @classmethod
    def show(
        cls,
        reset_sent=False,
        rev_confirmed=True,
        title="Befehl bestätigt",
        duration=1.4
    ):
        if cls._dismiss_event:
            Clock.unschedule(cls._dismiss_event)
            cls._dismiss_event = None

        if cls._active_popup:
            try:
                cls._active_popup.dismiss()
            except Exception:
                pass

        if reset_sent and rev_confirmed:
            detail = "Revision bestätigt\nSoft-Reset gesendet"
        elif reset_sent:
            detail = "Soft-Reset gesendet"
        else:
            detail = "Revision bestätigt"

        content = BoxLayout(
            orientation="vertical",
            padding=[dp_scaled(24), dp_scaled(18)],
            spacing=dp_scaled(8),
            size_hint=(None, None),
            size=(dp_scaled(330), dp_scaled(170)),
        )

        with content.canvas.before:
            Color(0.05, 0.05, 0.05, 0.85)
            bg = RoundedRectangle(
                pos=content.pos,
                size=content.size,
                radius=[dp_scaled(12)]
            )

        content.bind(
            pos=lambda _, value: setattr(bg, "pos", value),
            size=lambda _, value: setattr(bg, "size", value),
        )

        content.add_widget(Label(
            text="[font=FA]\uf00c[/font]",
            markup=True,
            bold=True,
            font_size=sp_scaled(42),
            color=(0.2, 1.0, 0.4, 1),
            size_hint_y=None,
            height=dp_scaled(50),
        ))
        content.add_widget(Label(
            text=title,
            bold=True,
            font_size=sp_scaled(20),
            color=(0.2, 1.0, 0.4, 1),
            size_hint_y=None,
            height=dp_scaled(28),
        ))
        content.add_widget(Label(
            text=detail,
            font_size=sp_scaled(16),
            color=(1, 1, 1, 0.9),
            halign="center",
            valign="middle",
        ))

        popup = Popup(
            title="",
            content=content,
            size_hint=(None, None),
            size=(dp_scaled(350), dp_scaled(190)),
            background="",
            background_color=(0, 0, 0, 0),
            auto_dismiss=True,
        )

        cls._active_popup = popup
        popup.open()
        cls._dismiss_event = Clock.schedule_once(lambda *_: cls.dismiss(), duration)

    @classmethod
    def dismiss(cls):
        if cls._dismiss_event:
            Clock.unschedule(cls._dismiss_event)
            cls._dismiss_event = None

        if cls._active_popup:
            try:
                cls._active_popup.dismiss()
            except Exception:
                pass
            cls._active_popup = None
