from kivy.graphics import Color, Ellipse


class VPDScatterRenderer:
    def __init__(self, graph):
        self.graph = graph
        with self.graph.canvas.after:
            Color(1.0, 0.85, 0.2, 0.85)
            self.p_in = Ellipse(size=(30, 30), pos=(-1000, -1000))

            Color(0.3, 1.0, 0.3, 0.85)
            self.p_ex = Ellipse(size=(30, 30), pos=(-1000, -1000))

            Color(1.0, 0.2, 0.6, 0.85)
            self.p_outside = Ellipse(size=(30, 30), pos=(-1000, -1000))

            Color(0.2, 0.8, 1.0, 0.85)
            self.p_inside = Ellipse(size=(30, 30), pos=(-1000, -1000))

    def _place_point(self, ellipse, temp, hum):
        gx, gy = self.graph.pos
        gw, gh = self.graph.size

        xr = max(self.graph.xmax - self.graph.xmin, 0.0001)
        yr = max(self.graph.ymax - self.graph.ymin, 0.0001)

        hum = min(max(hum, self.graph.xmin), self.graph.xmax)
        temp = min(max(temp, self.graph.ymin), self.graph.ymax)

        x = gx + (hum - self.graph.xmin) / xr * gw
        y = gy + (1.0 - (temp - self.graph.ymin) / yr) * gh

        ellipse.pos = (
            x - ellipse.size[0] / 2,
            y - ellipse.size[1] / 2,
        )

    def update_points(self, coords_dict):
        mapping = {
            "in": self.p_in,
            "ex": self.p_ex,
            "outside": self.p_outside,
            "inside": self.p_inside,
        }

        for key, ellipse in mapping.items():
            hx, ty = coords_dict.get(key, (None, None))
            if hx is not None and ty is not None:
                self._place_point(ellipse, ty, hx)
            else:
                ellipse.pos = (-1000, -1000)
