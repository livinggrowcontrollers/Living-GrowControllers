import unittest

from dashboard_gui.ui.common.graph_chart_content.graph_mesh import (
    clear_graph_mesh,
    update_graph_mesh,
)


class FakeGraph:
    xmin = 0.0
    xmax = 10.0
    ymin = 0.0
    ymax = 100.0
    pos = (300.0, 180.0)
    view_pos = (37.5, 22.25)
    view_size = (200.0, 80.0)


class FakePlot:
    points = [(0.0, 25.0), (10.0, 75.0)]


class FakeMesh:
    def __init__(self):
        self.vertices = None
        self.indices = None
        self.texture = "old"
        self.mode = None


class GraphMeshTests(unittest.TestCase):
    def test_fill_uses_the_exact_inner_plot_area(self):
        mesh = FakeMesh()

        update_graph_mesh(FakeGraph(), FakePlot(), mesh)

        self.assertEqual(
            mesh.vertices,
            [
                337.5,
                222.25,
                0,
                0,
                337.5,
                202.25,
                0,
                0,
                537.5,
                262.25,
                0,
                0,
                537.5,
                202.25,
                0,
                0,
            ],
        )
        self.assertEqual(mesh.indices, [0, 1, 2, 3])
        self.assertEqual(mesh.mode, "triangle_strip")
        self.assertIsNone(mesh.texture)

    def test_empty_inner_plot_area_clears_stale_geometry(self):
        mesh = FakeMesh()
        graph = FakeGraph()
        graph.view_size = (0.0, 80.0)

        update_graph_mesh(graph, FakePlot(), mesh)

        self.assertEqual(mesh.vertices, [])
        self.assertEqual(mesh.indices, [])
        self.assertIsNone(mesh.texture)

    def test_clear_graph_mesh_is_safe_without_a_mesh(self):
        self.assertIsNone(clear_graph_mesh(None))


if __name__ == "__main__":
    unittest.main()
