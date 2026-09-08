import csv
import os
from datetime import datetime

class CANLogger:
    def __init__(self):
        self.file = None
        self.writer = None
        self.current_filename = ""

    def start_logging(self, filepath=None):
        if not filepath:
            # Gets your C:\Users\Johni.Megreli\Desktop directory dynamically
            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
            logs_dir = os.path.join(desktop_path, "logs")
            
            # Automatically creates the 'logs' folder on your Desktop if it doesn't exist
            os.makedirs(logs_dir, exist_ok=True)
            
            self.current_filename = datetime.now().strftime("can_log_%Y%m%d_%H%M%S.csv")
            filepath = os.path.join(logs_dir, self.current_filename)

        self.file = open(filepath, mode="w", newline="", encoding="UTF-8")
        self.writer = csv.writer(self.file)
        self.writer.writerow(["Timestamp", "ID", "Ext", "RTR", "Dir", "Bus", "Len", "ASCII", "Data"])

    def log_frame(self, timestamp, can_id, ext, rtr, direction, bus, length, ascii_val, data_bytes):
        if self.writer:
            self.writer.writerow([timestamp, can_id, ext, rtr, direction, bus, length, ascii_val, data_bytes])
            self.file.flush()

    def stop_logging(self):
        if self.file:
            self.file.close()
            self.file = None
            self.writer = None