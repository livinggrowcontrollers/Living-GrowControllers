###############################################################################
# UNIFIED SLIDER - Supports both single-point and range (2-point) modes
# Created for consistent scaling across all overlays (Light, Exhaust, Circulation)
#
# USAGE:
#   - Single point: UnifiedSlider(min=0, max=100, mode='single')
#   - Range (2-point): UnifiedSlider(min=0, max=100, mode='range')
#
# Benefits:
#   - All size parameters use dp_scaled() for cross-platform consistency
#   - Easy to switch between 1-point and 2-point sliders
#   - Unified look and feel across all overlays
#   - Future-proof for light_overlay 2-point expansion
###############################################################################
# Canonical slider implementation for control overlays.

# dashboard_gui/overlays/components/unified_slider.py

from kivy.uix.widget import Widget
from kivy.properties import NumericProperty, StringProperty, BooleanProperty, AliasProperty
from kivy.graphics import Color, RoundedRectangle, Ellipse, Line
from kivy.core.window import Window
from dashboard_gui.ui.scaling_utils import dp_scaled


class UnifiedSlider(Widget):
    """
    A flexible slider that supports both single-point and range (2-point) modes.
    
    Properties:
        - min: minimum value (range mode: left handle)
        - max: maximum value (range mode: right handle, single: current value)
        - range_min: minimum allowed value
        - range_max: maximum allowed value
        - mode: 'single' or 'range'
        - value: alias for max_value in single mode (for compatibility with Kivy Slider)
    """
    
    min_value = NumericProperty(0)
    max_value = NumericProperty(100)
    range_min = NumericProperty(0)
    range_max = NumericProperty(100)
    mode = StringProperty('single')  # 'single' or 'range'
    fill_entire_track = BooleanProperty(False)  # If True, fill entire track (for light slider)

    def _get_value(self):
        """In single mode, value is max_value. In range mode, it's... well, undefined (we use min/max)"""
        return self.max_value if self.mode == 'single' else self.max_value

    def _set_value(self, value):
        """Setting value in single mode updates max_value"""
        if self.mode == 'single':
            self.max_value = value
        else:
            self.max_value = value

    # Create an alias property 'value' that maps to max_value for compatibility
    value = AliasProperty(_get_value, _set_value, bind=('max_value',))

    def __init__(self, min=0, max=100, range_min=0, range_max=100, mode='single', fill_entire_track=False, **kwargs):
        super().__init__(**kwargs)
        self.range_min = range_min
        self.range_max = range_max
        self.min_value = min
        self.max_value = max
        self.mode = mode
        self.fill_entire_track = fill_entire_track
        
        self.bind(
            pos=self._update_canvas, 
            size=self._update_canvas, 
            min_value=self._update_canvas, 
            max_value=self._update_canvas,
            mode=self._update_canvas,
            fill_entire_track=self._update_canvas
        )
    def _update_canvas(self, *args):
        self.canvas.after.clear()
        
        track_h = dp_scaled(10)
        active_h = dp_scaled(14)
        handle_size = dp_scaled(34)
        side_padding = handle_size / 2 + dp_scaled(4)   # WICHTIG: Platz für Griffe
    
        with self.canvas.after:
            # BACK TRACK (mit Abstand zu den Rändern)
            Color(0.15, 0.15, 0.15, 1)
            RoundedRectangle(
                pos=(self.x + side_padding, self.center_y - track_h / 2),
                size=(self.width - 2 * side_padding, track_h),
                radius=[dp_scaled(6)]
            )
            
            if self.mode == 'single':
                self._draw_single_mode(handle_size, active_h, track_h, side_padding)
            else:
                self._draw_range_mode(handle_size, active_h, track_h, side_padding)

    def _draw_single_mode(self, handle_size, active_h, track_h, side_padding):
        Color(0, 1, 0, 0.75)
        
        range_span = max(1, self.range_max - self.range_min)
        x_val = self.x + side_padding + ((self.max_value - self.range_min) / range_span) * (self.width - 2 * side_padding)
        
        # Active track
        RoundedRectangle(
            pos=(self.x + side_padding, self.center_y - active_h / 2),
            size=(x_val - (self.x + side_padding), active_h),
            radius=[dp_scaled(8)]
        )
        
        # Handle
        Color(1, 1, 1, 1)
        Ellipse(
            pos=(x_val - handle_size / 2, self.center_y - handle_size / 2),
            size=(handle_size, handle_size)
        )
    
    
    def _draw_range_mode(self, handle_size, active_h, track_h, side_padding):
        Color(0, 1, 0, 0.75)
        
        range_span = max(1, self.range_max - self.range_min)
        track_width = self.width - 2 * side_padding
        
        x_min = self.x + side_padding + ((self.min_value - self.range_min) / range_span) * track_width
        x_max = self.x + side_padding + ((self.max_value - self.range_min) / range_span) * track_width
        
        if self.fill_entire_track:
            RoundedRectangle(
                pos=(self.x + side_padding, self.center_y - active_h / 2),
                size=(track_width, active_h),
                radius=[dp_scaled(8)]
            )
        else:
            RoundedRectangle(
                pos=(x_min, self.center_y - active_h / 2),
                size=(x_max - x_min, active_h),
                radius=[dp_scaled(8)]
            )
        
        Color(1, 1, 1, 1)
        Ellipse(pos=(x_min - handle_size / 2, self.center_y - handle_size / 2), size=(handle_size, handle_size))
        Ellipse(pos=(x_max - handle_size / 2, self.center_y - handle_size / 2), size=(handle_size, handle_size))



    def on_touch_down(self, touch):
        if self.disabled: # <-- ABSOLUT KRITISCH
            return False 
        if self.collide_point(*touch.pos):
            self._handle_touch(touch)
            return True
    def on_touch_move(self, touch):
        if self.disabled: # <-- ABSOLUT KRITISCH
            return False
        if self.collide_point(*touch.pos):
            self._handle_touch(touch)
            return True

    def _handle_touch(self, touch):
        """Handle touch events for both single and range modes"""
        # 1. Sicherstellen, dass wir valide Werte haben
        r_min = float(self.range_min)
        r_max = float(self.range_max)
        range_span = r_max - r_min
        
        if range_span <= 0 or self.width <= 0:
            return 
        
        # 2. Padding berechnen (wie in der Grafik-Logik)
        side_padding = dp_scaled(34)/2 + dp_scaled(4)
        usable_width = self.width - 2 * side_padding
    
        # 3. Relative Position bestimmen und CLAMPEN (0.0 - 1.0)
        relative_x = (touch.x - (self.x + side_padding)) / usable_width
        relative_x = max(0.0, min(1.0, relative_x))
        
        # 4. Wert berechnen basierend auf dem ECHTEN range_max (z.B. 96)
        raw_val = relative_x * range_span + r_min
        
        # 5. HARD CLAMP auf den definierten Bereich
        val = max(r_min, min(r_max, raw_val))
        
        if self.mode == 'single':
            self.max_value = val # Setzt via AliasProperty auch 'self.value'
        else:  # 'range'
            self._handle_range_touch(val, relative_x)

    def _handle_range_touch(self, val, relative_x):
        """Handle touch for range (2-point) mode"""
        # Entferne den "HARD SNAP TO ZERO", wenn der Slider bei 15 starten soll!
        # Wenn du bei 0.03 auf range_min snappst, landet er bei 15, nicht 0.
        if relative_x < 0.03:
            self.min_value = self.range_min
            # Hier NICHT beides auf range_min setzen, sonst kleben beide Griffe bei 15
            return
        
        # Logic: welcher Griff ist näher?
        dist_min = abs(val - self.min_value)
        dist_max = abs(val - self.max_value)
        
        if dist_min < dist_max:
            # Bewege linken Griff, aber nicht über den rechten
            self.min_value = min(val, self.max_value)
        else:
            # Bewege rechten Griff, aber nicht unter den linken
            self.max_value = max(val, self.min_value)

    def _handle_single_touch(self, val, relative_x):
        """Handle touch for single-point mode"""
        # HARD SNAP TO MIN
        if relative_x < 0.03:
            self.max_value = self.range_min
            return
        
        # Clamp to range
        val = max(self.range_min, min(self.range_max, val))
        self.max_value = val

  
