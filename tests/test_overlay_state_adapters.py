import unittest

from dashboard_gui.overlays.features.circulation.state_adapter import CirculationFanStateAdapter
from dashboard_gui.overlays.features.exhaust.state_adapter import ExhaustFanStateAdapter
from dashboard_gui.overlays.features.light.schedule import LightSchedule
from dashboard_gui.overlays.features.light.state_adapter import LightStateAdapter
from dashboard_gui.overlays.features.climate_hub.profiles import PROFILES, match_profile
from dashboard_gui.overlays.features.climate_hub.state_adapter import ClimateHubStateAdapter


class StateAdapterTests(unittest.TestCase):
    def test_circulation_instances_use_their_own_revision_and_values(self):
        raw = {
            "circulation_fan2_min": 31,
            "circulation_fan2_pct": 77,
            "circulation_fan2_mode": "chao",
            "circulation_fan2_speed_now": 66,
            "circulation_fan2_rpm": 910,
            "rev_circfan2": 12,
        }
        state = CirculationFanStateAdapter(2).decode(raw)
        self.assertEqual((state.fan_id, state.revision), (2, 12))
        self.assertEqual((state.target_min, state.target_max, state.mode), (31, 77, "chao"))
        self.assertEqual((state.live_speed, state.rpm), (66, 910))

    def test_exhaust_collects_only_fan_state(self):
        state = ExhaustFanStateAdapter.decode({
            "rev_exhaust": 4,
            "exhaust_fan_min": 25,
            "exhaust_fan_pct": 80,
            "exhaust_fan_mode": "auto",
            "exhaust_fan": {"exhaust_fan_rpm": 1200},
        })
        self.assertEqual(state.revision, 4)
        self.assertEqual((state.target_min, state.target_max), (25, 80))
        self.assertEqual(state.rpm, 1200)
        self.assertFalse(hasattr(state, "climate"))
        self.assertFalse(hasattr(state, "night_reduction_enabled"))

    def test_climate_hub_owns_climate_night_reduction_and_phase(self):
        state = ClimateHubStateAdapter.decode({
            "rev_exhaust": 4,
            "target_temp_min": 21.5,
            "target_temp_max": 27.5,
            "target_humidity_min": 44,
            "target_humidity_max": 63,
            "target_vpd_min": 0.9,
            "target_vpd_max": 1.4,
            "exhaust_fan_night_reduction": False,
            "plant_phase": 2,
        })
        self.assertEqual(state.revision, 4)
        self.assertEqual((state.climate.temp_min, state.climate.vpd_max), (21.5, 1.4))
        self.assertFalse(state.night_reduction_enabled)
        self.assertEqual(state.plant_phase, 2)

    def test_light_adapter_normalizes_legacy_manual_mode(self):
        state = LightStateAdapter.decode({
            "rev_light": 3,
            "light_mode": "man",
            "light_target": 72,
            "l_start_h": 20,
            "l_start_m": 0,
            "l_dur": 480,
            "l_sunrise": 60,
            "l_sunset": 60,
        })
        self.assertEqual(state.schedule.mode, "manual")
        self.assertEqual(state.schedule.start_minute, 1200)

    def test_climate_profile_is_derived_from_target_values(self):
        self.assertEqual(match_profile(PROFILES["flowering"]), "flowering")


class LightScheduleTests(unittest.TestCase):
    def test_curve_wraps_over_midnight(self):
        schedule = LightSchedule(
            target_pct=80,
            start_minute=20 * 60,
            duration_minutes=8 * 60,
            sunrise_minutes=60,
            sunset_minutes=60,
        )
        self.assertEqual(schedule.intensity_at(12 * 60), 0)
        self.assertEqual(schedule.intensity_at(22 * 60), 80)
        self.assertEqual(schedule.intensity_at(2 * 60), 80)
        self.assertEqual(schedule.intensity_at(3 * 60 + 30), 40)
        self.assertEqual(len(schedule.curve()), 97)

    def test_normalization_clamps_schedule_boundaries(self):
        normalized = LightSchedule(
            target_pct=150,
            start_minute=1500,
            duration_minutes=0,
            sunrise_minutes=500,
            sunset_minutes=500,
        ).normalized()
        self.assertEqual(normalized.target_pct, 100)
        self.assertEqual(normalized.start_minute, 1425)
        self.assertEqual(normalized.duration_minutes, 15)
        self.assertEqual(normalized.sunrise_minutes, 15)
        self.assertEqual(normalized.sunset_minutes, 0)


if __name__ == "__main__":
    unittest.main()
