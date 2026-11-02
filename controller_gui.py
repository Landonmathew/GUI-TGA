# =====================================================
# controller_gui.py
# Omega CN76000 Temperature Controller GUI
#
# Simplified interface:
#   - RS-485 ASCII communication
#   - Live process value
#   - SP1 / SP2 monitoring
#   - SP1 / SP2 adjustment
#   - Controller status
#   - Standalone operation
#
# Developed by:
# Landon Boger
#
# © 2026 Landon Boger
# All Rights Reserved.
#
# This software was developed for use with the
# TGA system at NREC/USF.
#
# Version 1.9
# =====================================================

import sys
import time

from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QComboBox,
    QVBoxLayout,
    QGridLayout,
    QGroupBox,
    QDoubleSpinBox,
)

from PyQt5.QtCore import (
    QTimer,
    QThread,
    pyqtSignal,
    QObject,
)

from temperature_controller import (
    OmegaTemperatureController,
    DEFAULT_BAUDRATE,
    DEFAULT_ADDRESS,
)

from simulated_temperature_controller import SimulatedCN76000Serial


# =====================================================
# Colors
# =====================================================

BLUE = "#0080FF"
LIGHT_BLUE = "#00AAFF"

WHITE = "#FFFFFF"

LIGHT_GRAY = "#D0D0D0"
DARK_GRAY = "#1E1E1E"

DARK_GREEN = "#00D26A"
ERROR_RED = "#FF4D4D"
ALARM_RED = "#FF4D4D"

ORANGE = "#FFA500"

DISABLED_GRAY = "#666666"


# =====================================================
# Timing
# =====================================================

# Normal controller polling interval
CONTROLLER_POLL_INTERVAL = 2000

# System health check interval
CONTROLLER_HEALTH_CHECK_INTERVAL = 6000

# Maximum time allowed without a valid controller
# state response before the health check reports FAIL.
CONTROLLER_HEALTH_TIMEOUT = 6.0


# =====================================================
# Controller Worker
# =====================================================

class ControllerWorker(QObject):

    connection_result = pyqtSignal(bool)

    controller_state_received = pyqtSignal(object)

    # name, success, value, message
    setpoint_result = pyqtSignal(
        str,
        bool,
        float,
        str
    )

    error = pyqtSignal(str)

    def __init__(self):

        super().__init__()

        self.controller = None

    # =================================================
    # Connect
    # =================================================

    def connect_controller(
        self,
        port,
        baudrate,
        address,
        mode
    ):

        try:

            # Simulation uses the same controller/protocol
            # layer as hardware.
            #
            # Hardware mode retains the original real
            # serial connection path.

            if mode == "Simulation":

                simulated_serial = SimulatedCN76000Serial()

                self.controller = OmegaTemperatureController(
                    baudrate=baudrate,
                    slave_address=address,
                    timeout=1.0,
                    verbose=False,
                    serial_override=simulated_serial,
                )

            else:

                self.controller = OmegaTemperatureController(
                    port=port,
                    baudrate=baudrate,
                    slave_address=address,
                    timeout=1.0,
                    verbose=False,
                )

            success = self.controller.connect()

            if not success:

                self.controller = None

            self.connection_result.emit(
                success
            )

        except Exception as exc:

            self.controller = None

            self.error.emit(
                str(exc)
            )

            self.connection_result.emit(
                False
            )

    # =================================================
    # Read Controller State
    # =================================================

    def read_controller_state(self):

        if self.controller is None:

            return

        if not self.controller.connected:

            return

        try:

            state = (
                self.controller.read_controller_state()
            )

            self.controller_state_received.emit(
                state
            )

        except Exception as exc:

            self.error.emit(
                str(exc)
            )

    # =================================================
    # Set SP1
    # =================================================

    def set_sp1(
        self,
        value
    ):

        self._set_setpoint(
            "SP1",
            value,
            self.controller.set_setpoint_1
            if self.controller
            else None
        )

    # =================================================
    # Set SP2
    # =================================================

    def set_sp2(
        self,
        value
    ):

        self._set_setpoint(
            "SP2",
            value,
            self.controller.set_setpoint_2
            if self.controller
            else None
        )

    # =================================================
    # Setpoint Helper
    # =================================================

    def _set_setpoint(
        self,
        name,
        value,
        function
    ):

        if self.controller is None:

            self.setpoint_result.emit(
                name,
                False,
                value,
                "Controller not connected."
            )

            return

        if not self.controller.connected:

            self.setpoint_result.emit(
                name,
                False,
                value,
                "Controller not connected."
            )

            return

        if function is None:

            self.setpoint_result.emit(
                name,
                False,
                value,
                f"{name} write function unavailable."
            )

            return

        try:

            result = function(
                value
            )

            success = bool(
                result
                and result.get("success")
            )

            if success:

                message = (
                    f"{name} updated."
                )

            else:

                message = (
                    result.get(
                        "error_description",
                        f"{name} write failed."
                    )
                    if result
                    else
                    f"{name} write failed."
                )

            # Return the EXACT value that was sent.
            self.setpoint_result.emit(
                name,
                success,
                value,
                message
            )

        except Exception as exc:

            self.setpoint_result.emit(
                name,
                False,
                value,
                str(exc)
            )

    # =================================================
    # Disconnect
    # =================================================

    def disconnect_controller(self):

        try:

            if self.controller:

                self.controller.disconnect()

        except Exception:

            pass

        self.controller = None

    # =================================================
    # Shutdown
    # =================================================

    def shutdown(self):

        self.disconnect_controller()


