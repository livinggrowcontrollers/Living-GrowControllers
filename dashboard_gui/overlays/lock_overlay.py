# dashboard_gui/overlays/lock_overlay.py
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.graphics import Color, RoundedRectangle
from kivy.animation import Animation

from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled


class _TouchBlocker(Widget):
    # Wir überlassen das Handling komplett der LockOverlay-Klasse,
    # blockieren aber standardmäßig Touches innerhalb des Widgets.
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            return True
        return False

    def on_touch_move(self, touch):
        if self.collide_point(*touch.pos):
            return True
        return False

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            return True
        return False


class LockOverlay:

    def __init__(self, parent, panel, unlock_callback):
        self.parent = parent
        self.panel = panel
        self.unlock_callback = unlock_callback

        self.overlay = None
        self.unlock_button = None
        self._pulse_anim = None

    def create(self):
        if self.overlay:
            return

        # ==========================
        # TOUCH BLOCKER
        # ==========================
        self.overlay = _TouchBlocker(
            size=self.panel.size,
            pos=self.panel.pos,
            size_hint=(None, None)
        )

        with self.overlay.canvas.before:
            Color(0, 0, 0, 0.60)
            self.overlay_bg = RoundedRectangle(
                pos=self.panel.pos,
                size=self.panel.size,
                radius=[dp_scaled(20)]
            )

        # WICHTIG: Wir binden an das globale Window oder fangen den Touch 
        # im Overlay ab, bevor _TouchBlocker ihn konsumiert.
        self.overlay.bind(
            on_touch_down=self._overlay_touch_down
        )

        # ==========================
        # UNLOCK BUTTON
        # ==========================
        lock_icon = "[font=FA]\uf023[/font]"

        self.unlock_button = Button(
            text=f"{lock_icon}  [b]UNLOCK TO EDIT[/b]",
            markup=True,
            size_hint=(None, None),
            size=(dp_scaled(220), dp_scaled(50)),
            background_color=(0.05, 0.55, 0.95, 1.0),
            color=(1, 1, 1, 1),
            font_size=sp_scaled(15.5)
        )

        self.unlock_button.bind(
            on_release=self._on_unlock
        )

        # ==========================
        # POSITIONIERUNG
        # ==========================
        self._update_overlay_pos()

        self.parent.add_widget(self.overlay)
        self.parent.add_widget(self.unlock_button)

        self.panel.bind(
            pos=self._update_overlay_pos,
            size=self._update_overlay_pos
        )

        self._start_pulse_animation()

    def _overlay_touch_down(self, instance, touch):
        if not self.unlock_button:
            return False

        # Fall 1: Klick auf den Unlock-Button -> Button regelt das on_release selbst
        if self.unlock_button.collide_point(*touch.pos):
            return False

        # Fall 2: Klick ist AUSSERHALB des Overlays/Panels -> Schließen (Dismiss)
        if not self.overlay.collide_point(*touch.pos):
            self._on_unlock()  # Führt den Unlock aus
            return False       # Touch nicht blockieren, damit andere UI-Elemente reagieren können

        # Fall 3: Klick ist INNERHALB des Overlays (aber nicht auf dem Button) -> Shake
        self._shake_button()
        return True

    def _shake_button(self):
        if not self.unlock_button:
            return

        current_x = self.unlock_button.x

        (
            Animation(x=current_x + dp_scaled(12), duration=0.04) +
            Animation(x=current_x - dp_scaled(12), duration=0.04) +
            Animation(x=current_x + dp_scaled(6), duration=0.04) +
            Animation(x=current_x, duration=0.04)
        ).start(self.unlock_button)

    def _start_pulse_animation(self):
        if not self.unlock_button:
            return

        self._pulse_anim = (
            Animation(
                background_color=(0.10, 0.65, 1.00, 1.00),
                duration=1.2,
                t="in_out_quad"
            )
            +
            Animation(
                background_color=(0.05, 0.55, 0.95, 1.00),
                duration=1.2,
                t="in_out_quad"
            )
        )

        self._pulse_anim.repeat = True
        self._pulse_anim.start(self.unlock_button)

    def _update_overlay_pos(self, *_):
        if self.overlay:
            self.overlay.pos = self.panel.pos
            self.overlay.size = self.panel.size

            self.overlay_bg.pos = self.panel.pos
            self.overlay_bg.size = self.panel.size

        if self.unlock_button:
            margin = dp_scaled(20)
            self.unlock_button.pos = (
                self.panel.x + margin,
                self.panel.y + margin
            )

    def _on_unlock(self, *_):
        self.unlock()
        if self.unlock_callback:
            self.unlock_callback()

    def unlock(self):
        if self._pulse_anim and self.unlock_button:
            self._pulse_anim.cancel(self.unlock_button)

        if self.overlay and self.overlay.parent:
            self.overlay.parent.remove_widget(self.overlay)

        if self.unlock_button and self.unlock_button.parent:
            self.unlock_button.parent.remove_widget(self.unlock_button)

        self.overlay = None
        self.unlock_button = None
        self._pulse_anim = None

    def lock(self):
        if not self.overlay:
            self.create()