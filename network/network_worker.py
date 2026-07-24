from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass, field
import threading
import time
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter

import config
import network.client_storage
from platform_utils import is_android


_SESSION_RESET_ERRORS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.ContentDecodingError,
    requests.exceptions.ReadTimeout,
    requests.exceptions.SSLError,
)
_FAILURE_LOG_LIMIT = 128
_FAILURE_LOG_INTERVAL = 15.0
_failure_log_lock = threading.Lock()
_failure_log_state = OrderedDict()
_config_update_lock = threading.Lock()


@dataclass
class _SessionHandle:
    session: requests.Session
    lock: threading.Lock = field(default_factory=threading.Lock)


class PersistentHTTPTransport:
    """Besitzt wiederverwendbare, pro Gerät serialisierte HTTP-Sessions."""

    def __init__(self, session_factory=requests.Session):
        self._session_factory = session_factory
        self._handles = {}
        self._lock = threading.RLock()
        self._closed = False

    def _create_handle(self):
        session = self._session_factory()
        session.headers.update({"Accept": "application/json"})
        adapter = HTTPAdapter(
            pool_connections=1,
            pool_maxsize=2,
            max_retries=0,
            pool_block=True,
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return _SessionHandle(session=session)

    def _get_handle(self, key):
        with self._lock:
            if self._closed:
                raise RuntimeError("HTTP-Transport ist bereits geschlossen.")
            handle = self._handles.get(key)
            if handle is None:
                handle = self._create_handle()
                self._handles[key] = handle
            return handle

    def _discard_handle(self, key, expected_handle):
        with self._lock:
            if self._handles.get(key) is expected_handle:
                self._handles.pop(key, None)
        try:
            expected_handle.session.close()
        except Exception:
            pass

    @contextmanager
    def request(self, mac, channel, method, url, **kwargs):
        key = (str(mac), str(channel))
        handle = self._get_handle(key)

        with handle.lock:
            try:
                response = handle.session.request(method, url, **kwargs)
                with response:
                    yield response
            except _SESSION_RESET_ERRORS:
                self._discard_handle(key, handle)
                raise

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            handles = tuple(self._handles.values())
            self._handles.clear()

        for handle in handles:
            try:
                handle.session.close()
            except Exception:
                pass

    def retain_devices(self, active_devices):
        active = {str(device) for device in active_devices}
        with self._lock:
            stale_keys = [
                key for key in self._handles if key[0] not in active
            ]
            handles = [
                self._handles.pop(key) for key in stale_keys
            ]

        for handle in handles:
            try:
                handle.session.close()
            except Exception:
                pass


def _request_timeout(base_url, operation, is_ap=False):
    if is_ap:
        return (3.0, 6.0)

    if operation == "history":
        return (3.05, 20.0)

    if not is_android():
        return {
            "poll": 1.5,
            "heavy": 2.5,
            "control": 2.0,
        }[operation]

    is_https = urlparse(base_url).scheme.lower() == "https"
    if operation == "poll":
        return (3.0, 4.5) if is_https else (1.5, 2.5)
    if operation == "heavy":
        return (3.0, 5.0) if is_https else (2.0, 3.0)
    return (3.0, 5.0) if is_https else (2.0, 3.0)


@contextmanager
def _perform_request(
    transport,
    mac,
    channel,
    method,
    url,
    *,
    persistent=True,
    **kwargs,
):
    if transport is not None and persistent:
        with transport.request(
            mac,
            channel,
            method,
            url,
            **kwargs,
        ) as response:
            yield response
        return

    headers = dict(kwargs.pop("headers", {}) or {})
    headers["Connection"] = "close"
    response = requests.request(
        method,
        url,
        headers=headers,
        **kwargs,
    )
    try:
        yield response
    finally:
        response.close()


def _failure_key(mac, base_url, operation):
    return str(mac), str(base_url), str(operation)


def _record_failure(mac, base_url, operation, error):
    now = time.monotonic()
    description = f"{type(error).__name__}: {error}"[:240]
    key = _failure_key(mac, base_url, operation)

    with _failure_log_lock:
        state = _failure_log_state.get(key)
        if state is None:
            state = {
                "count": 0,
                "first_failure": now,
                "last_log": 0.0,
                "description": "",
            }
            _failure_log_state[key] = state
        else:
            _failure_log_state.move_to_end(key)

        state["count"] += 1
        should_log = (
            state["count"] == 1
            or state["description"] != description
            or (now - state["last_log"]) >= _FAILURE_LOG_INTERVAL
        )
        state["description"] = description
        if should_log:
            state["last_log"] = now
            count = state["count"]
        else:
            count = None

        while len(_failure_log_state) > _FAILURE_LOG_LIMIT:
            _failure_log_state.popitem(last=False)

    if count is not None:
        print(
            f"[NetworkWorker] {operation} fehlgeschlagen "
            f"({mac}, {base_url}, Versuch {count}): {description}"
        )


def _record_recovery(mac, base_url, operation):
    key = _failure_key(mac, base_url, operation)
    with _failure_log_lock:
        state = _failure_log_state.pop(key, None)

    if state:
        duration = max(0.0, time.monotonic() - state["first_failure"])
        print(
            f"[NetworkWorker] {operation} wieder stabil "
            f"({mac}, {base_url}) nach {state['count']} Fehlern/"
            f"{duration:.1f}s."
        )


def _http_status_error(status_code):
    return RuntimeError(f"HTTP {status_code}")


def send_history_request(
    base_url,
    params,
    user,
    pw,
    *,
    mac="history",
    transport=None,
):
    """Send one History target to the currently resolved device route."""
    base_url = base_url.rstrip("/")
    try:
        with _perform_request(
            transport,
            mac,
            "history",
            "GET",
            f"{base_url}/history",
            params=dict(params),
            timeout=_request_timeout(base_url, "history"),
            auth=(user, pw) if user else None,
            headers={"Accept": "application/json"},
        ) as response:
            try:
                payload = response.json()
            except ValueError:
                payload = None

            if response.status_code == 200 and isinstance(payload, dict):
                _record_recovery(mac, base_url, "history")
                return payload, None

            error = (
                str(
                    payload.get("error")
                    or f"History-HTTP-Fehler {response.status_code}"
                )
                if isinstance(payload, dict)
                else f"History-HTTP-Fehler {response.status_code}"
            )
            _record_failure(
                mac,
                base_url,
                "history",
                _http_status_error(response.status_code),
            )
            return payload if isinstance(payload, dict) else None, error
    except requests.exceptions.RequestException as exc:
        _record_failure(mac, base_url, "history", exc)
        return None, str(exc)


def fetch_single_device(
    mac,
    dev_cfg,
    targets,
    registry,
    local_plants_cache,
    local_plant_revs,
    transport=None,
    heavy_fetch_scheduler=None,
):
    """
    Führt den HTTP-Request für ein einzelnes Gerät aus.
    Gibt (mac, payload, is_ap) zurück oder (mac, None, False) im Fehlerfall.
    """
    if not targets:
        return mac, None, False

    user, pw = config.get_device_auth(mac)

    for base_url in targets:
        base_url = base_url.rstrip("/")
        is_ap = "192.168.4." in base_url
        timeout = _request_timeout(base_url, "poll", is_ap=is_ap)

        try:
            with _perform_request(
                transport,
                mac,
                "poll",
                "GET",
                f"{base_url}/data",
                persistent=not is_ap,
                timeout=timeout,
                auth=(user, pw) if user else None,
                headers={"Accept": "application/json"},
            ) as response:
                if response.status_code != 200:
                    _record_failure(
                        mac,
                        base_url,
                        "poll",
                        _http_status_error(response.status_code),
                    )
                    continue
                payload = response.json()

            _record_recovery(mac, base_url, "poll")
            _update_runtime_ip(mac, payload, registry)
            _update_config_ip_if_needed(mac, payload)

            esp_plant_rev = payload.get("rev_plant_planner", 0)
            local_rev = local_plant_revs.get(mac, -1)
            if esp_plant_rev != local_rev:
                if heavy_fetch_scheduler is not None:
                    heavy_fetch_scheduler(
                        mac,
                        base_url,
                        user,
                        pw,
                    )
                else:
                    fetch_heavy_plant_data(
                        mac,
                        base_url,
                        user,
                        pw,
                        local_plants_cache,
                        local_plant_revs,
                        transport=transport,
                    )

            cached = local_plants_cache.get(mac, {}).get(
                "plant_planner",
                {},
            )
            cached_rev = (
                int(cached.get("rev_plant_planner", -1))
                if isinstance(cached, dict)
                else -1
            )
            if cached_rev == int(esp_plant_rev):
                payload["plant_planner"] = cached

            registry.handle_success(mac, target=base_url)
            return mac, payload, is_ap

        except Exception as exc:
            _record_failure(mac, base_url, "poll", exc)
            continue

    registry.handle_failure(mac)
    return mac, None, False


def fetch_heavy_plant_data(
    mac,
    base_url,
    user,
    pw,
    local_plants_cache,
    local_plant_revs,
    transport=None,
):
    """Holt die erweiterten Pflanzendaten und meldet Erfolg explizit."""
    base_url = base_url.rstrip("/")
    is_ap = "192.168.4." in base_url
    try:
        with _perform_request(
            transport,
            mac,
            "heavy",
            "GET",
            f"{base_url}/data/plants",
            persistent=not is_ap,
            timeout=_request_timeout(base_url, "heavy", is_ap=is_ap),
            auth=(user, pw) if user else None,
            headers={"Accept": "application/json"},
        ) as response:
            if response.status_code != 200:
                _record_failure(
                    mac,
                    base_url,
                    "heavy",
                    _http_status_error(response.status_code),
                )
                return False
            plant_payload = response.json()

        network.client_storage.save_heavy_plant_data(
            mac,
            plant_payload,
            local_plants_cache,
        )
        if "plant_planner" in plant_payload:
            local_plant_revs[mac] = plant_payload["plant_planner"].get(
                "rev_plant_planner",
                0,
            )
        _record_recovery(mac, base_url, "heavy")
        return True
    except Exception as exc:
        _record_failure(mac, base_url, "heavy", exc)
        return False


def send_control_request(
    base_url,
    payload,
    user,
    pw,
    endpoint="/control",
    *,
    mac="control",
    transport=None,
):
    """Sendet jeden Steuerbefehl genau einmal; es gibt keine Auto-Retries."""
    base_url = base_url.rstrip("/")
    is_ap = "192.168.4." in base_url
    try:
        with _perform_request(
            transport,
            mac,
            "control",
            "POST",
            f"{base_url}{endpoint}",
            persistent=not is_ap,
            json=payload,
            timeout=_request_timeout(base_url, "control", is_ap=is_ap),
            auth=(user, pw) if user else None,
            headers={"Accept": "application/json"},
        ) as response:
            succeeded = 200 <= response.status_code < 300
            if not succeeded:
                _record_failure(
                    mac,
                    base_url,
                    "control",
                    _http_status_error(response.status_code),
                )
                return False

        _record_recovery(mac, base_url, "control")
        return True
    except Exception as exc:
        _record_failure(mac, base_url, "control", exc)
        return False

def _update_runtime_ip(mac, payload, registry):
    ip = payload.get("ip") or payload.get("ip_address")
    if not ip:
        return

    registry.update_device(mac, ip=ip, source="runtime")


def _update_config_ip_if_needed(mac, payload):
    """Setzt die `ip_address` in der Config, aber NUR wenn dort bisher kein Wert steht."""
    ip = payload.get("ip") or payload.get("ip_address")
    if not ip:
        return

    with _config_update_lock:
        try:
            cfg = config._init()
        except Exception:
            return

        devices = cfg.get("devices", {})
        if mac not in devices:
            return

        dev = devices[mac]
        current_ip = (dev.get("ip_address") or "").strip()
        if not current_ip:
            print(f"[NetworkWorker] Setze initiale IP für {mac}: {ip}")
            dev["ip_address"] = ip
            try:
                config.save(cfg)
            except Exception as exc:
                print(
                    "[NetworkWorker] Fehler beim Schreiben der initialen IP: "
                    f"{exc}"
                )
