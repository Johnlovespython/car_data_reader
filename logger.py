import csv
import os
from datetime import datetime

class CANLogger:
    def __init__(self):
        self.file = None
        self.writer = None
        self.current_filename = ""

    def start_logging(self):
            # Create a unique filename with timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            logs_dir = os.path.join(os.path.expanduser("~"), "Desktop", "logs")
            os.makedirs(logs_dir, exist_ok=True)
            
            # SAVE THE PATH HERE
            self.current_filename = os.path.join(logs_dir, f"can_log_{timestamp}.csv")
            self.is_logging = True
            
            # Initialize CSV file with headers
            with open(self.current_filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "ID", "Ext", "RTR", "Dir", "Bus", "Len", "ASCII", "Data"])

    def log_frame(self, timestamp, can_id, ext, rtr, direction, bus, length, ascii_val, data_bytes):
        if not self.is_logging or not self.current_filename:
                return

            # Open with append mode and flush after writing
        with open(self.current_filename, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, can_id, ext, rtr, direction, bus, length, ascii_val, data_bytes])
                f.flush()

    def stop_logging(self):
        if self.file:
            self.file.close()
            self.file = None
            self.writer = None