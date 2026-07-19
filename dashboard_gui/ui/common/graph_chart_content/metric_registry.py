"""Config-driven appearance for dashboard and fullscreen metrics.

Theme definitions live in ``data/themes/*.json``.  The registry keeps the
existing ``MetricRegistry.get(metric_id)`` API so widgets stay independent of
the loading mechanism.
"""

from copy import deepcopy
import json
from pathlib import Path

import config


class MetricRegistry:
    DEFAULT_STYLE = {
        "sz_val": 26,
        "sz_name": 16,
        "sz_unit": 16,
        "sz_trend": 20,
        "color_sub": "#bbbbbb",
        "decimals": 2,
    }
    FALLBACK_COLOR = [1, 1, 1, 1]
    LEGACY_THEME_ALIASES = {"tiles": "standard", "tiles2": "blossom", "tiles3": "aurora"}

    _loaded_theme = None
    _theme_data = None

    @classmethod
    def theme_directory(cls):
        return Path(config.DATA) / "themes"

    @classmethod
    def available_themes(cls):
        """Return selectable JSON themes, with standard always available."""
        directory = cls.theme_directory()
        names = {"standard"}
        if directory.exists():
            names.update(path.stem for path in directory.glob("*.json"))
        return tuple(sorted(names))

    @classmethod
    def normalize_theme(cls, theme):
        theme = cls.LEGACY_THEME_ALIASES.get(str(theme or ""), str(theme or ""))
        return theme if theme in cls.available_themes() else "standard"

    @classmethod
    def reload(cls):
        """Drop the cached JSON. The next get() reads the active theme."""
        cls._loaded_theme = None
        cls._theme_data = None

    @classmethod
    def _read_theme(cls, theme_name, visited=None):
        visited = set() if visited is None else visited
        if theme_name in visited:
            raise ValueError(f"Theme inheritance loop: {theme_name}")
        visited.add(theme_name)

        path = cls.theme_directory() / f"{theme_name}.json"
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError(f"Theme '{theme_name}' must be a JSON object")

        parent_name = data.get("extends")
        parent = cls._read_theme(parent_name, visited) if parent_name else {}
        return cls._merge_theme(parent, data)

    @staticmethod
    def _merge_theme(parent, child):
        def merge(left, right):
            result = deepcopy(left)
            for key, value in right.items():
                if isinstance(value, dict) and isinstance(result.get(key), dict):
                    result[key] = merge(result[key], value)
                else:
                    result[key] = deepcopy(value)
            return result

        return merge(parent, child)

    @classmethod
    def _active_data(cls):
        theme = cls.normalize_theme(config.get_theme())
        if cls._theme_data is not None and cls._loaded_theme == theme:
            return cls._theme_data

        try:
            data = cls._read_theme(theme)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            print(f"[MetricRegistry] Theme '{theme}' unavailable: {error}; using standard")
            data = cls._read_theme("standard")
            theme = "standard"

        cls._loaded_theme = theme
        cls._theme_data = data
        return data

    @classmethod
    def get(cls, key):
        data = cls._active_data()
        metric = data.get("metrics", {}).get(key, {})
        color_name = metric.get("color")
        base_color = data.get("colors", {}).get(color_name, cls.FALLBACK_COLOR)
        if not isinstance(base_color, list) or len(base_color) != 4:
            base_color = cls.FALLBACK_COLOR

        style = {
            **cls.DEFAULT_STYLE,
            **data.get("default_style", {}),
            **metric.get("style", {}),
        }
        return {
            "name": metric.get("name", key.replace("_", " ").title()),
            "unit": metric.get("unit", ""),
            "color": list(base_color),
            "glow": [*base_color[:3], 0.28],
            "style": style,
        }

    @classmethod
    def presentation(cls, surface):
        """Return the global visual roles for ``tile`` or ``fullscreen``."""
        presentation = cls._active_data().get("presentation", {})
        return deepcopy(presentation.get(surface, {}))
