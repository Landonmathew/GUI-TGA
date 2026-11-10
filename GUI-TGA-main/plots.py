# =====================================================
# plots.py
# Separate Plot Window for TGA
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
# Version 1.8
# =====================================================

from PyQt5.QtWidgets import QWidget, QVBoxLayout
import pyqtgraph as pg

import config


class PlotWindow(QWidget):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("Live TGA Data")
        self.resize(
            config.PLOT_WIDTH,
            config.PLOT_HEIGHT
        )

        self.init_ui()

    # --------------------------------------------------
    # Build Plot Window
    # --------------------------------------------------

    def init_ui(self):

        layout = QVBoxLayout()

        # --------------------------------------------------
        # Dark Window
        # --------------------------------------------------

        self.setStyleSheet(
            """
            QWidget {
                background-color: #1E1E1E;
                color: #D0D0D0;
                font-size: 14px;
            }
            """
        )

        # ---------------------------------------
        # Mass vs Time
        # ---------------------------------------

        self.mass_plot = pg.PlotWidget(
            title="Mass vs Time"
        )

        self.setup_plot(
            self.mass_plot,
            "Time (s)",
            "Mass (g)"
        )

        self.mass_curve = self.mass_plot.plot(
            pen=pg.mkPen(
                "#FFFFFF",
                width=config.PLOT_LINE_WIDTH
            )
        )

        layout.addWidget(self.mass_plot)

        # ---------------------------------------
        # Temperature vs Time
        # ---------------------------------------

        self.temp_plot = pg.PlotWidget(
            title="Temperature vs Time"
        )

        self.setup_plot(
            self.temp_plot,
            "Time (s)",
            "Temperature (°C)"
        )

        self.temp_curve = self.temp_plot.plot(
            pen=pg.mkPen(
                "#FFFFFF",
                width=config.PLOT_LINE_WIDTH
            )
        )

        layout.addWidget(self.temp_plot)

        # ---------------------------------------
        # Mass vs Temperature
        # ---------------------------------------

        self.mass_temp_plot = pg.PlotWidget(
            title="Mass vs Temperature"
        )

        self.setup_plot(
            self.mass_temp_plot,
            "Temperature (°C)",
            "Mass (g)"
        )

        self.mass_temp_curve = self.mass_temp_plot.plot(
            pen=pg.mkPen(
                "#0080FF",
                width=config.PLOT_LINE_WIDTH
            )
        )

        layout.addWidget(self.mass_temp_plot)

        self.setLayout(layout)

    # --------------------------------------------------
    # Configure Each Plot
    # --------------------------------------------------

    def setup_plot(self, plot, xlabel, ylabel):

        # --------------------------------------------------
        # Plot Background
        # --------------------------------------------------

        plot.setBackground("#1E1E1E")

        # --------------------------------------------------
        # Grid
        # --------------------------------------------------

        plot.showGrid(
            x=True,
            y=True,
            alpha=0.20
        )

        # --------------------------------------------------
        # Axes
        # --------------------------------------------------

        plot.getAxis("left").setPen(
            pg.mkPen("#D0D0D0")
        )

        plot.getAxis("bottom").setPen(
            pg.mkPen("#D0D0D0")
        )

        plot.getAxis("left").setTextPen(
            pg.mkPen("#D0D0D0")
        )

        plot.getAxis("bottom").setTextPen(
            pg.mkPen("#D0D0D0")
        )

        # --------------------------------------------------
        # Axis Labels
        # --------------------------------------------------

        plot.setLabel(
            "bottom",
            xlabel,
            color="#D0D0D0",
            size="11pt"
        )

        plot.setLabel(
            "left",
            ylabel,
            color="#D0D0D0",
            size="11pt"
        )

        # --------------------------------------------------
        # Plot Title
        # --------------------------------------------------

        plot.setTitle(
            plot.plotItem.titleLabel.text,
            color="#FFFFFF",
            size="14pt"
        )

        # --------------------------------------------------
        # Enable Mouse Interaction
        # --------------------------------------------------

        plot.setMouseEnabled(
            x=True,
            y=True
        )

        plot.enableAutoRange()

    # --------------------------------------------------
    # Update Graphs
    # --------------------------------------------------

    def update_plots(
        self,
        time_data,
        mass_data,
        temp_data
    ):

        self.mass_curve.setData(
            time_data,
            mass_data
        )

        self.temp_curve.setData(
            time_data,
            temp_data
        )

        self.mass_temp_curve.setData(
            temp_data,
            mass_data
        )

    # --------------------------------------------------
    # Clear Graphs
    # --------------------------------------------------

    def clear(self):

        self.mass_curve.clear()

        self.temp_curve.clear()

        self.mass_temp_curve.clear()