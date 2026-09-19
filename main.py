import sys
import os
import random
from datetime import datetime
from full_diagram import FullDiagramDialog
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QStackedWidget, QTableWidget, QHeaderView,
    QSplitter, QTableWidgetItem, QDialog, QComboBox, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
import serial.tools.list_ports
import matplotlib
matplotlib.use('Qt5Agg')

# Local Module Imports
from settings_page import SettingsDialog
from logger import CANLogger
from plot_canvas import UniversalPlotCanvas
from history_page import HistoryPage
from ai_helper_page import AIHelperPage
from can_serial_reader import CANSerialReader, CANFrame

# Special "port" value used to fall back to the built-in pseudo-data
# generator, so you can still exercise the UI with no ESP32 attached.
SIMULATE_PORT_TOKEN = "SIMULATE"


class ConnectionDialog(QDialog):
    """COM Port Selection Popup Dialog"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Serial Port")
        self.setFixedSize(320, 160)

        self.setStyleSheet("""
            QDialog {
                background-color: #121816;
                color: #e2e8f0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel { color: #e2e8f0; font-size: 13px; }
            QComboBox {
                background-color: #1b2421;
                color: #e2e8f0;
                border: 1px solid #2d3748;
                border-radius: 4px;
                padding: 5px;
            }
            QPushButton {
                background-color: #0f766e;
                color: white;
                border: 1px solid #115e59;
                border-radius: 5px;
                padding: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #059669; }
        """)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Available COM Ports:"))

        self.port_combo = QComboBox()
        layout.addWidget(self.port_combo)

        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh")
        self.btn_connect = QPushButton("Connect")

        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_connect)
        layout.addLayout(btn_layout)

        self.btn_refresh.clicked.connect(self.populate_ports)
        self.btn_connect.clicked.connect(self.accept)

        self.populate_ports()

    def populate_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.port_combo.addItem(f"{p.device} ({p.description})", p.device)
        # Always offer a no-hardware fallback so the UI can be tested
        # without the ESP32 plugged in.
        self.port_combo.addItem("Simulate (no hardware)", SIMULATE_PORT_TOKEN)

    def get_selected_port(self):
        return self.port_combo.currentData()


class SnifferPage(QWidget):

    status_update = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self.logger = CANLogger()
        self.is_recording = False
        self.current_log_filepath = None  # Holds active recording path

        main_splitter = QSplitter(Qt.Horizontal)

        # --- LEFT PANEL: CAN Live Table ---
        self.can_table = QTableWidget(0, 9)
        self.can_table.setHorizontalHeaderLabels([
            "Timestamp", "ID", "Ext", "RTR", "Dir", "Bus", "Len", "ASCII", "Data"
        ])
        header = self.can_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionResizeMode(8, QHeaderView.Stretch)
        self.can_table.setStyleSheet("""
            QTableWidget { background-color: #1b2421; gridline-color: #2d3748; color: #e2e8f0; font-size: 13px; }
            QHeaderView::section { background-color: #0f766e; color: white; font-weight: bold; padding: 4px; border: 1px solid #115e59; }
        """)

        # --- RIGHT PANEL ---
        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.setStyleSheet("""
            QSplitter::handle { background-color: #2d3748; height: 4px; }
            QSplitter::handle:hover { background-color: #10b981; }
        """)

        # 1. Decoded Signals Table
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(5, 5, 5, 5)

        signals_header = QLabel("Decoded Signals")
        signals_header.setStyleSheet("color: #10b981; font-size: 14px; font-weight: bold; margin-bottom: 2px;")
        table_layout.addWidget(signals_header)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Signal ID", "Signal Value"])
        header2 = self.table.horizontalHeader()
        header2.setSectionResizeMode(0, QHeaderView.Interactive)
        header2.setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setStyleSheet("""
            QTableWidget { background-color: #1b2421; gridline-color: #2d3748; color: #e2e8f0; font-size: 12px; }
            QTableWidget::item:selected { background-color: #0f766e; color: #ffffff; }
            QHeaderView::section { background-color: #115e59; color: white; font-weight: bold; padding: 3px; }
        """)
        table_layout.addWidget(self.table)
        self.table.cellClicked.connect(self.on_signal_selected)

        # 2. Graph Section with Full Diagram Button Layout Fix
        plot_container = QWidget()
        plot_layout = QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(5, 5, 5, 5)

        # Header Row Layout
        header_row = QHBoxLayout()

        self.plot_header = QLabel("Live Visualization: Select a signal")
        self.plot_header.setStyleSheet("color: #10b981; font-size: 14px; font-weight: bold;")

        self.full_diagram_btn = QPushButton("Show full diagram", self)
        self.full_diagram_btn.setStyleSheet("""
            QPushButton { 
                background-color: #0f766e; 
                color: white; 
                font-weight: bold; 
                padding: 4px 10px; 
                border-radius: 4px; 
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.full_diagram_btn.clicked.connect(self.open_live_full_diagrams)

        header_row.addWidget(self.plot_header)
        header_row.addStretch()
        header_row.addWidget(self.full_diagram_btn)

        plot_layout.addLayout(header_row)

        self.plot_canvas = UniversalPlotCanvas(self, width=5, height=3)
        plot_layout.addWidget(self.plot_canvas)

        right_splitter.addWidget(table_container)
        right_splitter.addWidget(plot_container)
        right_splitter.setSizes([200, 400])

        main_splitter.addWidget(self.can_table)
        main_splitter.addWidget(right_splitter)
        main_splitter.setSizes([550, 450])

        layout.addWidget(main_splitter)
        self.setLayout(layout)

        self.signals_data = {}
        self.previous_signal_values = {}
        self.signal_row_map = {}
        self.selected_signal_id = None

        # Simulate-mode timer (no hardware attached)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.simulate_incoming_can_data)

        # Real hardware: background thread owning the serial port
        self.can_reader = None

    # ------------------------------------------------------------------
    # Starting / stopping data acquisition (real hardware or simulation)
    # ------------------------------------------------------------------
    def start_acquisition(self, port: str):
        """port is either a real COM/tty device path, or SIMULATE_PORT_TOKEN."""
        if port == SIMULATE_PORT_TOKEN:
            self.timer.start(200)
            self.status_update.emit("Simulating CAN data (no hardware)")
            return

        self.can_reader = CANSerialReader(port, baudrate=115200)
        self.can_reader.frame_received.connect(self.process_incoming_frame)
        self.can_reader.status_message.connect(self.status_update.emit)
        self.can_reader.connection_lost.connect(self._on_connection_lost)
        self.can_reader.start()

    def stop_acquisition(self):
        if self.timer.isActive():
            self.timer.stop()
        if self.can_reader is not None:
            self.can_reader.stop()
            self.can_reader = None

    def is_acquisition_active(self) -> bool:
        return self.timer.isActive() or (self.can_reader is not None and self.can_reader.isRunning())

    def _on_connection_lost(self, message: str):
        self.status_update.emit(message)
        self.stop_acquisition()

    def open_live_full_diagrams(self):
        """Opens the live diagram window for the current sniffing session."""
        current_log = getattr(self, 'current_log_filepath', None)

        if not current_log or not os.path.exists(current_log):
            QMessageBox.warning(
                self,
                "Sniffing Not Active",
                "Please start sniffing/logging first to view full live diagrams."
            )
            return

        dialog = FullDiagramDialog(log_data=current_log, parent=self)
        dialog.exec_()

    def clear_data(self):
        self.can_table.setRowCount(0)
        self.table.setRowCount(0)

        self.signal_row_map.clear()
        self.signals_data.clear()
        self.previous_signal_values.clear()
        self.selected_signal_id = None

        if hasattr(self.plot_canvas, 'ax'):
            self.plot_canvas.ax.clear()
            self.plot_canvas.draw()

        self.plot_header.setText("Live Visualization: Select a signal")

    # ------------------------------------------------------------------
    # Real CAN frame handling (from the ESP32 bridge)
    # ------------------------------------------------------------------
    def process_incoming_frame(self, frame: CANFrame):
        """
        Handles one real CAN frame coming off the ESP32 bridge.
        Logs the raw frame in full, and feeds a numeric view of it into
        the existing decoded-signal table / plot so you keep the same
        UI you already built. Real per-signal decoding (via a DBC file)
        can replace the "numeric_value" heuristic below later.
        """
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        data_hex = " ".join(f"{b:02X}" for b in frame.data)
        ascii_repr = "".join(chr(b) if 32 <= b < 127 else "." for b in frame.data)

        if self.is_recording:
            self.logger.log_frame(
                timestamp=timestamp,
                can_id=frame.can_id,
                ext="1" if frame.extended else "0",
                rtr="1" if frame.rtr else "0",
                direction="Rx",
                bus="1",
                length=str(frame.dlc),
                ascii_val=ascii_repr,
                data_bytes=data_hex,
            )

        # --- Raw frame table (left panel) ---
        row_idx = self.can_table.rowCount()
        self.can_table.insertRow(row_idx)
        self.can_table.setItem(row_idx, 0, QTableWidgetItem(timestamp))
        self.can_table.setItem(row_idx, 1, QTableWidgetItem(frame.can_id))
        self.can_table.setItem(row_idx, 2, QTableWidgetItem("1" if frame.extended else "0"))
        self.can_table.setItem(row_idx, 3, QTableWidgetItem("1" if frame.rtr else "0"))
        self.can_table.setItem(row_idx, 4, QTableWidgetItem("Rx"))
        self.can_table.setItem(row_idx, 5, QTableWidgetItem("1"))
        self.can_table.setItem(row_idx, 6, QTableWidgetItem(str(frame.dlc)))
        self.can_table.setItem(row_idx, 7, QTableWidgetItem(ascii_repr))
        self.can_table.setItem(row_idx, 8, QTableWidgetItem(data_hex))
        self.can_table.scrollToBottom()

        # --- Decoded signal panel / plot (right panel) ---
        # Placeholder decoding: treat the first two data bytes as a
        # big-endian numeric value per CAN ID, purely so the existing
        # plot keeps working. Swap this out once you add real DBC
        # signal definitions for your car.
        if len(frame.data) >= 2:
            numeric_value = (frame.data[0] << 8) | frame.data[1]
        elif len(frame.data) == 1:
            numeric_value = frame.data[0]
        else:
            numeric_value = 0

        self._update_decoded_signal(frame.can_id, numeric_value)

    def _update_decoded_signal(self, signal_id: str, new_value: float):
        if signal_id not in self.signals_data:
            self.signals_data[signal_id] = []
        self.signals_data[signal_id].append(new_value)

        old_val = self.previous_signal_values.get(signal_id)
        has_changed = (old_val is not None) and (old_val != new_value)
        self.previous_signal_values[signal_id] = new_value

        if signal_id not in self.signal_row_map:
            sig_row = self.table.rowCount()
            self.table.insertRow(sig_row)
            self.signal_row_map[signal_id] = sig_row
        else:
            sig_row = self.signal_row_map[signal_id]

        id_item = QTableWidgetItem(signal_id)
        val_item = QTableWidgetItem(f"{new_value:.2f}")

        if has_changed:
            highlight_color = QColor(153, 27, 27)
            id_item.setBackground(highlight_color)
            val_item.setBackground(highlight_color)

        self.table.setItem(sig_row, 0, id_item)
        self.table.setItem(sig_row, 1, val_item)

        if has_changed:
            QTimer.singleShot(300, lambda r=sig_row: self.reset_row_background(r))

        if not self.selected_signal_id:
            self.selected_signal_id = signal_id
            self.plot_header.setText(f"Live Visualization: {signal_id}")

        if self.selected_signal_id == signal_id:
            self.plot_canvas.update_figure(self.signals_data[signal_id])

    def reset_row_background(self, row):
        default_color = QColor(27, 36, 33)
        id_item = self.table.item(row, 0)
        val_item = self.table.item(row, 1)

        if id_item:
            id_item.setBackground(default_color)
        if val_item:
            val_item.setBackground(default_color)

    def on_signal_selected(self, row, column):
        signal_id = self.table.item(row, 0).text()
        self.selected_signal_id = signal_id
        self.plot_header.setText(f"Live Visualization: {signal_id}")
        if signal_id in self.signals_data:
            self.plot_canvas.update_figure(self.signals_data[signal_id])

    # ------------------------------------------------------------------
    # Simulate mode (no hardware) - kept from the original app so the UI
    # stays testable without an ESP32 attached.
    # ------------------------------------------------------------------
    def simulate_incoming_can_data(self):
        mock_signals = ["0x208", "0x316", "0x1A0", "0x420"]
        chosen_id = random.choice(mock_signals)

        if chosen_id not in self.signals_data:
            val = random.uniform(50, 100)
        else:
            prev_val = self.signals_data[chosen_id][-1]
            val = prev_val + random.uniform(-2, 3)

        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        if self.is_recording:
            self.logger.log_frame(
                timestamp=timestamp,
                can_id=chosen_id,
                ext="0", rtr="0", direction="Rx", bus="1",
                length=str(len(f"{val:.2f}")),
                ascii_val=".",
                data_bytes=f"{val:.2f}"
            )

        row_idx = self.can_table.rowCount()
        self.can_table.insertRow(row_idx)
        self.can_table.setItem(row_idx, 0, QTableWidgetItem(timestamp))
        self.can_table.setItem(row_idx, 1, QTableWidgetItem(chosen_id))
        self.can_table.setItem(row_idx, 8, QTableWidgetItem(f"{val:.2f}"))
        self.can_table.scrollToBottom()

        self._update_decoded_signal(chosen_id, val)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SavvyPy - Dynamic CAN Analyzer")
        self.setGeometry(100, 100, 1200, 700)
        self.selected_port = None
        self.initUI()

    def initUI(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #121816;
                color: #e2e8f0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)

        # --- TOP BUTTONS BAR ---
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
            QPushButton:hover { background-color: #059669; }
            QPushButton:disabled {
                background-color: #1b2421;
                color: #4a5568;
                border: 1px solid #2d3748;
            }
        """

        self.connect_button = QPushButton(" Connect", self)
        self.connect_button.setFixedSize(130, 36)
        self.connect_button.setStyleSheet(button_style)

        self.sniff_button = QPushButton(" Start Sniffing", self)
        self.sniff_button.setFixedSize(150, 36)
        self.sniff_button.setStyleSheet(button_style)
        self.sniff_button.setEnabled(False)

        self.btn_history = QPushButton(" History", self)
        self.btn_history.setFixedSize(130, 36)
        self.btn_history.setStyleSheet(button_style)

        self.btn_analyze = QPushButton("🔍 Analyze", self)
        self.btn_analyze.setFixedSize(120, 36)
        self.btn_analyze.setStyleSheet(button_style)
        self.btn_analyze.setVisible(False)

        self.btn_settings = QPushButton("⚙ Settings", self)
        self.btn_settings.setFixedSize(120, 36)
        self.btn_settings.setStyleSheet(button_style)

        top_bar_layout.addWidget(self.connect_button)
        top_bar_layout.addWidget(self.sniff_button)
        top_bar_layout.addWidget(self.btn_history)
        top_bar_layout.addStretch()
        top_bar_layout.addWidget(self.btn_analyze)
        top_bar_layout.addWidget(self.btn_settings)

        main_layout.addLayout(top_bar_layout)

        # --- PAGES STACK ---
        self.stacked_widget = QStackedWidget()
        self.sniffer_page = SnifferPage()
        self.history_page = HistoryPage()
        self.ai_helper_page = AIHelperPage()

        self.stacked_widget.addWidget(self.sniffer_page)
        self.stacked_widget.addWidget(self.history_page)
        self.stacked_widget.addWidget(self.ai_helper_page)

        main_layout.addWidget(self.stacked_widget)

        # --- EVENT SIGNALS ---
        self.sniff_button.clicked.connect(self.handle_sniff_click)
        self.btn_history.clicked.connect(self.show_history_page)
        self.connect_button.clicked.connect(self.open_connection_dialog)
        self.btn_settings.clicked.connect(self.open_settings_dialog)
        self.btn_analyze.clicked.connect(self.go_to_ai_helper)

        self.history_page.log_selected_signal.connect(self.handle_log_selection)
        self.sniffer_page.status_update.connect(lambda m: self.statusBar().showMessage(m, 4000))

    def go_to_ai_helper(self):
        self.stacked_widget.setCurrentWidget(self.ai_helper_page)

    def handle_log_selection(self, is_selected: bool):
        if self.stacked_widget.currentWidget() == self.history_page:
            self.btn_analyze.setVisible(is_selected)

    def handle_sniff_click(self):
        if self.stacked_widget.currentWidget() != self.sniffer_page:
            self.stacked_widget.setCurrentWidget(self.sniffer_page)
            self.btn_analyze.setVisible(False)
            self.update_sniff_button_label()
        else:
            self.toggle_sniffing()

    def show_history_page(self):
        self.history_page.load_log_files()
        self.stacked_widget.setCurrentWidget(self.history_page)
        self.update_sniff_button_label()

        has_selection = len(self.history_page.log_list.selectedItems()) > 0
        self.btn_analyze.setVisible(has_selection)

    def update_sniff_button_label(self):
        is_on_sniffer = (self.stacked_widget.currentWidget() == self.sniffer_page)
        is_active = self.sniffer_page.is_acquisition_active()

        if not is_on_sniffer:
            self.sniff_button.setText(" Sniffer page")
        else:
            if is_active:
                self.sniff_button.setText(" Stop Sniffing")
            else:
                self.sniff_button.setText(" Start Sniffing")

    def open_connection_dialog(self):
        dialog = ConnectionDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            selected_port = dialog.get_selected_port()
            if selected_port:
                self.selected_port = selected_port
                label = "Simulate mode" if selected_port == SIMULATE_PORT_TOKEN else selected_port
                self.connect_button.setText(f" Connected ({label})")
                self.connect_button.setStyleSheet("""
                    QPushButton {
                        color: #ffffff;
                        background-color: #15803d;
                        border: 1px solid #166534;
                        border-radius: 6px;
                        font-size: 14px;
                        font-weight: bold;
                        padding: 5px 12px;
                    }
                """)
                self.sniff_button.setEnabled(True)

    def toggle_sniffing(self):
        # 1. Stop Sniffing & Save Log
        if self.sniffer_page.is_acquisition_active():
            self.sniffer_page.stop_acquisition()
            self.sniffer_page.is_recording = False
            self.sniffer_page.logger.stop_logging()

            self.sniff_button.setText(" Start Sniffing")
            self.sniff_button.setStyleSheet("""
                QPushButton {
                    color: #ffffff;
                    background-color: #0f766e;
                    border: 1px solid #115e59;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 5px 12px;
                }
                QPushButton:hover { background-color: #059669; }
            """)

            self.history_page.load_log_files()
            saved_file = getattr(self.sniffer_page.logger, 'current_filename', 'Desktop/logs')
            self.statusBar().showMessage(f"Log saved: {os.path.basename(saved_file)}", 5000)

        # 2. Start Sniffing
        else:
            if not self.selected_port:
                QMessageBox.warning(self, "No Port Selected", "Please connect to a port first.")
                return

            self.sniffer_page.logger.start_logging()
            self.sniffer_page.is_recording = True

            # Pass the updated file path directly to the SnifferPage instance
            self.sniffer_page.current_log_filepath = self.sniffer_page.logger.current_filename

            self.sniffer_page.clear_data()
            self.sniffer_page.start_acquisition(self.selected_port)

            self.sniff_button.setText(" Stop Sniffing")
            self.sniff_button.setStyleSheet("""
                QPushButton {
                    color: #ffffff;
                    background-color: #b91c1c;
                    border: 1px solid #991b1b;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 5px 12px;
                }
                QPushButton:hover { background-color: #dc2626; }
            """)

            self.statusBar().showMessage("Sniffing & Recording started...", 3000)

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.statusBar().showMessage("Settings updated.", 3000)

    def run_can_analysis(self):
        self.statusBar().showMessage("Running CAN analysis on selected log...", 3000)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())