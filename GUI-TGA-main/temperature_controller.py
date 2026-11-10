# =====================================================
# temperature_controller.py
# Omega CN76000 Temperature Controller
#
# OMEGA CN76000 RS-485 ASCII protocol
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

import serial
import serial.tools.list_ports
import time

from typing import Optional, Dict, Any


# =====================================================
# PROTOCOL CONSTANTS
# =====================================================

STX = 0x02
ETX = 0x03
ACK = 0x06

FILTER = b"L"


# =====================================================
# DEFAULT COMMUNICATION SETTINGS
# =====================================================

DEFAULT_BAUDRATE = 1200
DEFAULT_TIMEOUT = 1.0
DEFAULT_ADDRESS = 0x02


# =====================================================
# CONTROLLER ERROR CODES
# =====================================================

ERROR_MESSAGES = {

    "00":
        "Not used.",

    "01":
        "Undefined command. Command not within acceptable range.",

    "02":
        "Checksum error on received data from host.",

    "03":
        "Command not performed by instrument "
        "(option not enabled, restricted menu, or check message).",

    "04":
        "Illegal ASCII characters received in command.",

    "05":
        "Data field error: wrong length or character positioning.",

    "06":
        "Undefined command. Command not within acceptable range.",

    "07":
        "Not used.",

    "08":
        "Hardware fault. Return to factory for service.",

    "09":
        "Hardware fault. Return to factory for service.",

    "10":
        "Undefined command. Command not within acceptable range.",
}


# =====================================================
# COMMAND DEFINITIONS
# =====================================================

READ_COMMANDS = {

    "pv": "00",

    "full_status": "05",

    "sp1": "0100",
    "sp2": "0102",

    "alarm_low": "0104",
    "alarm_high": "0105",

    "sp1_differential": "0107",
    "pulse_width_sp1": "0108",

    "sp2_differential": "010A",
    "pulse_width_sp2": "010B",

    "cycle_sp1": "0106",
    "cycle_sp2": "0109",

    "pb1": "010C",
    "pb2": "010D",

    "reset": "010E",
    "rate": "010F",

    "input_fault_timer": "0118",
    "sensor_rate": "0129",
    "loop_break": "0128",

    "manual_output_sp1": "011E",
    "manual_output_sp2": "012A",

    "peak": "011A",
    "valley": "011B",

    "percent_output": "011D",

    "ramp_time": "0126",
    "soak_time": "0127",

    "input_correction": "0124",

    "scale_low": "0116",
    "scale_high": "0117",

    "setpoint_low": "0110",
    "setpoint_high": "0111",

    "comm_fault_setpoint": "0121",

    "security": "0334",

    "input_type": "0323",
    "decimal_places": "0324",

    "unit_iv": "0326",
    "unit_tc_rtd": "0310",

    "auto": "0328",
    "percent_output_display": "0327",

    "program": "0330",
    "program_status": "0331",
    "program_end_action": "0332",

    "remote_local": "032A",
    "comm_fault_mode": "0329",
    "no_activity_timer": "032B",

    "sp1_action": "0313",
    "sp1_lamp": "0314",
    "sp1_output_assignment": "0335",

    "sp2_type": "0336",
    "sp2_action": "0315",
    "sp2_lamp": "0316",

    "tune_mode": "0339",
    "tune_start": "0312",
    "tune_learning": "0338",

    "damping_factor": "032D",

    "pid2_link": "032E",
    "anti_reset_windup": "032F",
}


WRITE_COMMANDS = {

    "sp1": "0200",
    "sp2": "0202",

    "alarm_low": "0204",
    "alarm_high": "0205",

    "comm_fault_setpoint": "020E",

    "cycle_sp1": "0206",
    "cycle_sp2": "0207",

    "pb1": "0208",
    "pb2": "0209",

    "reset_auto": "020A",
    "reset_offset": "020B",

    "rate": "020C",

    "manual_output_sp1": "020F",
    "manual_output_sp2": "0210",

    "tune_self": "0403",
    "tune_pid": "0404",

    "alarm_ack": "0402",

    "auto_on": "0405",
    "auto_off": "0406",

    "peak_reset": "0407",
    "valley_reset": "0408",

    "percent_output_on": "040B",
    "percent_output_off": "040C",

    "remote": "0400",
    "local": "0401",

    "reset_enter_flag": "040D",
}


