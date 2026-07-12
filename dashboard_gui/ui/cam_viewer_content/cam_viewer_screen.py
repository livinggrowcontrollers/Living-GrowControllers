# dashboard_gui/ui/cam_viewer_content/cam_viewer_screen.py

import os
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.metrics import dp
from kivy.graphics import Color, Rectangle
from dashboard_gui.ui.scaling_utils import dp_scaled, sp_scaled

from dashboard_gui.ui.common.header_online import HeaderBar
from dashboard_gui.ui.cam_viewer_content.cam_viewer_panel import CamViewerPanel
from dashboard_gui.global_state_manager import GLOBAL_STATE

ASSET_ROOT = os.path.join("dashboard_gui", "assets")

class CamViewerScreen(Screen):
    """
    Voll integrierter Screen
    """

    def __init__(self, **kw):
        name = "cam_viewer"

        super().__init__(**kw)
        from dashboard_gui.global_state_manager import GLOBAL_STATE
        GLOBAL_STATE.ui_handler.attach_screen("cam_viewer", self)
        root = BoxLayout(orientation="vertical")
        with root.canvas.before:
            Color(1, 1, 1, 1)
            self.bg_rect = Rectangle(
                source=os.path.join(ASSET_ROOT, "background2.png"),
                pos=root.pos,
                size=root.size
            )

        root.bind(
            pos=lambda *_: setattr(self.bg_rect, "pos", root.pos),
            size=lambda *_: setattr(self.bg_rect, "size", root.size)
        )        

        
        
        # HEADER
        self.header = HeaderBar()

        
        root.add_widget(self.header)

        # PANEL
        panel = CamViewerPanel()
        root.add_widget(panel)

        self.add_widget(root)

    def update_from_global(self, d):
        self.header.update_from_global(d)        
