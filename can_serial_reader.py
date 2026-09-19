"""
can_serial_reader.py
---------------------
Reads real CAN frames coming from the ESP32 + CAN transceiver bridge
(see esp32_can_bridge.ino) over a USB-serial connection, and turns
them into Qt signals the rest of the app can consume without ever
blocking the GUI thread.

Wire protocol (one line per CAN frame, sent by the ESP32 sketch):
    FRAME,<id_hex>,<ext 0/1>,<rtr 0/1>,<dlc>,<data bytes hex space separated>
Example:
    FRAME,316,0,0,8,4A 3F 00 12 00 00 00 00

Requires: pip install pyserial
"""

import serial
from PyQt5.QtCore import QThread, pyqtSignal


class CANFrame:
    """Plain data holder for one decoded CAN frame."""
    __slots__ = ("can_id", "extended", "rtr", "dlc", "data")

    def __init__(self, can_id: str, extended: bool, rtr: bool, dlc: int, data: list):
        self.can_id = can_id        # e.g. "0x316"
        self.extended = extended
        self.rtr = rtr
        self.dlc = dlc
        self.data = data            # list[int], raw bytes


class CANSerialReader(QThread):
    """
    Owns the serial connection to the ESP32 and does all blocking I/O
    off the GUI thread. Communicates back to the app purely via Qt
    signals, which Qt automatically marshals onto the receiving
    (main/GUI) thread.
    """

    frame_received = pyqtSignal(object)   # emits a CANFrame
    status_message = pyqtSignal(str)      # info messages, e.g. for a status bar
    connection_lost = pyqtSignal(str)     # fired once, then the thread exits

    def __init__(self, port: str, baudrate: int = 115200, parent=None):
        super().__init__(parent)
        self.port = port
        self.baudrate = baudrate
        self._running = False
        self._serial = None

    def run(self):
        self._running = True
        try:
            self._serial = serial.Serial(self.port, self.baudrate, timeout=1)
        except serial.SerialException as exc:
            self.connection_lost.emit(f"Could not open {self.port}: {exc}")
            return

        self.status_message.emit(f"Connected to {self.port} @ {self.baudrate} baud")

        while self._running:
            try:
                raw = self._serial.readline()
            except serial.SerialException as exc:
                self.connection_lost.emit(f"Serial error: {exc}")
                break

            if not raw:
                continue  # readline timeout - loop again and check _running

            line = raw.decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            if line.startswith("FRAME,"):
                frame = self._parse_frame(line)
                if frame is not None:
                    self.frame_received.emit(frame)
            elif line.startswith("READY"):
                self.status_message.emit(line.replace("READY,", "ESP32: "))
            elif line.startswith("ERR"):
                self.status_message.emit(line.replace("ERR,", "ESP32 error: "))
            # anything else (stray debug prints etc.) is ignored

        if self._serial and self._serial.is_open:
            self._serial.close()

    @staticmethod
    def _parse_frame(line: str):
        try:
            parts = line.split(",")
            # parts[0] == "FRAME"
            can_id_hex = parts[1]
            extended = parts[2] == "1"
            rtr = parts[3] == "1"
            dlc = int(parts[4])
            data_str = parts[5] if len(parts) > 5 else ""
            data_bytes = [int(b, 16) for b in data_str.split()] if data_str else []

            return CANFrame(
                can_id=f"0x{can_id_hex.upper()}",
                extended=extended,
                rtr=rtr,
                dlc=dlc,
                data=data_bytes,
            )
        except (IndexError, ValueError):
            return None

    def stop(self):
        """Ask the thread to stop and block until it actually has."""
        self._running = False
        self.wait(2000)