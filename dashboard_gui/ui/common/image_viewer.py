# dashboard_gui/ui/common/image_viewer.py
from kivy.uix.popup import Popup
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from dashboard_gui.ui.common.buttons.glass_button import GlassButton
from dashboard_gui.ui.scaling_utils import dp_scaled
import math

class ZoomableImagePopup(Popup):
    """
    High-End Image Viewer: Garantiert flüssiges Ziehen (Dragging) im gezoomten Zustand.
    Der Close-Button schwebt absolut unangreifbar auf einer eigenen Ebene ganz oben.
    Optimiert für fehlerfreies Android Multi-Touch & Clamping.
    """
    def __init__(self, title, image_source, **kwargs):
        # 1. Das absolute Root-Layout
        root = FloatLayout(size_hint=(1, 1))
        
        # 2. Die Bildebene (Unten)
        self.image_layer = FloatLayout(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        
        # WICHTIG: size_hint=None für manuelle Pixelsteuerung (verhindert teure do_layout-Zyklen)
        self.img = Image(
            source=image_source,
            allow_stretch=True,
            keep_ratio=True,
            size_hint=(None, None)
        )
        self.img.bind(texture=self._optimize_texture)
        self.image_layer.add_widget(self.img)
        root.add_widget(self.image_layer)

        # 3. Die UI-Ebene (Oben)
        ui_layer = FloatLayout(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        
        self.close_btn = GlassButton(
            text="[font=FA]\uf00d[/font] CLOSE",
            markup=True,
            size_hint=(None, None),
            size=(dp_scaled(140), dp_scaled(48)),
            pos_hint={"right": 0.985, "top": 0.985}
        )
        self.close_btn.bind(on_release=self.dismiss)
        ui_layer.add_widget(self.close_btn)
        root.add_widget(ui_layer)

        # Interne States für Zoom und Drag
        self.current_scale = 1.0
        self.scale_min = 1.0
        self.scale_max = 8.0
        
        # Basis-Dimensionen für Berechnungen merken
        self._base_size = (0, 0)
        self.image_layer.bind(size=self._init_image_size)

        # Android-sicheres Touch-Tracking über Unique IDs
        self.active_touches = {}

        super().__init__(
            title=title,
            content=root,
            size_hint=(0.98, 0.98),
            background='',
            background_color=(0, 0, 0, 0.95),
            **kwargs
        )

    def _optimize_texture(self, instance, texture):
        if texture:
            texture.filters = ('linear', 'linear')

    def _init_image_size(self, instance, size):
        """Initialisiert und zentriert das Bild basierend auf der Layer-Größe."""
        self._base_size = size[:]
        self.apply_transformations()

    def apply_transformations(self):
        """Berechnet die exakte Pixel-Größe und schützt vor Out-of-Bounds (Clamping)."""
        if not self._base_size or self._base_size == (0, 0):
            return

        # 1. Neue Zielgröße berechnen
        target_w = self._base_size[0] * self.current_scale
        target_h = self._base_size[1] * self.current_scale
        self.img.size = (target_w, target_h)

        # 2. Wenn ungezommt: Exakt zentrieren
        if self.current_scale <= 1.0:
            self.img.pos = (
                (self._base_size[0] - target_w) / 2,
                (self._base_size[1] - target_h) / 2
            )
            return

        # 3. Drag-Grenzen (Clamping) berechnen
        # Das Bild darf sich nur so weit bewegen, dass die Ränder den Screen füllen
        min_x = self._base_size[0] - target_w
        max_x = 0
        min_y = self._base_size[1] - target_h
        max_y = 0

        # Sicherheitsnetz: Falls Bild kleiner als der Screen ist (selten bei Keep-Ratio Fills)
        if min_x > max_x: min_x, max_x = max_x, min_x
        if min_y > max_y: min_y, max_y = max_y, min_y

        # Aktuelle Position limitieren
        new_x = max(min_x, min(max_x, self.img.x))
        new_y = max(min_y, min(max_y, self.img.y))
        
        self.img.pos = (new_x, new_y)

    def on_touch_down(self, touch):
        # 1. BUTTON PRIORITÄT: Frisst das Event sofort auf, falls getroffen
        if self.close_btn.collide_point(*touch.pos):
            self.close_btn.on_touch_down(touch)
            return True

        if self.collide_point(*touch.pos):
            if touch.is_mouse_scrolling:
                if touch.button == 'scrolldown':
                    self.zoom(1.1, touch.pos)
                elif touch.button == 'scrollup':
                    self.zoom(0.9, touch.pos)
                return True
            
            # Touch sauber über ID/UID tracken
            touch.grab(self)
            self.active_touches[touch.uid] = touch
            return True
            
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return super().on_touch_move(touch)

        # Touch-Daten im Dict aktuell halten
        if touch.uid in self.active_touches:
            self.active_touches[touch.uid] = touch

        # MULTI-TOUCH: Pinch to Zoom (Exakt 2 Finger registriert)
        if len(self.active_touches) == 2:
            touches = list(self.active_touches.values())
            t1, t2 = touches[0], touches[1]
            
            # Aktuelle Distanz (jetziger Frame)
            curr_dist = math.hypot(t1.x - t2.x, t1.y - t2.y)
            # Vorherige Distanz (vorheriger Frame via ppos)
            prev_dist = math.hypot(t1.px - t2.px, t1.py - t2.py)
            
            if prev_dist > 0:
                factor = curr_dist / prev_dist
                mid_x = (t1.x + t2.x) / 2
                mid_y = (t1.y + t2.y) / 2
                self.zoom(factor, (mid_x, mid_y))
            return True

        # SINGLE-TOUCH: Flüssiges Dragging via Pixel-Verschiebung
        elif len(self.active_touches) == 1 and self.current_scale > 1.0:
            # Nutze direkte Pixel-Differenzen statt relativer pos_hints
            self.img.x += touch.dx
            self.img.y += touch.dy
            self.apply_transformations()
            return True

        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            # Sicher aus dem Tracking-Dict entfernen
            if touch.uid in self.active_touches:
                del self.active_touches[touch.uid]
            return True
        return super().on_touch_up(touch)

    def zoom(self, factor, anchor_pos):
        """
        Präzise Zoom-Engine: Fixiert den Anchor-Punkt (z.B. die Mitte zwischen zwei Fingern)
        bombenfest auf dem Bildschirm, während das Bild darunter skaliert.
        """
        old_scale = self.current_scale
        new_scale = max(self.scale_min, min(self.scale_max, old_scale * factor))
        
        if new_scale == old_scale:
            return

        # 1. Bestimme, wo sich der Anchor-Punkt RELATIV innerhalb des Bildes befindet (0.0 bis 1.0)
        # Wenn das Bild z.B. bei X=100 liegt, 400px breit ist und dein Finger bei X=200 steht,
        # dann touchst du das Bild bei genau 25% seiner Breite (rel_touch_x = 0.25).
        if self.img.width > 0 and self.img.height > 0:
            rel_touch_x = (anchor_pos[0] - self.img.x) / self.img.width
            rel_touch_y = (anchor_pos[1] - self.img.y) / self.img.height
        else:
            rel_touch_x, rel_touch_y = 0.5, 0.5

        # 2. Skalierung anwenden (Größe des Bildes für die Berechnung simulieren)
        self.current_scale = new_scale
        target_w = self._base_size[0] * new_scale
        target_h = self._base_size[1] * new_scale

        # 3. Die neue Position so verschieben, dass der relative Punkt exakt unter dem Anchor bleibt.
        # Wir berechnen, wo der Punkt NACH der Skalierung liegen würde, und ziehen das vom Bildschirm-Anchor ab.
        self.img.x = anchor_pos[0] - (rel_touch_x * target_w)
        self.img.y = anchor_pos[1] - (rel_touch_y * target_h)

        # 4. Transformation und das bewährte Clamping (Sicherheitsgrenzen) ausführen
        self.apply_transformations()