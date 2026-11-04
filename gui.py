# =====================================================
# gui.py
# TGA Control and Data Acquisition System
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
#
# Main GUI
#
# Communication is handled by:
#     - controller_gui.py
#     - scale_controller.py
#
# The main GUI is responsible for:
#     - Experiment control
#     - Live data display
#     - Graphs
#     - CSV export
#     - Opening the Scale Controller
#     - Opening the Temperature Controller
#
# =====================================================

import sys
import time
import csv

from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QFileDialog,
)

from PyQt5.QtCore import (
    QTimer,
    Qt,
)

import config

from plots import PlotWindow

from controller_gui import (
    TemperatureControllerWindow
)

from scale_controller import (
    ScaleControlWindow
)


# =====================================================
# Main GUI Class
# =====================================================

class TGA_GUI(QWidget):

    def __init__(self):

        super().__init__()

        # =================================================
        # Data Storage
        # =================================================

        self.time_data = []

        self.mass_data = []

        self.temp_data = []

        self.start_time = None

        self.running = False

        self.latest_mass = 0.0

        self.latest_temperature = 0.0

        # =================================================
        # Plot Window
        # =================================================

        self.plot_window = PlotWindow()

        # =================================================
        # Temperature Controller
        # =================================================

        self.temperature_controller_window = (
            TemperatureControllerWindow(hide_on_close=True)
        )

        # =================================================
        # Scale Controller
        # =================================================

        self.scale_control_window = (
            ScaleControlWindow(hide_on_close=True)
        )

        # =================================================
        # Main Experiment Update Timer
        # =================================================

        r = QTimer(self)

        self.timer.timeout.connect(
            self.update_system
        )

        # =================================================
        # Connection Monitoring Timer
        #
        # This timer runs independently of the experiment.
        # It allows the GUI to detect connected devices
        # before the user starts an experiment.
        # =================================================

        self.connection_timer = QTimer(self)

        self.connection_timer.timeout.connect(
            self.update_connection_status
        )

        # Check connections every 1 second
        self.connection_timer.start(
            1000
        )

        # =================================================
        # Build GUI
        # =================================================

        self.init_ui()

        # =================================================
        # Check Connections Immediately
        #
        # This avoids waiting one full second for the
        # first connection check.
        # =================================================

        self.update_connection_status()

    # =====================================================
    # Create GUI
    # =====================================================

    def init_ui(self):

        self.setWindowTitle(
            config.WINDOW_TITLE
        )

        self.resize(
            config.MAIN_WIDTH,
            config.MAIN_HEIGHT
        )

        # =================================================
        # Theme
        #
        # Main background:
        #     Dark gray
        #
        # Normal text:
        #     Light gray
        #
        # Section headers:
        #     White
        #
        # Blue:
        #     Accent color for title and controls
        #
        # Status colors:
        #     Green = Connected / Running
        #     Red = Disconnected / Stopped / Error
        # =================================================

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
            """
        )

        # =================================================
        # Main Layout
        # =================================================

        main_layout = QVBoxLayout()

        # =================================================
        # TITLE
        # =================================================

        self.title = QLabel(
            "THERMOGRAVIMETRIC ANALYZER"
        )

        self.title.setStyleSheet(
            """
            color: #0080FF;
            font-size: 24px;
            font-weight: bold;
            """
        )

        self.title.setAlignment(
            Qt.AlignCenter
        )

        main_layout.addWidget(
            self.title
        )

        # =================================================
        # SYSTEM STATUS
        # =================================================

        status_group = QGroupBox(
            "TGA System Status"
        )

        status_layout = QGridLayout()

        status_layout.addWidget(
            QLabel("Experiment Status:"),
            0,
            0
        )

        self.status_label = QLabel(
            "Ready"
        )

        self.status_label.setStyleSheet(
            """
            color: #FFFFFF;
            font-weight: bold;
            """
        )

        status_layout.addWidget(
            self.status_label,
            0,
            1
        )

        status_layout.addWidget(
            QLabel("Temperature Controller:"),
            1,
            0
        )

        self.temperature_connection_status = QLabel(
            "Disconnected"
        )

        self.temperature_connection_status.setStyleSheet(
            """
            color: #FF4D4D;
            font-weight: bold;
            """
        )

        status_layout.addWidget(
            self.temperature_connection_status,
            1,
            1
        )

        status_layout.addWidget(
            QLabel("Scale:"),
            2,
            0
        )

        self.scale_connection_status = QLabel(
            "Disconnected"
        )

        self.scale_connection_status.setStyleSheet(
            """
            color: #FF4D4D;
            font-weight: bold;
            """
        )

        status_layout.addWidget(
            self.scale_connection_status,
            2,
            1
        )

        status_group.setLayout(
            status_layout
        )

        main_layout.addWidget(
            status_group
        )

        # =================================================
        # LIVE DATA
        # =================================================

        live_group = QGroupBox(
            "Live TGA Data"
        )

        live_layout = QGridLayout()

        # =================================================
        # Mass
        # =================================================

        live_layout.addWidget(
            QLabel("Mass:"),
            0,
            0
        )

        self.mass_value = QLabel(
            "0.0000 g"
        )

        self.mass_value.setAlignment(
            Qt.AlignCenter
        )

        self.mass_value.setStyleSheet(
            """
            color: #FFFFFF;
            font-size: 30px;
            font-weight: bold;
            """
        )

        live_layout.addWidget(
            self.mass_value,
            0,
            1
        )

        # =================================================
        # Temperature
        # =================================================

        live_layout.addWidget(
            QLabel("Temperature:"),
            1,
            0
        )

        self.temp_value = QLabel(
            "0.00 °C"
        )

        self.temp_value.setAlignment(
            Qt.AlignCenter
        )

        self.temp_value.setStyleSheet(
            """
            color: #FFFFFF;
            font-size: 30px;
            font-weight: bold;
            """
        )

        live_layout.addWidget(
            self.temp_value,
            1,
            1
        )

        # =================================================
        # Time
        # =================================================

        live_layout.addWidget(
            QLabel("Elapsed Time:"),
            2,
            0
        )

        self.time_value = QLabel(
            "00:00:00"
        )

        self.time_value.setAlignment(
            Qt.AlignCenter
        )

        self.time_value.setStyleSheet(
            """
            color: #FFFFFF;
            font-size: 28px;
            font-weight: bold;
            """
        )

        live_layout.addWidget(
            self.time_value,
            2,
            1
        )

        # =================================================
        # Temperature SP1
        # =================================================

        live_layout.addWidget(
            QLabel("Temperature SP1:"),
            0,
            2
        )

        self.sp1_value = QLabel(
            "---- °C"
        )

        self.sp1_value.setAlignment(
            Qt.AlignCenter
        )

        self.sp1_value.setStyleSheet(
            """
            color: #FFFFFF;
            font-size: 20px;
            font-weight: bold;
            """
        )

        live_layout.addWidget(
            self.sp1_value,
            0,
            3
        )

        # =================================================
        # Temperature SP2
        # =================================================

        live_layout.addWidget(
            QLabel("Temperature SP2:"),
            1,
            2
        )

        self.sp2_value = QLabel(
            "---- °C"
        )

        self.sp2_value.setAlignment(
            Qt.AlignCenter
        )

        self.sp2_value.setStyleSheet(
            """
            color: #FFFFFF;
            font-size: 20px;
            font-weight: bold;
            """
        )

        live_layout.addWidget(
            self.sp2_value,
            1,
            3
        )

        # =================================================
        # Temperature Mode
        # =================================================

        live_layout.addWidget(
            QLabel("Temperature Mode:"),
            2,
            2
        )

        self.mode_value = QLabel(
            "----"
        )

        self.mode_value.setAlignment(
            Qt.AlignCenter
        )

        self.mode_value.setStyleSheet(
            """
            color: #FFFFFF;
            font-size: 20px;
            font-weight: bold;
            """
        )

        live_layout.addWidget(
            self.mode_value,
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
        # EXPERIMENT CONTROLS
        # =================================================

        experiment_group = QGroupBox(
            "Experiment Control"
        )

        experiment_layout = QHBoxLayout()

        # =================================================
        # Start
        # =================================================

        self.start_button = QPushButton(
            "Start Experiment"
        )

        self.start_button.clicked.connect(
            self.start_experiment
        )

        experiment_layout.addWidget(
            self.start_button
        )

        # =================================================
        # Stop
        # =================================================

        self.stop_button = QPushButton(
            "Stop Experiment"
        )

        self.stop_button.clicked.connect(
            self.stop_experiment
        )

        experiment_layout.addWidget(
            self.stop_button
        )

        # =================================================
        # Graphs
        # =================================================

        self.plot_button = QPushButton(
            "Open Graphs"
        )

        self.plot_button.clicked.connect(
            self.open_plots
        )

        experiment_layout.addWidget(
            self.plot_button
        )

        # =================================================
        # Export
        # =================================================

        self.export_button = QPushButton(
            "Export CSV"
        )

        self.export_button.clicked.connect(
            self.export_csv
        )

        experiment_layout.addWidget(
            self.export_button
        )

        experiment_group.setLayout(
            experiment_layout
        )

        main_layout.addWidget(
            experiment_group
        )

        # =================================================
        # EQUIPMENT CONTROL
        # =================================================

        equipment_group = QGroupBox(
            "Equipment Control"
        )

        equipment_layout = QHBoxLayout()

        # =================================================
        # Temperature Controller
        # =================================================

        self.controller_button = QPushButton(
            "Temperature Controller"
        )

        self.controller_button.clicked.connect(
            self.open_temperature_controller
        )

        equipment_layout.addWidget(
            self.controller_button
        )

        # =================================================
        # Scale Controller
        # =================================================

        self.scale_button = QPushButton(
            "Scale Control"
        )

        self.scale_button.clicked.connect(
            self.open_scale_control
        )

        equipment_layout.addWidget(
            self.scale_button
        )

        equipment_group.setLayout(
            equipment_layout
        )

        main_layout.addWidget(
            equipment_group
        )

        # =================================================
        # Set Layout
        # =================================================

        self.setLayout(
            main_layout
        )

    # =====================================================
    # Start Experiment
    # =====================================================

    def start_experiment(self):

        if self.running:

            return

        self.running = True

        self.start_time = time.monotonic()

        # =================================================
        # Clear Previous Data
        # =================================================

        self.time_data.clear()

        self.mass_data.clear()

        self.temp_data.clear()

        # =================================================
        # Reset Stored Values
        # =================================================

        self.latest_mass = 0.0

        self.latest_temperature = 0.0

        self.mass_value.setText(
            "0.0000 g"
        )

        self.temp_value.setText(
            "0.00 °C"
        )

        self.time_value.setText(
            "00:00:00"
        )

        # =================================================
        # Clear Graph
        # =================================================

        self.plot_window.clear()

        # =================================================
        # Start Experiment Update Timer
        # =================================================

        self.timer.start(
            config.REFRESH_RATE
        )

        self.status_label.setText(
            "Running"
        )

        # =================================================
        # Running = Green
        # =================================================

        self.status_label.setStyleSheet(
            """
            color: #00D26A;
            font-weight: bold;
            """
        )

    # =====================================================
    # Stop Experiment
    # =====================================================

    def stop_experiment(self):

        self.running = False

        self.timer.stop()

        self.status_label.setText(
            "Stopped"
        )

        # =================================================
        # Stopped = Red
        # =================================================

        self.status_label.setStyleSheet(
            """
            color: #FF4D4D;
            font-weight: bold;
            """
        )

    # =====================================================
    # Open Graphs
    # =====================================================

    def open_plots(self):

        self.plot_window.show()

        self.plot_window.raise_()

        self.plot_window.activateWindow()

    # =====================================================
    # Open Temperature Controller
    # =====================================================

    def open_temperature_controller(self):

        self.temperature_controller_window.show()

        self.temperature_controller_window.raise_()

        self.temperature_controller_window.activateWindow()

    # =====================================================
    # Open Scale Controller
    # =====================================================

    def open_scale_control(self):

        self.scale_control_window.show()

        self.scale_control_window.raise_()

        self.scale_control_window.activateWindow()

    # =====================================================
    # Update System
    # =====================================================

    def update_system(self):

        if not self.running:

            return

        # =================================================
        # Elapsed Time
        # =================================================

        elapsed = (
        time.monotonic()
        - self.start_time
        )

        # Convert elapsed seconds to hh:mm:ss format
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        
        self.time_value.setText(
            f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        )

        # =================================================
        # Read Temperature Controller
        # =================================================

        temperature = (
            self.get_temperature()
        )

        # =================================================
        # Read Scale Controller
        # =================================================

        mass = (
            self.get_mass()
        )

        # =================================================
        # Connection Status
        #
        # Connection status is also monitored by the
        # independent connection timer. This call keeps
        # the status synchronized during an experiment.
        # =================================================

        self.update_connection_status()

        # =================================================
        # Record Only Valid Data
        # =================================================

        if temperature is None:

            temperature = (
                float("nan")
            )

        if mass is None:

            mass = (
                float("nan")
            )

        # =================================================
        # Record Measurement
        # =================================================

        self.record_measurement(
            elapsed,
            mass,
            temperature
        )

    # =====================================================
    # Get Temperature
    # =====================================================

    def get_temperature(self):

        try:

            return (
                self.temperature_controller_window
                .get_temperature()
            )

        except Exception:

            return None

    # =====================================================
    # Get Mass
    # =====================================================

    def get_mass(self):

        try:

            scale_window = (
                self.scale_control_window
            )

            # =================================================
            # Preferred method
            # =================================================

            if hasattr(
                scale_window,
                "get_weight"
            ):

                return (
                    scale_window.get_weight()
                )

            # =================================================
            # Compatibility fallback
            # =================================================

            if hasattr(
                scale_window,
                "weight_label"
            ):

                text = (
                    scale_window
                    .weight_label
                    .text()
                )

                text = (
                    text
                    .replace(
                        "g",
                        ""
                    )
                    .strip()
                )

                return float(
                    text
                )

        except Exception:

            pass

        return None

    # =====================================================
    # Update Connection Status
    # =====================================================

    def update_connection_status(self):

        # =================================================
        # Temperature Controller
        # =================================================

        try:

            controller = (
                self.temperature_controller_window
                .controller
            )

            if (
                controller is not None
                and controller.connected
            ):

                self.temperature_connection_status.setText(
                    "Connected"
                )

                self.temperature_connection_status.setStyleSheet(
                    """
                    color: #00D26A;
                    font-weight: bold;
                    """
                )

            else:

                self.temperature_connection_status.setText(
                    "Disconnected"
                )

                self.temperature_connection_status.setStyleSheet(
                    """
                    color: #FF4D4D;
                    font-weight: bold;
                    """
                )

        except Exception:

            self.temperature_connection_status.setText(
                "Disconnected"
            )

            self.temperature_connection_status.setStyleSheet(
                """
                color: #FF4D4D;
                font-weight: bold;
                """
            )

        # =================================================
        # Scale
        # =================================================

        try:

            scale_window = (
                self.scale_control_window
            )

            if hasattr(
                scale_window,
                "connected"
            ):

                if scale_window.connected:

                    self.scale_connection_status.setText(
                        "Connected"
                    )

                    self.scale_connection_status.setStyleSheet(
                        """
                        color: #00D26A;
                        font-weight: bold;
                        """
                    )

                else:

                    self.scale_connection_status.setText(
                        "Disconnected"
                    )

                    self.scale_connection_status.setStyleSheet(
                        """
                        color: #FF4D4D;
                        font-weight: bold;
                        """
                    )

            else:

                self.scale_connection_status.setText(
                    "Disconnected"
                )

                self.scale_connection_status.setStyleSheet(
                    """
                    color: #FF4D4D;
                    font-weight: bold;
                    """
                )

        except Exception:

            self.scale_connection_status.setText(
                "Disconnected"
            )

            self.scale_connection_status.setStyleSheet(
                """
                color: #FF4D4D;
                font-weight: bold;
                """
            )

    # =====================================================
    # Record Measurement
    # =====================================================

    def record_measurement(
        self,
        elapsed,
        mass,
        temperature
    ):

        # =================================================
        # Store Data
        # =================================================

        self.time_data.append(
            elapsed
        )

        self.mass_data.append(
            mass
        )

        self.temp_data.append(
            temperature
        )

        # =================================================
        # Limit Data
        # =================================================

        self.limit_data_size()

        # =================================================
        # Store Latest Values
        # =================================================

        self.latest_mass = mass

        self.latest_temperature = temperature

        # =================================================
        # Update Live Display
        # =================================================

        self.mass_value.setText(
            f"{mass:.4f} g"
        )

        self.temp_value.setText(
            f"{temperature:.2f} °C"
        )

        # =================================================
        # Update Temperature Controller Displays
        # =================================================

        self.update_temperature_displays()

        # =================================================
        # Update Graph
        # =================================================

        self.plot_window.update_plots(
            self.time_data,
            self.mass_data,
            self.temp_data
        )

    # =====================================================
    # Update Temperature Displays
    # =====================================================

    def update_temperature_displays(self):

        try:

            controller_window = (
                self.temperature_controller_window
            )

            # =================================================
            # SP1
            # =================================================

            if hasattr(
                controller_window,
                "sp1_display"
            ):

                self.sp1_value.setText(
                    controller_window
                    .sp1_display
                    .text()
                )

            # =================================================
            # SP2
            # =================================================

            if hasattr(
                controller_window,
                "sp2_display"
            ):

                self.sp2_value.setText(
                    controller_window
                    .sp2_display
                    .text()
                )

            # =================================================
            # Mode
            # =================================================

            if hasattr(
                controller_window,
                "mode_display"
            ):

                self.mode_value.setText(
                    controller_window
                    .mode_display
                    .text()
                )

        except Exception:

            pass

    # =====================================================
    # Limit Data Size
    # =====================================================

    def limit_data_size(self):

        max_points = 10000

        if len(
            self.time_data
        ) > max_points:

            self.time_data = (
                self.time_data[-max_points:]
            )

            self.mass_data = (
                self.mass_data[-max_points:]
            )

            self.temp_data = (
                self.temp_data[-max_points:]
            )

    # =====================================================
    # Export CSV
    # =====================================================

    def export_csv(self):

        if not self.time_data:

            self.status_label.setText(
                "No Data to Export"
            )

            self.status_label.setStyleSheet(
                """
                color: #FF4D4D;
                font-weight: bold;
                """
            )

            return

        file_path, _ = (
            QFileDialog.getSaveFileName(
                self,
                "Save TGA Data",
                "",
                "CSV Files (*.csv)"
            )
        )

        if not file_path:

            return

        try:

            with open(
                file_path,
                "w",
                newline="",
                encoding="utf-8-sig"
            ) as file:

                writer = csv.writer(
                    file
                )

                writer.writerow(
                    [
                        "Time (s)",
                        "Temperature (°C)",
                        "Mass (g)"
                    ]
                )

                for (
                    elapsed,
                    temperature,
                    mass
                ) in zip(
                    self.time_data,
                    self.temp_data,
                    self.mass_data
                ):

                    writer.writerow(
                        [
                            elapsed,
                            temperature,
                            mass
                        ]
                    )

            self.status_label.setText(
                "Data Exported"
            )

            self.status_label.setStyleSheet(
                """
                color: #FFFFFF;
                font-weight: bold;
                """
            )

        except Exception as exc:

            self.status_label.setText(
                "Export Failed"
            )

            self.status_label.setStyleSheet(
                """
                color: #FF4D4D;
                font-weight: bold;
                """
            )

            print(
                f"CSV Export Error: {exc}"
            )

    # =====================================================
    # Close Event
    # =====================================================

    def closeEvent(
        self,
        event
    ):

        # =================================================
        # Stop Experiment
        # =================================================

        self.running = False

        self.timer.stop()

        # =================================================
        # Stop Connection Monitoring
        # =================================================

        self.connection_timer.stop()

        # =================================================
        # Close Graph Window
        # =================================================

        try:

            self.plot_window.close()

        except Exception:

            pass

        # =================================================
        # Close Temperature Controller
        # =================================================

        try:

            self.temperature_controller_window.hide_on_close = False
            self.temperature_controller_window.close()

        except Exception:

            pass

        # =================================================
        # Close Scale Controller
        # =================================================

        try:

            self.scale_control_window.hide_on_close = False
            self.scale_control_window.close()

        except Exception:

            pass

        event.accept()


# =====================================================
# Run GUI
# =====================================================

if __name__ == "__main__":

    app = QApplication(
        sys.argv
    )

    window = TGA_GUI()

    window.show()

    sys.exit(
        app.exec_()
    )
