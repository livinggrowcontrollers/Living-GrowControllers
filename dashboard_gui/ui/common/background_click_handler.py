# dashboard_gui/ui/common/background_click_handler.py

class BackgroundClickHandler:

    def _on_background_click(self, instance):

        if self._locked:
            self.close()
            return

        from kivy.core.window import Window

        touch_pos = Window.mouse_pos

        if not self.panel.collide_point(*touch_pos):
            self.close()