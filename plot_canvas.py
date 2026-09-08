from PyQt5.QtWidgets import QSizePolicy
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class UniversalPlotCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=3, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor='#121816')
        self.axes = self.fig.add_subplot(111)
        self.axes.set_facecolor('#1b2421')

        self.axes.tick_params(colors='#e2e8f0', labelsize=8)
        for spine in self.axes.spines.values():
            spine.set_color('#2d3748')

        super().__init__(self.fig)
        self.setParent(parent)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.updateGeometry()

        self.max_points = 30
        self.x_data = list(range(self.max_points))
        self.y_data = [0.0] * self.max_points

        self.line, = self.axes.plot(self.x_data, self.y_data, color='#10b981', linewidth=2)
        self.axes.grid(True, color='#2d3748', linestyle='--', alpha=0.5)
        self.fig.tight_layout()

    def update_figure(self, history_data):
        if not history_data:
            return

        self.y_data = history_data[-self.max_points:]
        if len(self.y_data) < self.max_points:
            fill_val = self.y_data[0]
            self.y_data = [fill_val] * (self.max_points - len(self.y_data)) + self.y_data

        self.line.set_ydata(self.y_data)
        y_min, y_max = min(self.y_data), max(self.y_data)
        margin = max(2.0, (y_max - y_min) * 0.2)
        self.axes.set_ylim(y_min - margin, y_max + margin)
        self.draw()