"""Android-Startfreigabe fuer BLE und Foreground-Service.

Die sichtbare Activity besitzt diesen Ablauf. Der Service selbst fordert keine
Berechtigungen an, sondern wird erst gestartet, nachdem alle fuer die jeweilige
Android-Version notwendigen Freigaben und Systemschalter bereit sind.
"""

from platform_utils import is_android


ANDROID_10 = 29
ANDROID_11 = 30
ANDROID_12 = 31
ANDROID_13 = 33

ACCESS_FINE_LOCATION = "android.permission.ACCESS_FINE_LOCATION"
ACCESS_COARSE_LOCATION = "android.permission.ACCESS_COARSE_LOCATION"
ACCESS_BACKGROUND_LOCATION = "android.permission.ACCESS_BACKGROUND_LOCATION"
BLUETOOTH_SCAN = "android.permission.BLUETOOTH_SCAN"
BLUETOOTH_CONNECT = "android.permission.BLUETOOTH_CONNECT"
BLUETOOTH_ADVERTISE = "android.permission.BLUETOOTH_ADVERTISE"
POST_NOTIFICATIONS = "android.permission.POST_NOTIFICATIONS"


def permission_stages_for_sdk(sdk_int):
    """Liefert die nacheinander anzufragenden Runtime-Permission-Gruppen."""
    if sdk_int <= ANDROID_11:
        stages = [(ACCESS_FINE_LOCATION,)]
    else:
        stages = [
            (BLUETOOTH_SCAN, BLUETOOTH_CONNECT, BLUETOOTH_ADVERTISE),
            # Android 12+ verlangt COARSE und FINE gemeinsam in einer Anfrage.
            # FINE bleibt notwendig, weil unsere Rohdaten/RSSI-Auswertung nicht
            # als ``neverForLocation`` deklariert werden darf.
            (ACCESS_COARSE_LOCATION, ACCESS_FINE_LOCATION),
        ]

    if sdk_int >= ANDROID_13:
        # Die Notification bleibt absichtlich ein eigener Android-Dialog.
        stages.append((POST_NOTIFICATIONS,))

    return tuple(stages)


def requires_background_location(sdk_int):
    """Android 10/11 brauchen dies fuer BLE-Suche aus einem Dauerservice."""
    return ANDROID_10 <= sdk_int <= ANDROID_11


