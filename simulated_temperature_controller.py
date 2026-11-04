# =====================================================
# simulated_temperature_controller.py
#
# Simulated devices for TGA system testing.
#
# Developed by:
# Landon Boger
#
# © 2026 Landon Boger
# All Rights Reserved.
#
# This module contains ALL simulation behavior for:
#
#     - Omega CN76000 temperature controller
#     - Sartorius scale
#
# Production GUI and hardware-controller files only
# select and communicate with these simulated devices.
# They do not contain simulation calculations.
# =====================================================

"""Simulated temperature controller and scale for TGA testing."""

import math
import threading
import time


# =====================================================
# Shared TGA Simulation Environment
#
# The temperature controller and scale use the same
# environment so simulated mass loss can respond to the
# simulated process temperature.
# =====================================================

class TGASimulationEnvironment:

    def __init__(
        self,
        temperature_time_constant=30.0,
        initial_temperature=25.6,
        initial_mass=10.0
    ):

        if (
            not math.isfinite(
                temperature_time_constant
            )
            or temperature_time_constant <= 0
        ):

            raise ValueError(
                "temperature_time_constant must be a "
                "finite positive number."
            )

        self.lock = threading.RLock()

        self.temperature_time_constant = (
            temperature_time_constant
        )

        self.default_temperature = float(
            initial_temperature
        )

        self.default_mass = float(
            initial_mass
        )

        # =================================================
        # Temperature-Controller State
        # =================================================

        self.pv = self.default_temperature

        self.sp1 = self.default_temperature

        self.sp2 = self.default_temperature

        self.pb1 = 10

        self.pb2 = 10

        self.reset = 100

        self.rate = 100

        self.tune_mode = 0

        self.auto = True

        self.remote = True

        self.temperature_last_update = (
            time.monotonic()
        )

        # =================================================
        # Scale State
        # =================================================

        self.raw_mass = self.default_mass

        self.tare_offset = 0.0

        self.scale_last_update = (
            time.monotonic()
        )

    # =================================================
    # Reset Temperature Controller
    # =================================================

    def reset_temperature_controller(self):

        with self.lock:

            self.pv = self.default_temperature

            self.sp1 = self.default_temperature

            self.sp2 = self.default_temperature

            self.pb1 = 10

            self.pb2 = 10

            self.reset = 100

            self.rate = 100

            self.tune_mode = 0

            self.auto = True

            self.remote = True

            self.temperature_last_update = (
                time.monotonic()
            )

    # =================================================
    # Reset Scale
    # =================================================

    def reset_scale(self):

        with self.lock:

            self.raw_mass = self.default_mass

            self.tare_offset = 0.0

            self.scale_last_update = (
                time.monotonic()
            )

    # =================================================
    # Update Temperature
    #
    # The simulated process value follows SP1 using a
    # continuous first-order thermal response.
    # =================================================

    def update_temperature(self):

        with self.lock:

            now = time.monotonic()

            elapsed = (
                now
                - self.temperature_last_update
            )

            self.temperature_last_update = now

            if elapsed <= 0:

                return self.pv

            # Hold the current temperature in MANUAL mode.

            if not self.auto:

                return self.pv

            response_fraction = (
                -math.expm1(
                    -elapsed
                    / self.temperature_time_constant
                )
            )

            self.pv += (
                (self.sp1 - self.pv)
                * response_fraction
            )

            self.pv = max(
                -999.9,
                min(
                    999.9,
                    self.pv
                )
            )

            return self.pv

    # =================================================
    # Update Scale
    #
    # The simulated sample begins near 10 grams.
    #
    # It loses mass continuously. Mass loss increases as
    # process temperature rises.
    # =================================================

    def update_mass(self):

        with self.lock:

            # Make sure the temperature is current before
            # calculating temperature-dependent mass loss.

            self.update_temperature()

            now = time.monotonic()

            elapsed = (
                now
                - self.scale_last_update
            )

            self.scale_last_update = now

            if elapsed <= 0:

                return (
                    self.raw_mass
                    - self.tare_offset
                )

            temperature_above_room = max(
                0.0,
                self.pv - 25.0
            )

            # Baseline loss plus temperature-dependent loss.
            #
            # Units are grams per second.

            mass_loss_rate = (
                0.00005
                + (
                    temperature_above_room
                    * 0.0000015
                )
            )

            self.raw_mass -= (
                mass_loss_rate
                * elapsed
            )

            self.raw_mass = max(
                0.0,
                self.raw_mass
            )

            return (
                self.raw_mass
                - self.tare_offset
            )

    # =================================================
    # Tare Simulated Scale
    # =================================================

    def tare_scale(self):

        with self.lock:

            self.update_mass()

            self.tare_offset = self.raw_mass

            return 0.0


