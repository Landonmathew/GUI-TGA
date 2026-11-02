
# =====================================================
# Scale Control GUI
#
# Developed by:
# Landon Boger
#
# © 2026 Landon Boger
# All Rights Reserved.
#
# Version 1.9
#
# RS-485 Scale Communication Interface
#
# Communication is handled entirely by this.
# The main TGA GUI does not contain scale communication.
#
# Sartorius 1773MP Communication:
#     Baud Rate : 1200
#     Data Bits : 7
#     Parity    : Odd
#     Stop Bits : 1
#
# Commands:
#     ESC P = Request Weight
#     ESC T = Tare
#
# IMPORTANT:
#     Opening the COM port does NOT mean that the
#     balance is connected.
#
#     The balance is considered connected only after
#     ESC P produces a valid weight response.
# =====================================================

import sys
import re
import time

import serial
import serial.tools.list_ports

from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QComboBox,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
)

from PyQt5.QtCore import (
    QTimer,
    QThread,
    QObject,
    pyqtSignal,
    Qt,
)


# =====================================================
# Sartorius 1773MP Commands
# =====================================================

# ESC P
# Request current weight
#
# HEX:
#     1B 50

REQUEST_WEIGHT = bytes([
    0x1B,
    0x50
])


# ESC T
# Tare balance
#
# HEX:
#     1B 54

TARE = bytes([
    0x1B,
    0x54
])


# =====================================================
# Scale Worker
# =====================================================

