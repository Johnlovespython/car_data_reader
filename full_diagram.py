import os
import csv
import math
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QMessageBox
from PyQt5.QtCore import Qt, QTimer

class FullDiagramDialog(QDialog):
    def __init__(self, log_data, parent=None):
        super().__init__(parent)
        self.log_data = log_data

        # Window Setup
        self.setWindowTitle(f"Live Full Diagram Analysis - {self.log_data}")
        self.resize(1200, 800)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)

        # Layout Setup
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Matplotlib Figure & Canvas
        plt.style.use('dark_background')
        self.figure = plt.figure(facecolor='#1b2421')
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

        # Filepath Resolution
        self.filepath = self.resolve_filepath(log_data)

        # Dictionary to keep line objects for fast redrawing without clearing axes
        self.axes = {}
        self.lines = {}

        # 1. Initial plot render
        if self.filepath and os.path.exists(self.filepath):
            self.generate_plots()
        else:
            QMessageBox.critical(self, "Error", f"Could not locate log file: {log_data}")

        # 2. Live Update Timer (Triggers every 150ms during active sniffing)
        self.live_timer = QTimer(self)
        self.live_timer.timeout.connect(self.update_live_data)
        self.live_timer.start(150)  # Update interval in milliseconds

    def resolve_filepath(self, log_data):
        clean_filename = log_data.replace("📄 ", "").strip()
        if os.path.exists(clean_filename):
            return clean_filename

        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        return os.path.join(desktop_path, "logs", clean_filename)

    def parse_log_file(self):
        """Reads the CSV file from start to finish to gather current data points."""
        signals = {}
        if not os.path.exists(self.filepath):
            return signals

        try:
            with open(self.filepath, mode="r", encoding="UTF-8") as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip CSV header

                for row in reader:
                    if row and len(row) >= 9:
                        can_id = row[1]
                        try:
                            val = float(row[8])
                            if can_id not in signals:
                                signals[can_id] = []
                            signals[can_id].append(val)
                        except ValueError:
                            continue
        except Exception as e:
            print(f"File reading error during live update: {e}")

        return signals

    def generate_plots(self):
        """Builds the initial subplots layout."""
        signals = self.parse_log_file()
        total_signals = len(signals)

        if total_signals == 0:
            self.figure.suptitle("Waiting for incoming live CAN data...", color='#10b981', fontsize=14)
            self.canvas.draw()
            return

        cols = math.ceil(math.sqrt(total_signals))
        rows = math.ceil(total_signals / cols)

        self.figure.clear()
        self.axes.clear()
        self.lines.clear()

        for idx, (can_id, data_points) in enumerate(signals.items(), start=1):
            ax = self.figure.add_subplot(rows, cols, idx)
            ax.set_facecolor('#111827')
            
            # Save the line object reference for fast updates
            line, = ax.plot(data_points, color='#10b981', linewidth=1.5)
            
            ax.set_title(f"Signal ID: {can_id}", color='#e2e8f0', fontsize=10, fontweight='bold')
            ax.tick_params(colors='#94a3b8', labelsize=8)
            ax.grid(True, color='#2d3748', linestyle='--', linewidth=0.5)

            for spine in ax.spines.values():
                spine.set_color('#2d3748')

            self.axes[can_id] = ax
            self.lines[can_id] = line

        self.figure.tight_layout(pad=2.0)
        self.canvas.draw()

    def update_live_data(self):
        """Periodic method triggered by QTimer to pull new CSV entries dynamically."""
        signals = self.parse_log_file()

        # If a new CAN ID appeared that wasn't in the grid, rebuild the grid
        if set(signals.keys()) != set(self.lines.keys()):
            self.generate_plots()
            return

        # Otherwise, update existing lines efficiently without flickering
        for can_id, data_points in signals.items():
            if can_id in self.lines:
                # Update X and Y data of the plot line
                self.lines[can_id].set_ydata(data_points)
                self.lines[can_id].set_xdata(range(len(data_points)))
                
                # Rescale axis bounds dynamically as new points arrive
                self.axes[can_id].relim()
                self.axes[can_id].autoscale_view(True, True, True)

        # Redraw efficiently on idle
        self.canvas.draw_idle()

    def closeEvent(self, event):
        """Stop timer upon closing the dialog to release resources."""
        self.live_timer.stop()
        super().closeEvent(event)