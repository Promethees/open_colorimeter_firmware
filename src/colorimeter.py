import time
import ulab
import board
import keypad
import constants
import displayio
import adafruit_itertools
import gc
from light_sensor import LightSensor, LightSensorOverflow, LightSensorIOError
from battery_monitor import BatteryMonitor
from configuration import Configuration, ConfigurationError
from calibrations import Calibrations, CalibrationsError
from button_handler import ButtonHandler
from screen_manager import ScreenManager
from serial_manager import SerialManager
from mode import Mode

class Colorimeter:
    ABOUT_STR = 'About'
    RAW_SENSOR_STR = 'Raw Sensor'
    ABSORBANCE_STR = 'Absorbance'
    TRANSMITTANCE_STR = 'Transmittance'
    SETTINGS_STR = 'Settings'
    CONCENTRATION_STR = 'Concentration'
    DEFAULT_MEASUREMENTS = [ABSORBANCE_STR, TRANSMITTANCE_STR, RAW_SENSOR_STR]

    def __init__(self):
        # Setup managers
        self.screen_manager = ScreenManager(self)
        self.button_handler = ButtonHandler(self)
        self.serial_manager = SerialManager(self)

        self.menu_items = list(self.DEFAULT_MEASUREMENTS)
        self.menu_view_pos = 0
        self.menu_item_pos = 0
        self.mode = Mode.MEASURE
        self.is_blanked = False
        self.is_talking = False
        self.serial_connected = False
        self.blank_value = 1.0
        self.last_transmission_time = 0.0
        self.calibrations_checked = False
        self.serial_start_time = None
        self.to_use_gain_asB = False
        self.concentration = None

        # Initialize components
        self._init_display()
        self._init_keypad()
        self._init_configuration()
        self._init_calibrations()
        self._init_light_sensor()
        self._init_battery_monitor()
        self._init_settings()

        # Extend menu items
        self.menu_items.extend([k for k in self.calibrations.data])
        self.menu_items.extend([self.CONCENTRATION_STR, self.ABOUT_STR, self.SETTINGS_STR])

        # Set default measurement
        self._set_default_measurement()

    def _init_display(self):
        board.DISPLAY.brightness = 1.0

    def _init_keypad(self):
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

    def _init_configuration(self):
        self.configuration = Configuration()
        try:
            self.configuration.load()
        except ConfigurationError as e:
            self.mode = Mode.MESSAGE
            self.screen_manager.set_error_message(str(e))

    def _init_calibrations(self):
        self.calibrations = Calibrations()
        try:
            self.calibrations.load()
        except CalibrationsError as e:
            self.mode = Mode.MESSAGE
            self.screen_manager.set_error_message(str(e))
        else:
            if self.calibrations.has_errors:
                self.mode = Mode.MESSAGE
                self.screen_manager.set_error_message("errors found in calibrations file")

    def _init_light_sensor(self):
        try:
            self.light_sensor = LightSensor()
        except LightSensorIOError as e:
            self.mode = Mode.ABORT
            self.screen_manager.set_abort_message(f"TSL2591 missing? {e}")
        else:
            if self.configuration.gain:
                self.light_sensor.gain = self.configuration.gain
            if self.configuration.integration_time:
                self.light_sensor.integration_time = self.configuration.integration_time
            self.blank_sensor(set_blanked=False)
            self.screen_manager.set_not_blanked()

    def _init_battery_monitor(self):
        self.battery_monitor = BatteryMonitor()
        self.gain_cycle = adafruit_itertools.cycle(constants.GAIN_TO_STR)
        if self.configuration.gain:
            while next(self.gain_cycle) != self.configuration.gain:
                continue
        self.itime_cycle = adafruit_itertools.cycle(constants.INTEGRATION_TIME_TO_STR)
        if self.configuration.integration_time:
            while next(self.itime_cycle) != self.configuration.integration_time:
                continue

    def _init_settings(self):
        self.timeout_value = self.configuration.timeout_value
        self.timeout_unit = self.configuration.timeout_unit
        self.transmission_interval_value = self.configuration.transmission_interval_value
        self.transmission_interval_unit = self.configuration.transmission_interval_unit
        if self.timeout_value is not None:
            if self._convert_to_seconds(self.timeout_value, self.timeout_unit) <= self._convert_to_seconds(self.transmission_interval_value, self.transmission_interval_unit):
                self.timeout_value = constants.DEFAULT_TIMEOUT_VALUE
                self.timeout_unit = constants.DEFAULT_TIMEOUT_UNIT
                self.transmission_interval_value = constants.DEFAULT_TRANSMISSION_INTERVAL_VALUE
                self.transmission_interval_unit = constants.DEFAULT_TRANSMISSION_INTERVAL_UNIT

    def _set_default_measurement(self):
        if self.configuration.startup in self.menu_items:
            self.measurement_name = self.configuration.startup
        else:
            if self.configuration.startup:
                self.mode = Mode.MESSAGE
                self.screen_manager.set_error_message(f"startup measurement {self.configuration.startup} not found")
            self.measurement_name = self.menu_items[0]

    def _convert_to_seconds(self, value, unit):
        if unit == "sec":
            return value
        elif unit == "min":
            return value * 60.0
        elif unit == "hour":
            return value * 3600.0
        return value

    def blank_sensor(self, set_blanked=True):
        blank_samples = ulab.numpy.zeros((constants.NUM_BLANK_SAMPLES,))
        for i in range(constants.NUM_BLANK_SAMPLES):
            try:
                value = self.light_sensor.value
            except LightSensorOverflow:
                value = self.light_sensor.max_counts
            blank_samples[i] = value
            time.sleep(constants.BLANK_DT)
        self.blank_value = ulab.numpy.median(blank_samples)
        if self.blank_value <= 0:
            self.blank_value = 1.0
            if set_blanked:
                self.is_blanked = False
                self.screen_manager.set_error_message("Blanking failed: TSL2591 reading zero")
            return
        if set_blanked:
            self.is_blanked = True

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
        return self.light_sensor.value

    @property
    def transmittance(self):
        if self.blank_value <= 0:
            self.mode = Mode.MESSAGE
            self.screen_manager.set_error_message("Error: Invalid blank value")
            return 0.0
        return float(self.raw_sensor_value) / self.blank_value

    @property
    def absorbance(self):
        try:
            absorbance = -ulab.numpy.log10(self.transmittance)
            return absorbance if absorbance > 0.0 else 0.0
        except ValueError:
            return 0.0

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
                    self.screen_manager.set_error_message(f"{self.measurement_name}: Absorbance out of range")
                return (value, type_tag)
            except CalibrationsError as e:
                self.screen_manager.set_error_message(str(e))
                self.measurement_name = 'Absorbance'
                return (None, None)

    @property
    def num_menu_items(self):
        return len(self.menu_items)

    def run(self):
        while True:
            self.button_handler.handle_button_press()
            self.screen_manager.update_screens()
            self.serial_manager.handle_serial_communication()
            self.battery_monitor.update()
            self.screen_manager.update_battery(self.battery_monitor.voltage_lowpass)
            time.sleep(constants.LOOP_DT)