class ScaleWorker(QObject):

    connection_result = pyqtSignal(bool)

    weight_received = pyqtSignal(object)

    error = pyqtSignal(str)

    command_result = pyqtSignal(
        bool,
        str
    )

    def __init__(self):

        super().__init__()

        self.serial = None

        self.read_in_progress = False

    # =================================================
    # Get Available COM Ports
    # =================================================

    @staticmethod
    def get_ports():

        return [
            port.device
            for port in serial.tools.list_ports.comports()
        ]

    # =================================================
    # Connect
    #
    # IMPORTANT:
    #
    # The COM port opening successfully does NOT mean
    # that the Sartorius balance is connected.
    #
    # The balance must respond to ESC P with a valid
    # weight before connection_result(True) is emitted.
    # =================================================

    def connect_scale(
        self,
        port,
        baudrate
    ):

        try:

            # =================================================
            # Close any previous connection
            # =================================================

            if self.serial is not None:

                try:

                    if self.serial.is_open:
                        self.serial.close()

                except Exception:

                    pass

                self.serial = None

            # =================================================
            # Open Serial Port
            # =================================================

            self.serial = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.SEVENBITS,
                parity=serial.PARITY_ODD,
                stopbits=serial.STOPBITS_ONE,
                timeout=2.0,
                write_timeout=2.0,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )

            if not self.serial.is_open:

                self.serial = None

                self.connection_result.emit(
                    False
                )

                return

            # =================================================
            # Clear Old Data
            # =================================================

            self.serial.reset_input_buffer()

            self.serial.reset_output_buffer()

            # =================================================
            # VERIFY BALANCE
            #
            # Send ESC P.
            # =================================================

            self.serial.write(
                REQUEST_WEIGHT
            )

            self.serial.flush()

            # =================================================
            # Give the balance time to respond.
            # =================================================

            time.sleep(
                0.25
            )

            # =================================================
            # Read Response
            #
            # Continue reading until:
            #
            # 1. Data has arrived and the response is complete
            # OR
            #
            # 2. The 2-second verification timeout expires.
            # =================================================

            response = bytearray()

            start_time = time.monotonic()

            last_data_time = None

            while time.monotonic() - start_time < 2.0:

                if self.serial.in_waiting:

                    response.extend(
                        self.serial.read(
                            self.serial.in_waiting
                        )
                    )

                    last_data_time = (
                        time.monotonic()
                    )

                    time.sleep(
                        0.05
                    )

                else:

                    current_time = (
                        time.monotonic()
                    )

                    # If data has arrived and no more data
                    # has appeared for 50 ms, consider the
                    # response complete.

                    if (
                        response
                        and last_data_time is not None
                        and (
                            current_time
                            - last_data_time
                        ) >= 0.05
                    ):

                        break

                    # Overall verification timeout.

                    if (
                        current_time
                        - start_time
                        >= 2.0
                    ):

                        break

                    time.sleep(
                        0.05
                    )

            # =================================================
            # No Response
            # =================================================

            if not response:

                print(
                    "Scale connection verification failed: "
                    "No response to ESC P."
                )

                self._close_serial()

                self.connection_result.emit(
                    False
                )

                return

            # =================================================
            # Parse Response
            # =================================================

            weight = self.parse_weight(
                bytes(response)
            )

            # =================================================
            # Invalid Response
            # =================================================

            if weight is None:

                try:

                    response_text = bytes(
                        response
                    ).decode(
                        "ascii",
                        errors="replace"
                    ).strip()

                except Exception:

                    response_text = "<unreadable>"

                print(
                    "Scale connection verification failed: "
                    "Invalid ESC P response."
                )

                print(
                    f"Scale response HEX: "
                    f"{bytes(response).hex(' ').upper()}"
                )

                print(
                    f"Scale response ASCII: "
                    f"{response_text}"
                )

                self._close_serial()

                self.connection_result.emit(
                    False
                )

                return

            # =================================================
            # BALANCE VERIFIED
            # =================================================

            print(
                f"Sartorius balance verified. "
                f"Initial weight: {weight}"
            )

            self.read_in_progress = False

            # Send the verified initial weight immediately.

            self.weight_received.emit(
                weight
            )

            # ONLY NOW report successful connection.

            self.connection_result.emit(
                True
            )

        except Exception as exc:

            print(
                f"Scale connection error: {exc}"
            )

            self._close_serial()

            self.read_in_progress = False

            self.error.emit(
                str(exc)
            )

            self.connection_result.emit(
                False
            )

    # =================================================
    # Read Weight
    #
    # ESC P
    # =================================================

    def read_weight(self):

        if self.read_in_progress:

            return

        if self.serial is None:

            return

        try:

            if not self.serial.is_open:

                return

        except Exception:

            return

        self.read_in_progress = True

        try:

            # =================================================
            # Remove old response data
            # =================================================

            self.serial.reset_input_buffer()

            # =================================================
            # Send ESC P
            # =================================================

            self.serial.write(
                REQUEST_WEIGHT
            )

            self.serial.flush()

            # =================================================
            # Give the balance time to respond
            # =================================================

            time.sleep(
                0.25
            )

            # =================================================
            # Read Response
            # =================================================

            response = bytearray()

            start_time = time.monotonic()

            last_data_time = None

            while time.monotonic() - start_time < 2.0:

                if self.serial.in_waiting:

                    response.extend(
                        self.serial.read(
                            self.serial.in_waiting
                        )
                    )

                    last_data_time = (
                        time.monotonic()
                    )

                    time.sleep(
                        0.05
                    )

                else:

                    current_time = (
                        time.monotonic()
                    )

                    # Response is complete once data has
                    # stopped arriving.

                    if (
                        response
                        and last_data_time is not None
                        and (
                            current_time
                            - last_data_time
                        ) >= 0.05
                    ):

                        break

                    # Do not wait forever.

                    if (
                        current_time
                        - start_time
                        >= 2.0
                    ):

                        break

                    time.sleep(
                        0.05
                    )

            # =================================================
            # No Response
            # =================================================

            if not response:

                self.weight_received.emit(
                    None
                )

                return

            # =================================================
            # Parse Weight
            # =================================================

            weight = self.parse_weight(
                bytes(response)
            )

            self.weight_received.emit(
                weight
            )

        except Exception as exc:

            self.error.emit(
                str(exc)
            )

            self.weight_received.emit(
                None
            )

        finally:

            self.read_in_progress = False

    # =================================================
    # Parse Weight
    # =================================================

    @staticmethod
    def parse_weight(data):

        if not data:

            return None

        try:

            # =================================================
            # Convert Response to ASCII
            # =================================================

            text = data.decode(
                "ascii",
                errors="ignore"
            )

            text = text.strip()

            if not text:

                return None

            # =================================================
            # Find Numeric Value
            #
            # Supported examples:
            #
            # 12.345
            # -12.345
            # +12.345
            # 0.001
            # 123
            # 1.23E-03
            # =================================================

            matches = re.findall(
                r"[-+]?\s*\d+(?:\.\d+)?(?:[eE][-+]?\d+)?",
                text
            )

            if not matches:

                return None

            return float(
                re.sub(r"\s+", "", matches[0])
            )

        except Exception:

            return None

    # =================================================
    # Tare
    #
    # ESC T
    # =================================================

    def tare(self):

        if self.serial is None:

            self.command_result.emit(
                False,
                "Scale not connected."
            )

            return

        try:

            if not self.serial.is_open:

                self.command_result.emit(
                    False,
                    "Scale not connected."
                )

                return

        except Exception:

            self.command_result.emit(
                False,
                "Scale not connected."
            )

            return

        try:

            # =================================================
            # Clear Old Response
            # =================================================

            self.serial.reset_input_buffer()

            # =================================================
            # Send ESC T
            # =================================================

            self.serial.write(
                TARE
            )

            self.serial.flush()

            # =================================================
            # Give Balance Time to Process
            # =================================================

            time.sleep(
                0.25
            )

            # =================================================
            # Clear Any Response
            # =================================================

            deadline = time.monotonic() + 2.0

            while (
                self.serial.in_waiting
                and time.monotonic() < deadline
            ):

                self.serial.read(
                    self.serial.in_waiting
                )

                time.sleep(
                    0.05
                )

            self.command_result.emit(
                True,
                "ESC T - Tare command sent."
            )

        except Exception as exc:

            self.command_result.emit(
                False,
                str(exc)
            )

    # =================================================
    # Zero
    #
    # No ZERO command was provided for this balance.
    # Do not invent one.
    # =================================================

    def zero(self):

        self.command_result.emit(
            False,
            "ZERO command not configured."
        )

    # =================================================
    # Close Serial
    # =================================================

    def _close_serial(self):

        try:

            if self.serial is not None:

                if self.serial.is_open:

                    self.serial.close()

        except Exception:

            pass

        self.serial = None

        self.read_in_progress = False

    # =================================================
    # Disconnect
    # =================================================

    def disconnect_scale(self):

        self._close_serial()