# =====================================================
# TUNE MODES
# =====================================================

TUNE_MODES = {

    0: "SELF",
    1: "PID",
    2: "SLO",
    3: "NOR",
    4: "FAST",
}


# =====================================================
# OMEGA TEMPERATURE CONTROLLER
# =====================================================

class OmegaTemperatureController:

    def __init__(
        self,
        port=None,
        baudrate=DEFAULT_BAUDRATE,
        slave_address=DEFAULT_ADDRESS,
        timeout=DEFAULT_TIMEOUT,
        verbose=False,
        serial_override=None,
    ):

        self.port = port

        self.baudrate = baudrate

        self.slave_address = slave_address

        self.timeout = timeout

        self.verbose = verbose

        self.serial = None

        self.serial_override = serial_override

        self.connected = False

        self.decimal_places = 0


    # =================================================
    # Available COM Ports
    # =================================================

    @staticmethod
    def get_ports():

        ports = serial.tools.list_ports.comports()

        return [
            port.device
            for port in ports
        ]


    # =================================================
    # Check Address
    # =================================================

    def _validate_address(self):

        if not (
            1
            <= self.slave_address
            <= 0xFF
        ):

            raise ValueError(
                "Controller address must be 1 through 255."
            )


    # =================================================
    # Connect
    # =================================================

    def connect(self):

        # =================================================
        # Simulator connection
        # =================================================

        if self.serial_override is not None:

            self.serial = self.serial_override

            self.connected = True

            # Load decimal-point configuration.
            self.read_decimal_places()

            # Verify simulator response.
            pv = self.read_temperature()

            if pv is None:

                self.disconnect()

                return False

            return True


        # =================================================
        # Real RS-485 connection
        # =================================================

        if not self.port:

            return False


        try:

            self._validate_address()


            self.serial = serial.Serial(

                port=self.port,

                baudrate=self.baudrate,

                bytesize=serial.EIGHTBITS,

                parity=serial.PARITY_NONE,

                stopbits=serial.STOPBITS_ONE,

                timeout=self.timeout,

                write_timeout=self.timeout,
            )


            self.connected = True


            # Load decimal-point configuration.

            self.read_decimal_places()


            # Verify an actual controller response.

            pv = self.read_temperature()


            if pv is None:

                self.disconnect()

                return False


            return True


        except Exception as exc:

            print(
                f"Omega connection error: {exc}"
            )

            self.disconnect()

            return False


    # =================================================
    # Disconnect
    # =================================================

    def disconnect(self):

        self.connected = False


        if self.serial:

            try:

                self.serial.close()

            except Exception:

                pass


        self.serial = None


    # =================================================
    # Checksum
    # =================================================

    @staticmethod
    def calculate_checksum(
        data: bytes
    ):

        return sum(data) & 0xFF


    # =================================================
    # Hex Display
    # =================================================

    @staticmethod
    def hex_string(
        data: bytes
    ):

        return " ".join(
            f"{byte:02X}"
            for byte in data
        )


    # =================================================
    # Build Frame
    # =================================================

    def build_frame(
        self,
        command,
        data=""
    ):

        command = command.upper()

        data = data.upper()


        if len(command) not in (
            2,
            4
        ):

            raise ValueError(
                f"Invalid command: {command}"
            )


        try:

            int(
                command,
                16
            )

        except ValueError:

            raise ValueError(
                f"Invalid command: {command}"
            )


        if data:

            try:

                int(
                    data,
                    16
                )

            except ValueError:

                raise ValueError(
                    f"Invalid data field: {data}"
                )


        address_ascii = (
            f"{self.slave_address:02X}"
            .encode("ascii")
        )


        payload = (

            address_ascii

            + command.encode("ascii")

            + data.encode("ascii")
        )


        checksum = (
            self.calculate_checksum(
                payload
            )
        )


        checksum_ascii = (
            f"{checksum:02X}"
            .encode("ascii")
        )


        frame = (

            bytes([STX])

            + FILTER

            + payload

            + checksum_ascii

            + bytes([ETX])
        )


        return frame


    # =================================================
    # Transaction
    # =================================================

    def transact(
        self,
        command,
        data="",
        label=None
    ):

        if not self.serial:

            return None


        if not self.connected:

            return None


        frame = self.build_frame(
            command,
            data
        )


        if self.verbose:

            print()
            print(
                "TX:",
                self.hex_string(frame)
            )


        try:

            self.serial.reset_input_buffer()


            self.serial.write(
                frame
            )


            self.serial.flush()


            response = bytearray()


            start_time = time.monotonic()


            while (
                time.monotonic()
                - start_time
                < self.timeout
            ):

                byte = self.serial.read(1)


                if not byte:

                    continue


                response += byte


                if byte[0] == ACK:

                    break


            response = bytes(response)


            if self.verbose:

                print(
                    "RX:",
                    self.hex_string(response)
                    if response
                    else "NO RESPONSE"
                )


            return response


        except Exception as exc:

            print(
                f"Omega transaction error"
                f"{f' ({label})' if label else ''}: "
                f"{exc}"
            )

            return None


    # =================================================
    # Parse Response
    # =================================================

    def parse_response(
        self,
        response,
        command=None
    ):

        if not response:

            return {

                "success": False,

                "error": True,

                "error_description":
                    "No response from controller.",
            }


        if response[0] != STX:

            return {

                "success": False,

                "error": True,

                "error_description":
                    "Response does not start with STX.",

                "raw_response":
                    response,
            }


        if len(response) < 6:

            return {

                "success": False,

                "error": True,

                "error_description":
                    "Response is too short.",

                "raw_response":
                    response,
            }


        if response[1:2] != FILTER:

            return {

                "success": False,

                "error": True,

                "error_description":
                    "Unexpected filter character.",

                "raw_response":
                    response,
            }


        try:

            address = (
                response[2:4]
                .decode("ascii")
            )

        except UnicodeDecodeError:

            address = "UNKNOWN"

        if address.upper() != f"{self.slave_address:02X}":
            return {
                "success": False,
                "error": True,
                "error_description": "Response address does not match controller.",
                "raw_response": response,
            }


        # -------------------------------------------------
        # Error Response
        #
        # STX L address N error_code ACK
        # -------------------------------------------------

        if response[4:5] == b"N":

            if (
                len(response) >= 7
                and response[-1] == ACK
            ):

                try:

                    error_code = (
                        response[5:7]
                        .decode("ascii")
                        .upper()
                    )

                except UnicodeDecodeError:

                    error_code = "UNKNOWN"


                return {

                    "success": False,

                    "error": True,

                    "address": address,

                    "error_code": error_code,

                    "error_description":
                        ERROR_MESSAGES.get(
                            error_code,
                            "Unknown controller error."
                        ),

                    "raw_response":
                        response,
                }


        # -------------------------------------------------
        # Normal response
        # -------------------------------------------------

        if response[-1] != ACK:

            return {

                "success": False,

                "error": True,

                "address": address,

                "error_description":
                    "ACK was not received.",

                "raw_response":
                    response,
            }


        if len(response) < 8:

            return {

                "success": False,

                "error": True,

                "address": address,

                "error_description":
                    "Normal response is too short.",

                "raw_response":
                    response,
            }


        try:

            data = (
                response[4:-3]
                .decode("ascii")
                .upper()
            )


            received_checksum = (
                response[-3:-1]
                .decode("ascii")
                .upper()
            )


        except UnicodeDecodeError:

            return {

                "success": False,

                "error": True,

                "address": address,

                "error_description":
                    "Response contains invalid ASCII.",

                "raw_response":
                    response,
            }


        checksum_input = (
            response[1:-3]
        )


        calculated_checksum = (
            self.calculate_checksum(
                checksum_input
            )
        )


        calculated_checksum_ascii = (
            f"{calculated_checksum:02X}"
        )


        if (
            received_checksum
            != calculated_checksum_ascii
        ):

            return {

                "success": False,

                "error": True,

                "address": address,

                "error_description":
                    "Invalid response checksum.",

                "data":
                    data,

                "received_checksum":
                    received_checksum,

                "calculated_checksum":
                    calculated_checksum_ascii,

                "raw_response":
                    response,
            }


        return {

            "success": True,

            "error": False,

            "address": address,

            "command": command,

            "data": data,

            "checksum":
                received_checksum,

            "checksum_valid": True,

            "raw_response":
                response,
        }


    # =================================================
    # Generic Read
    # =================================================

    def _read(
        self,
        name
    ):

        command = (
            READ_COMMANDS[name]
        )


        response = self.transact(
            command,
            label=f"READ {name}"
        )


        return self.parse_response(
            response,
            command
        )


    # =================================================
    # Decimal Places
    # =================================================

    def read_decimal_places(self):

        result = self._read(
            "decimal_places"
        )


        if (
            not result
            or not result.get("success")
        ):

            return self.decimal_places


        data = result["data"]


        if len(data) >= 2:

            try:

                value = int(
                    data[1],
                    16
                )


                if value in (
                    0,
                    1,
                    2,
                    3
                ):

                    self.decimal_places = value


            except ValueError:

                pass


        return self.decimal_places


    # =================================================
    # Signed Six Character Decode
    # =================================================

    @staticmethod
    def decode_signed_6(
        data
    ):

        if len(data) != 6:

            raise ValueError(
                f"Expected 6 characters, got {len(data)}"
            )


        if not all(
            char in "0123456789ABCDEF"
            for char in data
        ):

            raise ValueError(
                f"Invalid hexadecimal data: {data}"
            )


        # Negative values use FF.

        if data[4:6] == "FF":

            return -int(
                data[0:4]
            )


        return int(
            data[0:4]
        )


    # =================================================
    # Unsigned Six Character Decode
    # =================================================

    @staticmethod
    def decode_unsigned_6(
        data
    ):

        if len(data) != 6:

            raise ValueError(
                f"Expected 6 characters, got {len(data)}"
            )


        return int(
            data[2:6]
        )


    # =================================================
    # Apply Decimal
    # =================================================

    @staticmethod
    def apply_decimal(
        value,
        places
    ):

        return value / (
            10 ** places
        )


    # =================================================
    # PV Status
    # =================================================

    @staticmethod
    def decode_pv_status(
        data
    ):

        if len(data) != 8:

            raise ValueError(
                f"PV response must contain 8 characters: {data}"
            )


        chars = [
            int(
                char,
                16
            )
            for char in data
        ]


        status_1 = chars[0]

        status_2 = chars[1]

        status_4 = chars[3]


        auto = bool(
            status_1 & 0x08
        )


        remote = bool(
            status_1 & 0x04
        )


        enter_pressed = bool(
            status_1 & 0x02
        )


        error_present = bool(
            status_1 & 0x01
        )


        alarm_relay_energized = bool(
            status_2 & 0x08
        )


        sp_type_cfsv = bool(
            status_2 & 0x02
        )


        no_activity_timeout = bool(
            status_4 & 0x02
        )


        pv_negative = bool(
            status_4 & 0x01
        )


        pv_digits = data[4:8]


        raw_pv = int(
            pv_digits
        )


        if pv_negative:

            raw_pv = -raw_pv


        return {

            "auto":
                auto,

            "mode":
                "AUTO"
                if auto
                else "MANUAL",

            "remote":
                remote,

            "control_location":
                "REMOTE"
                if remote
                else "LOCAL",

            "enter_pressed":
                enter_pressed,

            "error_present":
                error_present,

            "alarm_relay_energized":
                alarm_relay_energized,

            "sp_type_cfsv":
                sp_type_cfsv,

            "setpoint_source":
                "CFSV"
                if sp_type_cfsv
                else "LOCAL",

            "no_activity_timeout":
                no_activity_timeout,

            "pv_negative":
                pv_negative,

            "status_char_1":
                data[0],

            "status_char_2":
                data[1],

            "status_char_3":
                data[2],

            "status_char_4":
                data[3],

            "pv_raw_digits":
                pv_digits,

            "pv_raw":
                raw_pv,
        }


    # =================================================
    # Read Temperature / PV
    # =================================================

    def read_temperature(
        self
    ):

        if not self.connected:

            return None


        result = self._read(
            "pv"
        )


        if (
            not result
            or not result.get("success")
        ):

            return None


        try:

            status = (
                self.decode_pv_status(
                    result["data"]
                )
            )


            raw_pv = status["pv_raw"]


            return self.apply_decimal(
                raw_pv,
                self.decimal_places
            )


        except Exception as exc:

            print(
                f"Omega PV decode error: {exc}"
            )

            return None


    # =================================================
    # Read PV Detailed
    # =================================================

    def read_pv_detailed(self):

        result = self._read(
            "pv"
        )


        if (
            not result
            or not result.get("success")
        ):

            return result


        try:

            status = (
                self.decode_pv_status(
                    result["data"]
                )
            )


            result.update(
                status
            )


            result["process_value"] = (
                self.apply_decimal(
                    status["pv_raw"],
                    self.decimal_places
                )
            )


            result["decimal_places"] = (
                self.decimal_places
            )


            return result


        except Exception as exc:

            result["success"] = False

            result["error"] = True

            result["error_description"] = str(
                exc
            )

            return result


    # =================================================
    # Full Status
    # =================================================

    @staticmethod
    def decode_full_status(
        data
    ):

        if len(data) != 10:

            raise ValueError(
                f"Full status must contain 10 characters: {data}"
            )


        c = [
            int(
                char,
                16
            )
            for char in data
        ]


        fail_test = bool(
            c[0] & 0x08
        )


        check_calibration = bool(
            c[0] & 0x02
        )


        overflow = bool(
            c[0] & 0x01
        )


        underflow = bool(
            c[1] & 0x08
        )


        bad_input = bool(
            c[1] & 0x04
        )


        open_input = bool(
            c[1] & 0x02
        )


        area_error = bool(
            c[1] & 0x01
        )


        in_primary_or_secondary = bool(
            c[4] & 0x02
        )


        in_secure_menu = bool(
            c[4] & 0x01
        )


        output_a_energized = bool(
            c[5] & 0x04
        )


        output_b_energized = bool(
            c[5] & 0x02
        )


        alarm_relay_energized = bool(
            c[5] & 0x01
        )


        check_calibration_2 = bool(
            c[6] & 0x08
        )


        loop_break = bool(
            c[6] & 0x04
        )


        sensor_rate_of_change = bool(
            c[6] & 0x02
        )


        errors = {

            "fail_test":
                fail_test,

            "check_calibration":
                (
                    check_calibration
                    or check_calibration_2
                ),

            "overflow":
                overflow,

            "underflow":
                underflow,

            "bad_input":
                bad_input,

            "open_input":
                open_input,

            "area_error":
                area_error,

            "loop_break":
                loop_break,

            "sensor_rate_of_change":
                sensor_rate_of_change,
        }


        return {

            "full_status_raw":
                data,

            "fail_test":
                fail_test,

            "check_calibration":
                errors["check_calibration"],

            "overflow":
                overflow,

            "underflow":
                underflow,

            "bad_input":
                bad_input,

            "open_input":
                open_input,

            "area_error":
                area_error,

            "loop_break":
                loop_break,

            "sensor_rate_of_change":
                sensor_rate_of_change,

            "in_primary_or_secondary":
                in_primary_or_secondary,

            "in_secure_menu":
                in_secure_menu,

            "output_a_energized":
                output_a_energized,

            "output_b_energized":
                output_b_energized,

            "alarm_relay_energized":
                alarm_relay_energized,

            "errors":
                errors,

            "error_active":
                any(
                    errors.values()
                ),
        }


    def read_full_status(self):

        result = self._read(
            "full_status"
        )


        if (
            not result
            or not result.get("success")
        ):

            return result


        try:

            result["full_status"] = (
                self.decode_full_status(
                    result["data"]
                )
            )


        except Exception as exc:

            result["success"] = False

            result["error"] = True

            result["error_description"] = str(
                exc
            )


        return result


    # =================================================
    # Signed Parameter
    # =================================================

    def read_signed_parameter(
        self,
        name
    ):

        result = self._read(
            name
        )


        if (
            not result
            or not result.get("success")
        ):

            return result


        try:

            raw = (
                self.decode_signed_6(
                    result["data"]
                )
            )


            result["raw_value"] = raw


            result["value"] = (
                self.apply_decimal(
                    raw,
                    self.decimal_places
                )
            )


            result["decimal_places"] = (
                self.decimal_places
            )


        except Exception as exc:

            result["success"] = False

            result["error"] = True

            result["error_description"] = str(
                exc
            )


        return result


    # =================================================
    # Unsigned Parameter
    # =================================================

    def read_unsigned_parameter(
        self,
        name
    ):

        result = self._read(
            name
        )


        if (
            not result
            or not result.get("success")
        ):

            return result


        try:

            raw = (
                self.decode_unsigned_6(
                    result["data"]
                )
            )


            result["raw_value"] = raw

            result["value"] = raw


        except Exception as exc:

            result["success"] = False

            result["error"] = True

            result["error_description"] = str(
                exc
            )


        return result


    # =================================================
    # Setpoint Reads
    # =================================================

    def read_setpoint_1(self):

        return self.read_signed_parameter(
            "sp1"
        )


    def read_setpoint_2(self):

        return self.read_signed_parameter(
            "sp2"
        )


    # =================================================
    # PID Reads
    # =================================================

    def read_pb1(self):

        return self.read_unsigned_parameter(
            "pb1"
        )


    def read_pb2(self):

        return self.read_unsigned_parameter(
            "pb2"
        )


    def read_reset(self):

        result = (
            self.read_unsigned_parameter(
                "reset"
            )
        )


        if (
            result
            and result.get("success")
        ):

            result["reset_minutes"] = (
                result["raw_value"]
                / 10.0
            )


        return result


    def read_rate(self):

        result = (
            self.read_unsigned_parameter(
                "rate"
            )
        )


        if (
            result
            and result.get("success")
        ):

            result["rate_minutes"] = (
                result["raw_value"]
                / 100.0
            )


        return result


    # =================================================
    # Tune Mode
    # =================================================

    def read_tune_mode(self):

        result = self._read(
            "tune_mode"
        )


        if (
            not result
            or not result.get("success")
        ):

            return result


        try:

            code = int(
                result["data"][0],
                16
            )


            result["tune_mode_code"] = code


            result["tune_mode"] = (
                TUNE_MODES.get(
                    code,
                    "UNKNOWN"
                )
            )


        except Exception as exc:

            result["success"] = False

            result["error"] = True

            result["error_description"] = str(
                exc
            )


        return result


    # =================================================
    # Auto / Manual
    # =================================================

    def read_auto(self):

        result = self._read(
            "auto"
        )


        if (
            not result
            or not result.get("success")
        ):

            return result


        try:

            value = int(
                result["data"][0],
                16
            )


            result["auto"] = bool(
                value
            )


            result["mode"] = (
                "AUTO"
                if value
                else "MANUAL"
            )


        except Exception as exc:

            result["success"] = False

            result["error"] = True

            result["error_description"] = str(
                exc
            )


        return result


    # =================================================
    # Remote / Local
    # =================================================

    def read_remote_local(self):

        result = self._read(
            "remote_local"
        )


        if (
            not result
            or not result.get("success")
        ):

            return result


        try:

            value = int(
                result["data"][1],
                16
            )


            result["remote"] = (
                value == 0
            )


            result["control_location"] = (
                "REMOTE"
                if value == 0
                else "LOCAL"
            )


        except Exception as exc:

            result["success"] = False

            result["error"] = True

            result["error_description"] = str(
                exc
            )


        return result


    # =================================================
    # Percent Output
    # =================================================

    def read_percent_output(self):

        result = self._read(
            "percent_output"
        )


        if (
            not result
            or not result.get("success")
        ):

            return result


        try:

            data = result["data"]


            if len(data) == 6:

                sp2 = (
                    data[0] != "0"
                    or data[1] != "0"
                )


                raw = int(
                    data[4:6]
                )


                result["setpoint"] = (
                    "SP2"
                    if sp2
                    else "SP1"
                )


                result["percent_output"] = (
                    raw / 10.0
                )


        except Exception as exc:

            result["success"] = False

            result["error"] = True

            result["error_description"] = str(
                exc
            )


        return result


    # =================================================
    # Write Helpers
    # =================================================

    @staticmethod
    def _validate_integer_range(
        value,
        minimum,
        maximum,
        name
    ):

        if not (
            minimum
            <= value
            <= maximum
        ):

            raise ValueError(
                f"{name} must be between "
                f"{minimum} and {maximum}."
            )


    def _write_no_data(
        self,
        name
    ):

        command = (
            WRITE_COMMANDS[name]
        )


        response = self.transact(
            command,
            label=f"WRITE {name}"
        )


        return self.parse_response(
            response,
            command
        )


    def _write_signed_value(
        self,
        name,
        value,
        decimal_places
    ):

        scaled = int(
            round(
                abs(value)
                * (
                    10 ** decimal_places
                )
            )
        )


        self._validate_integer_range(
            scaled,
            0,
            9999,
            name
        )


        digits = (
            f"{scaled:04d}"
        )


        sign = (
            "FF"
            if value < 0
            else "00"
        )


        data = (
            digits
            + sign
        )


        command = (
            WRITE_COMMANDS[name]
        )


        response = self.transact(
            command,
            data,
            label=f"WRITE {name}"
        )


        return self.parse_response(
            response,
            command
        )


    def _write_unsigned_4(
        self,
        name,
        value
    ):

        self._validate_integer_range(
            value,
            0,
            9999,
            name
        )


        data = (
            f"{value:04d}"
            + "00"
        )


        command = (
            WRITE_COMMANDS[name]
        )


        response = self.transact(
            command,
            data,
            label=f"WRITE {name}"
        )


        return self.parse_response(
            response,
            command
        )


    # =================================================
    # SP1 / SP2 Writes
    # =================================================

    def set_setpoint_1(
        self,
        value
    ):

        return self._write_signed_value(
            "sp1",
            value,
            self.decimal_places
        )


    def set_setpoint_2(
        self,
        value
    ):

        return self._write_signed_value(
            "sp2",
            value,
            self.decimal_places
        )


    # Backwards-compatible names.

    def set_temperature(
        self,
        temperature
    ):

        return (
            self.set_setpoint_1(
                temperature
            )
        )


    # =================================================
    # PID Writes
    # =================================================

    def set_pb1(
        self,
        value
    ):

        return self._write_unsigned_4(
            "pb1",
            int(value)
        )


    def set_pb2(
        self,
        value
    ):

        return self._write_unsigned_4(
            "pb2",
            int(value)
        )


    def set_reset_auto(
        self,
        value
    ):

        scaled = int(
            round(
                value * 10
            )
        )


        return self._write_unsigned_4(
            "reset_auto",
            scaled
        )


    def set_reset_offset(
        self,
        value
    ):

        scaled = int(
            round(
                value * 10
            )
        )


        return self._write_unsigned_4(
            "reset_offset",
            scaled
        )


    def set_rate(
        self,
        value
    ):

        scaled = int(
            round(
                value * 100
            )
        )


        return self._write_unsigned_4(
            "rate",
            scaled
        )


    # =================================================
    # Manual Output
    # =================================================

    def set_manual_output_sp1(
        self,
        percent
    ):

        if not (
            0
            <= percent
            <= 100
        ):

            raise ValueError(
                "SP1 manual output must be 0 to 100%."
            )


        scaled = int(
            round(
                percent * 10
            )
        )


        return self._write_unsigned_4(
            "manual_output_sp1",
            scaled
        )


    def set_manual_output_sp2(
        self,
        percent
    ):

        if not (
            0
            <= percent
            <= 100
        ):

            raise ValueError(
                "SP2 manual output must be 0 to 100%."
            )


        scaled = int(
            round(
                percent * 10
            )
        )


        return self._write_unsigned_4(
            "manual_output_sp2",
            scaled
        )


    # =================================================
    # Cycle Rate
    # =================================================

    def set_cycle_rate_sp1(
        self,
        seconds
    ):

        self._validate_integer_range(
            seconds,
            2,
            80,
            "SP1 cycle rate"
        )


        if seconds % 2 != 0:

            raise ValueError(
                "Cycle rate must be an even number of seconds."
            )


        return self._write_unsigned_4(
            "cycle_sp1",
            seconds
        )


    def set_cycle_rate_sp2(
        self,
        seconds
    ):

        self._validate_integer_range(
            seconds,
            2,
            80,
            "SP2 cycle rate"
        )


        if seconds % 2 != 0:

            raise ValueError(
                "Cycle rate must be an even number of seconds."
            )


        return self._write_unsigned_4(
            "cycle_sp2",
            seconds
        )


    # =================================================
    # Auto / Manual Writes
    # =================================================

    def set_auto(self):

        return self._write_no_data(
            "auto_on"
        )


    def set_manual(self):

        return self._write_no_data(
            "auto_off"
        )


    # =================================================
    # Remote / Local Writes
    # =================================================

    def set_remote(self):

        return self._write_no_data(
            "remote"
        )


    def set_local(self):

        return self._write_no_data(
            "local"
        )


    # =================================================
    # Tune
    # =================================================

    def set_tune_mode(
        self,
        mode
    ):

        mode = mode.upper()


        if mode == "SELF":

            return self._write_no_data(
                "tune_self"
            )


        if mode == "PID":

            return self._write_no_data(
                "tune_pid"
            )


        raise ValueError(
            "Write-supported tune modes are SELF and PID."
        )


    # =================================================
    # Service Commands
    # =================================================

    def acknowledge_alarm(self):

        return self._write_no_data(
            "alarm_ack"
        )


    def reset_peak(self):

        return self._write_no_data(
            "peak_reset"
        )


    def reset_valley(self):

        return self._write_no_data(
            "valley_reset"
        )


    def enable_percent_output_display(self):

        return self._write_no_data(
            "percent_output_on"
        )


    def disable_percent_output_display(self):

        return self._write_no_data(
            "percent_output_off"
        )


    def reset_enter_pressed_flag(self):

        return self._write_no_data(
            "reset_enter_flag"
        )


    # =================================================
    # Complete Controller State
    # =================================================

    def read_controller_state(
        self
    ):

        state = {}


        # PV

        pv = self.read_pv_detailed()


        if pv and pv.get("success"):

            state["pv"] = pv.get(
                "process_value"
            )

            state["mode"] = pv.get(
                "mode"
            )

            state["control_location"] = pv.get(
                "control_location"
            )

            state["alarm_relay"] = pv.get(
                "alarm_relay_energized"
            )

            state["error_present"] = pv.get(
                "error_present"
            )

            state["enter_pressed"] = pv.get(
                "enter_pressed"
            )

            state["no_activity_timeout"] = pv.get(
                "no_activity_timeout"
            )


        # SP1

        sp1 = self.read_setpoint_1()


        if sp1 and sp1.get("success"):

            state["sp1"] = sp1.get(
                "value"
            )


        # SP2

        sp2 = self.read_setpoint_2()


        if sp2 and sp2.get("success"):

            state["sp2"] = sp2.get(
                "value"
            )


        # PID

        pb1 = self.read_pb1()

        if pb1 and pb1.get("success"):

            state["pb1"] = pb1.get(
                "value"
            )


        pb2 = self.read_pb2()

        if pb2 and pb2.get("success"):

            state["pb2"] = pb2.get(
                "value"
            )


        reset = self.read_reset()

        if reset and reset.get("success"):

            state["reset_minutes"] = reset.get(
                "reset_minutes"
            )


        rate = self.read_rate()

        if rate and rate.get("success"):

            state["rate_minutes"] = rate.get(
                "rate_minutes"
            )


        # Tune

        tune = self.read_tune_mode()

        if tune and tune.get("success"):

            state["tune_mode"] = tune.get(
                "tune_mode"
            )


        # Full error status

        if state.get(
            "error_present"
        ):

            full = self.read_full_status()


            if (
                full
                and full.get("success")
            ):

                state["full_status"] = (
                    full.get(
                        "full_status"
                    )
                )


        return state


    # =================================================
    # Test Connection
    # =================================================

    def test_connection(self):

        temperature = (
            self.read_temperature()
        )


        if temperature is not None:

            print(
                f"Omega Temperature: "
                f"{temperature:.2f} °C"
            )

            return True


        print(
            "Unable to read temperature "
            "from Omega controller."
        )


        return False