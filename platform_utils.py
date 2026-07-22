# platform_utils.py
"""
Central platform helpers for the project.

Provides a single place to decide the running platform so
the rest of the codebase does not import `kivy.utils.platform`
directly.

The checks combine Kivy's platform hint (if available) with
`sys.platform` and a few environment heuristics for Android.
"""
import os
import sys

try:
    from kivy.utils import platform as _kivy_platform
except Exception:
    _kivy_platform = None


def _kivy():
    return _kivy_platform


def is_android() -> bool:
    if _kivy_platform == "android":
        return True
    # Some Python-for-Android environments expose ANDROID_ROOT
    if "ANDROID_ROOT" in os.environ:
        return True
    return False


def is_ios() -> bool:
    if _kivy_platform == "ios":
        return True
    # conservative fallback: iOS usually not running CPython here
    return False


def is_macos() -> bool:
    if _kivy_platform == "macosx":
        return True
    return sys.platform == "darwin"


def is_windows() -> bool:
    if _kivy_platform == "win":
        return True
    return sys.platform.startswith("win")


def is_linux() -> bool:
    if _kivy_platform == "linux":
        return True
    return sys.platform.startswith("linux") and not is_android()


def is_desktop() -> bool:
    return is_windows() or is_linux() or is_macos()


__all__ = [
    "is_android",
    "is_ios",
    "is_windows",
    "is_linux",
    "is_macos",
    "is_desktop",
]
