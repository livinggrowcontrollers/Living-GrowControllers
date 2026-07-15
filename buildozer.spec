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
requirements = python3,setuptools,kivy,pyjnius,pillow==9.5.0,certifi,six,kivy_garden.graph,zeroconf,ifaddr
# (list) Services to declare
android.add_src = src/main/java
services = ble_service:services/ble_service.py

android.permissions = INTERNET, ACCESS_NETWORK_STATE, ACCESS_WIFI_STATE, BLUETOOTH, BLUETOOTH_ADMIN, ACCESS_FINE_LOCATION, ACCESS_COARSE_LOCATION, BLUETOOTH_SCAN, BLUETOOTH_CONNECT, BLUETOOTH_ADVERTISE, FOREGROUND_SERVICE, FOREGROUND_SERVICE_CONNECTED_DEVICE, POST_NOTIFICATIONS, WAKE_LOCK, REQUEST_IGNORE_BATTERY_OPTIMIZATIONS

#android.manifest.application_attributes = android:usesCleartextTraffic="true"

android.api = 33
android.minapi = 29
android.ndk_api = 29
android.debug = True
android.archs = arm64-v8a

# --- HIER SIND DIE FIXES FÜR DIE ALLGEMEINGÜLTIGKEIT ---

# SDK und NDK Pfade auskommentieren! 
# Buildozer nutzt dann automatisch den Standardpfad des aktuellen Users (~/.buildozer/android/platform/...)
# android.sdk_path = 
# android.ndk_path = 

# Falls du eine ganz bestimmte NDK-Version erzwingen willst (r25b), übergibst du sie so:
android.ndk = 25b

# p4a.source_dir komplett auskommentieren, außer du arbeitest aktiv an einem eigenen Fork von python-for-android.
# Wenn auskommentiert, lädt Buildozer die passende Version automatisch in das User-Verzeichnis.
# p4a.source_dir = 

p4a.build_threads = 6
p4a.extra_args = --allow-minsdk-ndkapi-mismatch
android.gradle_version = 8.0.2
# android.build_tools_version = 34.0.0
android.logcat_filters = *:I python:D