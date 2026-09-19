"""
can_serial_reader.py
---------------------
Reads real CAN frames coming from the ESP32 + CAN transceiver bridge
(see esp32_can_bridge.ino) over a USB-serial connection, and turns
them into Qt signals the rest of the app can consume without ever
blocking the GUI thread.

Wire protocol (one line per CAN frame, sent by the ESP32 sketch):
    <millis>,0x<id_hex>,<dlc>,<data bytes hex space separated>
Example:
    156644,0x003,5,03 0F 60 1F 00
    156645,0x41B,8,FD 1A 04 FF FF FF FF FF

Standard (11-bit) IDs come in as 3 hex digits, extended (29-bit) IDs
as 8 hex digits - extended/RTR flags aren't in this format, so we
infer "extended" from the numeric ID being too big for 11 bits, and
RTR is not currently detected (defaults to False). If you need real
RTR detection, add a flag to the ESP32 sketch's output line and to
_parse_frame below.

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

            if line[0].isdigit():
                # A real frame line always starts with the millis timestamp.
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
            # parts[0] = millis timestamp (informational only, we timestamp
            #            with the PC's own clock elsewhere for display)
            # parts[1] = "0x<hex id>"
            # parts[2] = dlc
            # parts[3] = data bytes, hex, space separated
            id_hex = parts[1]
            dlc = int(parts[2])
            data_str = parts[3] if len(parts) > 3 else ""
            data_bytes = [int(b, 16) for b in data_str.split()] if data_str else []

            can_id_int = int(id_hex, 16)  # works fine with the "0x" prefix
            extended = can_id_int > 0x7FF  # doesn't fit in an 11-bit standard ID

            return CANFrame(
                can_id=f"0x{can_id_int:03X}" if not extended else f"0x{can_id_int:08X}",
                extended=extended,
                rtr=False,  # not present in this wire format
                dlc=dlc,
                data=data_bytes,
            )
        except (IndexError, ValueError):
            return None

    def stop(self):
        """Ask the thread to stop and block until it actually has."""
        self._running = False
        self.wait(2000)