# =====================================================
# Scale Control Window
# =====================================================

class ScaleControlWindow(QWidget):

    connect_worker = pyqtSignal(
        str,
        int
    )

    read_weight_worker = pyqtSignal()

    tare_worker = pyqtSignal()

    zero_worker = pyqtSignal()

    disconnect_worker = pyqtSignal()

    def __init__(self, hide_on_close=False):

        super().__init__()

        self.hide_on_close = hide_on_close

        self._read_pending = False

        # =================================================
        # 1.9 UPDATE
        #
        # Scale health state.
        #
        # connected:
        #     COM port is open and the balance was verified.
        #
        # system_healthy:
        #     Valid weight readings are currently being
        #     received within the health-check timeout.
        #
        # These are intentionally separate states.
        # A health failure does NOT disconnect the COM port.
        # =================================================

        self.system_healthy = False

        self.last_valid_reading = None

        self.health_timeout = 6.0

        # =================================================
        # Window
        # =================================================

        self.setWindowTitle(
            "Scale Control"
        )

        self.resize(
            700,
            600
        )

        # =================================================
        # State
        # =================================================

        self.connected = False

        # =================================================
        # Worker Thread
        # =================================================

        self.thread = QThread(
            self
        )

        self.worker = ScaleWorker()

        self.worker.moveToThread(
            self.thread
        )

        # =================================================
        # Worker Signals
        # =================================================

        self.connect_worker.connect(
            self.worker.connect_scale
        )

        self.read_weight_worker.connect(
            self.worker.read_weight
        )

        self.tare_worker.connect(
            self.worker.tare
        )

        self.zero_worker.connect(
            self.worker.zero
        )

        self.disconnect_worker.connect(
            self.worker.disconnect_scale
        )

        # =================================================
        # Worker Results
        # =================================================

        self.worker.connection_result.connect(
            self.connection_finished
        )

        self.worker.weight_received.connect(
            self.weight_received
        )

        self.worker.command_result.connect(
            self.command_finished
        )

        self.worker.error.connect(
            self.worker_error
        )

        # =================================================
        # Start Worker
        # =================================================

        self.thread.finished.connect(
            self.worker.disconnect_scale
        )

        self.thread.start()

        # =================================================
        # Weight Timer
        # =================================================

        self.timer = QTimer(
            self
        )

        self.timer.timeout.connect(
            self.request_weight
        )

        self.timer.start(
            2000
        )

        # =================================================
        # 1.9 UPDATE
        #
        # System Health Check Timer
        #
        # Health is evaluated every 6 seconds.
        #
        # Normal weight polling remains every 2 seconds.
        # =================================================

        self.health_timer = QTimer(
            self
        )

        self.health_timer.timeout.connect(
            self.system_health_check
        )

        self.health_timer.start(
            6000
        )

        # =================================================
        # Create UI
        # =================================================

        self.init_ui()

    # =================================================
    # UI
    # =================================================

    def init_ui(self):

        self.setStyleSheet(
            """
            QWidget {
                background-color: #1E1E1E;
                color: #D0D0D0;
                font-size: 14px;
            }

            QGroupBox {
                background-color: #1E1E1E;
                border: 1px solid #3A5A75;
                border-radius: 6px;
                margin-top: 10px;
                padding: 10px;
                font-weight: bold;
                color: #FFFFFF;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #FFFFFF;
            }

            QLabel {
                color: #D0D0D0;
            }

            QPushButton {
                background-color: #1E1E1E;
                color: #D0D0D0;
                border: 1px solid #0080FF;
                padding: 8px;
                border-radius: 5px;
            }

            QPushButton:hover {
                background-color: #003B66;
                color: #FFFFFF;
            }

            QPushButton:pressed {
                background-color: #005A99;
                color: #FFFFFF;
            }

            QPushButton:disabled {
                background-color: #1E1E1E;
                color: #666666;
                border: 1px solid #444444;
            }

            QComboBox {
                background-color: #1E1E1E;
                color: #D0D0D0;
                border: 1px solid #0080FF;
                padding: 6px;
            }

            QComboBox:hover {
                background-color: #003B66;
                color: #FFFFFF;
            }

            QComboBox QAbstractItemView {
                background-color: #1E1E1E;
                color: #D0D0D0;
                selection-background-color: #003B66;
                selection-color: #FFFFFF;
            }
            """
        )

        main_layout = QVBoxLayout()

        # =================================================
        # Title
        # =================================================

        title = QLabel(
            "SCALE CONTROL"
        )

        title.setAlignment(
            Qt.AlignCenter
        )

        title.setStyleSheet(
            """
            color: #0080FF;
            font-size: 24px;
            font-weight: bold;
            """
        )

        main_layout.addWidget(
            title
        )

        # =================================================
        # Communication
        # =================================================

        communication_group = QGroupBox(
            "RS-485 Communication"
        )

        communication_layout = QGridLayout()

        communication_layout.addWidget(
            QLabel("COM Port:"),
            0,
            0
        )

        self.com_box = QComboBox()

        communication_layout.addWidget(
            self.com_box,
            0,
            1
        )

        self.refresh_button = QPushButton(
            "Refresh"
        )

        self.refresh_button.clicked.connect(
            self.refresh_ports
        )

        communication_layout.addWidget(
            self.refresh_button,
            0,
            2
        )

        self.connect_button = QPushButton(
            "Connect"
        )

        self.connect_button.clicked.connect(
            self.toggle_connection
        )

        communication_layout.addWidget(
            self.connect_button,
            0,
            3
        )

        communication_layout.addWidget(
            QLabel("Baud Rate:"),
            1,
            0
        )

        self.baud_box = QComboBox()

        self.baud_box.addItems(
            [
                "1200",
                "2400",
                "4800",
                "9600",
                "19200",
                "38400",
            ]
        )

        self.baud_box.setCurrentText(
            "1200"
        )

        communication_layout.addWidget(
            self.baud_box,
            1,
            1
        )

        communication_group.setLayout(
            communication_layout
        )

        main_layout.addWidget(
            communication_group
        )

        # =================================================
        # Live Scale Values
        # =================================================

        live_group = QGroupBox(
            "Live Scale Values"
        )

        live_layout = QVBoxLayout()

        live_title = QLabel(
            "Current Mass"
        )

        live_title.setAlignment(
            Qt.AlignCenter
        )

        live_title.setStyleSheet(
            """
            color: #FFFFFF;
            font-size: 17px;
            font-weight: bold;
            """
        )

        live_layout.addWidget(
            live_title
        )

        self.weight_label = QLabel(
            "0.0000 g"
        )

        self.weight_label.setAlignment(
            Qt.AlignCenter
        )

        self.weight_label.setStyleSheet(
            """
            color: #FFFFFF;
            font-size: 42px;
            font-weight: bold;
            """
        )

        live_layout.addWidget(
            self.weight_label
        )

        self.weight_status = QLabel(
            "Waiting for scale..."
        )

        self.weight_status.setAlignment(
            Qt.AlignCenter
        )

        self.weight_status.setStyleSheet(
            """
            color: #D0D0D0;
            font-size: 14px;
            """
        )

        live_layout.addWidget(
            self.weight_status
        )

        live_group.setLayout(
            live_layout
        )

        main_layout.addWidget(
            live_group
        )

        # =================================================
        # Scale Functions
        # =================================================

        function_group = QGroupBox(
            "Scale Functions"
        )

        function_layout = QHBoxLayout()

        self.request_button = QPushButton(
            "ESC P\nREQUEST WEIGHT"
        )

        self.request_button.clicked.connect(
            self.manual_request_weight
        )

        function_layout.addWidget(
            self.request_button
        )

        self.tare_button = QPushButton(
            "TARE"
        )

        self.tare_button.clicked.connect(
            self.tare
        )

        function_layout.addWidget(
            self.tare_button
        )

        self.zero_button = QPushButton(
            "ZERO"
        )

        self.zero_button.clicked.connect(
            self.zero
        )

        function_layout.addWidget(
            self.zero_button
        )

        function_group.setLayout(
            function_layout
        )

        main_layout.addWidget(
            function_group
        )

        # =================================================
        # Scale Status
        # =================================================

        status_group = QGroupBox(
            "Scale Status"
        )

        status_layout = QGridLayout()

        status_layout.addWidget(
            QLabel("Communication:"),
            0,
            0
        )

        self.status_label = QLabel(
            "Disconnected"
        )

        self.status_label.setStyleSheet(
            """
            color: #FF4D4D;
            font-weight: bold;
            """
        )

        status_layout.addWidget(
            self.status_label,
            0,
            1
        )

        status_layout.addWidget(
            QLabel("Reading Status:"),
            1,
            0
        )

        self.reading_status = QLabel(
            "----"
        )

        self.reading_status.setStyleSheet(
            """
            color: #FFFFFF;
            font-weight: bold;
            """
        )

        status_layout.addWidget(
            self.reading_status,
            1,
            1
        )

        status_group.setLayout(
            status_layout
        )

        main_layout.addWidget(
            status_group
        )

        # =================================================
        # Set Layout
        # =================================================

        self.setLayout(
            main_layout
        )

        # =================================================
        # Initial Setup
        # =================================================

        self.refresh_ports()

        self.set_controls_enabled(
            False
        )

    # =================================================
    # Refresh Ports
    # =================================================

    def refresh_ports(self):

        current = (
            self.com_box.currentText()
        )

        self.com_box.clear()

        ports = ScaleWorker.get_ports()

        if not ports:

            self.com_box.addItem(
                "No COM Ports Found"
            )

        else:

            for port in ports:

                self.com_box.addItem(
                    port
                )

            if current:

                index = self.com_box.findText(
                    current
                )

                if index >= 0:

                    self.com_box.setCurrentIndex(
                        index
                    )

    # =================================================
    # Enable Controls
    # =================================================

    def set_controls_enabled(
        self,
        enabled
    ):

        self.request_button.setEnabled(
            enabled
        )

        self.tare_button.setEnabled(
            enabled
        )

        self.zero_button.setEnabled(
            enabled
        )

    # =================================================
    # Connect / Disconnect
    # =================================================

    def toggle_connection(self):

        # =================================================
        # CONNECT
        #
        # Do NOT assume that opening the COM port means
        # the balance is connected.
        # =================================================

        if not self.connected:

            port = self.com_box.currentText()

            if (
                not port
                or port == "No COM Ports Found"
            ):

                self.set_status(
                    "Select a COM port.",
                    "red"
                )

                return

            try:

                baudrate = int(
                    self.baud_box.currentText()
                )

            except ValueError:

                self.set_status(
                    "Invalid baud rate.",
                    "red"
                )

                return

            # =================================================
            # Sartorius 1773MP requires 1200 baud.
            # =================================================

            if baudrate != 1200:

                self.set_status(
                    "Sartorius 1773MP requires 1200 baud.",
                    "red"
                )

                return

            # =================================================
            # Connecting
            # =================================================

            self.set_status(
                "Connecting...",
                "orange"
            )

            self.connect_button.setEnabled(
                False
            )

            self.refresh_button.setEnabled(
                False
            )

            # Make sure controls remain disabled until
            # the balance is actually verified.

            self.set_controls_enabled(
                False
            )

            # =================================================
            # 1.9 UPDATE
            #
            # Reset health state before a new connection.
            # =================================================

            self.system_healthy = False

            self.last_valid_reading = None

            self.connect_worker.emit(
                port,
                baudrate
            )

        # =================================================
        # DISCONNECT
        # =================================================

        else:

            self.disconnect_scale()

    # =================================================
    # Connection Finished
    # =================================================

    def connection_finished(
        self,
        success
    ):

        self.connect_button.setEnabled(
            True
        )

        self.refresh_button.setEnabled(
            True
        )

        # =================================================
        # VERIFIED CONNECTION
        # =================================================

        if success:

            self.connected = True

            # =================================================
            # 1.9 UPDATE
            #
            # The initial valid ESC P response has already
            # been received by weight_received().
            #
            # Mark the system healthy here as well so the
            # verified connection starts in a healthy state.
            # =================================================

            self.system_healthy = True

            self.connect_button.setText(
                "Disconnect"
            )

            self.set_controls_enabled(
                True
            )

            self.set_status(
                "Connected",
                "#00D26A"
            )

            self.reading_status.setText(
                "Live"
            )

            self.reading_status.setStyleSheet(
                """
                color: #FFFFFF;
                font-weight: bold;
                """
            )

        # =================================================
        # CONNECTION FAILED
        # =================================================

        else:

            self.connected = False

            # =================================================
            # 1.9 UPDATE
            #
            # Reset health state after a failed connection.
            # =================================================

            self.system_healthy = False

            self.last_valid_reading = None

            self.connect_button.setText(
                "Connect"
            )

            self.set_controls_enabled(
                False
            )

            self.set_status(
                "Balance Not Found",
                "#FF4D4D"
            )

            self.reading_status.setText(
                "Not Connected"
            )

            self.reading_status.setStyleSheet(
                """
                color: #FF4D4D;
                font-weight: bold;
                """
            )

            self.weight_status.setText(
                "Waiting for scale..."
            )

    # =================================================
    # Automatic Weight Request
    #
    # Only requests a reading after the balance has
    # been successfully verified.
    # =================================================

    def request_weight(self):

        if self._read_pending:
            return

        if not self.connected:

            return

        self._read_pending = True

        self.read_weight_worker.emit()

    # =================================================
    # Manual ESC P Request
    # =================================================

    def manual_request_weight(self):

        if not self.connected:

            self.set_status(
                "Connect Scale First",
                "#FF4D4D"
            )

            return

        self.request_weight()

    # =================================================
    # Weight Received
    # =================================================

    def weight_received(
        self,
        weight
    ):

        self._read_pending = False

        if weight is None:

            self.weight_label.setText(
                "---- g"
            )

            self.weight_status.setText(
                "No scale response"
            )

            self.weight_status.setStyleSheet(
                """
                color: #D0D0D0;
                font-size: 14px;
                """
            )

            self.reading_status.setText(
                "No response"
            )

            self.reading_status.setStyleSheet(
                """
                color: orange;
                font-weight: bold;
                """
            )

            return

        try:

            weight = float(
                weight
            )

        except Exception:

            return

        # =================================================
        # 1.9 UPDATE
        #
        # Record the time of every valid weight response.
        #
        # The health check uses this timestamp rather than
        # counting failed polling attempts.
        # =================================================

        self.last_valid_reading = time.monotonic()

        self.system_healthy = True

        # =================================================
        # LIVE MASS
        # =================================================

        self.weight_label.setText(
            f"{weight:.4f} g"
        )

        self.weight_label.setStyleSheet(
            """
            color: #FFFFFF;
            font-size: 42px;
            font-weight: bold;
            """
        )

        # =================================================
        # LIVE STATUS
        # =================================================

        self.weight_status.setText(
            "Live reading"
        )

        self.weight_status.setStyleSheet(
            """
            color: #D0D0D0;
            font-size: 14px;
            """
        )

        self.reading_status.setText(
            "Live"
        )

        self.reading_status.setStyleSheet(
            """
            color: #FFFFFF;
            font-weight: bold;
            """
        )

    # =================================================
    # 1.9 UPDATE
    # System Health Check
    #
    # The scale is checked every 6 seconds.
    #
    # Health is determined by whether a valid weight
    # response has been received within the last 6 seconds.
    #
    # IMPORTANT:
    #
    # A failed health check does NOT close the COM port.
    #
    # Weight polling continues every 2 seconds.
    #
    # The system automatically returns to healthy when
    # a valid weight response is received again.
    #
    # Terminal output:
    #
    #     Scale_health_check PASS
    #
    #     Scale_health_check FAIL
    # =================================================

    def system_health_check(self):

        # =================================================
        # Only perform the health evaluation when the
        # balance has been successfully connected.
        # =================================================

        if not self.connected:

            return

        # =================================================
        # No valid reading has been received.
        # =================================================

        if self.last_valid_reading is None:

            self.system_healthy = False

            print(
                "Scale_health_check FAIL"
            )

            self.reading_status.setText(
                "Communication Unhealthy"
            )

            self.reading_status.setStyleSheet(
                """
                color: orange;
                font-weight: bold;
                """
            )

            return

        # =================================================
        # Determine how long it has been since the last
        # valid scale response.
        # =================================================

        elapsed = (
            time.monotonic()
            - self.last_valid_reading
        )

        # =================================================
        # HEALTHY
        #
        # A valid weight has been received within the
        # 6-second health-check window.
        # =================================================

        if elapsed < self.health_timeout:

            self.system_healthy = True

            print(
                "Scale_health_check PASS"
            )

            self.reading_status.setText(
                "Live"
            )

            self.reading_status.setStyleSheet(
                """
                color: #FFFFFF;
                font-weight: bold;
                """
            )

        # =================================================
        # UNHEALTHY
        #
        # No valid weight has been received for 6 seconds.
        #
        # The COM port remains open.
        #
        # The normal 2-second polling continues.
        # =================================================

        else:

            self.system_healthy = False

            print(
                "Scale_health_check FAIL"
            )

            self.reading_status.setText(
                "Communication Unhealthy"
            )

            self.reading_status.setStyleSheet(
                """
                color: orange;
                font-weight: bold;
                """
            )

    # =================================================
    # Get Weight
    #
    # IMPORTANT:
    #
    # The main TGA GUI calls this function.
    #
    # No serial communication is performed here.
    #
    # It simply returns the latest verified/displayed
    # balance reading.
    # =================================================

    def get_weight(self):

        # Do not provide a weight to the main GUI unless
        # the balance has actually been verified connected.

        if not self.connected:

            return None

        text = (
            self.weight_label.text()
        )

        if not text:

            return None

        try:

            value = (
                text
                .replace(
                    "g",
                    ""
                )
                .strip()
            )

            return float(
                value
            )

        except Exception:

            return None

    # =================================================
    # Tare
    # =================================================

    def tare(self):

        if not self.connected:

            self.set_status(
                "Connect Scale First",
                "#FF4D4D"
            )

            return

        self.tare_worker.emit()

    # =================================================
    # Zero
    # =================================================

    def zero(self):

        if not self.connected:

            self.set_status(
                "Connect Scale First",
                "#FF4D4D"
            )

            return

        self.zero_worker.emit()

    # =================================================
    # Command Result
    # =================================================

    def command_finished(
        self,
        success,
        message
    ):

        if success:

            self.set_status(
                message,
                "#00D26A"
            )

        else:

            self.set_status(
                message,
                "#FF4D4D"
            )

    # =================================================
    # Status
    # =================================================

    def set_status(
        self,
        message,
        color
    ):

        self.status_label.setText(
            message
        )

        self.status_label.setStyleSheet(
            f"""
            color: {color};
            font-weight: bold;
            """
        )

    # =================================================
    # Worker Error
    # =================================================

    def worker_error(
        self,
        message
    ):

        self._read_pending = False

        self.weight_label.setText(
            "---- g"
        )

        print(
            f"Scale Error: {message}"
        )

        self.set_status(
            "Communication Error",
            "#FF4D4D"
        )

        self.reading_status.setText(
            "Communication Error"
        )

        self.reading_status.setStyleSheet(
            """
            color: #FF4D4D;
            font-weight: bold;
            """
        )

    # =================================================
    # Disconnect
    # =================================================

    def disconnect_scale(self):

        self.disconnect_worker.emit()

        self.connected = False

        # =================================================
        # 1.9 UPDATE
        #
        # Reset health state when the user intentionally
        # disconnects the balance.
        # =================================================

        self.system_healthy = False

        self.last_valid_reading = None

        self.connect_button.setText(
            "Connect"
        )

        self.connect_button.setEnabled(
            True
        )

        self.refresh_button.setEnabled(
            True
        )

        self.set_controls_enabled(
            False
        )

        # =================================================
        # Reset Live Values
        # =================================================

        self.weight_label.setText(
            "0.0000 g"
        )

        self.weight_status.setText(
            "Waiting for scale..."
        )

        self.weight_status.setStyleSheet(
            """
            color: #D0D0D0;
            font-size: 14px;
            """
        )

        self.reading_status.setText(
            "Waiting"
        )

        self.reading_status.setStyleSheet(
            """
            color: #FFFFFF;
            font-weight: bold;
            """
        )

        self.set_status(
            "Disconnected",
            "#FF4D4D"
        )

    # =================================================
    # Close
    # =================================================

    def closeEvent(
        self,
        event
    ):

        if self.hide_on_close:

            self.hide()

            event.accept()

            return

        # =================================================
        # 1.9 UPDATE
        #
        # Stop the health-check timer when the window
        # is permanently closing.
        # =================================================

        self.health_timer.stop()

        self.timer.stop()

        self.disconnect_worker.emit()

        self.thread.quit()

        self.thread.wait()

        event.accept()


# =====================================================
# Run Scale Controller Directly
# =====================================================

if __name__ == "__main__":

    app = QApplication(
        sys.argv
    )

    window = ScaleControlWindow()

    window.show()

    sys.exit(
        app.exec_()
    )