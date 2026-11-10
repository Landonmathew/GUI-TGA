# =====================================================
# scale_controller.py
# Scale Control GUI
#
# Developed by:
# Landon Boger
#
# © 2026 Landon Boger
# All Rights Reserved.
#
# Version 2.1
#
# RS-485 Sartorius scale communication.
#
# Simulation calculations are contained entirely in:
#
#     simulated_temperature_controller.py
#
# This file only selects and communicates with either
# the physical scale or the simulated scale device.
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

from simulated_temperature_controller import (
    SimulatedScaleDevice,
    get_simulation_environment,
)


# =====================================================
# Timing
# =====================================================

# Poll the scale every fifteen seconds.
SCALE_POLL_INTERVAL = 15000

# Evaluate health every six seconds.
SCALE_HEALTH_CHECK_INTERVAL = 6000

# Three polling intervals without data are allowed.
SCALE_HEALTH_TIMEOUT = 18.0


# =====================================================
# Sartorius Commands
# =====================================================

REQUEST_WEIGHT = bytes(
    [
        0x1B,
        0x50
    ]
)

TARE = bytes(
    [
        0x1B,
        0x54
    ]
)


# =====================================================
# Scale Worker
# =====================================================

class ScaleWorker(QObject):

    connection_result = pyqtSignal(
        bool
    )

    weight_received = pyqtSignal(
        object
    )

    error = pyqtSignal(
        str
    )

    command_result = pyqtSignal(
        bool,
        str
    )

    def __init__(self):

        super().__init__()

        self.serial = None

        self.read_in_progress = False

    # =================================================
    # Available COM Ports
    # =================================================

    @staticmethod
    def get_ports():

        return [
            port.device
            for port in serial.tools.list_ports.comports()
        ]

    # =================================================
    # Connect Physical Scale
    # =================================================

    def connect_scale(
        self,
        port,
        baudrate
    ):

        try:

            self._close_serial()

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

                self._close_serial()

                self.connection_result.emit(
                    False
                )

                return

            self.serial.reset_input_buffer()

            self.serial.reset_output_buffer()

            self.serial.write(
                REQUEST_WEIGHT
            )

            self.serial.flush()

            response = self._read_response()

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

            weight = self.parse_weight(
                bytes(response)
            )

            if weight is None:

                print(
                    "Scale connection verification failed: "
                    "Invalid ESC P response."
                )

                print(
                    "Scale response HEX: "
                    f"{bytes(response).hex(' ').upper()}"
                )

                self._close_serial()

                self.connection_result.emit(
                    False
                )

                return

            self.read_in_progress = False

            self.weight_received.emit(
                weight
            )

            self.connection_result.emit(
                True
            )

        except Exception as exc:

            print(
                f"Scale connection error: {exc}"
            )

            self._close_serial()

            self.error.emit(
                str(exc)
            )

            self.connection_result.emit(
                False
            )

    # =================================================
    # Read Complete Physical Response
    # =================================================

    def _read_response(self):

        response = bytearray()

        start_time = time.monotonic()

        last_data_time = None

        while (
            time.monotonic()
            - start_time
            < 2.0
        ):

            if self.serial.in_waiting:

                response.extend(
                    self.serial.read(
                        self.serial.in_waiting
                    )
                )

                last_data_time = time.monotonic()

                time.sleep(
                    0.05
                )

            else:

                now = time.monotonic()

                if (
                    response
                    and last_data_time is not None
                    and now - last_data_time >= 0.05
                ):

                    break

                time.sleep(
                    0.05
                )

        return response

    # =================================================
    # Read Physical Weight
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

            self.serial.reset_input_buffer()

            self.serial.write(
                REQUEST_WEIGHT
            )

            self.serial.flush()

            response = self._read_response()

            if not response:

                self.weight_received.emit(
                    None
                )

                return

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
    def parse_weight(
        data
    ):

        if not data:

            return None

        try:

            text = data.decode(
                "ascii",
                errors="ignore"
            ).strip()

            if not text:

                return None

            matches = re.findall(
                r"[-+]?\s*\d+(?:\.\d+)?"
                r"(?:[eE][-+]?\d+)?",
                text
            )

            if not matches:

                return None

            return float(
                re.sub(
                    r"\s+",
                    "",
                    matches[0]
                )
            )

        except Exception:

            return None

    # =================================================
    # Tare Physical Scale
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

            self.serial.reset_input_buffer()

            self.serial.write(
                TARE
            )

            self.serial.flush()

            time.sleep(
                0.25
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
    # =================================================

    def zero(self):

        self.command_result.emit(
            False,
            "ZERO command not configured."
        )

    # =================================================
    # Close Physical Serial Port
    # =================================================

    def _close_serial(self):

        try:

            if (
                self.serial is not None
                and self.serial.is_open
            ):

                self.serial.close()

        except Exception:

            pass

        self.serial = None

        self.read_in_progress = False

    # =================================================
    # Disconnect Physical Scale
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

    def __init__(
        self,
        hide_on_close=False
    ):

        super().__init__()

        self.hide_on_close = hide_on_close

        self._read_pending = False

        self.connected = False

        self.system_healthy = False

        self.last_valid_reading = None

        self.health_timeout = SCALE_HEALTH_TIMEOUT

        # =================================================
        # Simulation Device Interface
        #
        # No simulation values or calculations are stored
        # in this file.
        # =================================================

        self.simulation_mode = False

        self.simulated_device = None

        self.setWindowTitle(
            "Scale Control"
        )

        self.resize(
            700,
            650
        )

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

        self.thread.finished.connect(
            self.worker.disconnect_scale
        )

        self.thread.start()

        # =================================================
        # Polling Timer
        # =================================================

        self.timer = QTimer(
            self
        )

        self.timer.timeout.connect(
            self.request_weight
        )

        self.timer.start(
            SCALE_POLL_INTERVAL
        )

        # =================================================
        # Health Timer
        # =================================================

        self.health_timer = QTimer(
            self
        )

        self.health_timer.timeout.connect(
            self.system_health_check
        )

        self.health_timer.start(
            SCALE_HEALTH_CHECK_INTERVAL
        )

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

            QPushButton:disabled {
                color: #666666;
                border: 1px solid #444444;
            }

            QComboBox {
                background-color: #1E1E1E;
                color: #D0D0D0;
                border: 1px solid #0080FF;
                padding: 6px;
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
            "Scale Communication"
        )

        communication_layout = QGridLayout()

        communication_layout.addWidget(
            QLabel("Connection Mode:"),
            0,
            0
        )

        self.mode_box = QComboBox()

        self.mode_box.addItems(
            [
                "Hardware (RS-485)",
                "Simulation"
            ]
        )

        self.mode_box.currentTextChanged.connect(
            self.update_connection_mode
        )

        communication_layout.addWidget(
            self.mode_box,
            0,
            1,
            1,
            3
        )

        communication_layout.addWidget(
            QLabel("COM Port:"),
            1,
            0
        )

        self.com_box = QComboBox()

        communication_layout.addWidget(
            self.com_box,
            1,
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
            1,
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
            1,
            3
        )

        communication_layout.addWidget(
            QLabel("Baud Rate:"),
            2,
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
            2,
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
            "Waiting"
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

        self.setLayout(
            main_layout
        )

        self.refresh_ports()

        self.set_controls_enabled(
            False
        )

        self.update_connection_mode(
            self.mode_box.currentText()
        )

        self.set_status(
            "Disconnected",
            "#FF4D4D"
        )

    # =================================================
    # Connection Mode
    # =================================================

    def update_connection_mode(
        self,
        mode
    ):

        if self.connected:

            return

        simulation = (
            mode == "Simulation"
        )

        self.com_box.setEnabled(
            not simulation
        )

        self.refresh_button.setEnabled(
            not simulation
        )

        self.baud_box.setEnabled(
            not simulation
        )

        if simulation:

            self.set_status(
                "Simulation selected",
                "#FFA500"
            )

        else:

            self.set_status(
                "Hardware mode selected",
                "#0080FF"
            )

        self.set_reading_status(
            "Waiting",
            "#FFFFFF"
        )

    # =================================================
    # Refresh Ports
    # =================================================

    def refresh_ports(self):

        current = self.com_box.currentText()

        self.com_box.clear()

        ports = ScaleWorker.get_ports()

        if not ports:

            self.com_box.addItem(
                "No COM Ports Found"
            )

        else:

            self.com_box.addItems(
                ports
            )

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

        if self.connected:

            self.disconnect_scale()

            return

        selected_mode = (
            self.mode_box.currentText()
        )

        if selected_mode == "Simulation":

            self.set_status(
                "Connecting...",
                "#FFA500"
            )

            self.set_reading_status(
                "Connecting...",
                "#FFA500"
            )

            self.connect_simulation()

            return

        port = self.com_box.currentText()

        if (
            not port
            or port == "No COM Ports Found"
        ):

            self.set_status(
                "Select a COM port.",
                "#FF4D4D"
            )

            self.set_reading_status(
                "Connection Failed",
                "#FF4D4D"
            )

            return

        try:

            baudrate = int(
                self.baud_box.currentText()
            )

        except ValueError:

            self.set_status(
                "Invalid baud rate.",
                "#FF4D4D"
            )

            self.set_reading_status(
                "Connection Failed",
                "#FF4D4D"
            )

            return

        if baudrate != 1200:

            self.set_status(
                "Sartorius 1773MP requires 1200 baud.",
                "#FF4D4D"
            )

            self.set_reading_status(
                "Connection Failed",
                "#FF4D4D"
            )

            return

        self.simulation_mode = False

        self.set_status(
            "Connecting...",
            "#FFA500"
        )

        self.set_reading_status(
            "Connecting...",
            "#FFA500"
        )

        self.connect_button.setEnabled(
            False
        )

        self.refresh_button.setEnabled(
            False
        )

        self.set_controls_enabled(
            False
        )

        self.system_healthy = False

        self.last_valid_reading = None

        self.connect_worker.emit(
            port,
            baudrate
        )

    # =================================================
    # Connect Simulated Scale
    # =================================================

    def connect_simulation(self):

        try:

            self.simulated_device = SimulatedScaleDevice(
                environment=get_simulation_environment()
            )

            success = (
                self.simulated_device.connect()
            )

        except Exception as exc:

            print(
                f"Simulated Scale Connection Error: {exc}"
            )

            success = False

        if not success:

            self.simulated_device = None

            self.simulation_mode = False

            self.connected = False

            self.set_status(
                "Simulation Connection Failed",
                "#FF4D4D"
            )

            self.set_reading_status(
                "Connection Failed",
                "#FF4D4D"
            )

            return

        self.simulation_mode = True

        self.connected = True

        self.system_healthy = True

        self.last_valid_reading = time.monotonic()

        self.mode_box.setEnabled(
            False
        )

        self.com_box.setEnabled(
            False
        )

        self.baud_box.setEnabled(
            False
        )

        self.refresh_button.setEnabled(
            False
        )

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

        self.set_reading_status(
            "Live Simulation",
            "#00D26A"
        )

        self.weight_status.setText(
            "Simulated reading"
        )

        self.read_simulated_weight()

    # =================================================
    # Physical Connection Result
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

        if success:

            self.connected = True

            self.system_healthy = True

            self.simulation_mode = False

            self.mode_box.setEnabled(
                False
            )

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

            self.set_reading_status(
                "Live Hardware",
                "#00D26A"
            )

        else:

            self.connected = False

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

            self.set_reading_status(
                "Connection Failed",
                "#FF4D4D"
            )

    # =================================================
    # Read Simulated Weight
    #
    # This method only communicates with the simulated
    # device. No simulation calculation is performed here.
    # =================================================

    def read_simulated_weight(self):

        if (
            not self.connected
            or not self.simulation_mode
            or self.simulated_device is None
        ):

            return

        try:

            weight = (
                self.simulated_device.read_weight()
            )

        except Exception as exc:

            self.worker_error(
                str(exc)
            )

            return

        self.weight_received(
            weight
        )

        if weight is not None:

            self.weight_status.setText(
                "Simulated reading"
            )

            self.set_reading_status(
                "Live Simulation",
                "#00D26A"
            )

    # =================================================
    # Request Weight
    # =================================================

    def request_weight(self):

        if not self.connected:

            return

        if self.simulation_mode:

            self.read_simulated_weight()

            return

        if self._read_pending:

            return

        self._read_pending = True

        self.read_weight_worker.emit()

    # =================================================
    # Manual Request
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

            self.set_reading_status(
                "No Live Reading",
                "#FF4D4D"
            )

            return

        try:

            weight = float(
                weight
            )

        except Exception:

            self.set_reading_status(
                "Invalid Reading",
                "#FF4D4D"
            )

            return

        self.last_valid_reading = time.monotonic()

        self.system_healthy = True

        self.weight_label.setText(
            f"{weight:.4f} g"
        )

        if self.simulation_mode:

            self.weight_status.setText(
                "Simulated reading"
            )

            self.set_reading_status(
                "Live Simulation",
                "#00D26A"
            )

        else:

            self.weight_status.setText(
                "Live reading"
            )

            self.set_reading_status(
                "Live Hardware",
                "#00D26A"
            )

    # =================================================
    # Health Check
    # =================================================

    def system_health_check(self):

        if not self.connected:

            return

        if self.last_valid_reading is None:

            self.system_healthy = False

            print(
                "Scale_health_check FAIL"
            )

            self.set_reading_status(
                "Communication Unhealthy",
                "#FFA500"
            )

            return

        elapsed = (
            time.monotonic()
            - self.last_valid_reading
        )

        if elapsed <= self.health_timeout:

            self.system_healthy = True

            print(
                "Scale_health_check PASS"
            )

            if self.simulation_mode:

                self.set_reading_status(
                    "Live Simulation",
                    "#00D26A"
                )

            else:

                self.set_reading_status(
                    "Live Hardware",
                    "#00D26A"
                )

        else:

            self.system_healthy = False

            print(
                "Scale_health_check FAIL"
            )

            self.set_reading_status(
                "Communication Unhealthy",
                "#FFA500"
            )

    # =================================================
    # Get Weight
    #
    # Returns the most recently received weight.
    # It performs no hardware or simulation operation.
    # =================================================

    def get_weight(self):

        if not self.connected:

            return None

        text = self.weight_label.text()

        if not text:

            return None

        try:

            return float(
                text.replace(
                    "g",
                    ""
                ).strip()
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

        if self.simulation_mode:

            success = (
                self.simulated_device is not None
                and self.simulated_device.tare()
            )

            if success:

                self.read_simulated_weight()

                self.set_status(
                    "Simulated scale tared.",
                    "#00D26A"
                )

            else:

                self.set_status(
                    "Simulated tare failed.",
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

        if self.simulation_mode:

            success = (
                self.simulated_device is not None
                and self.simulated_device.zero()
            )

            if success:

                self.read_simulated_weight()

                self.set_status(
                    "Simulated scale zeroed.",
                    "#00D26A"
                )

            else:

                self.set_status(
                    "Simulated zero failed.",
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

        self.set_status(
            message,
            "#00D26A"
            if success
            else "#FF4D4D"
        )

    # =================================================
    # Communication Status
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
    # Reading Status
    # =================================================

    def set_reading_status(
        self,
        message,
        color
    ):

        self.reading_status.setText(
            message
        )

        self.reading_status.setStyleSheet(
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

        self.set_reading_status(
            "Communication Error",
            "#FF4D4D"
        )

    # =================================================
    # Disconnect
    # =================================================

    def disconnect_scale(self):

        if self.simulation_mode:

            if self.simulated_device is not None:

                try:

                    self.simulated_device.disconnect()

                except Exception:

                    pass

        else:

            self.disconnect_worker.emit()

        self.simulated_device = None

        self.connected = False

        self.system_healthy = False

        self.last_valid_reading = None

        self._read_pending = False

        self.simulation_mode = False

        self.connect_button.setText(
            "Connect"
        )

        self.connect_button.setEnabled(
            True
        )

        self.mode_box.setEnabled(
            True
        )

        self.set_controls_enabled(
            False
        )

        self.weight_label.setText(
            "0.0000 g"
        )

        self.weight_status.setText(
            "Waiting for scale..."
        )

        self.set_reading_status(
            "Waiting",
            "#FFFFFF"
        )

        self.set_status(
            "Disconnected",
            "#FF4D4D"
        )

        self.update_connection_mode(
            self.mode_box.currentText()
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

        self.health_timer.stop()

        self.timer.stop()

        if self.simulation_mode:

            if self.simulated_device is not None:

                try:

                    self.simulated_device.disconnect()

                except Exception:

                    pass

        else:

            self.disconnect_worker.emit()

        self.simulated_device = None

        self.connected = False

        self.simulation_mode = False

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