from kivy.uix.button import Button

from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled
from dashboard_gui.overlays.infrastructure.contracts import SyncState


class SyncButton(Button):
    _VISUALS = {
        SyncState.CONFIRMED: ("[font=FA]\uf058[/font]", (0, 1, 0, 1)),
        SyncState.DIRTY: ("[font=FA]\uf021[/font]", (1, 0.5, 0, 1)),
        SyncState.RETRY: ("[font=FA]\uf021[/font]", (1, 0.5, 0, 1)),
        SyncState.ERROR: ("[font=FA]\uf071[/font]", (1, 0.3, 0, 1)),
    }

    def __init__(self, **kwargs):
        super().__init__(
            text="[font=FA]\uf021[/font]",
            markup=True,
            font_size=sp_scaled(30),
            size_hint=(None, None),
            width=dp_scaled(45),
            height=dp_scaled(45),
            background_color=(0, 0, 0, 0),
            color=(1, 0.5, 0, 1),
            **kwargs,
        )

    def show_state(self, state):
        if not isinstance(state, SyncState):
            state = SyncState(state)
        self.text, self.color = self._VISUALS[state]