# =====================================================
# Shared Environment
#
# Both simulated devices retrieve this same object.
# =====================================================

_SHARED_ENVIRONMENT = TGASimulationEnvironment()


def get_simulation_environment():

    return _SHARED_ENVIRONMENT


# =====================================================
# Simulated Omega CN76000 Serial Device
# =====================================================

class SimulatedCN76000Serial:

    def __init__(
        self,
        time_constant=30.0,
        environment=None
    ):

        if environment is None:

            # A standalone simulator receives its own
            # environment. The GUI explicitly supplies the
            # shared environment when both devices are used.

            self.environment = TGASimulationEnvironment(
                temperature_time_constant=time_constant
            )

        else:

            self.environment = environment

            self.environment.temperature_time_constant = (
                time_constant
            )

        self.environment.reset_temperature_controller()

        self._response = bytearray()

        self.is_open = True

    # =================================================
    # Compatibility Properties
    # =================================================

    @property
    def pv(self):

        return self.environment.pv

    @pv.setter
    def pv(
        self,
        value
    ):

        self.environment.pv = float(
            value
        )

    @property
    def sp1(self):

        return self.environment.sp1

    @sp1.setter
    def sp1(
        self,
        value
    ):

        self.environment.sp1 = float(
            value
        )

    @property
    def sp2(self):

        return self.environment.sp2

    @sp2.setter
    def sp2(
        self,
        value
    ):

        self.environment.sp2 = float(
            value
        )

    @property
    def pb1(self):

        return self.environment.pb1

    @pb1.setter
    def pb1(
        self,
        value
    ):

        self.environment.pb1 = int(
            value
        )

    @property
    def pb2(self):

        return self.environment.pb2

    @pb2.setter
    def pb2(
        self,
        value
    ):

        self.environment.pb2 = int(
            value
        )

    @property
    def reset(self):

        return self.environment.reset

    @reset.setter
    def reset(
        self,
        value
    ):

        self.environment.reset = int(
            value
        )

    @property
    def rate(self):

        return self.environment.rate

    @rate.setter
    def rate(
        self,
        value
    ):

        self.environment.rate = int(
            value
        )

    @property
    def tune_mode(self):

        return self.environment.tune_mode

    @tune_mode.setter
    def tune_mode(
        self,
        value
    ):

        self.environment.tune_mode = int(
            value
        )

    @property
    def auto(self):

        return self.environment.auto

    @auto.setter
    def auto(
        self,
        value
    ):

        self.environment.auto = bool(
            value
        )

    @property
    def remote(self):

        return self.environment.remote

    @remote.setter
    def remote(
        self,
        value
    ):

        self.environment.remote = bool(
            value
        )

    # Compatibility retained for existing tests.

    @property
    def _last_update(self):

        return (
            self.environment
            .temperature_last_update
        )

    @_last_update.setter
    def _last_update(
        self,
        value
    ):

        self.environment.temperature_last_update = (
            float(value)
        )

    # =================================================
    # Temperature Update
    # =================================================

    def _update_temperature(self):

        return (
            self.environment
            .update_temperature()
        )

    # =================================================
    # Serial Compatibility
    # =================================================

    def reset_input_buffer(self):

        self._response.clear()

    def reset_output_buffer(self):

        pass

    def flush(self):

        pass

    def close(self):

        self.is_open = False

    # =================================================
    # Command Handling
    # =================================================

    def write(
        self,
        frame
    ):

        if not self.is_open:

            raise OSError(
                "Simulated serial port is closed."
            )

        if not frame:

            return 0

        self._update_temperature()

        address = frame[2:4]

        try:

            command = (
                frame[4:-3]
                .decode(
                    "ascii"
                )
                .upper()
            )

        except Exception:

            self._build_error_response(
                address,
                "04"
            )

            return len(
                frame
            )

        # =================================================
        # Read Process Value
        # =================================================

        if command == "00":

            status = (
                (8 if self.auto else 0)
                | (4 if self.remote else 0)
            )

            sign_status = (
                "1"
                if self.pv < 0
                else "0"
            )

            pv_digits = min(
                round(
                    abs(self.pv)
                    * 10
                ),
                9999
            )

            data = (
                f"{status:X}"
                f"00"
                f"{sign_status}"
                f"{pv_digits:04d}"
            )

        # =================================================
        # Read Decimal Places
        # =================================================

        elif command == "0324":

            data = "01"

        # =================================================
        # Read SP1
        # =================================================

        elif command == "0100":

            data = self._encode_signed(
                self.sp1
            )

        # =================================================
        # Read SP2
        # =================================================

        elif command == "0102":

            data = self._encode_signed(
                self.sp2
            )

        # =================================================
        # Read PID Values
        # =================================================

        elif command == "010C":

            data = (
                f"00{self.pb1:04d}"
            )

        elif command == "010D":

            data = (
                f"00{self.pb2:04d}"
            )

        elif command == "010E":

            data = (
                f"00{self.reset:04d}"
            )

        elif command == "010F":

            data = (
                f"00{self.rate:04d}"
            )

        # =================================================
        # Read Tune Mode
        # =================================================

        elif command == "0339":

            data = (
                f"{self.tune_mode:X}0"
            )

        # =================================================
        # Read AUTO / MANUAL
        # =================================================

        elif command == "0328":

            data = (
                "10"
                if self.auto
                else "00"
            )

        # =================================================
        # Read REMOTE / LOCAL
        # =================================================

        elif command == "032A":

            data = (
                "00"
                if self.remote
                else "01"
            )

        # =================================================
        # Read Full Status
        # =================================================

        elif command == "05":

            data = "0000000000"

        # =================================================
        # Write SP1
        # =================================================

        elif (
            command.startswith(
                "0200"
            )
            and len(command) == 10
        ):

            value = self._decode_written_signed(
                command
            )

            if value is None:

                self._build_error_response(
                    address,
                    "05"
                )

                return len(
                    frame
                )

            self.sp1 = value

            data = "00"

        # =================================================
        # Write SP2
        # =================================================

        elif (
            command.startswith(
                "0202"
            )
            and len(command) == 10
        ):

            value = self._decode_written_signed(
                command
            )

            if value is None:

                self._build_error_response(
                    address,
                    "05"
                )

                return len(
                    frame
                )

            self.sp2 = value

            data = "00"

        # =================================================
        # AUTO / MANUAL
        # =================================================

        elif command == "0405":

            self.auto = True

            data = "00"

        elif command == "0406":

            self.auto = False

            data = "00"

        # =================================================
        # REMOTE / LOCAL
        # =================================================

        elif command == "0400":

            self.remote = True

            data = "00"

        elif command == "0401":

            self.remote = False

            data = "00"

        # =================================================
        # Write PID Values
        # =================================================

        elif (
            command.startswith(
                "0208"
            )
            and len(command) == 10
        ):

            self.pb1 = int(
                command[4:8]
            )

            data = "00"

        elif (
            command.startswith(
                "0209"
            )
            and len(command) == 10
        ):

            self.pb2 = int(
                command[4:8]
            )

            data = "00"

        elif (
            command.startswith(
                "020A"
            )
            and len(command) == 10
        ):

            self.reset = int(
                command[4:8]
            )

            data = "00"

        elif (
            command.startswith(
                "020B"
            )
            and len(command) == 10
        ):

            self.reset = int(
                command[4:8]
            )

            data = "00"

        elif (
            command.startswith(
                "020C"
            )
            and len(command) == 10
        ):

            self.rate = int(
                command[4:8]
            )

            data = "00"

        # =================================================
        # Tune Modes
        # =================================================

        elif command == "0403":

            self.tune_mode = 0

            data = "00"

        elif command == "0404":

            self.tune_mode = 1

            data = "00"

        # =================================================
        # Supported Commands Without Additional State
        # =================================================

        elif command in (
            "0402",
            "0407",
            "0408",
            "040B",
            "040C",
            "040D",
        ):

            data = "00"

        # =================================================
        # Unknown Command
        # =================================================

        else:

            self._build_error_response(
                address,
                "01"
            )

            return len(
                frame
            )

        self._build_normal_response(
            address,
            data
        )

        return len(
            frame
        )

    # =================================================
    # Read Response
    # =================================================

    def read(
        self,
        size=1
    ):

        if not self.is_open:

            return b""

        if size <= 0:

            return b""

        data = bytes(
            self._response[:size]
        )

        del self._response[:size]

        return data

    # =================================================
    # Normal Response
    # =================================================

    def _build_normal_response(
        self,
        address,
        data
    ):

        payload = (
            b"L"
            + address
            + data.encode(
                "ascii"
            )
        )

        checksum = (
            f"{sum(payload) & 0xFF:02X}"
            .encode(
                "ascii"
            )
        )

        self._response = bytearray(
            b"\x02"
            + payload
            + checksum
            + b"\x06"
        )

    # =================================================
    # Error Response
    # =================================================

    def _build_error_response(
        self,
        address,
        error_code
    ):

        self._response = bytearray(
            b"\x02L"
            + address
            + b"N"
            + error_code.encode(
                "ascii"
            )
            + b"\x06"
        )

    # =================================================
    # Decode Written Signed Value
    # =================================================

    @staticmethod
    def _decode_written_signed(
        command
    ):

        try:

            value = (
                int(command[4:8])
                / 10.0
            )

            sign = command[8:10]

            if sign == "FF":

                value = -value

            elif sign != "00":

                return None

            return value

        except Exception:

            return None

    # =================================================
    # Encode Signed Value
    # =================================================

    @staticmethod
    def _encode_signed(
        value
    ):

        scaled = min(
            round(
                abs(value)
                * 10
            ),
            9999
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


# =====================================================
# Simulated Scale Device
#
# All simulated scale calculations remain in this class.
# =====================================================

class SimulatedScaleDevice:

    def __init__(
        self,
        environment=None
    ):

        if environment is None:

            self.environment = (
                get_simulation_environment()
            )

        else:

            self.environment = environment

        self.connected = False

    # =================================================
    # Connect
    # =================================================

    def connect(self):

        self.environment.reset_scale()

        self.connected = True

        return True

    # =================================================
    # Disconnect
    # =================================================

    def disconnect(self):

        self.connected = False

    # =================================================
    # Read Weight
    # =================================================

    def read_weight(self):

        if not self.connected:

            return None

        return (
            self.environment
            .update_mass()
        )

    # =================================================
    # Tare
    # =================================================

    def tare(self):

        if not self.connected:

            return False

        self.environment.tare_scale()

        return True

    # =================================================
    # Zero
    # =================================================

    def zero(self):

        return self.tare()
