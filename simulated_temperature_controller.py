# =====================================================
# simulated_temperature_controller.py
#
# Simulator for Omega CN76000 GUI testing.
#
# Developed by:
# Landon Boger
#
# © 2026 Landon Boger
# All Rights Reserved.
#
# This simulator is used for testing the TGA
# temperature controller GUI without the physical
# Omega CN76000 controller.
# =====================================================

# simulated_temperature_controller.py

"""Simulator for Omega CN76000 GUI testing."""

import math
import time


class SimulatedCN76000Serial:

    def __init__(self, time_constant=5.0):

        if not math.isfinite(time_constant) or time_constant <= 0:
            raise ValueError(
                "time_constant must be a finite positive number of seconds"
            )

        self.time_constant = time_constant

        # Simulated controller state
        self.pv = 25.6
        self.sp1 = 25.6
        self.sp2 = 25.6

        self.pb1 = 10
        self.pb2 = 10
        self.reset = 100
        self.rate = 100

        self.tune_mode = 0
        self.auto = True
        self.remote = True

        self._last_update = time.monotonic()
        self._response = bytearray()
        self.is_open = True

        # =================================================
        # HEALTH CHECK FAILURE TEST
        # =================================================
        #
        # COMMENT OUT THIS ENTIRE BLOCK AFTER TESTING.
        #
        # This does NOT change the normal simulator logic.
        # It simply causes the simulator to stop responding
        # after 10 seconds so the GUI health check can detect
        # the failure.
        #
        # =================================================

        self.health_test_enabled = True
        self.health_test_start = time.monotonic()
        self.health_test_failure_time = 10.0

        # =================================================
        # END HEALTH CHECK FAILURE TEST
        # =================================================

    # =================================================
    # Simulated temperature response
    # =================================================

    def _update_temperature(self):

        now = time.monotonic()

        elapsed = now - self._last_update

        self._last_update = now

        self.pv += (
            (self.sp1 - self.pv)
            * (-math.expm1(-elapsed / self.time_constant))
        )

    # =================================================
    # Serial compatibility
    # =================================================

    def reset_input_buffer(self):

        self._response.clear()

    def flush(self):

        pass

    def close(self):

        self.is_open = False

    # =================================================
    # Command handling
    # =================================================

    def write(self, frame):

        # =================================================
        # HEALTH CHECK FAILURE TEST
        # =================================================
        #
        # COMMENT OUT THIS ENTIRE BLOCK AFTER TESTING.
        #
        # This is the only change inside the normal
        # simulator command handling.
        #
        # It does NOT close the simulated connection.
        # It simply stops the controller from responding.
        #
        # =================================================

        if self.health_test_enabled:

            elapsed = (
                time.monotonic()
                - self.health_test_start
            )

            if elapsed >= self.health_test_failure_time:

                # Do not create a response.
                # The GUI will continue polling normally.
                return len(frame)

        # =================================================
        # END HEALTH CHECK FAILURE TEST
        # =================================================

        self._update_temperature()

        address = frame[2:4]

        command = frame[4:-3].decode("ascii")

        # -------------------------------------------------
        # READ PV
        # -------------------------------------------------

        if command == "00":

            # 8-character PV status:
            # C00 + sign + 4 digits

            sign = "1" if self.pv < 0 else "0"

            data = (
                f"{(8 if self.auto else 0) | (4 if self.remote else 0):X}00"
                f"{sign}"
                f"{round(abs(self.pv) * 10):04d}"
            )

        # -------------------------------------------------
        # READ DECIMAL PLACES
        # -------------------------------------------------

        elif command == "0324":

            data = "01"

        # -------------------------------------------------
        # READ SP1
        # -------------------------------------------------

        elif command == "0100":

            data = self._encode_signed(self.sp1)

        # -------------------------------------------------
        # READ SP2
        # -------------------------------------------------

        elif command == "0102":

            data = self._encode_signed(self.sp2)

        # -------------------------------------------------
        # READ PB1
        # -------------------------------------------------

        elif command == "010C":

            data = f"00{self.pb1:04d}"

        # -------------------------------------------------
        # READ PB2
        # -------------------------------------------------

        elif command == "010D":

            data = f"00{self.pb2:04d}"

        # -------------------------------------------------
        # READ RESET
        # -------------------------------------------------

        elif command == "010E":

            data = f"00{self.reset:04d}"

        # -------------------------------------------------
        # READ RATE
        # -------------------------------------------------

        elif command == "010F":

            data = f"00{self.rate:04d}"

        # -------------------------------------------------
        # READ TUNE MODE
        # -------------------------------------------------

        elif command == "0339":

            data = f"{self.tune_mode:X}0"

        # -------------------------------------------------
        # READ AUTO / MANUAL
        # -------------------------------------------------

        elif command == "0328":

            data = "10" if self.auto else "00"

        # -------------------------------------------------
        # READ REMOTE / LOCAL
        # -------------------------------------------------

        elif command == "032A":

            data = "00" if self.remote else "01"

        # -------------------------------------------------
        # FULL STATUS
        # -------------------------------------------------

        elif command == "05":

            # No simulated errors.
            data = "0000000000"

        # -------------------------------------------------
        # WRITE SP1
        # -------------------------------------------------

        elif command.startswith("0200") and len(command) == 10:

            value = int(command[4:8]) / 10.0

            if command[8:10] == "FF":

                value = -value

            self.sp1 = value

            data = "00"

        # -------------------------------------------------
        # WRITE SP2
        # -------------------------------------------------

        elif command.startswith("0202") and len(command) == 10:

            value = int(command[4:8]) / 10.0

            if command[8:10] == "FF":

                value = -value

            self.sp2 = value

            data = "00"

        # -------------------------------------------------
        # AUTO ON
        # -------------------------------------------------

        elif command == "0405":

            self.auto = True

            data = "00"

        # -------------------------------------------------
        # AUTO OFF
        # -------------------------------------------------

        elif command == "0406":

            self.auto = False

            data = "00"

        # -------------------------------------------------
        # REMOTE
        # -------------------------------------------------

        elif command == "0400":

            self.remote = True

            data = "00"

        # -------------------------------------------------
        # LOCAL
        # -------------------------------------------------

        elif command == "0401":

            self.remote = False

            data = "00"

        # -------------------------------------------------
        # OTHER WRITE COMMANDS
        # -------------------------------------------------

        elif command.startswith("0208") and len(command) == 10:

            self.pb1 = int(command[4:8])

            data = "00"

        elif command.startswith("0209") and len(command) == 10:

            self.pb2 = int(command[4:8])

            data = "00"

        elif command.startswith("020A") and len(command) == 10:

            self.reset = int(command[4:8])

            data = "00"

        elif command.startswith("020C") and len(command) == 10:

            self.rate = int(command[4:8])

            data = "00"

        elif command in ("0403", "0404"):

            self.tune_mode = 0 if command == "0403" else 1
            data = "00"

        elif command in (
            "0402",
            "0403",
            "0404",
            "0407",
            "0408",
            "040B",
            "040C",
            "040D",
        ):

            data = "00"

        else:

            # Simulated controller error:
            # STX L address N01 ACK

            self._response = bytearray(
                b"\x02L"
                + address
                + b"N01\x06"
            )

            return len(frame)

        # =================================================
        # Build normal response
        # =================================================

        payload = (
            b"L"
            + address
            + data.encode("ascii")
        )

        checksum = (
            f"{sum(payload) & 0xFF:02X}"
            .encode("ascii")
        )

        self._response = bytearray(
            b"\x02"
            + payload
            + checksum
            + b"\x06"
        )

        return len(frame)

    # =================================================
    # Response reader
    # =================================================

    def read(self, size=1):

        data = bytes(
            self._response[:size]
        )

        del self._response[:size]

        return data

    # =================================================
    # Helpers
    # =================================================

    @staticmethod
    def _encode_signed(value):

        scaled = round(
            abs(value) * 10
        )

        sign = (
            "FF"
            if value < 0
            else "00"
        )

        return (
            f"{scaled:04d}"
            + sign
        )