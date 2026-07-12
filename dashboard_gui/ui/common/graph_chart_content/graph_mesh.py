# dashboard_gui/ui/common/graph_chart_content/graph_mesh.py
from dashboard_gui.ui.scaling_utils import dp_scaled

def clear_graph_mesh(mesh):
    """Leert die Fill-Fläche vollständig, inklusive alter Triangle-Indizes."""
    if not mesh:
        return
    mesh.vertices = []
    mesh.indices = []
    mesh.texture = None

def clear_graph_series(plot, mesh, glow_plot=None):
    """Zentraler Graph-Reset für Linie, Glow-Linie und Fill-Mesh."""
    if plot:
        plot.points = []
    if glow_plot:
        glow_plot.points = []
    clear_graph_mesh(mesh)

def update_graph_mesh(graph, plot, mesh):
    """
    Berechnet die Vertices für die transparente Fill-Fläche (Mesh) eines Kivy-Graphen.
    Optimiert gegen Flackern durch Pixel-Rundung und Stabilitäts-Checks.
    """
    if not plot.points or len(plot.points) < 2:
        clear_graph_mesh(mesh)
        return

    points = plot.points
    if len(points) > 150:
        points = points[::len(points) // 100]  # Dynamic-Fallback-Downsampling

    g_pos = graph.pos
    g_size = graph.size

    pad = dp_scaled(0)
    plot_w = g_size[0] - 2 * pad
    plot_h = g_size[1] - 2 * pad

    x_min, x_max = graph.xmin, graph.xmax
    y_min, y_max = graph.ymin, graph.ymax

    x_range = (x_max - x_min) if x_max != x_min else 1.0
    y_range = (y_max - y_min) if y_max != y_min else 1.0

    # Basis-Y-Linie (Boden des Graphen) festlegen und runden
    base_y = round(g_pos[1] + pad)

    vertices = []
    for pt in points:
        # Exakte Pixel-Positionen berechnen und runden, um Subpixel-Flackern zu verhindern
        px_x = round(g_pos[0] + pad + ((pt[0] - x_min) / x_range) * plot_w)
        px_y = round(g_pos[1] + pad + ((pt[1] - y_min) / y_range) * plot_h)
        
        # Triangle Strip Format: 
        # 1. Oberer Punkt (auf der Plot-Linie)
        vertices.extend([px_x, px_y, 0, 0])
        # 2. Unterer Punkt (auf der Baseline)
        vertices.extend([px_x, base_y, 0, 0])
            
    mesh.vertices = vertices
    # Indizes passend zur Anzahl der Vertices (4 Werte pro Vertex im Kivy-Mesh-Format)
    mesh.indices = list(range(len(vertices) // 4))
    mesh.texture = None
    mesh.mode = 'triangle_strip'
