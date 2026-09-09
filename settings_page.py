from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton
from PyQt5.QtCore import Qt

class SettingsDialog(QDialog):
    """POPUP window for Application Settings"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(360, 240)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #121816;
                color: #e2e8f0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel { 
                color: #e2e8f0; 
                font-size: 13px; 
            }
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

        # Example Setting: Baudrate
        layout.addWidget(QLabel("CAN Baudrate:"))
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["500000", "250000", "125000", "1000000"])
        layout.addWidget(self.baud_combo)

        # Example Setting: Display Mode / Theme
        layout.addWidget(QLabel("Display Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark Teal (Default)", "Dark Gray"])
        layout.addWidget(self.theme_combo)

        layout.addStretch()

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Save")
        self.btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)

        self.btn_save.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)