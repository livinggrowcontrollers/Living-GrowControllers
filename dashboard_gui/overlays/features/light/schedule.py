# dashboard_gui/overlays/features/light/schedule.py

from dataclasses import dataclass, replace


def _clamp(value, lower, upper):
    return max(lower, min(upper, value))


@dataclass(frozen=True)
class LightSchedule:
    mode: str = "time"
    target_pct: int = 0
    start_minute: int = 8 * 60
    duration_minutes: int = 12 * 60
    sunrise_minutes: int = 60
    sunset_minutes: int = 60
    climate_override: bool = False

    def normalized(self):
        duration = int(_clamp(round(self.duration_minutes / 15) * 15, 15, 1440))
        sunrise = int(_clamp(round(self.sunrise_minutes / 15) * 15, 15, duration))
        sunset = int(_clamp(round(self.sunset_minutes / 15) * 15, 0, duration - sunrise))
        mode = "manual" if self.mode == "man" else self.mode
        return replace(
            self,
            mode=mode,
            target_pct=int(_clamp(self.target_pct, 0, 100)),
            start_minute=int(_clamp(round(self.start_minute / 15) * 15, 0, 1425)),
            duration_minutes=duration,
            sunrise_minutes=sunrise,
            sunset_minutes=sunset,
            climate_override=bool(self.climate_override),
        )

    def intensity_at(self, minute_of_day):
        schedule = self.normalized()
        relative = (int(minute_of_day) - schedule.start_minute) % 1440
        if relative > schedule.duration_minutes:
            return 0.0
        if relative < schedule.sunrise_minutes:
            return schedule.target_pct * relative / schedule.sunrise_minutes
        sunset_start = schedule.duration_minutes - schedule.sunset_minutes
        if schedule.sunset_minutes and relative > sunset_start:
            return schedule.target_pct * (schedule.duration_minutes - relative) / schedule.sunset_minutes
        return float(schedule.target_pct)

    def curve(self, steps=96):
        return [
            (step / steps, self.intensity_at(1440 if step == steps else step * 1440 / steps))
            for step in range(steps + 1)
        ]
