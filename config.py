# =====================================================
# config.py
# TGA GUI Configuration File
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
# Version 2.1
# =====================================================

# -----------------------------
# Window Settings
# -----------------------------

WINDOW_TITLE = "TGA"

MAIN_WIDTH = 600
MAIN_HEIGHT = 550

PLOT_WIDTH = 1200
PLOT_HEIGHT = 900


# -----------------------------
# Colors
# -----------------------------

BACKGROUND = "#000000"

TEXT = "#008CFF"

BUTTON_RED = "#B22222"

BUTTON_GREEN = "#228B22"

GRAPH_BACKGROUND = "#000000"

GRAPH_AXIS = "#FFFFFF"

GRAPH_GRID = "#555555"

GRAPH_LINE = "#008CFF"


# -----------------------------
# Fonts
# -----------------------------

TITLE_FONT = 24

LABEL_FONT = 12

BUTTON_FONT = 12

VALUE_FONT = 13


# -----------------------------
# Plot Settings
# -----------------------------

PLOT_LINE_WIDTH = 2

GRID_ALPHA = 0.25


# -----------------------------
# Timing Settings
# -----------------------------

# Experiment data and CSV sample interval.
#
# 6000 milliseconds = 6 seconds.
# This corresponds to a sample rate of 1/6 Hz.

REFRESH_RATE = 6000


# The elapsed-time display is independent of acquisition.
#
# 250 milliseconds updates the visible clock four times
# per second without creating additional CSV measurements.

DISPLAY_REFRESH_RATE = 250


# Temperature controller and scale polling interval.
#
# Both devices are polled once every six seconds.

DEVICE_POLL_INTERVAL = 6000


# Device health is evaluated once every six seconds.

HEALTH_CHECK_INTERVAL = 6000


# A device is unhealthy after three complete polling
# intervals without a valid response.
#
# 3 x 6 seconds = 18 seconds.

HEALTH_TIMEOUT = 18.0


# -----------------------------
# Serial Settings
# -----------------------------

DEFAULT_BAUD = 9600

SERIAL_TIMEOUT = 0.1


# -----------------------------
# CSV Logging
# -----------------------------

DATA_FOLDER = "data"

CSV_HEADER = [
    "Time (s)",
    "Temperature (°C)",
    "Mass (g)"
]
