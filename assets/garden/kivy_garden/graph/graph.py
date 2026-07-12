# -*- coding: utf-8 -*-
"""
Kivy Garden Graph – Auto-Redraw Version 🌱
© 2025 Dominik Rosenthal (Hackintosh1980)
Reworked for live animation (no resize needed).
"""

from kivy.uix.widget import Widget
from kivy.properties import (
    ListProperty, NumericProperty, BooleanProperty,
    ObjectProperty, StringProperty
)
from kivy.graphics import Color, Line, Rectangle, InstructionGroup
from kivy.clock import Clock

from kivy.event import EventDispatcher

class MeshLinePlot(EventDispatcher):
    color = ListProperty([1, 1, 1, 1])
    points = ListProperty([])

    def __init__(self, color=(1, 1, 1, 1), points=None, **kwargs):
        super().__init__(**kwargs)
        self.color = color
        self.points = points or []
        self._graph_ref = None
        self.bind(points=lambda *_: self._graph_ref and self._graph_ref._trigger_redraw())

# -------------------------------------------------------------
# Graph Widget
# -------------------------------------------------------------
class Graph(Widget):
    xmin = NumericProperty(0)
    xmax = NumericProperty(100)
    ymin = NumericProperty(0)
    ymax = NumericProperty(1)
    background_color = ListProperty([0, 0, 0, 1])
    border_color = ListProperty([0.4, 1, 0.4, 0.3])
    tick_color = ListProperty([0.3, 0.9, 0.4, 0.6])
    draw_border = BooleanProperty(True)
    x_ticks_major = NumericProperty(10)
    y_ticks_major = NumericProperty(5)
    x_grid = BooleanProperty(False)
    y_grid = BooleanProperty(False)
    padding = NumericProperty(10)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._plots = []
        self._mesh_instr = {}
        self._trigger_redraw = Clock.create_trigger(self._redraw)

        with self.canvas.before:
            self._bg = Color(rgba=self.background_color)
            self._rect = Rectangle(pos=self.pos, size=self.size)
        with self.canvas.after:
            self._border_c = Color(rgba=self.border_color)
            self._border = Line(rectangle=(0, 0, 0, 0), width=1)

        self.bind(pos=self._trigger_redraw, size=self._trigger_redraw)
        self.bind(xmin=self._trigger_redraw, xmax=self._trigger_redraw,
                  ymin=self._trigger_redraw, ymax=self._trigger_redraw)

    # ---------------------------------------------------------
    def add_plot(self, plot):
        if plot in self._plots:
            return
        self._plots.append(plot)
        plot._graph_ref = self
        instr = InstructionGroup()
        instr.add(Color(rgba=plot.color))
        line = Line(points=[], width=1.2)
        instr.add(line)
        self.canvas.add(instr)
        self._mesh_instr[plot] = (instr, line)
        self._trigger_redraw()

    def remove_plot(self, plot):
        if plot in self._plots:
            self.canvas.remove(self._mesh_instr[plot][0])
            del self._mesh_instr[plot]
            self._plots.remove(plot)
            plot._graph_ref = None
            self._trigger_redraw()

    # ---------------------------------------------------------
    def _redraw(self, *_):
        if not self.get_parent_window():
            return

        x, y = self.pos
        w, h = self.size
        pad = self.padding
        gx, gy = x + pad, y + pad
        gw, gh = w - 2 * pad, h - 2 * pad

        self._bg.rgba = self.background_color
        self._border_c.rgba = self.border_color
        self._rect.pos, self._rect.size = self.pos, self.size

        if self.draw_border:
            self._border.rectangle = (x, y, w, h)
        else:
            self._border.rectangle = (0, 0, 0, 0)

        # Grid (optional)
        self.canvas.remove_group("grid")
        if self.x_grid:
            with self.canvas:
                Color(*self.tick_color)
                for i in range(1, self.x_ticks_major):
                    xx = gx + (gw / self.x_ticks_major) * i
                    Line(points=[xx, y + pad, xx, y + h - pad], group="grid")
        if self.y_grid:
            with self.canvas:
                Color(*self.tick_color)
                for i in range(1, self.y_ticks_major):
                    yy = gy + (gh / self.y_ticks_major) * i
                    Line(points=[x + pad, yy, x + w - pad, yy], group="grid")

        # Draw plots
        for plot in self._plots:
            pts = []
            for px, py in plot.points:
                if self.xmax == self.xmin or self.ymax == self.ymin:
                    continue
                sx = gx + ((px - self.xmin) / (self.xmax - self.xmin)) * gw
                sy = gy + ((py - self.ymin) / (self.ymax - self.ymin)) * gh
                pts.extend((sx, sy))
            _, line = self._mesh_instr[plot]
            line.points = pts

    # Manuelles Triggern (für externe Calls)
    def refresh(self):
        self._trigger_redraw()