# =====================================================
# Main Temperature Controller Window
# =====================================================

class TemperatureControllerWindow(QWidget):

    # =================================================
    # Worker Signals
    # =================================================

    connect_worker = pyqtSignal(
        str,
        int,
        int,
        str
    )

    read_state_worker = pyqtSignal()

    set_sp1_worker = pyqtSignal(
        float
    )

    set_sp2_worker = pyqtSignal(
        float
    )

    disconnect_worker = pyqtSignal()

    # =================================================
    # Initialize
    # =================================================

    def __init__(self, hide_on_close=False):

        super().__init__()

        self.hide_on_close = hide_on_close

        self._read_pending = False

        # =================================================
        # System Health State
        # =================================================

        # This is separate from controller.connected.
        #
        # connected:
        #     The controller communication connection is open.
        #
        # system_healthy:
        #     Valid controller state responses are currently
        #     being received.

        self.system_healthy = False

        # Time of the most recent valid controller state
        # response.
        self.last_valid_controller_response = None

        self.setWindowTitle(
            "Temperature Controller"
        )

        self.resize(
            700,
            600
        )

        # =================================================
        # Controller
        # =================================================

        self.controller = None

        # =================================================
        # Worker Thread
        # =================================================

        self.thread = QThread(
            self
        )

        self.worker = ControllerWorker()

        self.worker.moveToThread(
            self.thread
        )

        # =================================================
        # Worker Connections
        # =================================================

        self.connect_worker.connect(
            self.worker.connect_controller
        )

        self.read_state_worker.connect(
            self.worker.read_controller_state
        )

        self.set_sp1_worker.connect(
            self.worker.set_sp1
        )

        self.set_sp2_worker.connect(
            self.worker.set_sp2
        )

        self.disconnect_worker.connect(
            self.worker.disconnect_controller
        )

        self.worker.connection_result.connect(
            self.connection_finished
        )

        self.worker.controller_state_received.connect(
            self.controller_state_received
        )

        self.worker.setpoint_result.connect(
            self.setpoint_finished
        )

        self.worker.error.connect(
            self.worker_error
        )

        self.thread.finished.connect(
            self.worker.shutdown
        )

        self.thread.start()

        # =================================================
        # Poll Timer
        # =================================================

        self.update_timer = QTimer(
            self
        )

        self.update_timer.timeout.connect(
            self.request_state
        )

        self.update_timer.start(
            CONTROLLER_POLL_INTERVAL
        )

        # =================================================
        # Health Check Timer
        # =================================================

        self.health_timer = QTimer(
            self
        )

        self.health_timer.timeout.connect(
            self.system_health_check
        )

        self.health_timer.start(
            CONTROLLER_HEALTH_CHECK_INTERVAL
        )

        # =================================================
        # Build UI
        # =================================================

        self.init_ui()

        self.refresh_ports()

        self.update_connection_mode(
            self.mode_box.currentText()
        )

        self.set_controls_enabled(
            False
        )

    # =================================================
    # UI
    # =================================================

    def init_ui(self):

        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {DARK_GRAY};
                color: {LIGHT_GRAY};
                font-size: 14px;
            }}

            QGroupBox {{
                background-color: {DARK_GRAY};
                border: 1px solid #3A5A75;
                border-radius: 6px;
                margin-top: 10px;
                padding: 10px;
                font-weight: bold;
                color: {WHITE};
            }}

            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: {WHITE};
            }}

            QPushButton {{
                background-color: {DARK_GRAY};
                color: {LIGHT_GRAY};
                border: 1px solid {BLUE};
                padding: 7px;
                border-radius: 5px;
            }}

            QPushButton:hover {{
                background-color: #003B66;
                color: {WHITE};
            }}

            QPushButton:pressed {{
                background-color: #005A99;
                color: {WHITE};
            }}

            QPushButton:disabled {{
                background-color: {DARK_GRAY};
                color: {DISABLED_GRAY};
                border: 1px solid #444444;
            }}

            QComboBox {{
                background-color: {DARK_GRAY};
                color: {LIGHT_GRAY};
                border: 1px solid {BLUE};
                padding: 5px;
            }}

            QComboBox QAbstractItemView {{
                background-color: {DARK_GRAY};
                color: {LIGHT_GRAY};
                selection-background-color: #003B66;
                selection-color: {WHITE};
            }}

            QLineEdit,
            QDoubleSpinBox,
            QSpinBox {{
                background-color: {DARK_GRAY};
                color: {LIGHT_GRAY};
                border: 1px solid {BLUE};
                padding: 5px;
            }}

            QLabel {{
                color: {LIGHT_GRAY};
            }}
            """
        )

        main_layout = QVBoxLayout()

        # =================================================
        # Title
        # =================================================

        title = QLabel(
            "Temperature Controller"
        )

        title.setStyleSheet(
            f"""
            font-size: 21px;
            font-weight: bold;
            color: {BLUE};
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
            str(DEFAULT_BAUDRATE)
        )

        communication_layout.addWidget(
            self.baud_box,
            2,
            1
        )

        communication_layout.addWidget(
            QLabel("Controller Address:"),
            2,
            2
        )

        self.address_box = QComboBox()

        self.address_box.addItems(
            [
                str(i)
                for i in range(
                    1,
                    256
                )
            ]
        )

        self.address_box.setCurrentText(
            str(DEFAULT_ADDRESS)
        )

        communication_layout.addWidget(
            self.address_box,
            2,
            3
        )

        communication_group.setLayout(
            communication_layout
        )

        main_layout.addWidget(
            communication_group
        )

        # =================================================
        # Live Values
        # =================================================

        live_group = QGroupBox(
            "Live Controller Values"
        )

        live_layout = QGridLayout()

        # =================================================
        # Process Value
        # =================================================

        live_layout.addWidget(
            QLabel("Process Value:"),
            0,
            0
        )

        self.actual_temperature = QLabel(
            "---- °C"
        )

        self.actual_temperature.setStyleSheet(
            f"""
            font-size: 28px;
            font-weight: bold;
            color: {WHITE};
            """
        )

        live_layout.addWidget(
            self.actual_temperature,
            0,
            1
        )

        # =================================================
        # SP1
        # =================================================

        live_layout.addWidget(
            QLabel("SP1:"),
            1,
            0
        )

        self.sp1_display = QLabel(
            "----"
        )

        self.sp1_display.setStyleSheet(
            f"color: {WHITE};"
        )

        live_layout.addWidget(
            self.sp1_display,
            1,
            1
        )

        # =================================================
        # SP2
        # =================================================

        live_layout.addWidget(
            QLabel("SP2:"),
            2,
            0
        )

        self.sp2_display = QLabel(
            "----"
        )

        self.sp2_display.setStyleSheet(
            f"color: {WHITE};"
        )

        live_layout.addWidget(
            self.sp2_display,
            2,
            1
        )

        # =================================================
        # Mode
        # =================================================

        live_layout.addWidget(
            QLabel("Mode:"),
            0,
            2
        )

        self.mode_display = QLabel(
            "----"
        )

        self.mode_display.setStyleSheet(
            f"color: {WHITE};"
        )

        live_layout.addWidget(
            self.mode_display,
            0,
            3
        )

        # =================================================
        # Control Location
        # =================================================

        live_layout.addWidget(
            QLabel("Control Location:"),
            1,
            2
        )

        self.location_display = QLabel(
            "----"
        )

        self.location_display.setStyleSheet(
            f"color: {WHITE};"
        )

        live_layout.addWidget(
            self.location_display,
            1,
            3
        )

        # =================================================
        # Alarm
        # =================================================

        live_layout.addWidget(
            QLabel("Alarm Relay:"),
            2,
            2
        )

        self.alarm_display = QLabel(
            "----"
        )

        self.alarm_display.setStyleSheet(
            f"color: {WHITE};"
        )

        live_layout.addWidget(
            self.alarm_display,
            2,
            3
        )

        live_group.setLayout(
            live_layout
        )

        main_layout.addWidget(
            live_group
        )

        # =================================================
        # Setpoints
        # =================================================

        setpoint_group = QGroupBox(
            "Setpoints"
        )

        setpoint_layout = QGridLayout()

        # =================================================
        # SP1
        # =================================================

        setpoint_layout.addWidget(
            QLabel("SP1:"),
            0,
            0
        )

        self.sp1_input = QDoubleSpinBox()

        self.sp1_input.setRange(
            0,
            999.9
        )

        self.sp1_input.setDecimals(
            2
        )

        self.sp1_input.setSingleStep(
            0.1
        )

        setpoint_layout.addWidget(
            self.sp1_input,
            0,
            1
        )

        self.sp1_button = QPushButton(
            "Set SP1"
        )

        self.sp1_button.clicked.connect(
            self.set_sp1
        )

        setpoint_layout.addWidget(
            self.sp1_button,
            0,
            2
        )

        # =================================================
        # SP2
        # =================================================

        setpoint_layout.addWidget(
            QLabel("SP2:"),
            1,
            0
        )

        self.sp2_input = QDoubleSpinBox()

        self.sp2_input.setRange(
            0,
            999.9
        )

        self.sp2_input.setDecimals(
            2
        )

        self.sp2_input.setSingleStep(
            0.1
        )

        setpoint_layout.addWidget(
            self.sp2_input,
            1,
            1
        )

        self.sp2_button = QPushButton(
            "Set SP2"
        )

        self.sp2_button.clicked.connect(
            self.set_sp2
        )

        setpoint_layout.addWidget(
            self.sp2_button,
            1,
            2
        )

        setpoint_group.setLayout(
            setpoint_layout
        )

        main_layout.addWidget(
            setpoint_group
        )

        # =================================================
        # Controller Status
        # =================================================

        status_group = QGroupBox(
            "Controller Status"
        )

        status_layout = QGridLayout()

        # =================================================
        # Communication
        # =================================================

        status_layout.addWidget(
            QLabel("Communication:"),
            0,
            0
        )

        self.status_label = QLabel(
            "Disconnected"
        )

        self.status_label.setStyleSheet(
            f"color: {ERROR_RED}; font-weight: bold;"
        )

        status_layout.addWidget(
            self.status_label,
            0,
            1
        )

        # =================================================
        # Error
        # =================================================

        status_layout.addWidget(
            QLabel("Error:"),
            1,
            0
        )

        self.error_status = QLabel(
            "NONE"
        )

        self.error_status.setStyleSheet(
            f"color: {DARK_GREEN};"
        )

        status_layout.addWidget(
            self.error_status,
            1,
            1
        )

        # =================================================
        # Decimal Places
        # =================================================

        status_layout.addWidget(
            QLabel("Decimal Places:"),
            2,
            0
        )

        self.decimal_status = QLabel(
            "----"
        )

        self.decimal_status.setStyleSheet(
            f"color: {WHITE};"
        )

        status_layout.addWidget(
            self.decimal_status,
            2,
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

    # =================================================
    # Connection Mode
    # =================================================

    def update_connection_mode(
        self,
        mode
    ):

        simulation = (
            mode == "Simulation"
        )

        self.com_box.setEnabled(
            not simulation
        )

        self.refresh_button.setEnabled(
            not simulation
        )

        if simulation:

            self.set_status(
                "Simulation selected — no hardware will be accessed.",
                ORANGE
            )

        else:

            self.set_status(
                "Hardware mode selected.",
                BLUE
            )

    # =================================================
    # COM Ports
    # =================================================

    def refresh_ports(self):

        current = (
            self.com_box.currentText()
        )

        self.com_box.clear()

        ports = (
            OmegaTemperatureController.get_ports()
        )

        for port in ports:

            self.com_box.addItem(
                port
            )

        if current:

            index = (
                self.com_box.findText(
                    current
                )
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

        self.sp1_input.setEnabled(
            enabled
        )

        self.sp1_button.setEnabled(
            enabled
        )

        self.sp2_input.setEnabled(
            enabled
        )

        self.sp2_button.setEnabled(
            enabled
        )

    # =================================================
    # Connection
    # =================================================

    def toggle_connection(self):

        if (
            self.controller is None
            or not self.controller.connected
        ):

            selected_mode = (
                self.mode_box.currentText()
            )

            simulation = (
                selected_mode == "Simulation"
            )

            port = (
                self.com_box.currentText()
            )

            if not simulation and not port:

                self.set_status(
                    "Select a COM port.",
                    ERROR_RED
                )

                return

            try:

                baudrate = int(
                    self.baud_box.currentText()
                )

                address = int(
                    self.address_box.currentText()
                )

            except ValueError:

                self.set_status(
                    "Invalid communication settings.",
                    ERROR_RED
                )

                return

            self.set_status(
                "Connecting...",
                ORANGE
            )

            self.connect_button.setEnabled(
                False
            )

            self.refresh_button.setEnabled(
                False
            )

            mode = (
                "Simulation"
                if simulation
                else "Hardware"
            )

            self.connect_worker.emit(
                port,
                baudrate,
                address,
                mode
            )

        else:

            self.disconnect_controller()

    # =================================================
    # Connection Finished
    # =================================================

    def connection_finished(
        self,
        success
    ):

        self._read_pending = False

        self.connect_button.setEnabled(
            True
        )

        self.refresh_button.setEnabled(
            True
        )

        if success:

            self.controller = (
                self.worker.controller
            )

            # Reset health tracking for the new connection.
            self.system_healthy = False

            self.last_valid_controller_response = None

            self.connect_button.setText(
                "Disconnect"
            )

            self.set_status(
                "Connected",
                DARK_GREEN
            )

            self.set_controls_enabled(
                True
            )

            # Immediately request the first state.
            self.request_state()

        else:

            self.controller = None

            self.system_healthy = False

            self.last_valid_controller_response = None

            self.connect_button.setText(
                "Connect"
            )

            self.set_controls_enabled(
                False
            )

            self.set_status(
                "Controller Not Found",
                ERROR_RED
            )

    # =================================================
    # System Health Check
    # =================================================

    def system_health_check(self):

        # Do not run the health evaluation when there is
        # no active controller connection.
        if self.controller is None:

            return

        if not self.controller.connected:

            return

        # If no valid response has ever been received
        # since connection, the controller is not healthy.
        if self.last_valid_controller_response is None:

            self.system_healthy = False

            print(
                "Temperature_controller_health_check FAIL"
            )

            return

        elapsed = (
            time.monotonic()
            - self.last_valid_controller_response
        )

        if elapsed >= CONTROLLER_HEALTH_TIMEOUT:

            self.system_healthy = False

            print(
                "Temperature_controller_health_check FAIL"
            )

        else:

            self.system_healthy = True

            print(
                "Temperature_controller_health_check PASS"
            )

    # =================================================
    # Disconnect
    # =================================================

    def disconnect_controller(self):

        self.disconnect_worker.emit()

        self.controller = None

        # Reset health state.
        self.system_healthy = False

        self.last_valid_controller_response = None

        self.connect_button.setText(
            "Connect"
        )

        self.set_controls_enabled(
            False
        )

        # =================================================
        # Reset Live Values
        # =================================================

        self.actual_temperature.setText(
            "---- °C"
        )

        self.actual_temperature.setStyleSheet(
            f"""
            font-size: 28px;
            font-weight: bold;
            color: {WHITE};
            """
        )

        self.sp1_display.setText(
            "----"
        )

        self.sp1_display.setStyleSheet(
            f"color: {WHITE};"
        )

        self.sp2_display.setText(
            "----"
        )

        self.sp2_display.setStyleSheet(
            f"color: {WHITE};"
        )

        self.mode_display.setText(
            "----"
        )

        self.mode_display.setStyleSheet(
            f"color: {WHITE};"
        )

        self.location_display.setText(
            "----"
        )

        self.location_display.setStyleSheet(
            f"color: {WHITE};"
        )

        self.alarm_display.setText(
            "----"
        )

        self.alarm_display.setStyleSheet(
            f"color: {WHITE};"
        )

        # =================================================
        # Reset Status Values
        # =================================================

        self.error_status.setText(
            "NONE"
        )

        self.error_status.setStyleSheet(
            f"color: {DARK_GREEN};"
        )

        self.decimal_status.setText(
            "----"
        )

        self.decimal_status.setStyleSheet(
            f"color: {WHITE};"
        )

        self.set_status(
            "Disconnected",
            ERROR_RED
        )

    # =================================================
    # Request State
    # =================================================

    def request_state(self):

        if self._read_pending:

            return

        if self.controller is None:

            return

        if not self.controller.connected:

            return

        self._read_pending = True

        self.read_state_worker.emit()

    # =================================================
    # State Received
    # =================================================

    def controller_state_received(
        self,
        state
    ):

        self._read_pending = False

        self.actual_temperature.setText(
            "---- °C"
        )

        if self.controller is None:

            return

        if not state:

            self.set_status(
                "No Controller Response",
                ERROR_RED
            )

            return

        # =================================================
        # Valid Controller Response
        # =================================================
        #
        # A valid state object means communication was
        # successfully received from the controller.
        #
        # Update the health timestamp here.
        # =================================================

        self.last_valid_controller_response = (
            time.monotonic()
        )

        # Automatically recover the health state when
        # valid communication returns.

        self.system_healthy = True

        # =================================================
        # Process Value
        # =================================================

        if state.get("pv") is not None:

            self.actual_temperature.setText(
                f"{state['pv']:.2f} °C"
            )

            self.actual_temperature.setStyleSheet(
                f"""
                font-size: 28px;
                font-weight: bold;
                color: {WHITE};
                """
            )

        # =================================================
        # SP1
        # =================================================

        if state.get("sp1") is not None:

            value = state["sp1"]

            # Update ONLY the live controller display.
            #
            # The input box is intentionally NOT changed here.
            # The input box is for entering the next setpoint.

            self.sp1_display.setText(
                f"{value:.2f} °C"
            )

            self.sp1_display.setStyleSheet(
                f"color: {WHITE};"
            )

        # =================================================
        # SP2
        # =================================================

        if state.get("sp2") is not None:

            value = state["sp2"]

            # Update ONLY the live controller display.
            #
            # The input box is intentionally NOT changed here.
            # The input box is for entering the next setpoint.

            self.sp2_display.setText(
                f"{value:.2f} °C"
            )

            self.sp2_display.setStyleSheet(
                f"color: {WHITE};"
            )

        # =================================================
        # Mode
        # =================================================

        if state.get("mode"):

            self.mode_display.setText(
                state["mode"]
            )

            self.mode_display.setStyleSheet(
                f"color: {WHITE};"
            )

        # =================================================
        # Control Location
        # =================================================

        if state.get("control_location"):

            self.location_display.setText(
                state["control_location"]
            )

            self.location_display.setStyleSheet(
                f"color: {WHITE};"
            )

        # =================================================
        # Alarm
        # =================================================

        alarm = state.get(
            "alarm_relay"
        )

        if alarm is True:

            self.alarm_display.setText(
                "ENERGIZED"
            )

            self.alarm_display.setStyleSheet(
                f"color: {ALARM_RED};"
            )

        elif alarm is False:

            self.alarm_display.setText(
                "DE-ENERGIZED"
            )

            self.alarm_display.setStyleSheet(
                f"color: {WHITE};"
            )

        # =================================================
        # Decimal Places
        # =================================================

        if state.get(
            "decimal_places"
        ) is not None:

            self.decimal_status.setText(
                str(
                    state["decimal_places"]
                )
            )

            self.decimal_status.setStyleSheet(
                f"color: {WHITE};"
            )

        # =================================================
        # Full Error Status
        # =================================================

        full_status = state.get(
            "full_status"
        )

        if full_status:

            self.update_full_status(
                full_status
            )

        else:

            if state.get(
                "error_present"
            ):

                self.error_status.setText(
                    "ERROR PRESENT"
                )

                self.error_status.setStyleSheet(
                    f"color: {ERROR_RED}; font-weight: bold;"
                )

            else:

                self.error_status.setText(
                    "NONE"
                )

                self.error_status.setStyleSheet(
                    f"color: {DARK_GREEN};"
                )

        # =================================================
        # Communication Status
        # =================================================

        self.set_status(
            "Connected",
            DARK_GREEN
        )

    # =================================================
    # Full Status
    # =================================================

    def update_full_status(
        self,
        status
    ):

        if status.get(
            "error_active"
        ):

            active_errors = []

            for name, active in (
                status.get(
                    "errors",
                    {}
                ).items()
            ):

                if active:

                    active_errors.append(
                        name.replace(
                            "_",
                            " "
                        ).upper()
                    )

            if active_errors:

                self.error_status.setText(
                    ", ".join(
                        active_errors
                    )
                )

            else:

                self.error_status.setText(
                    "ERROR ACTIVE"
                )

            self.error_status.setStyleSheet(
                f"color: {ERROR_RED}; font-weight: bold;"
            )

        else:

            self.error_status.setText(
                "NONE"
            )

            self.error_status.setStyleSheet(
                f"color: {DARK_GREEN};"
            )

    # =================================================
    # Set SP1
    # =================================================

    def set_sp1(self):

        if not self.is_connected():

            return

        value = (
            self.sp1_input.value()
        )

        self.sp1_button.setEnabled(
            False
        )

        self.set_status(
            "Setting SP1...",
            ORANGE
        )

        self.set_sp1_worker.emit(
            value
        )

    # =================================================
    # Set SP2
    # =================================================

    def set_sp2(self):

        if not self.is_connected():

            return

        value = (
            self.sp2_input.value()
        )

        self.sp2_button.setEnabled(
            False
        )

        self.set_status(
            "Setting SP2...",
            ORANGE
        )

        self.set_sp2_worker.emit(
            value
        )

    # =================================================
    # Setpoint Result
    # =================================================

    def setpoint_finished(
        self,
        name,
        success,
        value,
        message
    ):

        # =================================================
        # Re-enable the buttons
        # =================================================

        self.sp1_button.setEnabled(
            True
        )

        self.sp2_button.setEnabled(
            True
        )

        if success:

            # =================================================
            # SP1
            # =================================================

            if name == "SP1":

                # Show the value that was actually sent
                # to the controller.

                self.sp1_display.setText(
                    f"{value:.2f} °C"
                )

                self.sp1_display.setStyleSheet(
                    f"color: {WHITE};"
                )

                # Reset the command-entry box.

                self.sp1_input.setValue(
                    0.0
                )

            # =================================================
            # SP2
            # =================================================

            elif name == "SP2":

                # Show the value that was actually sent
                # to the controller.

                self.sp2_display.setText(
                    f"{value:.2f} °C"
                )

                self.sp2_display.setStyleSheet(
                    f"color: {WHITE};"
                )

                # Reset the command-entry box.

                self.sp2_input.setValue(
                    0.0
                )

            self.set_status(
                message,
                DARK_GREEN
            )

            # Confirm the controller's actual value shortly
            # after the write.

            QTimer.singleShot(
                100,
                self.request_state
            )

        else:

            self.set_status(
                message,
                ERROR_RED
            )

    # =================================================
    # Connection Check
    # =================================================

    def is_connected(self):

        if (
            self.controller is None
            or not self.controller.connected
        ):

            self.set_status(
                "Connect Controller First",
                ERROR_RED
            )

            return False

        return True

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

        self.actual_temperature.setText(
            "---- °C"
        )

        print(
            f"Omega Controller Error: {message}"
        )

        self.set_status(
            "Communication Error",
            ERROR_RED
        )

        # IMPORTANT:
        #
        # Do not disconnect the controller here.
        #
        # The health check will determine whether the
        # communication has actually been lost.
        #
        # The controller remains connected and polling
        # continues every 2 seconds.

    # =================================================
    # Get Current Temperature
    #
    # Compatibility method for the TGA software.
    # No serial I/O is performed here.
    # =================================================

    def get_temperature(self):

        if self.controller is None or not self.controller.connected:

            return None

        text = (
            self.actual_temperature.text()
        )

        if not text:

            return None

        try:

            return float(
                text.replace(
                    "°C",
                    ""
                ).strip()
            )

        except ValueError:

            return None

    # =================================================
    # Close Event
    # =================================================

    def closeEvent(
        self,
        event
    ):

        if self.hide_on_close:

            self.hide()

            event.accept()

            return

        self.update_timer.stop()

        self.health_timer.stop()

        self.disconnect_worker.emit()

        self.thread.quit()

        self.thread.wait()

        event.accept()


# =====================================================
# Standalone Application Entry Point
#
# This allows:
#
#     python controller_gui.py
#
# to launch the controller window directly.
#
# When imported by the main GUI, this section does
# NOT execute, so TemperatureControllerWindow can
# still be imported and opened by the main application.
# =====================================================

if __name__ == "__main__":

    app = QApplication(
        sys.argv
    )

    window = TemperatureControllerWindow()

    window.show()

    sys.exit(
        app.exec_()
    )