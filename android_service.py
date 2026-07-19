"""Zentrale Aufloesung der von python-for-android erzeugten Service-Klasse."""

SERVICE_NAME = "ble_service"


def service_class_name(package_name, service_name=SERVICE_NAME):
    """Liefert z. B. ``org.example.app.ServiceBle_service``.

    Der Paketname kommt absichtlich aus dem Android-Kontext und nicht aus einer
    zweiten Konfigurationsdatei. Damit bleibt buildozer.spec die einzige Quelle
    fuer package.name und package.domain.
    """
    package_name = str(package_name or "").strip()
    if not package_name:
        raise RuntimeError("Android package name ist leer")
    if not service_name:
        raise RuntimeError("Service-Name ist leer")
    return f"{package_name}.Service{service_name.capitalize()}"


def load_service_class(context, autoclass_fn=None):
    """Loest die generierte Java-Serviceklasse fuer die installierte App auf."""
    if context is None:
        raise RuntimeError("Android context ist nicht verfuegbar")

    if autoclass_fn is None:
        from jnius import autoclass as autoclass_fn

    class_name = service_class_name(context.getPackageName())
    return autoclass_fn(class_name)

