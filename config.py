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
# Version 1.8
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

BACKGROUND = "#000000"      # Black

TEXT = "#008CFF"            # Bright Blue

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

REFRESH_RATE = 100      # milliseconds


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
    "Mass (g)",
    "Temperature (°C)"
]