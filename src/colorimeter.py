import time
import ulab
import board
import analogio
import digitalio
import keypad
import constants
import adafruit_itertools

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

class Mode:
    MEASURE = 0
    MENU    = 1
    MESSAGE = 2
    ABORT   = 3

class Colorimeter:

    ABOUT_STR = 'About'
    RAW_SENSOR_STR = 'Raw Sensor' 
    ABSORBANCE_STR = 'Absorbance'
    TRANSMITTANCE_STR = 'Transmittance'
    DEFAULT_MEASUREMENTS = [ABSORBANCE_STR, TRANSMITTANCE_STR, RAW_SENSOR_STR]

    def __init__(self):

        self.menu_items = list(self.DEFAULT_MEASUREMENTS)
        self.menu_view_pos = 0
        self.menu_item_pos = 0
        self.mode = Mode.MEASURE
        self.is_blanked = False
        self.blank_value = 1.0

        # Create screens
        board.DISPLAY.brightness = 1.0
        self.measure_screen = MeasureScreen()
        self.message_screen = MessageScreen()
        self.menu_screen = MenuScreen()

        # Setup keypad inputs using ShiftRegisterKeys
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
        except ConfigurationError as error:
            self.message_screen.set_message(str(error))
            self.message_screen.set_to_error()
            self.mode = Mode.MESSAGE

        # Load calibrations and populate menu items
        self.calibrations = Calibrations()
        try:
            self.calibrations.load()
        except CalibrationsError as error: 
            self.message_screen.set_message(str(error))
            self.message_screen.set_to_error()
            self.mode = Mode.MESSAGE
        else:
            if self.calibrations.has_errors:
                error_msg = 'errors found in calibrations file'
                self.message_screen.set_message(error_msg)
                self.message_screen.set_to_error()
                self.mode = Mode.MESSAGE

        self.menu_items.extend([k for k in self.calibrations.data])
        self.menu_items.append(self.ABOUT_STR)

        # Set default/startup measurement
        if self.configuration.startup in self.menu_items:
            self.measurement_name = self.configuration.startup
        else:
            if self.configuration.startup is not None:
                error_msg = f'startup measurement {self.configuration.startup} not found'
                self.message_screen.set_message(error_msg)
                self.message_screen.set_to_error()
                self.mode = Mode.MESSAGE
            self.measurement_name = self.menu_items[0] 

        # Setup light sensor (TSL2591) and preliminary blanking 
        try:
            self.light_sensor = LightSensor()
        except LightSensorIOError as error:
            error_msg = f'TSL2591 missing? {error}'
            self.message_screen.set_message(error_msg, ok_to_continue=False)
            self.message_screen.set_to_abort()
            self.mode = Mode.ABORT
        else:
            if self.configuration.gain is not None:
                self.light_sensor.gain = self.configuration.gain
            if self.configuration.integration_time is not None:
                self.light_sensor.integration_time = self.configuration.integration_time
            self.blank_sensor(set_blanked=False)
            self.measure_screen.set_not_blanked()

        # Setup battery monitoring settings cycles 
        self.battery_monitor = BatteryMonitor()
        self.setup_gain_and_itime_cycles()

    def setup_gain_and_itime_cycles(self):
        self.gain_cycle = adafruit_itertools.cycle(constants.GAIN_TO_STR) 
        if self.configuration.gain is not None:
            while next(self.gain_cycle) != self.configuration.gain: 
                continue

        self.itime_cycle = adafruit_itertools.cycle(constants.INTEGRATION_TIME_TO_STR)
        if self.configuration.integration_time is not None:
            while next(self.itime_cycle) != self.configuration.integration_time:
                continue

    @property
    def num_menu_items(self):
        return len(self.menu_items)

    def incr_menu_item_pos(self):
        #Increment menu item position, wrapping to 0 if at the end.
        self.menu_item_pos = (self.menu_item_pos + 1) % self.num_menu_items
        items_per_screen = self.menu_screen.items_per_screen
        if self.menu_item_pos < self.menu_view_pos:
            self.menu_view_pos = self.menu_item_pos
        elif self.menu_item_pos >= self.menu_view_pos + items_per_screen:
            self.menu_view_pos = self.menu_item_pos - items_per_screen + 1

    def decr_menu_item_pos(self):
        #Decrement menu item position, wrapping to last item if at 0.
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
            if led is None:
                item_text = f'{n0+i} {item}' 
            else:
                item_text = f'{n0+i} {item} ({led})' 
            view_items.append(item_text)
        self.menu_screen.set_menu_items(view_items)
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
        if self.measurement_name in self.DEFAULT_MEASUREMENTS: 
            units = None 
        else:
            units = self.calibrations.units(self.measurement_name)
        return units

    @property
    def raw_sensor_value(self):
        value = self.light_sensor.value
        # Debug: Uncomment to log TSL2591 readings
        # print(f"TSL2591 raw value: {value}")
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
                value, type_tag = self.calibrations.apply( 
                    self.measurement_name, 
                    self.absorbance
                )
                if value is None and type_tag is None:
                    self.message_screen.set_message(f"{self.measurement_name}: Absorbance out of defined range")
                    self.message_screen.set_to_error()
                    self.mode = Mode.MESSAGE
                return (value, type_tag)
            except CalibrationsError as error:
                self.message_screen.set_message(str(error))
                self.message_screen.set_to_error()
                self.measurement_name = 'Absorbance'
                self.mode = Mode.MESSAGE
                return (None, None)

    def blank_sensor(self, set_blanked=True):
        blank_samples = ulab.numpy.zeros((constants.NUM_BLANK_SAMPLES,))
        for i in range(constants.NUM_BLANK_SAMPLES):
            try:
                value = self.raw_sensor_value
                # Debug: Uncomment to log TSL2591 values and settings
                # print(f"Blank sample {i}: {value}, Gain: {self.light_sensor.gain}, Integration: {self.light_sensor.integration_time}")
            except LightSensorOverflow:
                value = self.light_sensor.max_counts
            blank_samples[i] = value
            time.sleep(constants.BLANK_DT)
        self.blank_value = ulab.numpy.median(blank_samples)
        if self.blank_value <= 0:
            self.blank_value = 1.0
            if set_blanked:
                self.is_blanked = False
                self.message_screen.set_message("Blanking failed: TSL2591 reading zero. Check LED and sensor.")
                self.message_screen.set_to_error()
                self.mode = Mode.MESSAGE
            # Debug: Uncomment to log blank value
            # print(f"Blank value set to fallback: {self.blank_value}")
            return
        if set_blanked:
            self.is_blanked = True
        # Debug: Uncomment to log successful blank value
        # print(f"Blank value: {self.blank_value}")

    def blank_button_pressed(self, buttons):  
        if self.is_raw_sensor:
            return False
        return 'blank' in buttons

    def menu_button_pressed(self, buttons): 
        return 'menu' in buttons

    def up_button_pressed(self, buttons):
        return 'up' in buttons

    def down_button_pressed(self, buttons):
        return 'down' in buttons

    def left_button_pressed(self, buttons):
        return 'left' in buttons

    def right_button_pressed(self, buttons):
        return 'right' in buttons

    def gain_button_pressed(self, buttons):
        if self.is_raw_sensor:
            return 'gain' in buttons
        return False

    def itime_button_pressed(self, buttons):
        if self.is_raw_sensor:
            return 'itime' in buttons
        return False

    def handle_button_press(self):
        pressed_buttons = set()
        while event := self.pad.events.get():
            if event.pressed:
                button_name = self.button_map.get(event.key_number)
                if button_name:
                    pressed_buttons.add(button_name)
        # Debug: Uncomment to log button presses and mode
        # print(f"Mode: {self.mode}, Buttons: {pressed_buttons}")

        if not pressed_buttons:
            return 
        if not self.check_debounce():
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
            elif self.menu_button_pressed(pressed_buttons):
                self.mode = Mode.MENU
                self.menu_view_pos = 0
                self.menu_item_pos = 0
                self.update_menu_screen()
            elif self.gain_button_pressed(pressed_buttons):
                self.light_sensor.gain = next(self.gain_cycle)
                self.is_blanked = False
                # Debug: Uncomment to log gain change
                # print(f"New gain: {self.light_sensor.gain}")
            elif self.itime_button_pressed(pressed_buttons):
                self.light_sensor.integration_time = next(self.itime_cycle)
                self.is_blanked = False
                # Debug: Uncomment to log integration time change
                # print(f"New integration time: {self.light_sensor.integration_time}")

        elif self.mode == Mode.MENU:
            if self.menu_button_pressed(pressed_buttons):
                self.mode = Mode.MEASURE
            elif self.up_button_pressed(pressed_buttons): 
                self.decr_menu_item_pos()
            elif self.down_button_pressed(pressed_buttons): 
                self.incr_menu_item_pos()
            elif self.right_button_pressed(pressed_buttons) or self.left_button_pressed(pressed_buttons): 
                selected_item = self.menu_items[self.menu_item_pos]
                if selected_item == self.ABOUT_STR:
                    about_msg = f'firmware version {constants.__version__}'
                    self.message_screen.set_message(about_msg) 
                    self.message_screen.set_to_about()
                    self.mode = Mode.MESSAGE
                else:
                    self.measurement_name = self.menu_items[self.menu_item_pos]
                    self.mode = Mode.MEASURE
            self.update_menu_screen()

        elif self.mode == Mode.MESSAGE:
            if self.menu_button_pressed(pressed_buttons) or self.right_button_pressed(pressed_buttons):
                self.mode = Mode.MEASURE
            elif self.calibrations.has_errors:
                error_msg = self.calibrations.pop_error()
                self.message_screen.set_message(error_msg)
                self.message_screen.set_to_error()
                self.mode = Mode.MESSAGE

        elif self.mode == Mode.ABORT:
            if self.menu_button_pressed(pressed_buttons) or self.right_button_pressed(pressed_buttons):
                self.mode = Mode.MEASURE

    def check_debounce(self):
        button_dt = time.monotonic() - self.last_button_press
        if button_dt < constants.DEBOUNCE_DT: 
            return False
        return True

    def run(self):
        while True:
            self.handle_button_press()
            if self.mode == Mode.MEASURE:
                try:
                    numeric_value, type_tag = self.measurement_value
                    self.measure_screen.set_measurement(
                        self.measurement_name, 
                        self.measurement_units, 
                        numeric_value,
                        self.configuration.precision if isinstance(numeric_value, (int, float)) else None,
                        type_tag=type_tag 
                    )
                except LightSensorOverflow:
                    self.measure_screen.set_measurement(self.measurement_name, None, 'overflow', None)

                if self.is_raw_sensor:
                    self.measure_screen.set_blanked()
                    gain = self.light_sensor.gain
                    itime = self.light_sensor.integration_time
                    self.measure_screen.set_gain(gain)
                    self.measure_screen.set_integration_time(itime)
                else:
                    if self.is_blanked:
                        self.measure_screen.set_blanked()
                    else:
                        self.measure_screen.set_not_blanked()
                    self.measure_screen.clear_gain()
                    self.measure_screen.clear_integration_time()

                self.battery_monitor.update()
                battery_voltage = self.battery_monitor.voltage_lowpass
                self.measure_screen.set_bat(battery_voltage)

                self.measure_screen.show()

            elif self.mode == Mode.MENU:
                self.menu_screen.show()

            elif self.mode in (Mode.MESSAGE, Mode.ABORT):
                self.message_screen.show()

            time.sleep(constants.LOOP_DT)