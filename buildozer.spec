[app]
title = ESPGrowcontroller
package.name = espgrowcontroller
package.domain = org.hackintosh1980

source.include_exts = py,kv,png,jpg,json,ttf,bin
include_patterns = garden/**/*
source.include_dirs = garden
source.dir = .

version = 1.1
package.version_code = 1

icon.filename = assets/logo.png
presplash.filename = assets/pre_splash.png
presplash.color = black

orientation = landscape
fullscreen = 1

android.add_assets = assets/fonts/fa-solid-900.ttf

# Alles der aktuellen p4a-Version überlassen
requirements = python3,setuptools,kivy,pyjnius,pillow,certifi,six,requests,kivy_garden.graph,zeroconf,ifaddr

android.add_src = src/main/java
services = ble_service:services/ble_service.py

android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,CHANGE_WIFI_MULTICAST_STATE,BLUETOOTH,BLUETOOTH_ADMIN,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,ACCESS_BACKGROUND_LOCATION,BLUETOOTH_SCAN,BLUETOOTH_CONNECT,BLUETOOTH_ADVERTISE,FOREGROUND_SERVICE,FOREGROUND_SERVICE_CONNECTED_DEVICE,POST_NOTIFICATIONS,WAKE_LOCK,REQUEST_IGNORE_BATTERY_OPTIMIZATIONS

android.api = 36
android.minapi = 29
android.ndk_api = 29

android.debug = True
android.archs = arm64-v8a

android.sdk_path = ~/.buildozer/android/platform/android-sdk
android.ndk_path = ~/.buildozer/android/platform/android-ndk-r25b

# p4a.source_dir bewusst NICHT setzen!
# Buildozer lädt automatisch die aktuelle python-for-android-Version.

p4a.build_threads = 6
p4a.extra_args = --allow-minsdk-ndkapi-mismatch

android.gradle_version = 8.0.2
android.build_tools_version = 34.0.0

android.logcat_filters = *:I python:D