class AndroidPermissionGate:
    """Asynchrones, versionsabhaengiges Starttor fuer den Android-Core."""

    def __init__(self):
        self._on_ready = None
        self._request_in_flight = False
        self._last_requested_permissions = ()
        self._popup = None
        self._battery_prompt_scheduled = False

    def ensure(self, on_ready):
        """Prueft alles und ruft ``on_ready`` erst bei echter Startfreigabe."""
        self._on_ready = on_ready

        if not is_android():
            self._dispatch_ready()
            return

        if self._request_in_flight:
            print("[PermissionFix] Android-Dialog laeuft bereits")
            return

        self._advance()

    def is_ready(self):
        """Seiteneffektfreie Zustandspruefung fuer den App-Lifecycle."""
        if not is_android():
            return True

        try:
            sdk_int = self._sdk_int()
            for stage in permission_stages_for_sdk(sdk_int):
                if self._missing_permissions(stage):
                    return False

            if requires_background_location(sdk_int):
                if self._missing_permissions((ACCESS_BACKGROUND_LOCATION,)):
                    return False

            if not self._location_enabled():
                return False

            return self._bluetooth_enabled()
        except Exception as exc:
            print(f"[PermissionFix] Zustandspruefung fehlgeschlagen: {exc}")
            return False

    def _advance(self):
        try:
            sdk_int = self._sdk_int()
            print(f"[PermissionFix] Pruefe Android SDK {sdk_int}")

            for stage in permission_stages_for_sdk(sdk_int):
                missing = self._missing_permissions(stage)
                if missing:
                    self._request_permissions(missing)
                    return

            if requires_background_location(sdk_int):
                missing_background = self._missing_permissions(
                    (ACCESS_BACKGROUND_LOCATION,)
                )
                if missing_background:
                    if sdk_int == ANDROID_10:
                        self._request_permissions(missing_background)
                    else:
                        self._show_blocker("background_location")
                    return

            if not self._bluetooth_enabled():
                self._show_blocker("bluetooth_off")
                return

            if not self._location_enabled():
                self._show_blocker("location_off")
                return

            self._dismiss_popup()
            print("[PermissionFix] Alle Android-Startbedingungen erfuellt")
            self._dispatch_ready()

        except Exception as exc:
            print(f"[PermissionFix] Pruefung fehlgeschlagen: {exc}")
            self._show_blocker("internal_error", str(exc))

    def _request_permissions(self, permissions):
        from android.permissions import request_permissions

        self._dismiss_popup()
        self._request_in_flight = True
        self._last_requested_permissions = tuple(permissions)
        print(f"[PermissionFix] Fordere an: {list(permissions)}")

        try:
            request_permissions(list(permissions), self._on_permission_result)
        except Exception:
            self._request_in_flight = False
            raise

    def _on_permission_result(self, permissions, grant_results):
        self._request_in_flight = False
        result = dict(zip(permissions, grant_results))
        print(f"[PermissionFix] Android-Ergebnis: {result}")

        # Das echte Ergebnis wird erneut ueber check_permission gelesen. Dadurch
        # bleiben auch leere oder herstellerspezifisch verzoegerte Callbacks sicher.
        self._schedule(self._continue_after_permission_result, 0.12)

    def _continue_after_permission_result(self):
        missing = self._missing_permissions(self._last_requested_permissions)
        if missing:
            if POST_NOTIFICATIONS in missing:
                reason = "notification_denied"
            elif ACCESS_BACKGROUND_LOCATION in missing:
                reason = "background_location_denied"
            elif ACCESS_FINE_LOCATION in missing:
                reason = "location_permission_denied"
            else:
                reason = "permission_denied"
            self._show_blocker(reason)
            return

        self._advance()

    def _missing_permissions(self, permissions):
        from android.permissions import check_permission

        return [permission for permission in permissions if not check_permission(permission)]

    @staticmethod
    def _sdk_int():
        from jnius import autoclass

        version = autoclass("android.os.Build$VERSION")
        return int(version.SDK_INT)

    @staticmethod
    def _activity():
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        if activity is None:
            raise RuntimeError("PythonActivity.mActivity ist nicht verfuegbar")
        return activity

    def _bluetooth_enabled(self):
        from jnius import autoclass

        adapter = autoclass("android.bluetooth.BluetoothAdapter").getDefaultAdapter()
        if adapter is None:
            raise RuntimeError("Dieses Geraet besitzt keinen Bluetooth-Adapter")
        return bool(adapter.isEnabled())

    def _location_enabled(self):
        from jnius import autoclass

        Context = autoclass("android.content.Context")
        manager = self._activity().getSystemService(Context.LOCATION_SERVICE)
        return bool(manager and manager.isLocationEnabled())

    def _show_blocker(self, reason, detail=""):
        if self._popup is not None:
            return

        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button
        from kivy.uix.label import Label
        from kivy.uix.popup import Popup

        messages = {
            "permission_denied": (
                "Bluetooth-Berechtigung erforderlich",
                "Bitte erlaube die angeforderten Android-Berechtigungen. "
                "Danach startet BLE automatisch – ein App-Neustart ist nicht noetig.",
                "Erneut anfragen",
                self._advance,
                "App-Einstellungen",
                self._open_app_settings,
            ),
            "notification_denied": (
                "Benachrichtigung erforderlich",
                "Android 13 benoetigt diese Freigabe fuer die sichtbare "
                "Foreground-Service-Benachrichtigung.",
                "Erneut anfragen",
                self._advance,
                "App-Einstellungen",
                self._open_app_settings,
            ),
            "background_location_denied": (
                "Hintergrundzugriff erforderlich",
                "Android 10 benoetigt fuer die dauerhafte BLE-Suche die "
                "Standortoption ‚Immer zulassen‘.",
                "Erneut anfragen",
                self._advance,
                "App-Einstellungen",
                self._open_app_settings,
            ),
            "location_permission_denied": (
                "Praeziser Standort erforderlich",
                "Bitte aktiviere im Standortdialog ‚Genauer Standort‘ und erlaube "
                "den Zugriff waehrend der App-Nutzung. Danach startet BLE automatisch.",
                "Erneut anfragen",
                self._advance,
                "App-Einstellungen",
                self._open_app_settings,
            ),
            "background_location": (
                "Android 11: Hintergrundzugriff",
                "Fuer die dauerhafte BLE-Suche muss Standort in den "
                "App-Berechtigungen auf ‚Immer zulassen‘ stehen.",
                "App-Einstellungen",
                self._open_app_settings,
                "Erneut pruefen",
                self._advance,
            ),
            "bluetooth_off": (
                "Bluetooth ist ausgeschaltet",
                "Bitte schalte Bluetooth ein. Danach startet der BLE-Core automatisch.",
                "Bluetooth einschalten",
                self._open_bluetooth_enable,
                "App-Einstellungen",
                self._open_app_settings,
            ),
            "location_off": (
                "Standortdienst ist ausgeschaltet",
                "Android benoetigt den aktiven Standortdienst fuer zuverlaessige BLE-Scans.",
                "Standort einschalten",
                self._open_location_settings,
                "App-Einstellungen",
                self._open_app_settings,
            ),
            "internal_error": (
                "Android-Freigabe fehlgeschlagen",
                "Die Startbedingungen konnten nicht geprueft werden. " + detail,
                "Erneut pruefen",
                self._advance,
                "App-Einstellungen",
                self._open_app_settings,
            ),
        }
        (
            title,
            message,
            primary_text,
            primary_action,
            secondary_text,
            secondary_action,
        ) = messages[reason]

        content = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(16))
        label = Label(text=message, halign="center", valign="middle")
        label.bind(size=lambda widget, size: setattr(widget, "text_size", size))
        content.add_widget(label)

        buttons = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        secondary = Button(text=secondary_text)
        primary = Button(text=primary_text)
        buttons.add_widget(secondary)
        buttons.add_widget(primary)
        content.add_widget(buttons)

        popup = Popup(
            title=title,
            content=content,
            size_hint=(0.82, 0.72),
            auto_dismiss=False,
        )
        self._popup = popup

        def run(action):
            popup.dismiss()
            self._popup = None
            self._schedule(action, 0.05)

        primary.bind(on_release=lambda *_args: run(primary_action))
        secondary.bind(on_release=lambda *_args: run(secondary_action))
        popup.open()

    def _dismiss_popup(self):
        popup = self._popup
        self._popup = None
        if popup is not None:
            popup.dismiss()

    def _open_app_settings(self):
        from jnius import autoclass

        Intent = autoclass("android.content.Intent")
        Settings = autoclass("android.provider.Settings")
        Uri = autoclass("android.net.Uri")
        activity = self._activity()
        intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
        intent.setData(Uri.parse("package:" + activity.getPackageName()))
        activity.startActivity(intent)

    def _open_bluetooth_enable(self):
        from jnius import autoclass

        Intent = autoclass("android.content.Intent")
        BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")
        intent = Intent(BluetoothAdapter.ACTION_REQUEST_ENABLE)
        self._activity().startActivityForResult(intent, 9102)

    def _open_location_settings(self):
        from jnius import autoclass

        Intent = autoclass("android.content.Intent")
        Settings = autoclass("android.provider.Settings")
        self._activity().startActivity(Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS))

    def offer_battery_optimization_exemption_once(self):
        """Bietet die optionale Akku-Ausnahme einmalig nach dem Core-Start an."""
        if not is_android() or self._battery_prompt_scheduled:
            return

        self._battery_prompt_scheduled = True
        self._schedule(self._offer_battery_optimization_exemption, 0.45)

    def _offer_battery_optimization_exemption(self):
        try:
            from jnius import autoclass

            Context = autoclass("android.content.Context")
            Intent = autoclass("android.content.Intent")
            Settings = autoclass("android.provider.Settings")
            Uri = autoclass("android.net.Uri")

            activity = self._activity()
            preferences = activity.getSharedPreferences(
                "permission_fix", Context.MODE_PRIVATE
            )
            if preferences.getBoolean("battery_prompt_shown", False):
                return

            power_manager = activity.getSystemService(Context.POWER_SERVICE)
            package_name = activity.getPackageName()
            if power_manager.isIgnoringBatteryOptimizations(package_name):
                preferences.edit().putBoolean("battery_prompt_shown", True).apply()
                print("[PermissionFix] Akkuoptimierung bereits freigegeben")
                return

            intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
            intent.setData(Uri.parse("package:" + package_name))
            activity.startActivity(intent)
            preferences.edit().putBoolean("battery_prompt_shown", True).apply()
            print("[PermissionFix] Optionale Akku-Ausnahme angeboten")
        except Exception as exc:
            # Bei einem OEM ohne diesen Dialog darf der BLE-Core weiterlaufen.
            self._battery_prompt_scheduled = False
            print(f"[PermissionFix] Akku-Ausnahme nicht verfuegbar: {exc}")

    def _dispatch_ready(self):
        callback = self._on_ready
        if callback is not None:
            callback()

    @staticmethod
    def _schedule(callback, delay):
        from kivy.clock import Clock

        Clock.schedule_once(lambda _dt: callback(), delay)


_PERMISSION_GATE = AndroidPermissionGate()


def ensure_permissions(on_ready):
    """Oeffentlicher Einstieg fuer den Activity-gesteuerten Startablauf."""
    _PERMISSION_GATE.ensure(on_ready)


def startup_requirements_ready():
    """Prueft, ob ein bereits laufender Core weiterlaufen darf."""
    return _PERMISSION_GATE.is_ready()


def offer_battery_optimization_exemption_once():
    """Startet die optionale, nicht blockierende Foreground-Service-Stufe."""
    _PERMISSION_GATE.offer_battery_optimization_exemption_once()
