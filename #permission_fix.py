#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
permission_fix.py – Android Permission Helper 🌿
Fragt Bluetooth- und Standortrechte aktiv an, wenn sie fehlen.
© 2025 Dominik Rosenthal (Hackintosh1980)
"""

from platform_utils import is_android

def check_permissions():
    """Fordert auf Android fehlende Berechtigungen aktiv an."""
    if not is_android():
        return True  # Desktop: keine Abfrage nötig

    try:
        from android.permissions import request_permissions, check_permission, Permission

        perms = [
            Permission.BLUETOOTH,
            Permission.BLUETOOTH_ADMIN,
            Permission.BLUETOOTH_CONNECT,
            Permission.BLUETOOTH_SCAN,
            Permission.BLUETOOTH_ADVERTISE,  # <--- DAS IST DER KEY FÜR ANDROID 13!
            Permission.ACCESS_FINE_LOCATION,
            Permission.ACCESS_COARSE_LOCATION,
        ]

        missing = [p for p in perms if not check_permission(p)]
        if missing:
            print(f"⚠️ Fehlende Berechtigungen: {missing}")
            request_permissions(missing)
            return False
        else:
            print("✅ Alle Berechtigungen OK")
            return True

    except Exception as e:
        print(f"💥 Permission-Check-Fehler: {e}")
        return False
