[app]
title = ESPGrowcontroller
package.name = espgrowcontroller
package.domain = org.hackintosh1980
#####undbedingt ble service.py abndern bei namensnderung!und ja keine binde und unterstriche verwenden!

source.include_exts = py,kv,png,jpg,json,ttf,bin
include_patterns = garden/**/*
source.include_dirs = garden
source.dir = .

version = 1.1
package.version_code = 1
icon.filename = assets/logo.png
presplash.filename = assets/pre_splash.png
#presplash.keep_ratio = True
presplash.color = black
orientation = landscape
fullscreen = 1

# Nur Font Awesome Solid soll eingebunden werden
android.add_assets = assets/fonts/fa-solid-900.ttf

# Python fest auf 3.11 pinnen, damit das System nicht eigenmächtig auf 3.14 springt
requirements = python3==3.11.9,setuptools,kivy,pyjnius,pillow==9.5.0,certifi,six,kivy_garden.graph,zeroconf,ifaddr

# (list) Services to declare
android.add_src = src/main/java
services = ble_service:services/ble_service.py

android.permissions = INTERNET, ACCESS_NETWORK_STATE, ACCESS_WIFI_STATE, BLUETOOTH, BLUETOOTH_ADMIN, ACCESS_FINE_LOCATION, ACCESS_COARSE_LOCATION, ACCESS_BACKGROUND_LOCATION, BLUETOOTH_SCAN, BLUETOOTH_CONNECT, BLUETOOTH_ADVERTISE, FOREGROUND_SERVICE, FOREGROUND_SERVICE_CONNECTED_DEVICE, POST_NOTIFICATIONS, WAKE_LOCK, REQUEST_IGNORE_BATTERY_OPTIMIZATIONS

#android.manifest.application_attributes = android:usesCleartextTraffic="true"

android.api = 33
android.minapi = 29
android.ndk_api = 29
android.debug = True
android.archs = arm64-v8a

# --- GENERISCHE PFADE (AKTIVIERTE ORIGINALE PFADE) ---
android.sdk_path = ~/.buildozer/android/platform/android-sdk
android.ndk_path = ~/.buildozer/android/platform/android-ndk-r25b

# Hier ist dein echtes p4a-Verzeichnis – gerettet und nutzerunabhängig gemacht!
p4a.source_dir = ~/python-for-android

p4a.build_threads = 6
p4a.extra_args = --allow-minsdk-ndkapi-mismatch
android.gradle_version = 8.0.2
android.build_tools_version = 34.0.0
android.logcat_filters = *:I python:D
