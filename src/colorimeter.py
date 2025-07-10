import time
import ulab
import board
import keypad
import constants
import adafruit_itertools
import gc
from light_sensor import LightSensor, LightSensorOverflow, LightSensorIOError
from battery_monitor import BatteryMonitor
from configuration import Configuration, ConfigurationError
from calibrations import Calibrations, CalibrationsError
from button_handler import ButtonHandler
from screen_manager import ScreenManager
from mode import Mode

class Colorimeter:
    _instance = None

    __slots__ = [
        'screen_manager',
        'button_handler',
        'menu_items',
        'menu_view_pos',
        'menu_item_pos',
        'mode',
        'is_blanked',
        'blank_values',
        'channel',
        'last_button_press',
        'pad',
        'configuration',
        'calibrations',
        'light_sensor',
        'battery_monitor',
        'gain_cycle',
        'itime_cycle',
        'channel_cycle',
        'measurement_name',
        'is_startup'
    ]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Colorimeter, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, 'screen_manager') and self.screen_manager is not None:
            return

        self.screen_manager = None
        self.button_handler = None
        self.menu_items = list(constants.DEFAULT_MEASUREMENTS)
        self.menu_view_pos = 0
        self.menu_item_pos = 0
        self.mode = Mode.MEASURE
        self.is_blanked = False
        self.blank_values = ulab.numpy.ones((constants.NUM_CHANNEL,))
        self.channel = None
        self.last_button_press = None
        self.pad = None
        self.configuration = None
        self.calibrations = None
        self.light_sensor = None
        self.battery_monitor = None
        self.gain_cycle = None
        self.itime_cycle = None
        self.channel_cycle = None
        self.measurement_name = None
        self.is_startup = True

        self._init_configuration()
        self._init_calibrations()
        self._init_light_sensor()
        self._init_display()
        self._init_keypad()
        self._init_managers()
        self._init_battery_monitor()
        self._extend_menu_items()
        self._set_default_measurement()
        self.is_startup = False

        gc.collect()

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
            value_when_pressed=True,
            interval=0.1
        )

    def _init_configuration(self):
        self.configuration = Configuration()
        try:
            self.configuration.load()
        except ConfigurationError as e:
            self.mode = Mode.MESSAGE
            self.screen_manager = ScreenManager(self)
            self.screen_manager.show_error_message(str(e))
        self.channel = self.configuration.channel

    def _init_calibrations(self):
        self.calibrations = Calibrations()
        try:
            self.calibrations.load()
        except CalibrationsError as e:
            self.mode = Mode.MESSAGE
            self.screen_manager = ScreenManager(self)
            self.screen_manager.show_error_message(str(e))
        else:
            if self.calibrations.has_errors:
                self.mode = Mode.MESSAGE
                self.screen_manager.show_error_message("errors found in calibrations file")

    def _init_light_sensor(self):
        try:
            self.light_sensor = LightSensor()
        except LightSensorIOError as e:
            self.mode = Mode.ABORT
            self.screen_manager = ScreenManager(self)
            self.screen_manager.show_abort_message(f"missing sensor? {e}")
        else:
            if self.configuration.gain is not None:
                self.light_sensor.gain = self.configuration.gain
            if self.configuration.integration_time is not None:
                self.light_sensor.integration_time = self.configuration.integration_time
            self.blank_sensor(set_blanked=False)
            if self.screen_manager:
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
        self.channel_cycle = adafruit_itertools.cycle(constants.CHANNEL_TO_STR)
        if self.configuration.channel:
            while next(self.channel_cycle) != self.configuration.channel:
                continue

    def _init_managers(self):
        self.screen_manager = ScreenManager(self)
        self.button_handler = ButtonHandler(self)

    def _extend_menu_items(self):
        self.menu_items.extend([k for k in self.calibrations.data])
        self.menu_items.append(constants.ABOUT_STR)

    def _set_default_measurement(self):
        if self.configuration.startup in self.menu_items:
            self.measurement_name = self.configuration.startup
        else:
            if self.configuration.startup:
                self.mode = Mode.MESSAGE
                self.screen_manager.show_error_message(f"startup measurement {self.configuration.startup} not found")
            self.measurement_name = self.menu_items[0]
        self.menu_item_pos = self.menu_items.index(self.measurement_name)

    @property
    def num_menu_items(self):
        return len(self.menu_items)

    @property
    def is_absorbance(self):
        return self.measurement_name == constants.ABSORBANCE_STR

    @property
    def is_transmittance(self):
        return self.measurement_name == constants.TRANSMITTANCE_STR

    @property
    def is_raw_sensor(self):
        return self.measurement_name == constants.RAW_SENSOR_STR

    @property
    def measurement_units(self):
        return None if self.measurement_name in constants.DEFAULT_MEASUREMENTS else self.calibrations.units(self.measurement_name)

    @property
    def raw_sensor_value(self):
        value = self.light_sensor.raw_values[self.channel]
        if value >= self.light_sensor.max_counts:
            raise LightSensorOverflow('light sensor reading > max_counts')
        return value

    @property
    def transmittance(self):
        value = self.raw_sensor_value
        blank_value = self.blank_values[self.channel]
        if blank_value <= 0:
            self.mode = Mode.MESSAGE
            self.screen_manager.show_error_message("Error: Invalid blank value")
            return 0.0
        return float(value) / blank_value

    @property
    def absorbance(self):
        try:
            absorbance = -ulab.numpy.log10(self.transmittance)
            return absorbance if absorbance > 0.0 else 0.0
        except ValueError:
            return 0.0

    @property
    def measurement_value(self):
        self.update_channel()
        if self.is_absorbance:
            return self.absorbance
        elif self.is_transmittance:
            return self.transmittance
        elif self.is_raw_sensor:
            return self.raw_sensor_value
        else:
            try:
                value = self.calibrations.apply(self.measurement_name, self.absorbance)
                if value is None:
                    self.screen_manager.show_error_message(f"{self.measurement_name}: Absorbance out of range")
                return value
            except CalibrationsError as e:
                self.mode = Mode.MESSAGE
                self.screen_manager.show_error_message(str(e))
                self.measurement_name = constants.ABSORBANCE_STR
                return None

    def update_channel(self):
        channel = self.calibrations.channel(self.measurement_name)
        if channel is not None and channel != self.channel:
            self.channel = channel
            while next(self.channel_cycle) != self.channel:
                continue

    def blank_sensor(self, set_blanked=True):
        blank_samples = ulab.numpy.zeros((constants.NUM_BLANK_SAMPLES, constants.NUM_CHANNEL))
        for i in range(constants.NUM_BLANK_SAMPLES):
            raw_values = self.light_sensor.raw_values
            blank_samples[i, constants.CHANNEL_UVA] = raw_values[constants.CHANNEL_UVA]
            blank_samples[i, constants.CHANNEL_UVB] = raw_values[constants.CHANNEL_UVB]
            blank_samples[i, constants.CHANNEL_UVC] = raw_values[constants.CHANNEL_UVC]
            time.sleep(constants.BLANK_DT)
        self.blank_values = ulab.numpy.median(blank_samples, axis=0)
        if set_blanked:
            self.is_blanked = True
            if self.screen_manager:
                self.screen_manager.set_blanked()

    def run(self):
        while True:
            self.button_handler.handle_button_press()
            self.screen_manager.update_screens()
            self.battery_monitor.update()
            time.sleep(constants.LOOP_DT)
            gc.collect()