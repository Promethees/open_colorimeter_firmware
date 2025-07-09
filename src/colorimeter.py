import time
import board
import busio
import keypad
import constants
import adafruit_itertools
import adafruit_tca9548a
import gc
import measurement
from light_sensor import LightSensorTSL2591, LightSensorIOError
from battery_monitor import BatteryMonitor
from configuration import Configuration, ConfigurationError
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
        'last_button_press',
        'pad',
        'configuration',
        'light_sensor_90',
        'light_sensor_180',
        'light_sensors',
        'battery_monitor',
        'gain_cycle_sensor_90',
        'itime_cycle_sensor_90',
        'gain_cycle_sensor_180',
        'itime_cycle_sensor_180',
        'measurement',
        'measurement_name',
        'i2c',
        'i2c_mux'
    ]

    ABOUT_STR = constants.ABOUT_STR
    DEFAULT_MEASUREMENTS = [
        measurement.RawCount.NAME,
        measurement.Irradiance.NAME,
        measurement.RelativeUnit.NAME
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
        self.menu_items = list(self.DEFAULT_MEASUREMENTS)
        self.menu_view_pos = 0
        self.menu_item_pos = 0
        self.mode = Mode.MEASURE
        self.last_button_press = None
        self.pad = None
        self.configuration = None
        self.light_sensor_90 = None
        self.light_sensor_180 = None
        self.light_sensors = None
        self.battery_monitor = None
        self.gain_cycle_sensor_90 = None
        self.itime_cycle_sensor_90 = None
        self.gain_cycle_sensor_180 = None
        self.itime_cycle_sensor_180 = None
        self.measurement = None
        self.measurement_name = None
        self.i2c = None
        self.i2c_mux = None

        self._init_display()
        self._init_keypad()
        self._init_i2c()
        self._init_configuration()
        self._init_light_sensors()
        self._init_battery_monitor()
        self._init_managers()
        self._extend_menu_items()
        self._set_default_measurement()

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

    def _init_i2c(self):
        try:
            self.i2c = busio.I2C(board.SCL, board.SDA)
            self.i2c_mux = adafruit_tca9548a.PCA9546A(self.i2c)
        except Exception as e:
            self.mode = Mode.ABORT
            self.screen_manager = ScreenManager(self)
            self.screen_manager.show_abort_message(f"I2C initialization failed: {e}")

    def _init_configuration(self):
        self.configuration = Configuration()
        try:
            self.configuration.load()
        except ConfigurationError as e:
            self.mode = Mode.MESSAGE
            self.screen_manager = ScreenManager(self)
            self.screen_manager.show_error_message(str(e))

    def _init_light_sensors(self):
        try:
            self.light_sensor_90 = LightSensorTSL2591(self.i2c_mux[1])
            if self.configuration.gain_sensor_90 is not None:
                self.light_sensor_90.gain = self.configuration.gain_sensor_90
            if self.configuration.itime_sensor_90 is not None:
                self.light_sensor_90.integration_time = self.configuration.itime_sensor_90
        except LightSensorIOError as e:
            self.mode = Mode.ABORT
            self.screen_manager = ScreenManager(self)
            self.screen_manager.show_abort_message(f"90° sensor missing? {e}")
            return

        try:
            self.light_sensor_180 = LightSensorTSL2591(self.i2c_mux[0])
            if self.configuration.gain_sensor_180 is not None:
                self.light_sensor_180.gain = self.configuration.gain_sensor_180
            if self.configuration.itime_sensor_180 is not None:
                self.light_sensor_180.integration_time = self.configuration.itime_sensor_180
        except LightSensorIOError as e:
            self.mode = Mode.ABORT
            self.screen_manager = ScreenManager(self)
            self.screen_manager.show_abort_message(f"180° sensor missing? {e}")
            return

        self.light_sensors = (self.light_sensor_90, self.light_sensor_180)

    def _init_battery_monitor(self):
        self.battery_monitor = BatteryMonitor()
        self.gain_cycle_sensor_90 = adafruit_itertools.cycle(constants.GAIN_TO_STR)
        if self.configuration.gain_sensor_90:
            while next(self.gain_cycle_sensor_90) != self.configuration.gain_sensor_90:
                continue
        self.itime_cycle_sensor_90 = adafruit_itertools.cycle(constants.INTEGRATION_TIME_TO_STR)
        if self.configuration.itime_sensor_90:
            while next(self.itime_cycle_sensor_90) != self.configuration.itime_sensor_90:
                continue
        self.gain_cycle_sensor_180 = adafruit_itertools.cycle(constants.GAIN_TO_STR)
        if self.configuration.gain_sensor_180:
            while next(self.gain_cycle_sensor_180) != self.configuration.gain_sensor_180:
                continue
        self.itime_cycle_sensor_180 = adafruit_itertools.cycle(constants.INTEGRATION_TIME_TO_STR)
        if self.configuration.itime_sensor_180:
            while next(self.itime_cycle_sensor_180) != self.configuration.itime_sensor_180:
                continue

    def _init_managers(self):
        self.screen_manager = ScreenManager(self)
        self.button_handler = ButtonHandler(self)

    def _extend_menu_items(self):
        self.menu_items.append(self.ABOUT_STR)

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

    def run(self):
        while True:
            self.button_handler.handle_button_press()
            self.screen_manager.update_screens()
            self.battery_monitor.update()
            time.sleep(constants.LOOP_DT)
            gc.collect()