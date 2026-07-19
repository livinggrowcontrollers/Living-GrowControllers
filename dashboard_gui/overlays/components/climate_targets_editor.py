from kivy.uix.boxlayout import BoxLayout

import config
from dashboard_gui.ui.scaling_utils import dp_scaled
from dashboard_gui.overlays.features.shared.climate_targets import ClimateTargets
from .labeled_slider import LabeledSlider


class ClimateTargetsEditor(BoxLayout):
    """Shared temperature, humidity and VPD range controls."""

    def __init__(self, defaults=None, on_change=None, on_touch_down=None, on_touch_up=None, **kwargs):
        super().__init__(orientation="vertical", size_hint_y=None, height=dp_scaled(150), **kwargs)
        defaults = defaults or ClimateTargets()
        self._applying = False
        self._on_change = on_change

        self.temp = LabeledSlider(
            "TEMPERATURE TARGET",
            slider_kwargs={"range_min": 15, "range_max": 30, "min": defaults.temp_min, "max": defaults.temp_max, "mode": "range"},
        )
        self.humidity = LabeledSlider(
            "HUMIDITY TARGET",
            slider_kwargs={"range_min": 30, "range_max": 70, "min": defaults.humidity_min, "max": defaults.humidity_max, "mode": "range"},
        )
        self.vpd = LabeledSlider(
            "VPD TARGET",
            slider_kwargs={"range_min": 1, "range_max": 26, "min": int(defaults.vpd_min * 10), "max": int(defaults.vpd_max * 10), "mode": "range"},
        )

        for field in self.fields:
            field.slider.bind(min_value=self._value_changed, max_value=self._value_changed)
            if on_touch_down:
                field.slider.bind(on_touch_down=on_touch_down)
            if on_touch_up:
                field.slider.bind(on_touch_up=on_touch_up)
            self.add_widget(field)
        self._update_labels(defaults)

    @property
    def fields(self):
        return (self.temp, self.humidity, self.vpd)

    @property
    def sliders(self):
        return [field.slider for field in self.fields]

    @property
    def is_applying(self):
        return self._applying

    def values(self):
        return ClimateTargets(
            temp_min=round(float(self.temp.slider.min_value), 1),
            temp_max=round(float(self.temp.slider.max_value), 1),
            humidity_min=int(self.humidity.slider.min_value),
            humidity_max=int(self.humidity.slider.max_value),
            vpd_min=round(self.vpd.slider.min_value / 10.0, 1),
            vpd_max=round(self.vpd.slider.max_value / 10.0, 1),
        )

    def apply(self, targets):
        self._applying = True
        try:
            self.temp.slider.min_value = targets.temp_min
            self.temp.slider.max_value = targets.temp_max
            self.humidity.slider.min_value = targets.humidity_min
            self.humidity.slider.max_value = targets.humidity_max
            self.vpd.slider.min_value = int(targets.vpd_min * 10)
            self.vpd.slider.max_value = int(targets.vpd_max * 10)
        finally:
            self._applying = False
        self._update_labels(targets)

    def set_disabled(self, disabled):
        for slider in self.sliders:
            slider.disabled = disabled

    def _value_changed(self, *_):
        if self._applying:
            return
        targets = self.values()
        self._update_labels(targets)
        if self._on_change:
            self._on_change(targets)

    def _update_labels(self, targets):
        if config.get_temperature_unit().upper() == "F":
            low = targets.temp_min * 9 / 5 + 32
            high = targets.temp_max * 9 / 5 + 32
            self.temp.value_label.text = f"{low:.1f} °F - {high:.1f} °F"
        else:
            self.temp.value_label.text = f"{targets.temp_min:.1f} °C - {targets.temp_max:.1f} °C"
        self.humidity.value_label.text = f"{targets.humidity_min}% - {targets.humidity_max}%"
        self.vpd.value_label.text = f"{targets.vpd_min:.1f} kPa - {targets.vpd_max:.1f} kPa"
