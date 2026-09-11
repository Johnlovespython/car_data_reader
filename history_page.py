import os
import csv
import gc
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QListWidget, QListWidgetItem, QLabel, QTableWidget, 
    QTableWidgetItem, QComboBox, QSplitter, QHeaderView, QSlider, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from plot_canvas import UniversalPlotCanvas
from full_diagram import FullDiagramDialog

class HistoryPage(QWidget):
    # Custom signal to notify MainWindow whether a log file is selected
    log_selected_signal = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.replay_timer = QTimer(self)
        self.replay_timer.timeout.connect(self.play_next_frame)
        self.replay_data = []
        self.current_index = 0
        self.signal_history = {}
        self.selected_signal_id = None
        self.is_paused = False

        # Initialize UI first so self.log_list exists before signal connections
        self.initUI()

    def initUI(self):
        # Main Layout
        main_layout = QHBoxLayout(self)

        # Splitter for Left and Right Panels
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setStyleSheet("""
            QSplitter::handle { background-color: #2d3748; width: 4px; }
            QSplitter::handle:hover { background-color: #10b981; }
        """)

        # --- LEFT PANEL: Logs List & Buttons ---
        left_widget = QWidget()
        left_panel = QVBoxLayout(left_widget)
        left_panel.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Saved Logs History")
        title.setStyleSheet("color: #10b981; font-size: 16px; font-weight: bold;")
        left_panel.addWidget(title)

        self.log_list = QListWidget()
        self.log_list.setStyleSheet("""
            QListWidget { background-color: #1b2421; color: #e2e8f0; border: 1px solid #2d3748; border-radius: 4px; }
            QListWidget::item:selected { background-color: #0f766e; color: white; }
        """)

        # Single item clicked handler (loads file and notifies MainWindow)
        self.log_list.itemClicked.connect(self.on_log_item_clicked)
        left_panel.addWidget(self.log_list)

        # Buttons block
        list_buttons_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setStyleSheet("""
            QPushButton { background-color: #0f766e; color: white; font-weight: bold; padding: 6px; border-radius: 4px; }
            QPushButton:hover { background-color: #059669; }
        """)
        self.refresh_btn.clicked.connect(self.load_log_files)

        self.delete_btn = QPushButton("🗑 Delete")
        self.delete_btn.setStyleSheet("""
            QPushButton { background-color: #991b1b; color: white; font-weight: bold; padding: 6px; border-radius: 4px; }
            QPushButton:hover { background-color: #dc2626; }
        """)
        self.delete_btn.clicked.connect(self.delete_selected_log)

        self.delete_all_btn = QPushButton("Delete All")
        self.delete_all_btn.setStyleSheet("""
            QPushButton { background-color: #7f1d1d; color: white; font-weight: bold; padding: 6px; border-radius: 4px; }
            QPushButton:hover { background-color: #991b1b; }
        """)
        self.delete_all_btn.clicked.connect(self.delete_all_logs)

        list_buttons_layout.addWidget(self.refresh_btn)
        list_buttons_layout.addWidget(self.delete_btn)
        list_buttons_layout.addWidget(self.delete_all_btn)

        left_panel.addLayout(list_buttons_layout)

        # --- RIGHT PANEL ---
        right_widget = QWidget()
        right_panel = QVBoxLayout(right_widget)
        right_panel.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel("Select a log from the list to replay.")
        self.status_label.setStyleSheet("color: #e2e8f0; font-size: 13px; font-weight: bold;")
        right_panel.addWidget(self.status_label)

        # --- CONTROLS BAR ---
        controls_layout = QHBoxLayout()
        button_style = """
            QPushButton { background-color: #115e59; color: white; font-weight: bold; padding: 6px 10px; border-radius: 4px; }
            QPushButton:hover { background-color: #0d9488; }
            QPushButton:disabled { background-color: #1b2421; color: #4a5568; }
        """
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setStyleSheet(button_style)
        self.play_btn.clicked.connect(self.toggle_play_pause)

        self.step_back_btn = QPushButton("◄ Step")
        self.step_back_btn.setStyleSheet(button_style)
        self.step_back_btn.clicked.connect(self.step_backward)

        self.step_fwd_btn = QPushButton("Step ►")
        self.step_fwd_btn.setStyleSheet(button_style)
        self.step_fwd_btn.clicked.connect(self.step_forward)

        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setStyleSheet(button_style)
        self.stop_btn.clicked.connect(self.stop_replay)

        self.signal_combo = QComboBox()
        self.signal_combo.setStyleSheet("""
            QComboBox { background-color: #1b2421; color: #e2e8f0; border: 1px solid #2d3748; padding: 4px; border-radius: 4px; }
        """)
        self.signal_combo.currentTextChanged.connect(self.on_signal_changed)

        controls_layout.addWidget(self.play_btn)
        controls_layout.addWidget(self.step_back_btn)
        controls_layout.addWidget(self.step_fwd_btn)
        controls_layout.addWidget(self.stop_btn)
        controls_layout.addWidget(QLabel(" Plot Signal:"))
        controls_layout.addWidget(self.signal_combo)
        controls_layout.addStretch()
        right_panel.addLayout(controls_layout)

        # --- SCRUBBER SLIDER ---
        slider_layout = QHBoxLayout()
        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setStyleSheet("""
            QSlider::groove:horizontal { background: #1b2421; height: 6px; border-radius: 3px; }
            QSlider::sub-page:horizontal { background: #10b981; border-radius: 3px; }
            QSlider::handle:horizontal { background: #e2e8f0; width: 14px; margin-top: -4px; margin-bottom: -4px; border-radius: 7px; }
            QSlider::handle:horizontal:hover { background: #10b981; }
        """)
        self.progress_slider.setMinimum(0)
        self.progress_slider.setMaximum(0)
        self.progress_slider.sliderMoved.connect(self.on_slider_seek)

        self.frame_counter_label = QLabel("0 / 0")
        self.frame_counter_label.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: bold;")

        slider_layout.addWidget(self.progress_slider)
        slider_layout.addWidget(self.frame_counter_label)
        right_panel.addLayout(slider_layout)

        # --- REPLAY SPLITTER ---
        replay_splitter = QSplitter(Qt.Vertical)
        replay_splitter.setStyleSheet("""
            QSplitter::handle { background-color: #2d3748; height: 6px; }
            QSplitter::handle:hover { background-color: #10b981; }
        """)

        # Replay Table
        self.replay_table = QTableWidget(0, 9)
        self.replay_table.setHorizontalHeaderLabels([
            "Timestamp", "ID", "Ext", "RTR", "Dir", "Bus", "Len", "ASCII", "Data"
        ])
        self.replay_table.setStyleSheet("""
            QTableWidget { background-color: #1b2421; gridline-color: #2d3748; color: #e2e8f0; font-size: 12px; }
            QHeaderView::section { background-color: #0f766e; color: white; font-weight: bold; padding: 4px; }
        """)
        header = self.replay_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionResizeMode(8, QHeaderView.Stretch)
        replay_splitter.addWidget(self.replay_table)

        # Plot Container
        plot_container = QWidget()
        plot_layout = QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(0, 4, 0, 0)

        # 1. Header Bar Layout (Horizontal layout to place label and button side-by-side)
        plot_header_layout = QHBoxLayout()

        self.plot_header = QLabel("Replay Visualization Diagram")
        self.plot_header.setStyleSheet("color: #10b981; font-size: 13px; font-weight: bold;")
        plot_header_layout.addWidget(self.plot_header)

        # Add flexible space between label and your new button
        plot_header_layout.addStretch()

        # 2. Define the new button

        self.custom_plot_btn = QPushButton("Full diagrams page")
        
        self.custom_plot_btn.setStyleSheet("""
            QPushButton { 
                background-color: #0f766e; 
                color: white; 
                font-weight: bold; 
                padding: 4px 10px; 
                border-radius: 4px; 
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.custom_plot_btn.setVisible(False)
        # Connect to your desired slot function
        self.custom_plot_btn.clicked.connect(self.all_diagrams_page)
        
        plot_header_layout.addWidget(self.custom_plot_btn)

        # Add the horizontal header bar to the vertical plot layout
        plot_layout.addLayout(plot_header_layout)

        # 3. Add Canvas below the header bar
        self.plot_canvas = UniversalPlotCanvas(self, width=5, height=3)
        plot_layout.addWidget(self.plot_canvas)

        replay_splitter.addWidget(plot_container)
        replay_splitter.setStretchFactor(0, 1)
        replay_splitter.setStretchFactor(1, 1)

        right_panel.addWidget(replay_splitter)

        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([280, 920])

        main_layout.addWidget(main_splitter)
        self.load_log_files()

    def on_log_item_clicked(self, item):
        """Single handler when an item in the log list is clicked."""
        self.current_selected_log = item.text()
        print(f"DEBUG: Selected log saved as -> '{self.current_selected_log}'")
        # 1. Emit signal so MainWindow can show the Analyze button
        self.log_selected_signal.emit(True)
        # 2. Parse and load the selected log
        self.load_selected_log(item)
        self.custom_plot_btn.setVisible(True)


    def get_logs_directory(self):
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        logs_dir = os.path.join(desktop_path, "logs")
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir, exist_ok=True)
        return logs_dir

    def all_diagrams_page(self):
        print("DEBUG: custom_plot_btn clicked!")
        
        selected_log = getattr(self, 'current_selected_log', None)
        print(f"DEBUG: Current selected log value is -> '{selected_log}'")

        if selected_log:
            try:
                dialog = FullDiagramDialog(log_data=selected_log, parent=self)
                dialog.exec_()
            except Exception as e:
                print(f"DEBUG Error opening dialog: {e}")
        else:
            print("DEBUG: selected_log is None or Empty! Dialog will not open.")

    def load_log_files(self):
        self.log_list.clear()
        logs_dir = self.get_logs_directory()

        if os.path.exists(logs_dir):
            files = sorted(
                [f for f in os.listdir(logs_dir) if f.endswith(".csv")], 
                reverse=True
            )
            for file in files:
                item = QListWidgetItem(f"📄 {file}")
                item.setData(32, os.path.join(logs_dir, file))
                self.log_list.addItem(item)
        
        # Hide Analyze button since no file is currently selected
        self.log_selected_signal.emit(False)

    def load_selected_log(self, item):
        self.current_index = 0
        filepath = item.data(32)
        self.stop_replay()
        self.replay_data = []
        self.signal_history = {}
        self.signal_combo.clear()

        try:
            with open(filepath, mode="r", encoding="UTF-8") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if row and len(row) >= 9:
                        self.replay_data.append(row)
                        can_id = row[1]
                        if can_id not in self.signal_history:
                            self.signal_history[can_id] = []
                            self.signal_combo.addItem(can_id)

            total_frames = len(self.replay_data)
            self.progress_slider.setMaximum(total_frames)
            self.progress_slider.setValue(0)
            self.frame_counter_label.setText(f"0 / {total_frames}")

            self.status_label.setText(f"Loaded: {item.text().replace('📄 ', '')} ({total_frames} frames)")
            self.replay_table.setRowCount(0)
            
            if self.signal_combo.count() > 0:
                self.selected_signal_id = self.signal_combo.currentText()
                self.plot_header.setText(f"Replay Visualization: {self.selected_signal_id}")

        except Exception as e:
            self.status_label.setText(f"Error loading file: {e}")

    def on_signal_changed(self, signal_id):
        self.selected_signal_id = signal_id
        self.plot_header.setText(f"Replay Visualization: {signal_id if signal_id else 'None'}")
        self.render_state_at_index(self.current_index)

    def toggle_play_pause(self):
        if not self.replay_data:
            self.status_label.setText("Select a valid log file first!")
            return

        if self.current_index >= len(self.replay_data):
            self.current_index = 0

        if self.replay_timer.isActive():
            self.replay_timer.stop()
            self.is_paused = True
            self.play_btn.setText("▶ Resume")
            self.status_label.setText("⏸ Replay Paused")
        else:
            self.replay_timer.start(100)
            self.is_paused = False
            self.play_btn.setText("⏸ Pause")
            self.status_label.setText("▶ Replaying CAN Data...")

    def play_next_frame(self):
        if self.current_index < len(self.replay_data):
            self.render_state_at_index(self.current_index + 1)
        else:
            self.stop_replay()
            self.status_label.setText("✔ Replay finished.")

    def step_forward(self):
        if self.current_index < len(self.replay_data):
            if self.replay_timer.isActive():
                self.toggle_play_pause()
            self.render_state_at_index(self.current_index + 1)

    def step_backward(self):
        if self.current_index > 0:
            if self.replay_timer.isActive():
                self.toggle_play_pause()
            self.render_state_at_index(self.current_index - 1)

    def on_slider_seek(self, value):
        if self.replay_data:
            self.render_state_at_index(value)

    def delete_all_logs(self):
        confirm = QMessageBox.question(
            self,
            "Delete All Logs",
            "Are you sure you want to delete ALL saved log files?\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            try:
                self.stop_replay()
                gc.collect()

                logs_dir = self.get_logs_directory()

                if not os.path.exists(logs_dir):
                    self.status_label.setText("⚠ Logs directory not found.")
                    return

                deleted_count = 0
                failed_count = 0

                for filename in os.listdir(logs_dir):
                    if filename.endswith(".csv"):
                        file_path = os.path.join(logs_dir, filename)
                        try:
                            os.remove(file_path)
                            deleted_count += 1
                        except Exception:
                            failed_count += 1

                self.replay_data = []
                self.signal_history = {}
                self.signal_combo.clear()
                self.replay_table.setRowCount(0)
                self.plot_canvas.update_figure([])
                self.progress_slider.setValue(0)
                self.progress_slider.setMaximum(0)
                self.frame_counter_label.setText("0 / 0")

                self.load_log_files()

                if failed_count > 0:
                    self.status_label.setText(
                        f"🗑 Deleted {deleted_count} logs. ({failed_count} file(s) skipped - in use)."
                    )
                else:
                    self.status_label.setText(f"🗑 All logs deleted successfully ({deleted_count} files).")

            except Exception as e:
                self.status_label.setText(f"Error during bulk deletion: {e}")

    def delete_selected_log(self):
        selected_log = self.log_list.currentItem()
        if not selected_log:
            self.status_label.setText("⚠ Please select a log file to delete")
            return
        filepath = selected_log.data(32)
        filename = selected_log.text().replace("📄 ", "")

        confirm = QMessageBox.question(
            self, 
            "Delete Confirmation", 
            f"Are you sure you want to delete '{filename}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            try:
                self.stop_replay()

                if os.path.exists(filepath):
                    os.remove(filepath)

                self.replay_data = []
                self.signal_history = {}
                self.signal_combo.clear()
                self.replay_table.setRowCount(0)
                self.plot_canvas.update_figure([])
                self.progress_slider.setValue(0)
                self.progress_slider.setMaximum(0)
                self.frame_counter_label.setText("0 / 0")

                self.load_log_files()
                self.status_label.setText(f"🗑 Deleted: {filename}")

            except Exception as e:
                self.status_label.setText(f"Error deleting file: {e}")

    def render_state_at_index(self, target_index):
        self.current_index = target_index
        
        self.progress_slider.blockSignals(True)
        self.progress_slider.setValue(target_index)
        self.progress_slider.blockSignals(False)
        self.frame_counter_label.setText(f"{target_index} / {len(self.replay_data)}")

        for k in self.signal_history:
            self.signal_history[k] = []

        self.replay_table.setRowCount(0)
        slice_data = self.replay_data[:target_index]

        for row_idx, row_data in enumerate(slice_data):
            self.replay_table.insertRow(row_idx)
            for col_idx, val in enumerate(row_data):
                self.replay_table.setItem(row_idx, col_idx, QTableWidgetItem(str(val)))

            can_id = row_data[1]
            try:
                data_val = float(row_data[8])
                if can_id in self.signal_history:
                    self.signal_history[can_id].append(data_val)
            except ValueError:
                pass

        self.replay_table.scrollToBottom()

        if self.selected_signal_id and self.selected_signal_id in self.signal_history:
            self.plot_canvas.update_figure(self.signal_history[self.selected_signal_id])

    def stop_replay(self):
        self.replay_timer.stop()
        self.is_paused = False
        self.play_btn.setText("▶ Play")
        self.current_index = 0
        self.render_state_at_index(0)
        self.status_label.setText("⏹ Replay stopped.")