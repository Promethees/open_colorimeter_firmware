import gc
import displayio
from menu_screen import MenuScreen
from message_screen import MessageScreen
from measure_screen import MeasureScreen
from settings_screen import SettingsScreen
from concentration_screen import ConcentrationScreen
from light_sensor import LightSensorOverflow
from mode import Mode

class ScreenManager:
    def __init__(self, colorimeter):
        self.colorimeter = colorimeter
        self.measure_screen = MeasureScreen()
        self.message_screen = None
        self.menu_screen = None
        self.settings_screen = None
        self.concentration_screen = None

    def set_error_message(self, message):
        self.colorimeter.mode = Mode.MESSAGE
        self.clear_measure_screen()
        self.clear_menu_screen()
        self.clear_settings_screen()
        self.clear_concentration_screen()
        if self.message_screen is None:
            self.message_screen = MessageScreen()
        self.message_screen.set_message(f"Error: {message}")
        self.message_screen.set_to_error()

    def set_abort_message(self, message):
        self.colorimeter.mode = Mode.MESSAGE
        if self.message_screen is None:
            self.clear_measure_screen()
            self.clear_menu_screen()
            self.clear_settings_screen()
            self.message_screen = MessageScreen()
        self.message_screen.set_message(message, ok_to_continue=False)
        self.message_screen.set_to_abort()

    def show_message(self, message, is_error=False):
        self.colorimeter.mode = Mode.MESSAGE
        self.clear_measure_screen()
        self.clear_menu_screen()
        self.clear_settings_screen()
        self.clear_concentration_screen()
        if self.message_screen is None:
            try:
                self.message_screen = MessageScreen()
            except MemoryError:
                self.set_error_message("Memory allocation failed for Message Screen")
                return
        self.message_screen.set_message(message)
        if is_error:
            self.message_screen.set_to_error()
        else:
            self.message_screen.set_to_about()

    def show_about_message(self, message):
        if self.message_screen is None:
            try:
                self.message_screen = MessageScreen()
            except MemoryError:
                self.set_error_message("Memory allocation failed for Message Screen")
                return
        self.message_screen.set_message(message)
        self.message_screen.set_to_about()

    def init_measure_screen(self):
        if self.measure_screen is None:
            try:
                self.clear_menu_screen()
                self.clear_settings_screen()
                self.clear_message_screen()
                self.clear_concentration_screen()
                self.measure_screen = MeasureScreen()

            except MemoryError:
                self.set_error_message("Memory allocation failed for MeasureScreen")

    def init_menu_screen(self):
        if self.menu_screen is None:
            try:
                self.menu_screen = MenuScreen()
            except MemoryError:
                self.set_error_message("Memory allocation failed for MenuScreen")

    def init_settings_screen(self):
        try:
            self.settings_screen = SettingsScreen()
            self.settings_screen.set_values(
                self.colorimeter.timeout_value,
                self.colorimeter.timeout_unit,
                self.colorimeter.transmission_interval_value,
                self.colorimeter.transmission_interval_unit
            )
        except MemoryError:
            self.set_error_message("Memory allocation failed for SettingsScreen")

    def init_concentration_screen(self):
        try:
            self.concentration_screen = ConcentrationScreen(self.colorimeter.concentration)
        except MemoryError:
            self.set_error_message("Memory allocation failed for Concentration Screen")

    def clear_measure_screen(self):
        if self.measure_screen:
            self.measure_screen.group = displayio.Group()
        
        gc.collect()

    def clear_menu_screen(self):
        if self.menu_screen:
            self.menu_screen.group = displayio.Group()
            self.menu_screen = None
        self.measure_screen = None
        gc.collect()

    def clear_settings_screen(self):
        if self.settings_screen:
            self.settings_screen.group = displayio.Group()
            self.settings_screen = None
        gc.collect()

    def clear_concentration_screen(self):
        if self.concentration_screen:
            self.concentration_screen.group = displayio.Group()
            self.concentration_screen = None
        gc.collect()

    def clear_message_screen(self):
        if self.message_screen:
            self.message_screen.clear()
            self.message_screen = None
        gc.collect()

    def set_blanking(self):
        self.measure_screen.set_blanking()

    def set_blanked(self):
        self.measure_screen.set_blanked()

    def set_not_blanked(self):
        self.measure_screen.set_not_blanked()

    def update_battery(self, voltage):
        if self.measure_screen:
            self.measure_screen.set_bat(voltage)

    def update_menu_screen(self):
        if not self.menu_screen:
            return
        n0 = self.colorimeter.menu_view_pos
        n1 = n0 + self.menu_screen.items_per_screen
        view_items = []
        for i, item in enumerate(self.colorimeter.menu_items[n0:n1]):
            led = self.colorimeter.calibrations.led(item)
            item_text = f"{n0+i} {item}" if led is None else f"{n0+i} {item} ({led})"
            view_items.append(item_text)
        try:
            self.menu_screen.set_menu_items(view_items)
        except MemoryError:
            self.set_error_message("Memory allocation failed for menu items")
            self.menu_screen.set_menu_items(view_items[:self.menu_screen.items_per_screen // 2])
        pos = self.colorimeter.menu_item_pos - self.colorimeter.menu_view_pos
        self.menu_screen.set_curr_item(pos)

    def get_settings_values(self):
        return self.settings_screen.get_values()

    def increment_setting_value(self):
        self.settings_screen.increment_value()

    def decrement_setting_value(self):
        self.settings_screen.decrement_value()

    def move_setting_down(self):
        self.settings_screen.move_down()

    def cycle_setting_unit(self):
        self.settings_screen.cycle_unit()

    def revert_settings_to_saved(self):
        self.settings_screen.revert_to_saved()

    def set_timeout_none(self):
        self.settings_screen.set_timeout_none()

    def get_concentration_value(self):
        return self.concentration_screen.concen_val

    def set_concentration_to_zero(self):
        self.concentration_screen.set_to_zero()

    def adjust_concentration(self, value):
        self.concentration_screen.add(value)

    def update_screens(self):
        if self.colorimeter.mode == Mode.MEASURE:
            if self.measure_screen is None:
                self.measure_screen = MeasureScreen()
            try:
                numeric_value, type_tag = self.colorimeter.measurement_value
                self.measure_screen.set_measurement(
                    self.colorimeter.measurement_name,
                    self.colorimeter.measurement_units,
                    numeric_value,
                    self.colorimeter.configuration.precision if isinstance(numeric_value, (int, float)) else None,
                    type_tag=type_tag,
                    talking=self.colorimeter.is_talking
                )
            except MemoryError:
                self.set_error_message("Memory allocation failed for Measure Screen")
            except LightSensorOverflow:
                self.measure_screen.set_measurement(self.colorimeter.measurement_name, None, "overflow", None)
            if self.colorimeter.is_raw_sensor:
                try:
                    self.measure_screen.set_blanked()
                    self.measure_screen.set_gain(self.colorimeter.light_sensor.gain)
                    self.measure_screen.set_integration_time(self.colorimeter.light_sensor.integration_time)
                except MemoryError:
                    self.set_error_message("Memory allocation failed for Measure Screen")
            else:
                try:
                    if self.colorimeter.is_blanked:
                        self.measure_screen.set_blanked()
                    else:
                        self.measure_screen.set_not_blanked()
                    self.measure_screen.clear_gain()
                    self.measure_screen.clear_integration_time()
                except MemoryError:
                    self.set_error_message("Memory allocation failed for Measure Screen")
            self.measure_screen.show()
        elif self.colorimeter.mode == Mode.MENU:
            if self.menu_screen is None:
                self.init_menu_screen()
            self.update_menu_screen()
            self.menu_screen.show()
        elif self.colorimeter.mode == Mode.SETTINGS:
            if self.settings_screen is None:
                self.init_settings_screen()
            self.settings_screen.show()
        elif self.colorimeter.mode == Mode.CONCENTRATION:
            if self.concentration_screen is None:
                self.init_concentration_screen()
            self.concentration_screen.show()
        elif self.colorimeter.mode in (Mode.MESSAGE, Mode.ABORT):
            self.message_screen.show()