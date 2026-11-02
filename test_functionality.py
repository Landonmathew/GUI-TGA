"""Hardware-free regression checks: python -m unittest discover -s TGA_GUI -v."""

import csv
import math
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication
from gui import TGA_GUI
from scale_controller import ScaleWorker
from simulated_temperature_controller import SimulatedCN76000Serial
from temperature_controller import OmegaTemperatureController


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.serial = SimulatedCN76000Serial()
        self.controller = OmegaTemperatureController(serial_override=self.serial)
        self.assertTrue(self.controller.connect())

    def tearDown(self):
        self.controller.disconnect()

    def test_setpoints_and_parameters_round_trip(self):
        for write, read, value, key in [
            (self.controller.set_setpoint_1, self.controller.read_setpoint_1, -12.3, "value"),
            (self.controller.set_setpoint_2, self.controller.read_setpoint_2, 150.4, "value"),
            (self.controller.set_pb1, self.controller.read_pb1, 25, "value"),
            (self.controller.set_pb2, self.controller.read_pb2, 35, "value"),
            (self.controller.set_reset_auto, self.controller.read_reset, 2.5, "reset_minutes"),
            (self.controller.set_rate, self.controller.read_rate, 1.23, "rate_minutes"),
        ]:
            with self.subTest(value=value, key=key):
                self.assertTrue(write(value)["success"])
                self.assertAlmostEqual(read()[key], value)

    def test_simulated_modes_agree_with_status(self):
        self.assertTrue(self.controller.read_auto()["auto"])
        self.controller.set_manual()
        self.controller.set_local()
        state = self.controller.read_controller_state()
        self.assertEqual(state["mode"], "MANUAL")
        self.assertEqual(state["control_location"], "LOCAL")
        self.controller.set_auto()
        self.controller.set_remote()
        self.controller.set_tune_mode("PID")
        state = self.controller.read_controller_state()
        self.assertEqual(state["mode"], "AUTO")
        self.assertEqual(state["control_location"], "REMOTE")
        self.assertEqual(state["tune_mode"], "PID")

    def test_checksum_and_wrong_address_rejected(self):
        response = self.controller.transact("00")
        self.assertTrue(self.controller.parse_response(response)["success"])
        damaged = response[:-3] + b"XX" + response[-1:]
        self.assertFalse(self.controller.parse_response(damaged)["success"])
        other = OmegaTemperatureController(slave_address=3)
        self.assertFalse(other.parse_response(response)["success"])

    def test_missing_and_malformed_responses(self):
        for response in (None, b"", b"garbage", b"\x02", b"\x02L01N01\x06"):
            with self.subTest(response=response):
                self.assertFalse(self.controller.parse_response(response)["success"])

    def test_invalid_setpoint_rejected(self):
        with self.assertRaises(ValueError):
            self.controller.set_setpoint_1(1000)

    def test_simulation_temperature_moves_toward_setpoint(self):
        self.controller.set_setpoint_1(100)
        self.serial._last_update -= 5
        value = self.controller.read_temperature()
        self.assertGreater(value, 25.6)
        self.assertLess(value, 100)


