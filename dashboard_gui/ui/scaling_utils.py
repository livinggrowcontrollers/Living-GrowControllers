# 🔥 GANZ OBEN – vor ALLEM
from kivy.config import Config

Config.set('graphics', 'position', 'custom')
Config.set('graphics', 'left', '0')
Config.set('graphics', 'top', '0')


# 👉 DANACH erst Imports
import sys
from kivy.core.window import Window
from platform_utils import is_android, is_ios
from kivy.metrics import dp, sp


# --- FENSTER SETUP ---
if not (is_android() or is_ios()):
    Window.size = (1440, 700)

    # 👉 ZENTRIERUNG (JETZT FUNKTIONIERT ES AUCH)
    screen_width, screen_height = Window.system_size

    Window.left = (screen_width - Window.width) // 2
    Window.top = (screen_height - Window.height) // 2

def compute_ui_scale():
    w, h = Window.size
    dpi = Window.dpi if Window.dpi and Window.dpi > 100 else 160
    short_side = min(w, h)
    long_side = max(w, h)
    
    # 0. Sicherheitscheck: Desktop / Tablet Umgebungen
    if not (is_android() or is_ios()):
        # Hier stellen wir exakt dein originales Skalierungsverhalten wieder her,
        # damit das Bild und die Elemente NICHT künstlich aufgebläht werden.
        # Unabhängig von Window.size bleibt die Basis fest auf 1400.
        return 1.15 * max(0.95, min(w / 1400.0, 1.10))

    # 1. High-Res / High-DPI Schutz (Handys)
    if short_side >= 1080 or dpi > 350:
        return 0.58 

    # 2. Dynamische Ratio-Korrektur
    aspect = long_side / short_side
    base_geom = short_side / 720.0
    density_boost = max(1.0, min(400.0 / dpi, 1.10))
    raw_scale = base_geom * density_boost
    
    if aspect > 2.1:
        return min(raw_scale, 0.72)
    elif aspect > 1.9:
        return min(raw_scale, 0.82)
    
    return raw_scale * 0.78

# 🔥 GLOBAL SCALE
UI_SCALE = compute_ui_scale()



UI_SCALE = compute_ui_scale()


def get_effective_width():
    w, h = Window.size
    short_side = min(w, h)
    return short_side / 1.5 if short_side > 900 else short_side


def dp_scaled(v: float) -> float:
    return dp(v * UI_SCALE)

def sp_scaled(v: float) -> float:
    return sp(v * UI_SCALE)