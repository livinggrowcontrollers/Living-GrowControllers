# -*- coding: utf-8 -*-
"""
I18N Helper – zentrale Übersetzungen
© 2026 Dominik Rosenthal (Hackintosh1980)
"""

import config

class I18N:
    _lang = "en"

    _translations = {
        "en": {
            # Settings
            "settings.title": "Settings",
            "settings.temperature_unit": "Temperature Unit",
            "settings.language": "Language",
            "settings.refresh_interval": "Refresh Interval",
            "settings.graph_resolution": "Graph Resolution",   
            "settings.graph_smoothing_factor": "Graph Smoothing Factor",
            "settings.stale_timeout": "Stale Timeout",
            "settings.tile_graph_window": "Graph Window (samples)",
            "settings.temp_offset": "Temp Offset",
            "settings.humidity_offset": "Humidity Offset",
            "settings.leaf_offset": "Leaf Offset",
            "settings.reset_defaults": "Reset Defaults",
            "settings.save": "Save",
            "settings.cancel": "Cancel",

            "menu.sensor_mixed_mode": "Sensor Mix",
            # ControlButtons
            "control.start": "Start",
            "control.stop": "Stop",
            "control.reset": "Reset",

            # Window Picker
            "menu.vpd_scatter": "VPD Scatter",
            "menu.setup": "Setup",
            "menu.settings": "Settings",
            "menu.debug": "Debug",
            "menu.csv": "CSV Viewer",
            "menu.camera": "Camera",
            "menu.devices": "Devices",
            "menu.about": "About",
            "menu.grow_controller": "Grow-Controller",
            "menu.plant_planner": "Plant Planner",
            "menu.grow_overview": "Grow-Overview",
            "menu.dashboard": "Dashboard",
            
            
            # --- About Screen ---
            # --- About Screen (EN) ---
            "about.version": "LGS Grow Master S3 v2.0",
            "about.description": (
                "LivingGrowSensors (LGS) is a hybrid ecosystem for monitoring and controlling "
                "cultivation environments.\n\n"
                "The system combines precise Bluetooth sensing (ADV/GATT) with active hardware control "
                "via the LGS Grow Master S3. Thanks to the integrated network stack, the controller "
                "seamlessly switches between AP and Router mode (STA).\n\n"
                "A key highlight is the 'Target Revision Law': UI and hardware operate "
                "asynchronously and only acknowledge commands after a successful match (Revision Sync). "
                "This ensures absolute stability without volatile command errors.\n\n"
                "The focus is on transparency and explicit control over lighting, exhaust, and "
                "circulation fans — with no hidden automations. Sensors are processed efficiently "
                "using pseudo-values to save space in communication packages.\n\n"
                "Bluetooth and WiFi are required to read sensors and manage the controller. "
                "Please grant the requested permissions."
            ),
            # EN
            "about.repo_url": "https://github.com/Hackintosh1980/AI-Dashboard",
            "about.repo_text": "Project & Updates:",
            "about.community_text": "Community & Grow Talk:",
            "about.community_url": "https://www.facebook.com/groups/896803673081754",
            "about.community_name": "OpenGrowController Community ",
            "about.coffee_url": "https://buymeacoffee.com/livinggrowcontrollers",
            "about.coffee_text": "Buy Me a Coffee:",
            "about.coffee_name": "Support the Project",
            "about.email_text": "[font=FA]\uf0e0[/font] Contact Email:",
            "about.email_address": "living.grow.controllers@gmail.com",
            "about.copyright": "© 2026 Dominik Rosenthal (Hackintosh1980)",
        },

        "es": {
            # Settings
            "settings.title": "Ajustes",
            "settings.temperature_unit": "Unidad de temperatura",
            "settings.language": "Idioma",
            "settings.refresh_interval": "Intervalo de actualización",
            "settings.graph_resolution": "Resolución del gráfico",
            "settings.tile_graph_window": "Ventana del gráfico (muestras)",
            "settings.temp_offset": "Offset de temperatura",
            "settings.humidity_offset": "Offset de humedad",
            "settings.leaf_offset": "Offset de hoja",
            "settings.reset_defaults": "Restablecer valores",
            "settings.save": "Guardar",
            "settings.cancel": "Cancelar",
            "settings.reset_defaults": "Restablecer valores predeterminados",
            "settings.graph_resolution": "Resolución del gráfico",
            "settings.stale_timeout": "Tiempo de espera de inactividad",
            "settings.tile_graph_window": "Ventana del gráfico (muestras)",
            "settings.graph_smoothing_factor": "Factor de suavizado del gráfico",
            
            "menu.sensor_mixed_mode": "Mezcla Sensor",
            # ControlButtons
            "control.start": "Iniciar",
            "control.stop": "Detener",
            "control.reset": "Restablecer",

            # Window Picker
            "menu.vpd_scatter": "Dispersión VPD",
            "menu.setup": "Configuración",
            "menu.settings": "Ajustes",
            "menu.debug": "Depuración",
            "menu.csv": "Visor CSV",
            "menu.camera": "Cámara",
            "menu.devices": "Dispositivos",
            "menu.about": "Acerca de",
            "menu.grow_controller": "Grow-Controller",
            "menu.plant_planner": "Plant Planner",
            "menu.grow_overview": "Resumen de Cultivo",
            "menu.dashboard": "Dashboard",
            

            # --- About Screen (ES) ---
            "about.version": "LGS Grow Master S3 v2.0",
            "about.description": (
                "LivingGrowSensors (LGS) es un ecosistema híbrido para el monitoreo y control "
                "de entornos de cultivo.\n\n"
                "El sistema combina sensores Bluetooth de precisión (ADV/GATT) con el control activo "
                "del hardware mediante el LGS Grow Master S3. Gracias a su stack de red integrado, "
                "el controlador cambia fluidamente entre el modo AP y el modo Router (STA).\n\n"
                "Un aspecto destacado es la 'Ley de Revisión de Objetivo': la interfaz y el hardware "
                "operan de forma asíncrona y solo confirman los comandos tras una sincronización exitosa "
                "(Revision Sync). Esto garantiza una estabilidad absoluta sin errores de comandos volátiles.\n\n"
                "El enfoque se centra en la transparencia y el control explícito de la iluminación, la "
                "extracción y la recirculación de aire, sin automatismos ocultos. Los sensores se procesan "
                "eficientemente mediante pseudo-valores para optimizar el espacio.\n\n"
                "Se requiere Bluetooth y WiFi para leer los sensores y gestionar el controlador. "
                "Por favor, conceda los permisos solicitados."
            ),
            
            # ES
            "about.repo_url": "https://github.com/Hackintosh1980/AI-Dashboard",
            "about.repo_text": "Proyecto y actualizaciones:",
            "about.community_text": "Comunidad y charla Grow:",
            "about.community_url": "https://www.facebook.com/groups/896803673081754",
            "about.community_name": "OpenGrowController Community ",
            "about.coffee_url": "https://buymeacoffee.com/livinggrowcontrollers",
            "about.coffee_text": "Buy Me a Coffee:",
            "about.coffee_name": "Support the Project",
            "about.email_text": "[font=FA]\uf0e0[/font] Contact Email:",
            "about.email_address": "living.grow.controllers@gmail.com",
            "about.copyright": "© 2026 Dominik Rosenthal (Hackintosh1980)",
        },

        "de": {
            # Settings
            "settings.title": "Einstellungen",
            "settings.temperature_unit": "Temperatureinheit",
            "settings.language": "Sprache",
            "settings.refresh_interval": "Aktualisierungsintervall",
            "settings.tile_graph_window": "Graph Window (samples)",
            "settings.graph_resolution": "Graph-Auflösung",
            "settings.graph_smoothing_factor": "Graph-Smoothing-Faktor",
            "settings.stale_timeout": "Inaktivitäts-Timeout",
            "settings.tile_graph_window": "Graph-Fenster (Samples)",
            "settings.temp_offset": "Temperatur-Korrektur",
            "settings.humidity_offset": "Feuchtigkeit-Korrektur",
            "settings.leaf_offset": "Blatt-Korrektur",
            "settings.reset_defaults": "Standardwerte zurücksetzen",
            "settings.save": "Speichern",
            "settings.cancel": "Abbrechen",

            "menu.sensor_mixed_mode": "Sensor Mix",
            # ControlButtons
            "control.start": "Start",
            "control.stop": "Stopp",
            "control.reset": "Zurücksetzen",

            # Window Picker
            "menu.vpd_scatter": "VPD-Diagramm",
            "menu.setup": "Setup",
            "menu.settings": "Einstellungen",
            "menu.debug": "Debug",
            "menu.csv": "CSV-Viewer",
            "menu.camera": "Kamera",
            "menu.devices": "Geräte",
            "menu.about": "Über",
            "menu.grow_controller": "Grow-Controller",
            "menu.plant_planner": "Pflanzen-Planer",
            "menu.grow_overview": "Grow-Übersicht",
            
            "menu.dashboard": "Dashboard",
            # --- About Screen ---
            # --- About Screen ---
            "about.version": "LGS Grow Master S3 v2.0",
            "about.description": (
                "LivingGrowSensors (LGS) ist ein hybrides Ökosystem zur Überwachung und Steuerung "
                "von Grow-Umgebungen.\n\n"
                "Das System vereint präzise Bluetooth-Sensorik (ADV/GATT) mit aktiver Hardware-Steuerung "
                "über den LGS Grow Master S3. Durch den integrierten Netzwerk-Stack wechselt der Controller "
                "nahtlos zwischen AP- und Router-Mode (STA).\n\n"
                "Ein zentrales Highlight ist das 'Target-Revision-Gesetz': UI und Hardware arbeiten "
                "asynchron und quittieren Befehle erst nach erfolgreichem Abgleich (Revision-Sync). "
                "Das garantiert absolute Stabilität ohne flüchtige Fehlkommandos.\n\n"
                "Fokus liegt auf Transparenz und expliziter Kontrolle über Licht, Abluft und Umluft — "
                "ganz ohne versteckte Automatismen. Sensoren werden durch Pseudo-Values platzsparend "
                "und effizient im System verarbeitet.\n\n"
                "Bluetooth und WiFi sind erforderlich, um Sensoren auszulesen und den Controller zu steuern. "
                "Bitte gewähre die angeforderten Berechtigungen."
            ),
                # DE
            "about.repo_url": "https://github.com/Hackintosh1980/AI-Dashboard",
            "about.repo_text": "Projekt & Updates:",
            "about.community_text": "Community & Grow Talk:",
            "about.community_url": "https://www.facebook.com/groups/896803673081754",
            "about.community_name": "OpenGrowController Community ",
            "about.coffee_url": "https://buymeacoffee.com/livinggrowcontrollers",
            "about.coffee_text": "Buy Me a Coffee:",
            "about.coffee_name": "Support the Project",
            
            "about.email_text": "[font=FA]\uf0e0[/font] Contact Email:",
            "about.email_address": "living.grow.controllers@gmail.com",
            "about.copyright": "© 2026 Dominik Rosenthal (Hackintosh1980)", 
        }
    }

    @classmethod
    def init(cls):
        cfg = config._init()
        cls._lang = cfg.get("language", "en")

    @classmethod
    def set_language(cls, lang: str):
        if lang in cls._translations:
            cls._lang = lang

    @classmethod
    def t(cls, key: str, **kwargs):
        text = cls._translations.get(cls._lang, {}).get(key, key)
        if kwargs:
            return text.format(**kwargs)
        return text
