import os

from kivy.clock import Clock
from kivy.uix.screenmanager import Screen

from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.overlays.infrastructure.revision_session import (
    RevisionSession,
)
from dashboard_gui.ui.common.graph_chart_content.graph_mesh import (
    clear_graph_series,
    update_graph_mesh,
)
from dashboard_gui.ui.common.graph_chart_content.metric_registry import (
    MetricRegistry,
)
from dashboard_gui.ui.formatters import UIFormatter
from dashboard_gui.ui.fullscreen_content.fullscreen_main_panel import (
    FullScreenMainPanel,
)
from dashboard_gui.ui.grow_controller_content.controller_command_status_popup import (
    GrowCommandStatusPopup,
)
from dashboard_gui.ui.scaling_utils import dp_scaled


class FullScreenView(Screen):
    name = "fullscreen"

    def __init__(self, **kw):
        super().__init__(**kw)
        self.tile_id = None
        self.current_key = None
        self.active_tile = None
        self._active_unit = ""
        self._history_selection_key = None
        self._history_command_key = None
        self._history_command_selection_id = None
        self._history_revision_session = RevisionSession()
        self._observed_graph_range_revision = -1
        self._rendered_history_signature = None
        self._rendered_graph_signature = None
        self._graph_snapshot = None
        self._history_touch_start = None

        self.layout = FullScreenMainPanel()
        self.add_widget(self.layout)

        self.graph = self.layout.graph
        self.plot = self.layout.plot
        self.plot_glow = self.layout.plot_glow
        self.mesh = self.layout.mesh
        self.mesh_color = self.layout.mesh_color
        self.labels_list = self.layout.labels_list
        self.lbl_title = self.layout.lbl_title
        self.lbl_value = self.layout.lbl_value
        self.lbl_sub = self.layout.lbl_sub
        self.header = self.layout.header
        self.controls = self.layout.controls
        self._mesh_update_trigger = Clock.create_trigger(
            self._upd_mesh,
            0,
        )
        self.graph.bind(
            pos=self._schedule_mesh_update,
            size=self._schedule_mesh_update,
            view_pos=self._schedule_mesh_update,
            view_size=self._schedule_mesh_update,
        )

        self.layout.btn_left.bind(on_release=lambda *_: self._switch(-1))
        self.layout.btn_right.bind(on_release=lambda *_: self._switch(1))
        self.layout.controls.on_reset = self.reset_from_global
        self.layout.on_range_selected = self._select_time_range
        self.layout.on_custom_range_selected = self._select_custom_time_range
        GLOBAL_STATE.ui_handler.attach_screen("fullscreen", self)

    @property
    def _graph_engine(self):
        return GLOBAL_STATE.graph_engine

    @property
    def _graph_history_engine(self):
        return GLOBAL_STATE.graph_history_engine

    @property
    def _history_window(self):
        history_window, _revision = (
            self._graph_history_engine.get_graph_range_state()
        )
        return history_window

    def _update_bg(self, *args):
        self.layout._update_bg(*args)

    def _upd_mesh(self, *args):
        update_graph_mesh(self.graph, self.plot, self.mesh)

    def _schedule_mesh_update(self, *args):
        self._mesh_update_trigger()

    def activate_tile(self, full_key):
        print(f"[FS] Aktiviere: {full_key}")

        dev_id, channel, tile_id = GLOBAL_STATE.tile_engine.parse_full_key(
            full_key
        )
        if not dev_id or not channel or not tile_id:
            print(f"[FS] INVALID KEY FORMAT: {full_key}")
            return False

        allowed = GLOBAL_STATE.get_active_tiles(dev_id, channel)
        if tile_id not in allowed:
            fallback_key = GLOBAL_STATE.tile_engine.get_first_tile_key(
                dev_id,
                channel,
            )
            print(f"[FS] BLOCKED INVALID TILE: {full_key}")
            if fallback_key and fallback_key != full_key:
                print(f"[FS] FALLBACK -> {fallback_key}")
                return self.activate_tile(fallback_key)
            self._clear_active_tile()
            return False

        clear_graph_series(self.plot, self.mesh, self.plot_glow)
        self.current_key = full_key
        self.tile_id = tile_id
        self._rendered_history_signature = None
        self._rendered_graph_signature = None
        self._graph_snapshot = None
        history_window = self._history_window
        self.layout.set_active_range(
            history_window.range_key
            if history_window is not None
            else None
        )

        is_rssi = self.tile_id == "rssi"
        if hasattr(GLOBAL_STATE, "tile_engine"):
            if (
                self.tile_id in GLOBAL_STATE.tile_engine.active_tiles
                or is_rssi
            ):
                readable_name = (
                    "RSSI"
                    if is_rssi
                    else (
                        self.tile_id.upper()
                        if "vpd" in self.tile_id
                        else self.tile_id.title()
                    )
                )
            else:
                readable_name = self.tile_id.replace("_", " ").title()
        else:
            readable_name = self.tile_id.replace("_", " ").title()

        metric_config = MetricRegistry.get(self.tile_id)
        fullscreen_presentation = MetricRegistry.presentation("fullscreen")
        self.layout.apply_metric_theme(fullscreen_presentation)

        main_color = metric_config["color"]
        glow_color = metric_config["glow"]
        self.lbl_title.text = metric_config.get("name", readable_name)
        self._active_unit = self._resolve_active_unit(metric_config)

        background_path = os.path.join(
            "dashboard_gui",
            "assets",
            "background2.png",
        )
        if os.path.exists(background_path):
            self.layout.bg_rect.source = background_path
            self.layout.bg_color.rgba = (1, 1, 1, 0.40)
        else:
            self.layout.bg_rect.source = ""
            self.layout.bg_color.rgba = (0.08, 0.08, 0.1, 1)

        self.mesh_color.rgba = (
            main_color[0],
            main_color[1],
            main_color[2],
            0.25,
        )
        self.plot, self.plot_glow = self.layout.configure_metric_plots(
            main_color,
            glow_color,
        )

        self._load_data()
        return True

    def _clear_active_tile(self):
        self._graph_history_engine.cancel_history_selection()
        self.current_key = None
        self.tile_id = None
        self.active_tile = None
        self._history_selection_key = None
        self._history_command_key = None
        self._history_command_selection_id = None
        self._rendered_history_signature = None
        self._rendered_graph_signature = None
        self._graph_snapshot = None
        self.lbl_title.text = ""
        self.lbl_value.text = "---"
        self.lbl_sub.text = "avg: --- | min: --- | max: ---"
        clear_graph_series(self.plot, self.mesh, self.plot_glow)
        self.graph.ymin = 0
        self.graph.ymax = 1

    def _select_time_range(self, hours):
        self._graph_history_engine.cancel_history_selection()
        self._history_selection_key = None
        self._rendered_history_signature = None
        self._rendered_graph_signature = None
        self._graph_snapshot = None
        self._history_touch_start = None
        self.layout.set_active_range(hours)
        clear_graph_series(self.plot, self.mesh, self.plot_glow)

        if hours is None:
            self._graph_history_engine.set_active_history_window(None)
            device_id = self._current_device_id()
            if device_id:
                result = GLOBAL_STATE.send_history_command(
                    mode="live",
                    device_id=device_id,
                    on_complete=self._history_selection_finished,
                )
                self._begin_history_command(result)
            self._load_live_data()
            return

        try:
            history_window = self._graph_history_engine.create_history_window(
                hours
            )
        except (TypeError, ValueError):
            self._show_history_error("Ungültiges History-Zeitfenster.")
            return

        self._graph_history_engine.set_active_history_window(history_window)
        self._select_history_pipeline(
            history_window=history_window,
            force=True,
        )

    def _select_custom_time_range(
        self,
        start_timestamp,
        end_timestamp,
    ):
        try:
            history_window = self._graph_history_engine.create_history_window(
                "custom",
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
            )
        except (TypeError, ValueError):
            self._show_history_error(
                "Ungültiges benutzerdefiniertes Zeitfenster."
            )
            return

        self._graph_history_engine.cancel_history_selection()
        self._graph_history_engine.set_active_history_window(history_window)
        self._history_selection_key = None
        self._rendered_history_signature = None
        self._rendered_graph_signature = None
        self._graph_snapshot = None
        self._history_touch_start = None
        self.layout.set_active_range("custom")
        clear_graph_series(self.plot, self.mesh, self.plot_glow)
        self._select_history_pipeline(
            history_window=history_window,
            force=True,
        )

    def _load_data(self):
        self._sync_history_target()
        if self._history_window is None:
            self._load_live_data()
        else:
            self._load_history_data()

    def _sync_history_target(self):
        history_window, revision = (
            self._graph_history_engine.get_graph_range_state()
        )
        confirmation = (
            self._graph_history_engine.consume_history_confirmation(
                self._history_command_selection_id
            )
        )
        if confirmation is not None:
            confirmed_revision = int(
                confirmation["rev_history"]
            )
            if not self._history_revision_session.is_pending(
                confirmed_revision
            ):
                self._history_revision_session.mark_confirmed_snapshot(
                    confirmed_revision
                )
                title = (
                    "Live-Modus bestätigt"
                    if confirmation.get("mode") == "live"
                    else "Logmodus bestätigt"
                )
                GrowCommandStatusPopup.show(
                    reset_sent=False,
                    title=title,
                )
                self._history_command_key = None
                self._history_command_selection_id = None

        if revision == self._observed_graph_range_revision:
            return

        self._observed_graph_range_revision = revision
        self.layout.set_active_range(
            history_window.range_key
            if history_window is not None
            else None
        )
        self._rendered_history_signature = None
        self._rendered_graph_signature = None
        if history_window is None:
            self._history_selection_key = None

    def _load_live_data(self):
        if not self.current_key:
            return

        snapshot = self._graph_engine.get_live_snapshot(
            self.current_key,
            label_count=len(self.labels_list),
        )
        if snapshot is None:
            self._render_empty_graph()
            return

        self._render_graph_snapshot(snapshot)

    def _load_history_data(self):
        if not self.current_key or not self.tile_id:
            self._render_empty_graph()
            return

        device_id = self._current_device_id()
        if not device_id:
            self._render_empty_graph()
            return

        pipeline_key = self._graph_history_engine.get_history_pipeline_key(
            device_id
        )
        if pipeline_key is None:
            if (
                self._history_selection_key is not None
                and self._history_selection_key[0] == device_id
            ):
                status, error = (
                    self._graph_history_engine.get_history_selection_state(
                        self._history_selection_key
                    )
                )
                if status == "failed":
                    self._show_history_error(
                        error
                        or "History konnte nicht geladen werden."
                    )
                    return
            else:
                self._history_selection_key = None
            self.lbl_sub.text = (
                f"{self._history_window.label} | "
                "Warte auf Hub-Bestätigung …"
            )
            return

        if pipeline_key != self._history_selection_key:
            self._history_selection_key = pipeline_key
            self._rendered_history_signature = None

        status, error = (
            self._graph_history_engine.get_history_selection_state(
                self._history_selection_key
            )
        )
        if status == "loaded":
            self._render_history_data()
        elif status == "failed":
            self._show_history_error(
                error or "History konnte nicht geladen werden."
            )

    def _current_device_id(self):
        if not self.current_key:
            return None

        device_id, _channel, _tile_id = (
            GLOBAL_STATE.tile_engine.parse_full_key(self.current_key)
        )
        return str(device_id) if device_id else None

    def _select_history_pipeline(
        self,
        history_window,
        force=False,
    ):
        if history_window is None:
            return

        device_id = self._current_device_id()
        if not device_id:
            self._render_empty_graph()
            return

        result = GLOBAL_STATE.send_history_command(
            mode="history",
            device_id=device_id,
            history_window=history_window,
            on_complete=self._history_selection_finished,
            force=force,
        )
        self._begin_history_command(result)

    def _begin_history_command(self, result):
        if result is None:
            self._show_history_error(
                "History-Befehl konnte nicht gesendet werden."
            )
            return

        self._history_command_key = result.key
        self._history_command_selection_id = result.selection_id
        if (
            result.status == "loading"
            and result.target_revision is not None
        ):
            self._history_revision_session.mark_sent(
                result.target_revision
            )

        if self._history_window is not None:
            self._history_selection_key = result.key

        if result.status == "loaded":
            if self._history_window is not None:
                self._render_history_data(force=True)
        elif result.status == "failed":
            self._show_history_error(
                result.error or "History konnte nicht geladen werden."
            )
        elif self._history_window is not None:
            self.lbl_sub.text = (
                f"{self._history_window.label} | "
                "Warte auf History-Pipeline …"
            )

    def _history_selection_finished(self, selection_key, error):
        Clock.schedule_once(
            lambda _dt, key=selection_key, message=error: (
                self._apply_history_selection_result(key, message)
            )
        )

    def _apply_history_selection_result(self, selection_key, error):
        if selection_key != self._history_command_key:
            return

        if error:
            print(f"[FS HISTORY] REST-Fehler: {error}")
            self._show_history_error(
                error or "History konnte nicht geladen werden."
            )
            self._history_command_key = None
            self._history_command_selection_id = None
            return

        if self._history_window is not None:
            self.lbl_sub.text = (
                f"{self._history_window.label} | "
                "Warte auf History-Pipeline …"
            )

    def _render_history_data(self, force=False):
        signature = (self._history_selection_key, self.tile_id)
        if not force and signature == self._rendered_history_signature:
            return

        snapshot = self._graph_history_engine.get_history_snapshot(
            pipeline_key=self._history_selection_key,
            tile_id=self.tile_id,
            label_count=len(self.labels_list),
            range_label=self._history_window.label,
        )
        self._rendered_history_signature = signature

        if snapshot is None:
            self._show_history_error(
                f"{self._history_window.label} | Keine History-Daten."
            )
            return

        self._render_graph_snapshot(snapshot)
        print(
            f"[FS HISTORY] {self.tile_id}: "
            f"{len(snapshot.values)} Punkte für "
            f"{snapshot.range_label} gerendert."
        )

    def _render_graph_snapshot(self, snapshot):
        self._graph_snapshot = snapshot
        graph_signature = (
            snapshot.mode,
            snapshot.points,
            snapshot.xmin,
            snapshot.xmax,
            snapshot.ymin,
            snapshot.ymax,
            snapshot.labels,
        )
        if graph_signature != self._rendered_graph_signature:
            self.graph.xmin = snapshot.xmin
            self.graph.xmax = snapshot.xmax
            self.graph.ymin = snapshot.ymin
            self.graph.ymax = snapshot.ymax
            points = list(snapshot.points)
            self.plot.points = points
            self.plot_glow.points = points

            for label, text in zip(self.labels_list, snapshot.labels):
                label.text = text

            self._rendered_graph_signature = graph_signature
            # Die Graph-Achsen werden von Kivy im nächsten Frame berechnet.
            # Erst danach wird das Fill-Mesh an dieselbe Plot-Fläche gelegt.
            self._schedule_mesh_update()

        self._active_unit = self._resolve_active_unit(
            MetricRegistry.get(self.tile_id)
        )
        number_style = self._number_style()
        self.lbl_value.text = UIFormatter.format_sensor_label(
            name="",
            value=snapshot.last_value,
            unit=self._active_unit,
            trend=snapshot.trend_icon if snapshot.mode == "live" else "",
            style=number_style,
        )
        self.lbl_sub.text = self._snapshot_stats_text(snapshot)

    def _resolve_active_unit(self, metric_config):
        if self.tile_id == "rssi":
            return "dBm"
        if self.tile_id and "temp" in self.tile_id:
            return GLOBAL_STATE.unit_engine.get_temp_unit()
        return (
            GLOBAL_STATE.get_unit(self.current_key)
            or metric_config.get("unit", "")
            or "—"
        )

    def _number_style(self):
        metric_config = MetricRegistry.get(self.tile_id)
        fullscreen_presentation = MetricRegistry.presentation("fullscreen")
        return {
            **fullscreen_presentation.get("formatter", {}),
            **metric_config.get("style", {}),
        }

    def _snapshot_stats_text(self, snapshot, point_label=None):
        parts = []
        if snapshot.mode == "history" and snapshot.range_label:
            parts.append(snapshot.range_label)
        if point_label:
            parts.append(point_label)

        if snapshot.stats is None:
            parts.append("avg: --- | min: --- | max: ---")
            return " | ".join(parts)

        style = self._number_style()
        stats = snapshot.stats
        parts.append(
            f"avg: {UIFormatter.format_number(stats.average, style)} "
            f"{self._active_unit} | "
            f"min: {UIFormatter.format_number(stats.minimum, style)} "
            f"{self._active_unit} | "
            f"max: {UIFormatter.format_number(stats.maximum, style)} "
            f"{self._active_unit}"
        )
        return " | ".join(parts)

    def _show_history_error(self, message):
        clear_graph_series(self.plot, self.mesh, self.plot_glow)
        self._rendered_graph_signature = None
        self._graph_snapshot = None
        self.lbl_value.text = f"--- {self._active_unit}"
        self.lbl_sub.text = message
        self.graph.ymin = 0
        self.graph.ymax = 1
        for label in self.labels_list:
            label.text = ""

    def update_from_global(self, data):
        self.header.update_from_global(data)

        active_device = GLOBAL_STATE.get_active_device_id()
        active_channel = GLOBAL_STATE.get_active_channel()
        if not active_device or not active_channel:
            self._clear_active_tile()
            return

        allowed = GLOBAL_STATE.get_active_tiles(
            active_device,
            active_channel,
        )
        if not allowed:
            self._clear_active_tile()
            return

        if not self.tile_id:
            fallback_key = GLOBAL_STATE.tile_engine.get_first_tile_key(
                active_device,
                active_channel,
            )
            if fallback_key:
                self.activate_tile(fallback_key)
            return

        expected_full_key = (
            f"{active_device}_{active_channel}_{self.tile_id}"
        )
        if self.tile_id not in allowed:
            fallback_key = GLOBAL_STATE.tile_engine.get_first_tile_key(
                active_device,
                active_channel,
            )
            print(
                f"[FS] Schutzfunktion! Tile {self.tile_id} nicht erlaubt "
                f"für neues Gerät. Springe zu: {fallback_key}"
            )
            if fallback_key:
                self.activate_tile(fallback_key)
            else:
                self._clear_active_tile()
            return

        if self.current_key != expected_full_key:
            if not self.activate_tile(expected_full_key):
                return

        self._load_data()

    def _switch(self, direction):
        if not self.current_key:
            return

        next_key = GLOBAL_STATE.tile_engine.get_next_full_key(
            self.current_key,
            direction,
        )
        next_device, next_channel, next_tile_id = (
            GLOBAL_STATE.tile_engine.parse_full_key(next_key)
        )
        allowed = GLOBAL_STATE.get_active_tiles(
            next_device,
            next_channel,
        )

        if next_tile_id in allowed:
            if next_key != self.current_key:
                self.activate_tile(next_key)
            return

        print(
            f"[FS UI-Gate] Blockiert: Tile '{next_tile_id}' ist für "
            f"dieses Gerät inaktiv!"
        )
        active_device = GLOBAL_STATE.get_active_device_id()
        active_channel = GLOBAL_STATE.get_active_channel()
        fallback = GLOBAL_STATE.tile_engine.get_first_tile_key(
            active_device,
            active_channel,
        )
        if fallback and fallback != self.current_key:
            self.activate_tile(fallback)

    def reset_from_global(self):
        print("[FS] Resetting Fullscreen UI...")
        self._graph_history_engine.cancel_history_selection()
        self._history_selection_key = None
        self._history_command_key = None
        self._history_command_selection_id = None
        self._rendered_history_signature = None
        self._rendered_graph_signature = None
        self._graph_snapshot = None
        history_window = self._history_window
        self.layout.set_active_range(
            history_window.range_key
            if history_window is not None
            else None
        )
        unit = (
            GLOBAL_STATE.get_unit(self.current_key)
            if self.current_key
            else ""
        )
        self.lbl_value.text = f"--- {unit}"
        self.lbl_sub.text = "avg: --- | min: --- | max: ---"

        clear_graph_series(self.plot, self.mesh, self.plot_glow)
        self.graph.ymin = 0
        self.graph.ymax = 1

        if hasattr(self, "header"):
            self.header.set_rssi(None)

        if self.tile_id == "rssi":
            self.lbl_value.text = "--- dBm"
            self.lbl_sub.text = "Signalstärke nicht verfügbar"

        for widget in self.walk():
            if (
                widget != self
                and hasattr(widget, "reset")
                and callable(widget.reset)
            ):
                widget.reset()

    def _render_empty_graph(self):
        clear_graph_series(self.plot, self.mesh, self.plot_glow)
        self._rendered_graph_signature = None
        self._graph_snapshot = None
        self.lbl_value.text = f"--- {self._active_unit}"
        self.lbl_sub.text = "avg: --- | min: --- | max: ---"
        self.graph.ymin = 0
        self.graph.ymax = 1
        for label in self.labels_list:
            label.text = ""

    def _is_history_plot_touch(self, touch):
        if self._command_overlay_is_active():
            return False

        if (
            self._history_window is None
            or self._history_selection_key is None
            or self._graph_snapshot is None
            or self._graph_snapshot.mode != "history"
        ):
            return False

        for widget in (
            self.header,
            self.layout.range_bar,
            self.layout.btn_left,
            self.layout.btn_right,
            self.controls,
        ):
            if widget.collide_point(*touch.pos):
                return False

        if not self.graph.collide_point(*touch.pos):
            return False

        local_x = touch.x - self.graph.x
        local_y = touch.y - self.graph.y
        return self.graph.collide_plot(local_x, local_y)

    def _command_overlay_is_active(self):
        """Give an open command overlay exclusive touch priority."""
        manager = getattr(
            GLOBAL_STATE.ui_handler,
            "overlay_manager",
            None,
        )
        overlay = getattr(manager, "active_overlay", None)
        return (
            overlay is not None
            and overlay.parent is self
        )

    def _inspect_history_touch(self, touch):
        if not self._is_history_plot_touch(touch):
            return False

        local_x = touch.x - self.graph.x
        local_y = touch.y - self.graph.y
        graph_x, _graph_y = self.graph.to_data(local_x, local_y)
        point = self._graph_history_engine.inspect_history_point(
            pipeline_key=self._history_selection_key,
            tile_id=self.tile_id,
            graph_x=graph_x,
        )
        if point is None:
            return False

        self.lbl_value.text = UIFormatter.format_sensor_label(
            name="",
            value=point.value,
            unit=self._active_unit,
            trend="",
            style=self._number_style(),
        )
        self.lbl_sub.text = self._snapshot_stats_text(
            self._graph_snapshot,
            point_label=point.label,
        )
        return True

    def on_touch_down(self, touch):
        if self._is_history_plot_touch(touch):
            self._history_touch_start = (touch.x, touch.y)
        else:
            self._history_touch_start = None

        if hasattr(GLOBAL_STATE, "ggm"):
            GLOBAL_STATE.ggm.handle_touch("fullscreen", "down", touch)
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self._history_touch_start is not None:
            start_x, start_y = self._history_touch_start
            if (
                abs(touch.x - start_x) > dp_scaled(12)
                or abs(touch.y - start_y) > dp_scaled(12)
            ):
                self._history_touch_start = None

        handled = False
        if hasattr(GLOBAL_STATE, "ggm"):
            handled = GLOBAL_STATE.ggm.handle_touch(
                "fullscreen",
                "move",
                touch,
            )
        if handled:
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        handled = False
        if hasattr(GLOBAL_STATE, "ggm"):
            handled = GLOBAL_STATE.ggm.handle_touch(
                "fullscreen",
                "up",
                touch,
            )

        inspect_point = self._history_touch_start is not None and not handled
        self._history_touch_start = None
        if inspect_point and self._inspect_history_touch(touch):
            return True
        if handled:
            return True
        return super().on_touch_up(touch)
