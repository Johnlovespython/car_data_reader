import sys
import random
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, 
                             QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QStackedWidget, QTableWidget, QHeaderView, 
                             QSplitter, QFrame, QTableWidgetItem)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QSize, QTimer

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class RealTimePlotCanvas(FigureCanvas):
    """დინამიური Matplotlib Canvas გრაფიკისთვის"""
    def __init__(self, parent=None, width=5, height=3, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor='#121816')
        self.axes = self.fig.add_subplot(111)
        self.axes.set_facecolor('#1b2421')
        
        self.axes.tick_params(colors='#e2e8f0', labelsize=8)
        for spine in self.axes.spines.values():
            spine.set_color('#2d3748')

        super().__init__(self.fig)
        self.setParent(parent)

        self.max_points = 30
        self.x_data = list(range(self.max_points))
        self.y_data = [0.0] * self.max_points
        
        # ხაზის შექმნა
        self.line, = self.axes.plot(self.x_data, self.y_data, color='#38bdf8', linewidth=2)
        self.axes.grid(True, color='#2d3748', linestyle='--', alpha=0.5)

    def set_line_color(self, color_hex):
        self.line.set_color(color_hex)

    def update_figure(self, new_data_list):
        self.y_data = new_data_list[-self.max_points:]
        self.line.set_ydata(self.y_data)
        
        y_min, y_max = min(self.y_data), max(self.y_data)
        margin = max(5.0, (y_max - y_min) * 0.2)
        self.axes.set_ylim(y_min - margin, y_max + margin)
        
        self.draw()


class SnifferPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Horizontal)

        # --- LEFT PANEL (60%): Main CAN Live Table ---
        self.can_table = QTableWidget(0, 9)
        self.can_table.setHorizontalHeaderLabels([
            "Timestamp", "ID", "Ext", "RTR", "Dir", "Bus", "Len", "ASCII", "Data"
        ])
        header = self.can_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionResizeMode(8, QHeaderView.Stretch)

        self.can_table.setStyleSheet("""
            QTableWidget {
                background-color: #1b2421;
                gridline-color: #2d3748;
                color: #e2e8f0;
                font-size: 13px;
            }
            QHeaderView::section {
                background-color: #0f766e;
                color: white;
                font-weight: bold;
                padding: 4px;
                border: 1px solid #115e59;
            }
        """)

        # --- RIGHT PANEL (40%): Dashboard ---
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setAlignment(Qt.AlignTop)

        # 1. Signals Table (Signal ID / Signal Value)
        signals_header = QLabel("Decoded Signals (Click row to view graph)")
        signals_header.setStyleSheet("color: #10b981; font-size: 14px; font-weight: bold; margin-bottom: 2px;")
        right_layout.addWidget(signals_header)

        self.table = QTableWidget(2, 2)
        self.table.setHorizontalHeaderLabels(["Signal ID", "Signal Value"])
        header2 = self.table.horizontalHeader()
        header2.setSectionResizeMode(0, QHeaderView.Interactive)
        header2.setSectionResizeMode(1, QHeaderView.Stretch)
        
        # ინიციალიზაცია 2 სიგნალისთვის
        self.table.setItem(0, 0, QTableWidgetItem("0x208 (Engine RPM)"))
        self.table.setItem(0, 1, QTableWidgetItem("100.0"))
        
        self.table.setItem(1, 0, QTableWidgetItem("0x316 (Engine Temp)"))
        self.table.setItem(1, 1, QTableWidgetItem("85.0"))

        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #1b2421;
                gridline-color: #2d3748;
                color: #e2e8f0;
                font-size: 12px;
            }
            QTableWidget::item:selected {
                background-color: #0f766e;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #115e59;
                color: white;
                font-weight: bold;
                padding: 3px;
            }
        """)
        self.table.setMaximumHeight(115)
        right_layout.addWidget(self.table)

        # ცხრილის რიგზე დაჭერის Event
        self.table.cellClicked.connect(self.on_signal_selected)

        # --- 2. Matplotlib Visuals (დინამიური გრაფიკი) ---
        self.plot_header = QLabel("Live Visualization: 0x208 (Engine RPM)")
        self.plot_header.setStyleSheet("color: #38bdf8; font-size: 14px; font-weight: bold; margin-top: 5px;")
        right_layout.addWidget(self.plot_header)

        self.plot_canvas = RealTimePlotCanvas(self, width=5, height=2.8)
        right_layout.addWidget(self.plot_canvas)

        # გამყოფი ხაზი
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #2d3748; margin: 5px 0px;")
        right_layout.addWidget(line)

        # 3. Connection Status
        status_header = QLabel("Connection Status:")
        status_header.setStyleSheet("color: #94a3b8; font-size: 13px; font-weight: bold;")
        
        self.lbl_status = QLabel("● Device: ESP32 (COM3)")
        self.lbl_status.setStyleSheet("color: #38bdf8; font-size: 12px; padding-left: 5px;")
        
        self.lbl_baudrate = QLabel("● Baudrate: 500 kbps")
        self.lbl_baudrate.setStyleSheet("color: #e2e8f0; font-size: 12px; padding-left: 5px;")

        right_layout.addWidget(status_header)
        right_layout.addWidget(self.lbl_status)
        right_layout.addWidget(self.lbl_baudrate)

        # 4. Live Statistics
        stats_header = QLabel("Live Statistics:")
        stats_header.setStyleSheet("color: #94a3b8; font-size: 13px; font-weight: bold; margin-top: 5px;")

        self.lbl_fps = QLabel("Frames / Sec: 60 fps")
        self.lbl_fps.setStyleSheet("color: #10b981; font-size: 13px; font-weight: bold; padding-left: 5px;")

        right_layout.addWidget(stats_header)
        right_layout.addWidget(self.lbl_fps)

        # მარჯვენა პანელის სტილი
        self.right_panel.setStyleSheet("""
            QWidget {
                background-color: #161e1b;
                border: 1px solid #2d3748;
                border-radius: 6px;
            }
            QLabel {
                border: none;
            }
        """)

        splitter.addWidget(self.can_table)
        splitter.addWidget(self.right_panel)
        splitter.setSizes([550, 450])

        layout.addWidget(splitter)
        self.setLayout(layout)

        self.active_signal_index = 0  # 0 = 0x208, 1 = 0x316
        
        # სიგნალი 1 (0x208 RPM): თავიდან სტაბილურია (100), მერე იზრდება
        self.signal_1_history = [100.0] * 30
        self.step_counter_1 = 0

        # სიგნალი 2 (0x316 Temp): ნელ-ნელა იმატებს (85-დან 110-მდე)
        self.signal_2_history = [85.0] * 30
        self.step_counter_2 = 0

        # ტაიმერი მონაცემების გენერაციისთვის
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.generate_mock_data)
        self.timer.start(200)

        self.table.selectRow(0)

    def on_signal_selected(self, row, column):
        self.active_signal_index = row
        if row == 0:
            self.plot_header.setText("Live Visualization: 0x208 (Engine RPM)")
            self.plot_header.setStyleSheet("color: #38bdf8; font-size: 14px; font-weight: bold; margin-top: 5px;")
            self.plot_canvas.set_line_color('#38bdf8')  # ლურჯი ხაზი
        else:
            self.plot_header.setText("Live Visualization: 0x316 (Engine Temp)")
            self.plot_header.setStyleSheet("color: #f59e0b; font-size: 14px; font-weight: bold; margin-top: 5px;")
            self.plot_canvas.set_line_color('#f59e0b')  # ნარინჯისფერი ხაზი

    def generate_mock_data(self):
        self.step_counter_1 += 1
        if self.step_counter_1 < 20:
            val_1 = 100 + random.uniform(-1.5, 1.5)
        elif 20 <= self.step_counter_1 < 40:
            val_1 = self.signal_1_history[-1] + random.uniform(3.5, 7.0)
        else:
            self.step_counter_1 = 0
            val_1 = 100.0
            
        self.signal_1_history.pop(0)
        self.signal_1_history.append(val_1)
        self.table.setItem(0, 1, QTableWidgetItem(f"{val_1:.1f}"))

        self.step_counter_2 += 1
        if self.step_counter_2 < 30:
            val_2 = self.signal_2_history[-1] + random.uniform(0.1, 0.8)
        else:
            self.step_counter_2 = 0
            val_2 = 85.0

        self.signal_2_history.pop(0)
        self.signal_2_history.append(val_2)
        self.table.setItem(1, 1, QTableWidgetItem(f"{val_2:.1f} °C"))

        if self.active_signal_index == 0:
            self.plot_canvas.update_figure(self.signal_1_history)
        else:
            self.plot_canvas.update_figure(self.signal_2_history)


class HistoryPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        title = QLabel("Saved CAN Logs & History")
        title.setStyleSheet("color: #10b981; font-size: 20px; font-weight: bold;")
        
        history_table = QTableWidget(5, 3)
        history_table.setHorizontalHeaderLabels(["ID", "Data Byte", "Timestamp"])
        history_table.setStyleSheet("gridline-color: #2d3748; background-color: #1b2421; color: #e2e8f0;")

        layout.addWidget(title)
        layout.addWidget(history_table)
        self.setLayout(layout)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SavvyPy - CAN Bus Analyzer")
        self.setGeometry(100, 100, 1200, 700)
        self.setWindowIcon(QIcon("icon.jpg"))
        self.initUI()

    def initUI(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #121816;
                color: #e2e8f0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)

        top_bar_layout = QHBoxLayout()
        button_style = """
            QPushButton {
                color: #ffffff;
                background-color: #0f766e;
                border: 1px solid #115e59;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                padding: 5px 12px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """

        self.connect_button = QPushButton(" Connect", self)
        self.connect_button.setFixedSize(130, 36)
        self.connect_button.setStyleSheet(button_style)

        self.sniff_button = QPushButton(" Start Sniffing", self)
        self.sniff_button.setFixedSize(150, 36)
        self.sniff_button.setStyleSheet(button_style)

        self.btn_history = QPushButton(" History", self)
        self.btn_history.setFixedSize(130, 36)
        self.btn_history.setStyleSheet(button_style)

        top_bar_layout.addWidget(self.connect_button)
        top_bar_layout.addWidget(self.sniff_button)
        top_bar_layout.addWidget(self.btn_history)
        top_bar_layout.addStretch()

        main_layout.addLayout(top_bar_layout)

        self.stacked_widget = QStackedWidget()
        self.sniffer_page = SnifferPage()
        self.history_page = HistoryPage()

        self.stacked_widget.addWidget(self.sniffer_page)
        self.stacked_widget.addWidget(self.history_page)

        main_layout.addWidget(self.stacked_widget)

        self.sniff_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        self.btn_history.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())