class BalanceTests(unittest.TestCase):
    def test_continuous_input_is_bounded(self):
        class StreamingSerial:
            is_open = True
            in_waiting = 12

            def reset_input_buffer(self):
                pass

            def write(self, data):
                return len(data)

            def flush(self):
                pass

            def read(self, size):
                return b"- 1.2345 g\r\n"

        worker = ScaleWorker()
        worker.serial = StreamingSerial()
        readings = []
        worker.weight_received.connect(readings.append)
        # A finite clock sequence also detects an unbounded streaming loop.
        with patch("scale_controller.time.monotonic", side_effect=range(20)), patch("scale_controller.time.sleep"):
            worker.read_weight()
        self.assertEqual(readings, [-1.2345])
        self.assertFalse(worker.read_in_progress)

    def test_signed_padded_weight(self):
        for data, expected in [(b"-    1.2345 g\r\n", -1.2345),
                               (b"+    2.5000 g\r\n", 2.5),
                               (b"-0.25 g", -0.25),
                               (b"0.0000 g", 0.0)]:
            with self.subTest(data=data):
                self.assertEqual(ScaleWorker.parse_weight(data), expected)

    def test_empty_weight(self):
        self.assertIsNone(ScaleWorker.parse_weight(b""))
        self.assertIsNone(ScaleWorker.parse_weight(b"No response"))


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.window = TGA_GUI()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()
        self.assertFalse(self.window.temperature_controller_window.thread.isRunning())
        self.assertFalse(self.window.scale_control_window.thread.isRunning())

    def wait_for(self, predicate):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            self.app.processEvents()
            if predicate():
                return
            time.sleep(0.01)
        self.fail("Timed out waiting for worker result")

    def connect_simulator(self):
        control = self.window.temperature_controller_window
        control.mode_box.setCurrentText("Simulation")
        control.toggle_connection()
        self.wait_for(lambda: control.get_temperature() is not None)
        return control

    def test_close_reopen_and_shutdown(self):
        control = self.connect_simulator()
        serial = control.controller.serial
        for child in (control, self.window.scale_control_window):
            child.show()
            child.close()
            self.assertTrue(child.thread.isRunning())
            child.show()
        control.set_sp1_worker.emit(80.0)
        self.wait_for(lambda: serial.sp1 == 80.0)
        self.window.close()
        self.assertFalse(serial.is_open)

    def test_failed_reads_do_not_return_old_values(self):
        control = self.connect_simulator()
        control.controller_state_received({})
        self.assertIsNone(control.get_temperature())
        control.controller_state_received({"sp1": 30})
        self.assertIsNone(control.get_temperature())
        scale = self.window.scale_control_window
        scale.connected = True
        scale.weight_received(1.2345)
        self.assertEqual(scale.get_weight(), 1.2345)
        scale.weight_received(None)
        self.assertIsNone(scale.get_weight())

    def test_polling_does_not_queue_duplicate_reads(self):
        control = self.window.temperature_controller_window
        scale = self.window.scale_control_window
        control.controller = SimpleNamespace(connected=True)
        scale.connected = True
        for child, signal, request, complete in [
            (control, control.read_state_worker, control.request_state,
             lambda: control.controller_state_received({})),
            (scale, scale.read_weight_worker, scale.request_weight,
             lambda: scale.weight_received(None)),
        ]:
            signal.disconnect()
            calls = []
            signal.connect(lambda: calls.append(True))
            request()
            request()
            self.assertEqual(len(calls), 1)
            complete()
            request()
            self.assertEqual(len(calls), 2)

    def test_elapsed_time_ignores_wall_clock(self):
        with patch("gui.time.monotonic", return_value=100):
            self.window.start_experiment()
        with patch("gui.time.monotonic", return_value=102.5), patch("gui.time.time", return_value=-9999):
            self.window.update_system()
        self.assertEqual(self.window.time_data, [2.5])
        self.window.stop_experiment()
        self.assertFalse(self.window.timer.isActive())

    def test_missing_measurements_plot_and_export(self):
        self.window.start_experiment()
        self.window.update_system()
        self.window.stop_experiment()
        self.assertTrue(math.isnan(self.window.mass_data[0]))
        self.assertTrue(math.isnan(self.window.temp_data[0]))
        self.window.record_measurement(2, 1.2345, 60)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "data.csv"
            with patch("gui.QFileDialog.getSaveFileName", return_value=(str(path), "")):
                self.window.export_csv()
            with path.open(encoding="utf-8-sig", newline="") as file:
                rows = list(csv.reader(file))
        self.assertEqual(rows[0], ["Time (s)", "Temperature (°C)", "Mass (g)"])
        self.assertEqual(rows[-1], ["2", "60", "1.2345"])
        self.assertEqual(rows[1][1:], ["nan", "nan"])


if __name__ == "__main__":
    unittest.main()
