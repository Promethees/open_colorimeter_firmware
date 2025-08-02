import time
import gc
import usb_hid
import usb_cdc
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
import constants
from mode import Mode

class SerialManager:
    def __init__(self, colorimeter):
        self.colorimeter = colorimeter
        self.keyboard = None
        self.layout = None
        self.serial = usb_cdc.data
        self.buffer = b""

    def serial_talking(self, set_talking=True, start_by_host=False):
        if not set_talking:
            self.colorimeter.is_talking = False
            self.colorimeter.serial_connected = False
            self.colorimeter.screen_manager.measure_screen.set_measurement(
                self.colorimeter.measurement_name, None, "stopped", None, talking=self.colorimeter.is_talking)
            self.colorimeter.screen_manager.measure_screen.show()
            self.keyboard = None
            self.layout = None
            self.colorimeter.serial_start_time = None
            gc.collect()
            time.sleep(0.5)
            return

        self.colorimeter.is_talking = True
        if not self.keyboard or not self.layout:
            try:
                self.keyboard = Keyboard(usb_hid.devices)
                self.layout = KeyboardLayoutUS(self.keyboard)
            except Exception as e:
                self.colorimeter.screen_manager.set_error_message(f"HID setup error: {e}")
                self.colorimeter.is_talking = False
                return
        try:
            self.colorimeter.screen_manager.measure_screen.set_measurement(
                self.colorimeter.measurement_name, None, "comm init", None, talking=self.colorimeter.is_talking)
            self.colorimeter.screen_manager.measure_screen.show()
            if (start_by_host):
                time.sleep(5)
            self.layout.write("Timestamp,Measurement,Value,Unit,Type,Blanked,Concentration\n")
        except OSError as e:
            self.colorimeter.screen_manager.show_message("Run script not started", is_error=True)
            self.colorimeter.is_talking = False
            self.colorimeter.serial_connected = False
            return

        if self.colorimeter.serial_start_time is None:
            self.colorimeter.serial_start_time = time.monotonic() + constants.CONNECTION_WAIT_TIME

        start_time = time.monotonic()
        while self.colorimeter.is_talking and not self.colorimeter.serial_connected:
            self.colorimeter.button_handler.handle_button_press()
            if time.monotonic() - start_time > constants.CONNECTION_WAIT_TIME:
                self.colorimeter.serial_connected = True
                self.colorimeter.screen_manager.measure_screen.set_measurement(
                    self.colorimeter.measurement_name, None, "connected", None, talking=self.colorimeter.is_talking)
                self.colorimeter.screen_manager.measure_screen.show()
            time.sleep(0.1)

    def handle_serial_communication(self):
        # Check for incoming serial commands
        if self.serial.in_waiting:
            self.buffer += self.serial.read(self.serial.in_waiting)
            if b"\n" in self.buffer:
                lines = self.buffer.split(b"\n")
                for line in lines[:-1]:
                    command = line.decode().strip()
                    if command == "1":
                        self.serial.write(b"ACK_START\n")
                        self.serial_talking(True, True)
                    elif command == "0":
                        self.serial.write(b"ACK_STOP\n")
                        self.colorimeter.serial_count = 0
                        self.serial_talking(False, True)
                self.buffer = lines[-1]  # Save incomplete data

        # Existing measurement data transmission
        if self.colorimeter.mode == Mode.MEASURE and self.colorimeter.is_talking and self.colorimeter.serial_connected and self.keyboard and self.layout and self.colorimeter.serial_start_time:
            try:
                numeric_value, type_tag = self.colorimeter.measurement_value
                units = self.colorimeter.measurement_units or "None"
                type_tag = type_tag or "None"
                concen_val = self.colorimeter.concentration or "None"

                current_time = time.monotonic()
                relative_time = current_time - self.colorimeter.serial_start_time
                if self.colorimeter.timeout_value and self.colorimeter.timeout_unit:
                    timeout_seconds = self.colorimeter._convert_to_seconds(
                        self.colorimeter.timeout_value, self.colorimeter.timeout_unit)
                    if timeout_seconds and relative_time > timeout_seconds:
                        self.colorimeter.is_talking = False
                        self.colorimeter.serial_start_time = None
                        self.colorimeter.serial_count = 0
                transmission_interval_seconds = self.colorimeter._convert_to_seconds(
                    self.colorimeter.transmission_interval_value, self.colorimeter.transmission_interval_unit)
                if current_time - self.colorimeter.last_transmission_time >= transmission_interval_seconds:
                    self.colorimeter.last_transmission_time = current_time
                    blanked = "True" if self.colorimeter.is_blanked else "False"
                    relative_time = 1 - relative_time if relative_time < 0 else relative_time
                    written_time = transmission_interval_seconds * self.colorimeter.serial_count if transmission_interval_seconds != 0 else relative_time
                    self.colorimeter.serial_count += 1
                    data_str = f"{written_time:.2f},{self.colorimeter.measurement_name.replace(' ', '')},{numeric_value:.{self.colorimeter.configuration.precision}f},{units.replace(' ', '')},{type_tag.replace(' ', '')},{blanked},{concen_val}\n"
                    self.layout.write(data_str)
            except MemoryError:
                self.colorimeter.screen_manager.set_error_message("Memory allocation failed for Measure Screen")
            except (ValueError, RuntimeError) as e:
                self.colorimeter.screen_manager.set_error_message(f"HID send error: {e}")
                self.colorimeter.is_talking = False
                self.colorimeter.serial_connected = False
                self.colorimeter.screen_manager.measure_screen.set_measurement(
                    self.colorimeter.measurement_name, None, "disconnected", None, talking=self.colorimeter.is_talking)