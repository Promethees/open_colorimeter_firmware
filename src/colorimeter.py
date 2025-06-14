import time
import ulab
import board
import keypad
import constants
import displayio
import adafruit_itertools
import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
import gc

from light_sensor import LightSensor
from light_sensor import LightSensorOverflow
from light_sensor import LightSensorIOError

from battery_monitor import BatteryMonitor

from configuration import Configuration
from configuration import ConfigurationError

from calibrations import Calibrations
from calibrations import CalibrationsError

from menu_screen import MenuScreen
from message_screen import MessageScreen
from measure_screen import MeasureScreen
from settings_screen import SettingsScreen
from concentration_screen import ConcentrationScreen

class Mode:
    MEASURE = 0
    MENU    = 1
    MESSAGE = 2
    ABORT   = 3
    SETTINGS = 4
    CONCENTRATION = 5

class Colorimeter:
    ABOUT_STR = 'About'
    RAW_SENSOR_STR = 'Raw Sensor'
    ABSORBANCE_STR = 'Absorbance'
    TRANSMITTANCE_STR = 'Transmittance'
    SETTINGS_STR = 'Settings'
    CONCENTRATION_STR = 'Concentration'
    DEFAULT_MEASUREMENTS = [ABSORBANCE_STR, TRANSMITTANCE_STR, RAW_SENSOR_STR]

    def __init__(self):
        self.menu_items = list(self.DEFAULT_MEASUREMENTS)
        self.menu_view_pos = 0
        self.menu_item_pos = 0
        self.mode = Mode.MEASURE
        self.is_blanked = False
        self.is_talking = False
        self.serial_connected = False
        self.blank_value = 1.0
        self.keyboard = None
        self.layout = None
        self.last_transmission_time = 0.0
        self.calibrations_checked = False
        self.serial_start_time = None
        self.settings_screen = None
        self.to_use_gain_asB = False
        self.concentration = None
        

        # Create screens
        board.DISPLAY.brightness = 1.0
        self.measure_screen = MeasureScreen()
        self.message_screen = MessageScreen()
        self.menu_screen = None  # Initialize as None; create on demand

        # Setup keypad inputs
        self.last_button_press = time.monotonic()
        self.pad = keypad.ShiftRegisterKeys(
            clock=board.BUTTON_CLOCK,
            data=board.BUTTON_OUT,
            latch=board.BUTTON_LATCH,
            value_to_latch=True,
            key_count=8,
            value_when_pressed=False,
            interval=0.1
        )
        self.button_map = {
            0: 'gain',
            1: 'itime',
            2: 'blank',
            3: 'menu',
            4: 'right',
            5: 'down',
            6: 'up',
            7: 'left'
        }

        # Load Configuration
        self.configuration = Configuration()
        try:
            self.configuration.load()
        except ConfigurationError as e:
            self.message_screen.set_message(str(e))
            self.message_screen.set_to_error()
            self.mode = Mode.MESSAGE

        # Load calibrations and populate menu items
        self.calibrations = Calibrations()
        try:
            self.calibrations.load()
        except CalibrationsError as e:
            self.message_screen.set_message(str(e))
            self.message_screen.set_to_error()
            self.mode = Mode.MESSAGE
        else:
            if self.calibrations.has_errors:
                self.message_screen.set_message("errors found in calibrations file")
                self.message_screen.set_to_error()
                self.mode = Mode.MESSAGE

        self.menu_items.extend([k for k in self.calibrations.data])
        self.menu_items.extend([self.CONCENTRATION_STR, self.ABOUT_STR, self.SETTINGS_STR])

        # Set default/startup measurement
        if self.configuration.startup in self.menu_items:
            self.measurement_name = self.configuration.startup
        else:
            if self.configuration.startup:
                self.message_screen.set_message(f"startup measurement {self.configuration.startup} not found")
                self.message_screen.set_to_error()
                self.mode = Mode.MESSAGE
            self.measurement_name = self.menu_items[0]

        # Setup light sensor (TSL2591)
        try:
            self.light_sensor = LightSensor()
        except LightSensorIOError as e:
            self.message_screen.set_message(f"TSL2591 missing? {e}", ok_to_continue=False)
            self.message_screen.set_to_abort()
            self.mode = Mode.ABORT
        else:
            if self.configuration.gain:
                self.light_sensor.gain = self.configuration.gain
            if self.configuration.integration_time:
                self.light_sensor.integration_time = self.configuration.integration_time
            self.blank_sensor(set_blanked=False)
            self.measure_screen.set_not_blanked()

        # Setup battery monitoring and cycles
        self.battery_monitor = BatteryMonitor()
        self.setup_gain_and_itime_cycles()

        # Initialize settings values
        self.timeout_value = self.configuration.timeout_value
        self.timeout_unit = self.configuration.timeout_unit
        self.transmission_interval_value = self.configuration.transmission_interval_value
        self.transmission_interval_unit = self.configuration.transmission_interval_unit

        # validate the timings set in configuration.json
        if self.timeout_value is not None:
            if self._convert_to_seconds(self.timeout_value, self.timeout_unit) <= self._convert_to_seconds(self.transmission_interval_value, self.transmission_interval_unit):
                self.timeout_value = constants.DEFAULT_TIMEOUT_VALUE
                self.timeout_unit = constants.DEFAULT_TIMEOUT_UNIT
                self.transmission_interval_value = constants.DEFAULT_TRANSMISSION_INTERVAL_VALUE
                self.transmission_interval_unit = constants.DEFAULT_TRANSMISION_INTERVAL_UNIT

    def _log_error(self, message):
        """Log errors to display."""
        self.mode = Mode.MESSAGE
        self.menu_screen = None
        self.settings_screen = None
        gc.collect()
        if self.mode == Mode.MESSAGE and self.message_screen is None:
            try:
                self.message_screen = MessageScreen()
            except MemoryError:
                self._log_error("Memory allocation failed for Message Screen")        
        self.message_screen.set_message(f"Error: {message}")
        self.message_screen.set_to_error()
        

    def setup_gain_and_itime_cycles(self):
        self.gain_cycle = adafruit_itertools.cycle(constants.GAIN_TO_STR)
        if self.configuration.gain:
            while next(self.gain_cycle) != self.configuration.gain:
                continue

        self.itime_cycle = adafruit_itertools.cycle(constants.INTEGRATION_TIME_TO_STR)
        if self.configuration.integration_time:
            while next(self.itime_cycle) != self.configuration.integration_time:
                continue

    @property
    def num_menu_items(self):
        return len(self.menu_items)

    def incr_menu_item_pos(self):
        """Increment menu item position, wrapping to 0."""
        self.menu_item_pos = (self.menu_item_pos + 1) % self.num_menu_items
        items_per_screen = self.menu_screen.items_per_screen
        if self.menu_item_pos < self.menu_view_pos:
            self.menu_view_pos = self.menu_item_pos
        elif self.menu_item_pos >= self.menu_view_pos + items_per_screen:
            self.menu_view_pos = self.menu_item_pos - items_per_screen + 1

    def decr_menu_item_pos(self):
        """Decrement menu item position, wrapping to last item."""
        self.menu_item_pos = (self.menu_item_pos - 1) % self.num_menu_items
        items_per_screen = self.menu_screen.items_per_screen
        if self.menu_item_pos < self.menu_view_pos:
            self.menu_view_pos = self.menu_item_pos
        elif self.menu_item_pos >= self.menu_view_pos + items_per_screen:
            self.menu_view_pos = self.menu_item_pos - items_per_screen + 1

    def update_menu_screen(self):
        n0 = self.menu_view_pos
        n1 = n0 + self.menu_screen.items_per_screen
        view_items = []
        for i, item in enumerate(self.menu_items[n0:n1]):
            led = self.calibrations.led(item)
            item_text = f"{n0+i} {item}" if led is None else f"{n0+i} {item} ({led})"
            view_items.append(item_text)
        try:
            self.menu_screen.set_menu_items(view_items)
        except MemoryError:
            self._log_error("Memory allocation failed for menu items")
            self.menu_screen.set_menu_items(view_items[:self.menu_screen.items_per_screen // 2])
        pos = self.menu_item_pos - self.menu_view_pos
        self.menu_screen.set_curr_item(pos)

    @property
    def is_absorbance(self):
        return self.measurement_name == self.ABSORBANCE_STR

    @property
    def is_transmittance(self):
        return self.measurement_name == self.TRANSMITTANCE_STR

    @property
    def is_raw_sensor(self):
        return self.measurement_name == self.RAW_SENSOR_STR

    @property
    def measurement_units(self):
        return None if self.measurement_name in self.DEFAULT_MEASUREMENTS else self.calibrations.units(self.measurement_name)

    @property
    def raw_sensor_value(self):
        value = self.light_sensor.value
        return value

    @property
    def transmittance(self):
        if self.blank_value <= 0:
            self.message_screen.set_message("Error: Invalid blank value ")
            self.message_screen.set_to_error()
            self.mode = Mode.MESSAGE
            return 0.0
        transmittance = float(self.raw_sensor_value) / self.blank_value
        return transmittance

    @property
    def absorbance(self):
        try:
            absorbance = -ulab.numpy.log10(self.transmittance)
            absorbance = absorbance if absorbance > 0.0 else 0.0
        except ValueError:
            absorbance = 0.0
        return absorbance

    @property
    def measurement_value(self):
        if self.is_absorbance:
            return (self.absorbance, None)
        elif self.is_transmittance:
            return (self.transmittance, None)
        elif self.is_raw_sensor:
            return (self.raw_sensor_value, None)
        else:
            try:
                value, type_tag = self.calibrations.apply(self.measurement_name, self.absorbance)
                if value is None and type_tag is None:
                    self._log_error(f"{self.measurement_name}: Absorbance out of range")
                return (value, type_tag)
            except CalibrationsError as e:
                self._log_error(str(e))
                self.measurement_name = 'Absorbance'
                return (None, None)

    def blank_sensor(self, set_blanked=True):
        blank_samples = ulab.numpy.zeros((constants.NUM_BLANK_SAMPLES,))
        for i in range(constants.NUM_BLANK_SAMPLES):
            try:
                value = self.raw_sensor_value
            except LightSensorOverflow:
                value = self.light_sensor.max_counts
            blank_samples[i] = value
            time.sleep(constants.BLANK_DT)
        self.blank_value = ulab.numpy.median(blank_samples)
        if self.blank_value <= 0:
            self.blank_value = 1.0
            if set_blanked:
                self.is_blanked = False
                self._log_error("Blanking failed: TSL2591 reading zero")
            return
        if set_blanked:
            self.is_blanked = True

    def serial_talking(self, set_talking=True, port=None):
        """Toggle USB HID communication."""
        if not set_talking:
            self.is_talking = False
            self.serial_connected = False
            self.measure_screen.set_measurement(self.measurement_name, None, "stopped", None, talking=self.is_talking)
            self.measure_screen.show()
            self.keyboard = None
            self.layout = None
            self.serial_start_time = None
            gc.collect()
            time.sleep(0.5)
            return

        self.is_talking = True
        if not self.keyboard or not self.layout:
            try:
                self.keyboard = Keyboard(usb_hid.devices)
                self.layout = KeyboardLayoutUS(self.keyboard)
            except Exception as e:
                self._log_error(f"HID setup error: {e}")
                self.is_talking = False      
                return

        self.measure_screen.set_measurement(self.measurement_name, None, "comm init", None, talking=self.is_talking)
        self.measure_screen.show()
        self.layout.write("Timestamp,Measurement,Value,Unit,Type,Blanked,Concentration\n")

        if self.serial_start_time is None:
            self.serial_start_time = time.monotonic() + constants.CONNECTION_WAIT_TIME

        start_time = time.monotonic()
        while self.is_talking and not self.serial_connected:
            self.handle_button_press()
            if time.monotonic() - start_time > constants.CONNECTION_WAIT_TIME:
                self.serial_connected = True
                self.measure_screen.set_measurement(self.measurement_name, None, "connected", None, talking=self.is_talking)
                self.measure_screen.show()
            time.sleep(0.1)

    def _convert_to_seconds(self, value, unit):
        """Convert value to seconds for internal use."""
        if unit == "sec":
            return value
        elif unit == "min":
            return value * 60.0
        elif unit == "hour":
            return value * 3600.0
        return value

    def blank_button_pressed(self, buttons):
        return 'blank' in buttons and not self.is_raw_sensor

    def menu_button_pressed(self, buttons):
        return 'menu' in buttons and not self.is_talking

    def up_button_pressed(self, buttons):
        return 'up' in buttons

    def down_button_pressed(self, buttons):
        return 'down' in buttons

    def left_button_pressed(self, buttons):
        return 'left' in buttons

    def right_button_pressed(self, buttons):
        return 'right' in buttons

    def gain_button_pressed(self, buttons):
        if not self.to_use_gain_asB:
            return 'gain' in buttons and self.is_raw_sensor
        else:
            return 'gain' in buttons

    def itime_button_pressed(self, buttons):
        return 'itime' in buttons

    def handle_button_press(self):
        pressed_buttons = set()
        while event := self.pad.events.get():
            if event.pressed:
                button_name = self.button_map.get(event.key_number)
                if button_name:
                    pressed_buttons.add(button_name)

        if not pressed_buttons or not self.check_debounce():
            return

        self.last_button_press = time.monotonic()

        if self.mode == Mode.MEASURE:
            if self.blank_button_pressed(pressed_buttons):
                if not self.is_blanked:
                    self.measure_screen.set_blanking()
                    self.blank_sensor()
                    if self.mode == Mode.MESSAGE:
                        return
                    self.measure_screen.set_blanked()
                else:
                    self.is_blanked = False
                    self.measure_screen.set_not_blanked()
            elif self.left_button_pressed(pressed_buttons):
                self.serial_talking(set_talking=not self.is_talking)
            elif self.menu_button_pressed(pressed_buttons):
                self.measure_screen.group = displayio.Group()
                self.menu_screen = None
                self.mode = Mode.MENU
                self.menu_view_pos = 0
                self.menu_item_pos = 0
                gc.collect()
                try:
                    self.menu_screen = MenuScreen()
                except MemoryError:
                    self._log_error("Memory allocation failed for MenuScreen")
            elif self.gain_button_pressed(pressed_buttons):
                self.light_sensor.gain = next(self.gain_cycle)
                self.is_blanked = False
            elif self.itime_button_pressed(pressed_buttons):
                self.light_sensor.integration_time = next(self.itime_cycle)
                self.is_blanked = False

        elif self.mode == Mode.MENU:
            if self.menu_button_pressed(pressed_buttons) or self.right_button_pressed(pressed_buttons) or self.left_button_pressed(pressed_buttons):
                selected_item = self.menu_items[self.menu_item_pos]
                if selected_item == self.ABOUT_STR:
                    if self.message_screen is None:
                        try:
                            self.message_screen = MessageScreen()
                        except MemoryError:
                            self._log_error("Memory allocation failed for Message Screen")
                    about_msg = f'firmware version {constants.__version__}'
                    self.message_screen.set_message(about_msg)
                    self.message_screen.set_to_about()
                    self.mode = Mode.MESSAGE
                elif selected_item == self.SETTINGS_STR:
                    self.menu_screen.group = displayio.Group()
                    self.menu_screen = None
                    self.measure_screen = None
                    self.message_screen = None
                    self.mode = Mode.SETTINGS
                    self.to_use_gain_asB = True
                    gc.collect()
                    try:
                        self.settings_screen = SettingsScreen()
                        self.settings_screen.set_values(
                            self.timeout_value,
                            self.timeout_unit,
                            self.transmission_interval_value,
                            self.transmission_interval_unit
                        )
                    except MemoryError:
                        self._log_error("Memory allocation failed for SettingsScreen")

                elif selected_item == self.CONCENTRATION_STR:
                    self.menu_screen.group = displayio.Group()
                    self.menu_screen = None
                    self.measure_screen = None
                    self.message_screen = None
                    self.mode = Mode.CONCENTRATION
                    self.to_use_gain_asB = True
                    gc.collect()
                    try:
                        self.concentration_screen = ConcentrationScreen()
                    except MemoryError:
                        self._log_error("Memory allocation failed for Concentration Screen")

                else:
                    self.menu_screen.group = displayio.Group()
                    self.menu_screen = None
                    self.measure_screen = None
                    self.measurement_name = self.menu_items[self.menu_item_pos]
                    self.mode = Mode.MEASURE
                    gc.collect()
            elif self.up_button_pressed(pressed_buttons):
                self.decr_menu_item_pos()
            elif self.down_button_pressed(pressed_buttons):
                self.incr_menu_item_pos()
            if self.mode == Mode.MENU:
                self.update_menu_screen()

        elif self.mode == Mode.SETTINGS:
            if self.menu_button_pressed(pressed_buttons):
                values = self.settings_screen.get_values()
                self.timeout_value = values["timeout_value"]
                self.timeout_unit = values["timeout_unit"]
                self.transmission_interval_value = values["interval_value"]
                self.transmission_interval_unit = values["interval_unit"]
                if self.timeout_value and self._convert_to_seconds(self.timeout_value, self.timeout_unit) <= self._convert_to_seconds(self.transmission_interval_value, self.transmission_interval_unit):
                    self.timeout_value = values["prev_timeout_value"]
                    self.timeout_unit = values["prev_timeout_unit"]
                    self.transmission_interval_value = values["prev_interval_value"]
                    self.transmission_interval_unit = values["prev_interval_unit"]
                    self.settings_screen = None
                    values = None
                    gc.collect()
                    if self.message_screen is None:
                        try:
                            self.message_screen = MessageScreen()
                            self.message_screen.set_message("Invalid timing values! Timeout is smaller than interval time. Discard!")
                            self.message_screen.set_to_error()
                            self.to_use_gain_asB = False
                            self.mode = Mode.MESSAGE
                            return 
                        except MemoryError:
                            self._log_error("Memory allocation failed for Message Screen")              
                try:
                    self.settings_screen.group = displayio.Group()
                    self.settings_screen = None
                    gc.collect()
                    if self.message_screen is None:
                        try:
                            print("Message screen created!")
                            self.message_screen = MessageScreen()
                            self.message_screen.set_message("Settings saved.")
                            self.message_screen.set_to_about()
                            self.to_use_gain_asB = False
                            self.mode = Mode.MESSAGE
                        except MemoryError:
                            self._log_error("Memory allocation failed for Message Screen")
                except ConfigurationError as e:
                    self._log_error(f"Failed to save settings: {e}")
            elif self.left_button_pressed(pressed_buttons): # Discard the settings
                self.settings_screen.group = displayio.Group()
                self.settings_screen = None
                self.mode = Mode.MENU
                self.to_use_gain_asB = False
                gc.collect()
                try:
                    self.menu_screen = MenuScreen()
                except MemoryError:
                    self._log_error("Memory allocation failed for MenuScreen")
            elif self.up_button_pressed(pressed_buttons):
                self.settings_screen.increment_value()
                # gc.mem_free()
            elif self.down_button_pressed(pressed_buttons):
                self.settings_screen.decrement_value()
                # gc.mem_free()
            elif self.right_button_pressed(pressed_buttons):
                self.settings_screen.move_down()
                # gc.mem_free()
            elif self.itime_button_pressed(pressed_buttons):
                self.settings_screen.cycle_unit()
                # gc.mem_free()
            elif self.blank_button_pressed(pressed_buttons):
                self.settings_screen.revert_to_saved()
                # gc.mem_free()
            elif self.gain_button_pressed(pressed_buttons):
                self.settings_screen.set_timeout_none()
                # gc.mem_free()

        elif self.mode == Mode.CONCENTRATION:
            if self.menu_button_pressed(pressed_buttons):
                self.concentration = self.concentration_screen.concen_val
                self.mode = Mode.MESSAGE
                self.concentration_screen.group = displayio.Group()
                self.concentration_screen = None
                gc.collect()
                try:
                    self.message_screen = MessageScreen()
                    msg = "Concen val is " + str(self.concentration) + " nM/l"
                    self.message_screen.set_message(msg)
                    self.message_screen.set_to_about()
                except MemoryError:
                    self._log_error("Memory allocation failed for MessageScreen")

            elif self.blank_button_pressed(pressed_buttons):
                self.concentration_screen.set_to_zero()
            elif self.up_button_pressed(pressed_buttons):
                self.concentration_screen.add(1)
            elif self.down_button_pressed(pressed_buttons):
                self.concentration_screen.add(-1)
            elif self.left_button_pressed(pressed_buttons):
                self.concentration_screen.add(-10)
            elif self.right_button_pressed(pressed_buttons):
                self.concentration_screen.add(10)
            elif self.itime_button_pressed(pressed_buttons):
                self.concentration_screen.add(100)
            elif self.gain_button_pressed(pressed_buttons):
                self.concentration_screen.add(-100)

        elif self.mode == Mode.MESSAGE or self.mode == Mode.ABORT:
            if pressed_buttons:
                self.message_screen = None
                self.measure_screen = None
                self.mode = Mode.MENU
                if self.menu_screen is None:
                    try:
                        self.menu_screen = MenuScreen()
                    except MemoryError:
                        self._log_error("Memory allocation failed for MenuScreen")
            elif not self.calibrations_checked and self.calibrations.has_errors:
                self.message_screen.set_message(self.calibrations.pop_error())
                self.message_screen.set_to_error()
                self.mode = Mode.MESSAGE
                self.calibrations_checked = True

    def check_debounce(self):
        return time.monotonic() - self.last_button_press >= constants.DEBOUNCE_DT

    def run(self):
        while True:
            self.handle_button_press()
            if self.mode == Mode.MEASURE:
                if self.measure_screen is None:
                    try:
                        self.measure_screen = MeasureScreen()
                    except MemoryError:
                        self._log_error("Memory allocation failed for MeasureScreen")
                        continue
                if self.is_talking and self.serial_connected and self.keyboard and self.layout:
                    try:
                        numeric_value, type_tag = self.measurement_value
                        units = self.measurement_units or "None"
                        type_tag = type_tag or "None"
                        concen_val = self.concentration or "None"

                        current_time = time.monotonic()
                        relative_time = current_time - self.serial_start_time
                        if self.timeout_value and self.timeout_unit:
                            timeout_seconds = self._convert_to_seconds(self.timeout_value, self.timeout_unit)
                            if timeout_seconds and relative_time > timeout_seconds:
                                self.is_talking = False
                        transmission_interval_seconds = self._convert_to_seconds(self.transmission_interval_value, self.transmission_interval_unit)
                        if current_time - self.last_transmission_time >= transmission_interval_seconds:
                            self.last_transmission_time = current_time
                            blanked = "True" if self.is_blanked else "False"
                            data_str = f"{relative_time:.2f},{self.measurement_name},{numeric_value:.2f},{units},{type_tag},{blanked},{concen_val}\n"
                            self.layout.write(data_str)
                        self.measure_screen.set_measurement(
                            self.measurement_name,
                            self.measurement_units,
                            numeric_value,
                            self.configuration.precision if isinstance(numeric_value, (int, float)) else None,
                            type_tag=type_tag,
                            talking=self.is_talking
                        )
                    except MemoryError:
                        self._log_error("Memory allocation failed for Measure Screen")
                    except (ValueError, RuntimeError) as e:
                        self._log_error(f"HID send error: {e}")
                        self.is_talking = False
                        self.serial_connected = False
                        self.measure_screen.set_measurement(self.measurement_name, None, "disconnected", None, talking=self.is_talking)
                    except LightSensorOverflow:
                        self.measure_screen.set_measurement(self.measurement_name, None, "overflow", None)
                else:
                    try:
                        numeric_value, type_tag = self.measurement_value
                        self.measure_screen.set_measurement(
                            self.measurement_name,
                            self.measurement_units,
                            numeric_value,
                            self.configuration.precision if isinstance(numeric_value, (int, float)) else None,
                            type_tag=type_tag,
                            talking=self.is_talking
                        )
                    except MemoryError:
                        self._log_error("Memory allocation failed for Measure Screen")
                    except LightSensorOverflow:
                        self.measure_screen.set_measurement(self.measurement_name, None, "overflow", None)

                if self.is_raw_sensor:
                    try:
                        self.measure_screen.set_blanked()
                        self.measure_screen.set_gain(self.light_sensor.gain)
                        self.measure_screen.set_integration_time(self.light_sensor.integration_time)
                    except MemoryError:
                        self._log_error("Memory allocation failed for Measure Screen")
                else:
                    try:
                        if self.is_blanked:
                            self.measure_screen.set_blanked()
                        else:
                            self.measure_screen.set_not_blanked()
                        self.measure_screen.clear_gain()
                        self.measure_screen.clear_integration_time()
                    except MemoryError:
                        self._log_error("Memory allocation failed for Measure Screen")

                self.battery_monitor.update()
                self.measure_screen.set_bat(self.battery_monitor.voltage_lowpass)
                self.measure_screen.show()

            elif self.mode == Mode.MENU:
                if self.menu_screen is None:
                    continue
                self.update_menu_screen()
                self.menu_screen.show()

            elif self.mode == Mode.SETTINGS:
                if self.settings_screen is None:
                    continue
                self.settings_screen.show()

            elif self.mode == Mode.CONCENTRATION:
                if self.concentration_screen is None:
                    continue
                self.concentration_screen.show()

            elif self.mode in (Mode.MESSAGE, Mode.ABORT):
                self.message_screen.show()

            time.sleep(constants.LOOP_DT)