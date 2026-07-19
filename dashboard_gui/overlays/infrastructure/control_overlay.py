import time

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout

from dashboard_gui.global_state_manager import GLOBAL_STATE
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.overlays.components.control_panel import ControlPanel
from dashboard_gui.overlays.components.lock_overlay import LockOverlay
from dashboard_gui.overlays.components.overlay_header import OverlayHeader
from .contracts import OverlayKey, SyncState
from .revision_session import RevisionSession


class ControlOverlay(FloatLayout):
    """Shared shell and target-revision lifecycle for editable overlays."""

    def __init__(
        self,
        parent_header,
        *,
        overlay_key,
        command_type,
        adapter,
        title,
        panel_spacing=8,
        header_height=35,
        accent=(0.1, 0.45, 0.9),
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.opacity = 0
        self.parent_header = parent_header
        self.overlay_key = overlay_key if isinstance(overlay_key, OverlayKey) else OverlayKey(str(overlay_key))
        self.command_type = command_type
        self.adapter = adapter
        self.revision = RevisionSession()
        self.engine = self.revision
        self._user_active = False
        self._last_user_action = 0.0
        self._init_done = False
        self._locked = True
        self._ui_lock = False
        self._closed = False
        self._update_event = None
        self._init_event = None
        self._deferred_events = []

        self.bg_btn = Button(background_color=(0, 0, 0, 0.25))
        self.bg_btn.bind(on_release=self._on_background_click)
        self.add_widget(self.bg_btn)

        self.panel = ControlPanel(
            orientation="vertical",
            spacing=dp_scaled(panel_spacing),
            size_hint=(None, None),
            size=(dp_scaled(800), dp_scaled(500)),
            padding=[dp_scaled(25), dp_scaled(15), dp_scaled(25), dp_scaled(25)],
            pos_hint={"right": 0.98, "y": 0.01},
            accent=accent,
        )
        self.header = OverlayHeader(title, height=header_height)
        self.header.sync_button.bind(on_release=self._force_sync)
        self.panel.add_widget(self.header)
        self.add_widget(self.panel)

        # Compatibility aliases used by feature-specific color updates.
        self.lbl_title = self.header.title_label
        self.sync_icon = self.header.sync_button
        self.bg_color = self.panel.bg_color
        self.bg_rect = self.panel.bg_rect
        self.glow_color = self.panel.glow_color
        self.border_color = self.panel.border_color
        self.glow_line = self.panel.glow_line
        self.border_line = self.panel.border_line
        self.lock_overlay = None

    def _finish_setup(self, update_interval=0.1, init_delay=0.1):
        self.lock_overlay = LockOverlay(parent=self, panel=self.panel, unlock_callback=self._unlock_controls)
        self._update_event = Clock.schedule_interval(self.update_ui, update_interval)
        self._init_event = Clock.schedule_once(self._init_values, init_delay)

    def _fetch_state(self):
        mac = GLOBAL_STATE.get_active_device_id()
        raw = GLOBAL_STATE.overlay_engine.get_buffer_data(mac) if mac else None
        return self.adapter.decode(raw) if raw else None

    def _init_values(self, *_):
        if self._closed:
            return
        state = self._fetch_state()
        if state is None:
            self._init_event = Clock.schedule_once(self._init_values, 0.1)
            return

        revision = self.adapter.revision(state)
        self.revision.mark_confirmed_snapshot(revision)
        self._ui_lock = True
        try:
            self._apply_server_state(state)
            self._render_live_state(state)
        finally:
            self._ui_lock = False

        self._init_done = True
        self._user_active = False
        self._last_user_action = 0.0
        self.sync_icon.show_state(SyncState.CONFIRMED)
        if self._locked and self.lock_overlay and not self.lock_overlay.overlay:
            self.lock_overlay.create()
        self.opacity = 1

    def update_ui(self, *_):
        if self._closed:
            return
        state = self._fetch_state()
        if state is None:
            if self._init_done:
                self.sync_icon.show_state(SyncState.ERROR)
            return

        self._render_live_state(state)
        server_revision = self.adapter.revision(state)
        if self.revision.is_pending(server_revision) and self.revision.should_retry():
            if self.revision.retry_allowed():
                self.revision.register_retry()
                self._retry_current_command()
                return

        status = self.revision.status(server_revision, self._user_active)
        self.sync_icon.show_state(status)
        if status == SyncState.CONFIRMED and not self._user_active:
            self._ui_lock = True
            try:
                self._apply_server_state(state)
            finally:
                self._ui_lock = False

    def _submit_current_state(self, **overrides):
        if not self._init_done or self._closed:
            return None
        revision = GLOBAL_STATE.send_overlay_command(
            self.command_type,
            **self._build_command_kwargs(**overrides),
        )
        if revision:
            self.revision.mark_sent(revision)
            self.sync_icon.show_state(SyncState.DIRTY)
        return revision

    def _retry_current_command(self):
        retry = getattr(GLOBAL_STATE, "retry_overlay_command", None)
        revision = retry(self.command_type, instance_id=self.overlay_key.command_instance_id) if retry else None
        if revision:
            self.revision.mark_retried()
        else:
            self._submit_current_state()

    def _force_sync(self, *_):
        state = self._fetch_state()
        if state is None:
            self.sync_icon.show_state(SyncState.ERROR)
            return

        server_revision = self.adapter.revision(state)
        if self.revision.is_pending(server_revision):
            self._retry_current_command()
            self.sync_icon.show_state(SyncState.RETRY)
            return

        self._ui_lock = True
        try:
            self._apply_server_state(state)
        finally:
            self._ui_lock = False
        self.revision.mark_confirmed_snapshot(server_revision)
        event = Clock.schedule_once(lambda _dt: self._submit_current_state(), 0.05)
        self._deferred_events.append(event)
        self.sync_icon.show_state(SyncState.DIRTY)

    def _control_touch_down(self, instance, touch):
        if self._locked:
            return False
        if instance.collide_point(*touch.pos):
            self._user_active = True
        return False

    def _control_touch_up(self, instance, touch):
        if self._locked or not self._user_active:
            return False
        self._user_active = False
        self._last_user_action = time.time()
        self._submit_current_state()
        return False

    def _unlock_controls(self):
        self._locked = False
        self._set_controls_disabled(False)

    def _create_styled_btn(self, text):
        return Button(
            text=text,
            markup=True,
            background_normal="",
            background_down="",
            background_color=(0.15, 0.15, 0.15, 1),
            color=(1, 1, 1, 1),
            font_size=sp_scaled(20),
        )

    def _set_orange(self):
        self.sync_icon.show_state(SyncState.DIRTY)

    def _on_background_click(self, *_):
        if not self.panel.collide_point(*Window.mouse_pos):
            self.close()

    def _render_live_state(self, state):
        pass

    def _apply_server_state(self, state):
        raise NotImplementedError

    def _build_command_kwargs(self, **overrides):
        raise NotImplementedError

    def _set_controls_disabled(self, disabled):
        pass

    def close(self):
        if self._closed:
            return
        self._closed = True
        for event in [self._update_event, self._init_event, *self._deferred_events]:
            if event:
                event.cancel()
        if self.lock_overlay:
            self.lock_overlay.unlock()
        if self.parent:
            self.parent.remove_widget(self)
        manager = getattr(GLOBAL_STATE.ui_handler, "overlay_manager", None)
        if manager:
            manager.unregister(self)
