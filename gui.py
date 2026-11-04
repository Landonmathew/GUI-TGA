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
# Version 2.0
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
#     - Automatic CSV logging
#     - Opening the Scale Controller
#     - Opening the Temperature Controller
#
# =====================================================

import sys
import time
import csv
import os

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
# Timing
# =====================================================

# One measurement and CSV row every six seconds.
ACQUISITION_INTERVAL = 6000

# Refresh only the visible elapsed-time display.
DISPLAY_INTERVAL = 250


# =====================================================
# Main GUI Class
# =====================================================

class TGA_GUI(QWidget):

    def __init__(self):

        super().__init__()

        # =================================================
        # Data Storage
        #
        # Every measurement collected during the experiment
        # remains in RAM.
        # =================================================

        self.time_data = []

        self.mass_data = []

        self.temp_data = []

        self.start_time = None

        self.running = False

        self.latest_mass = 0.0

        self.latest_temperature = 0.0

        # =================================================
        # Automatic CSV Logging
        # =================================================

        self.csv_file = None

        self.csv_writer = None

        self.csv_file_path = None

        # =================================================
        # Plot Window
        # =================================================

        self.plot_window = PlotWindow()

        # =================================================
        # Temperature Controller
        # =================================================

        self.temperature_controller_window = (
            TemperatureControllerWindow(
                hide_on_close=True
            )
        )

        # =================================================
        # Scale Controller
        # =================================================

        self.scale_control_window = (
            ScaleControlWindow(
                hide_on_close=True
            )
        )

        # =================================================
        # Experiment Acquisition Timer
        #
        # This timer creates RAM measurements and CSV rows.
        # =================================================

        self.timer = QTimer(
            self
        )

        self.timer.setTimerType(
            Qt.PreciseTimer
        )

        self.timer.timeout.connect(
            self.update_system
        )

        # =================================================
        # Elapsed-Time Display Timer
        #
        # This timer does not collect or save measurements.
        # =================================================

        self.display_timer = QTimer(
            self
        )

        self.display_timer.setTimerType(
            Qt.PreciseTimer
        )

        self.display_timer.timeout.connect(
            self.update_elapsed_time
        )

        # =================================================
        # Connection Monitoring Timer
        # =================================================

        self.connection_timer = QTimer(
            self
        )

        self.connection_timer.timeout.connect(
            self.update_connection_status
        )

        self.connection_timer.start(
            1000
        )

        # =================================================
        # Build GUI
        # =================================================

        self.init_ui()

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

        main_layout = QVBoxLayout()

        # =================================================
        # Title
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
        # System Status
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
        # Live Data
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
        # Elapsed Time
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
        # Experiment Controls
        # =================================================

        experiment_group = QGroupBox(
            "Experiment Control"
        )

        experiment_layout = QHBoxLayout()

        self.start_button = QPushButton(
            "Start Experiment"
        )

        self.start_button.clicked.connect(
            self.start_experiment
        )

        experiment_layout.addWidget(
            self.start_button
        )

        self.stop_button = QPushButton(
            "Stop Experiment"
        )

        self.stop_button.clicked.connect(
            self.stop_experiment
        )

        self.stop_button.setEnabled(
            False
        )

        experiment_layout.addWidget(
            self.stop_button
        )

        self.plot_button = QPushButton(
            "Open Graphs"
        )

        self.plot_button.clicked.connect(
            self.open_plots
        )

        experiment_layout.addWidget(
            self.plot_button
        )

        experiment_group.setLayout(
            experiment_layout
        )

        main_layout.addWidget(
            experiment_group
        )

        # =================================================
        # Equipment Control
        # =================================================

        equipment_group = QGroupBox(
            "Equipment Control"
        )

        equipment_layout = QHBoxLayout()

        self.controller_button = QPushButton(
            "Temperature Controller"
        )

        self.controller_button.clicked.connect(
            self.open_temperature_controller
        )

        equipment_layout.addWidget(
            self.controller_button
        )

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

        self.setLayout(
            main_layout
        )

    # =====================================================
    # Start Experiment
    # =====================================================

    def start_experiment(self):

        if self.running:

            return

        # =================================================
        # Select CSV Before Starting
        # =================================================

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Select TGA Experiment CSV",
            "",
            "CSV Files (*.csv)"
        )

        if not file_path:

            self.set_experiment_status(
                "Experiment Start Canceled",
                "#FF4D4D"
            )

            return

        if not file_path.lower().endswith(
            ".csv"
        ):

            file_path += ".csv"

        self.close_csv_log()

        # =================================================
        # Create CSV Before Starting
        # =================================================

        try:

            self.csv_file = open(
                file_path,
                "w",
                newline="",
                encoding="utf-8-sig"
            )

            self.csv_writer = csv.writer(
                self.csv_file
            )

            self.csv_writer.writerow(
                [
                    "Time (s)",
                    "Temperature (°C)",
                    "Mass (g)"
                ]
            )

            self.synchronize_csv()

            self.csv_file_path = file_path

        except Exception as exc:

            self.close_csv_log()

            self.csv_file_path = None

            self.set_experiment_status(
                "Unable to Create CSV",
                "#FF4D4D"
            )

            print(
                f"CSV Open Error: {exc}"
            )

            return

        # =================================================
        # Clear Previous Experiment Data
        # =================================================

        self.time_data.clear()

        self.mass_data.clear()

        self.temp_data.clear()

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

        self.plot_window.clear()

        # =================================================
        # Start Experiment
        # =================================================

        self.start_time = time.monotonic()

        self.running = True

        self.start_button.setEnabled(
            False
        )

        self.stop_button.setEnabled(
            True
        )

        self.timer.start(
            ACQUISITION_INTERVAL
        )

        self.display_timer.start(
            DISPLAY_INTERVAL
        )

        self.set_experiment_status(
            "Running - CSV Logging",
            "#00D26A"
        )

        # Record the starting condition immediately.
        # Additional rows are recorded every six seconds.

        self.update_system()

    # =====================================================
    # Stop Experiment
    # =====================================================

    def stop_experiment(self):

        if not self.running:

            return

        self.running = False

        self.timer.stop()

        self.display_timer.stop()

        self.start_button.setEnabled(
            True
        )

        self.stop_button.setEnabled(
            False
        )

        saved_path = self.csv_file_path

        self.close_csv_log()

        self.set_experiment_status(
            "Stopped - Data Saved",
            "#00D26A"
        )

        if saved_path:

            print(
                f"CSV data saved to: {saved_path}"
            )

    # =====================================================
    # Experiment Status Helper
    # =====================================================

    def set_experiment_status(
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

    # =====================================================
    # Open Child Windows
    # =====================================================

    def open_plots(self):

        self.plot_window.show()

        self.plot_window.raise_()

        self.plot_window.activateWindow()

    def open_temperature_controller(self):

        self.temperature_controller_window.show()

        self.temperature_controller_window.raise_()

        self.temperature_controller_window.activateWindow()

    def open_scale_control(self):

        self.scale_control_window.show()

        self.scale_control_window.raise_()

        self.scale_control_window.activateWindow()

    # =====================================================
    # Update Elapsed-Time Display
    # =====================================================

    def update_elapsed_time(self):

        if (
            not self.running
            or self.start_time is None
        ):

            return

        elapsed = (
            time.monotonic()
            - self.start_time
        )

        total_seconds = max(
            0,
            int(elapsed)
        )

        hours, remainder = divmod(
            total_seconds,
            3600
        )

        minutes, seconds = divmod(
            remainder,
            60
        )

        self.time_value.setText(
            f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        )

    # =====================================================
    # Acquire One Measurement
    # =====================================================

    def update_system(self):

        if not self.running:

            return

        elapsed = (
            time.monotonic()
            - self.start_time
        )

        self.update_elapsed_time()

        temperature = self.get_temperature()

        mass = self.get_mass()

        self.update_connection_status()

        if temperature is None:

            temperature = float(
                "nan"
            )

        if mass is None:

            mass = float(
                "nan"
            )

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

            if hasattr(
                scale_window,
                "get_weight"
            ):

                return (
                    scale_window.get_weight()
                )

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

            connected = (
                controller is not None
                and controller.connected
            )

        except Exception:

            connected = False

        if connected:

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

        # =================================================
        # Scale
        # =================================================

        try:

            scale_connected = bool(
                self.scale_control_window.connected
            )

        except Exception:

            scale_connected = False

        if scale_connected:

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
        # Store Every Point in RAM
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

        self.update_temperature_displays()

        # =================================================
        # Update Graphs
        # =================================================

        self.plot_window.update_plots(
            self.time_data,
            self.mass_data,
            self.temp_data
        )

        # =================================================
        # Write Measurement to CSV
        # =================================================

        if (
            self.csv_file is None
            or self.csv_writer is None
        ):

            self.stop_after_logging_failure(
                "CSV file is not open."
            )

            return

        try:

            self.csv_writer.writerow(
                [
                    elapsed,
                    temperature,
                    mass
                ]
            )

            self.synchronize_csv()

        except Exception as exc:

            self.stop_after_logging_failure(
                str(exc)
            )

    # =====================================================
    # Synchronize CSV
    # =====================================================

    def synchronize_csv(self):

        if self.csv_file is None:

            return

        self.csv_file.flush()

        os.fsync(
            self.csv_file.fileno()
        )

    # =====================================================
    # Stop After CSV Failure
    # =====================================================

    def stop_after_logging_failure(
        self,
        message
    ):

        print(
            f"CSV Logging Error: {message}"
        )

        self.running = False

        self.timer.stop()

        self.display_timer.stop()

        self.start_button.setEnabled(
            True
        )

        self.stop_button.setEnabled(
            False
        )

        self.close_csv_log()

        self.set_experiment_status(
            "Stopped - CSV Logging Failed",
            "#FF4D4D"
        )

    # =====================================================
    # Update Temperature Displays
    # =====================================================

    def update_temperature_displays(self):

        try:

            controller_window = (
                self.temperature_controller_window
            )

            if hasattr(
                controller_window,
                "sp1_display"
            ):

                self.sp1_value.setText(
                    controller_window
                    .sp1_display
                    .text()
                )

            if hasattr(
                controller_window,
                "sp2_display"
            ):

                self.sp2_value.setText(
                    controller_window
                    .sp2_display
                    .text()
                )

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
    # Close CSV Log
    # =====================================================

    def close_csv_log(self):

        if self.csv_file is not None:

            try:

                self.synchronize_csv()

            except Exception as exc:

                print(
                    f"CSV Synchronization Error: {exc}"
                )

            try:

                self.csv_file.close()

            except Exception as exc:

                print(
                    f"CSV Close Error: {exc}"
                )

        self.csv_file = None

        self.csv_writer = None

    # =====================================================
    # Close Event
    # =====================================================

    def closeEvent(
        self,
        event
    ):

        self.running = False

        self.timer.stop()

        self.display_timer.stop()

        self.connection_timer.stop()

        self.close_csv_log()

        try:

            self.plot_window.close()

        except Exception:

            pass

        try:

            self.temperature_controller_window.hide_on_close = False

            self.temperature_controller_window.close()

        except Exception:

            pass

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
