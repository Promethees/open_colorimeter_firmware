import gc
import time
import constants
from menu_screen import MenuScreen
from message_screen import MessageScreen
from settings_screen import SettingsScreen
from concentration_screen import ConcentrationScreen
from mode import Mode

class ButtonHandler:
    __slots__ = ['colorimeter']

    def __init__(self, colorimeter):
        self.colorimeter = colorimeter

    def check_debounce(self):
        return time.monotonic() - self.colorimeter.last_button_press >= constants.DEBOUNCE_DT

    def blank_button_pressed(self, buttons):
        return 'blank' in buttons and not self.colorimeter.is_raw_sensor

    def menu_button_pressed(self, buttons):
        return 'menu' in buttons and not self.colorimeter.is_talking

    def up_button_pressed(self, buttons):
        return 'up' in buttons

    def down_button_pressed(self, buttons):
        return 'down' in buttons

    def left_button_pressed(self, buttons):
        return 'left' in buttons

    def right_button_pressed(self, buttons):
        return 'right' in buttons

    def gain_button_pressed(self, buttons):
        return 'gain' in buttons

    def itime_button_pressed(self, buttons):
        return 'itime' in buttons

    def incr_menu_item_pos(self):
        self.colorimeter.menu_item_pos = (self.colorimeter.menu_item_pos + 1) % self.colorimeter.num_menu_items
        if self.colorimeter.menu_item_pos < self.colorimeter.menu_view_pos:
            self.colorimeter.menu_view_pos = self.colorimeter.menu_item_pos
        elif self.colorimeter.menu_item_pos >= self.colorimeter.menu_view_pos + self.colorimeter.screen_manager.menu_screen.items_per_screen:
            self.colorimeter.menu_view_pos = self.colorimeter.menu_item_pos - self.colorimeter.screen_manager.menu_screen.items_per_screen + 1

    def decr_menu_item_pos(self):
        self.colorimeter.menu_item_pos = (self.colorimeter.menu_item_pos - 1) % self.colorimeter.num_menu_items
        if self.colorimeter.menu_item_pos < self.colorimeter.menu_view_pos:
            self.colorimeter.menu_view_pos = self.colorimeter.menu_item_pos
        elif self.colorimeter.menu_item_pos >= self.colorimeter.menu_view_pos + self.colorimeter.screen_manager.menu_screen.items_per_screen:
            self.colorimeter.menu_view_pos = self.colorimeter.menu_item_pos - self.colorimeter.screen_manager.menu_screen.items_per_screen + 1

    def handle_button_press(self):
        pressed_buttons = set()
        while event := self.colorimeter.pad.events.get():
            if event.pressed:
                button_name = self.colorimeter.button_map.get(event.key_number)
                if button_name:
                    if self.colorimeter.mode == Mode.MEASURE and button_name in ('right', 'down', 'up'):
                        continue
                    if self.colorimeter.mode == Mode.MENU and button_name in ('blank', 'gain', 'itime'):
                        continue
                    pressed_buttons.add(button_name)

        if not pressed_buttons or not self.check_debounce():
            return

        self.colorimeter.last_button_press = time.monotonic()

        mode_handlers = {
            Mode.MEASURE: self._handle_measure_mode,
            Mode.MENU: self._handle_menu_mode,
            Mode.SETTINGS: self._handle_settings_mode,
            Mode.CONCENTRATION: self._handle_concentration_mode,
            Mode.MESSAGE: self._handle_message_mode,
            Mode.ABORT: self._handle_message_mode
        }
        handler = mode_handlers.get(self.colorimeter.mode)
        if handler:
            try:
                handler(pressed_buttons)
            except MemoryError:
                self.colorimeter.screen_manager.show_error_message("Memory allocation failed during button handling")
        gc.collect()

    def _handle_measure_mode(self, buttons):
        if self.blank_button_pressed(buttons):
            if not self.colorimeter.is_blanked:
                self.colorimeter.screen_manager.set_blanking()
                self.colorimeter.blank_sensor()
                if self.colorimeter.mode == Mode.MESSAGE:
                    return
                self.colorimeter.screen_manager.set_blanked()
            else:
                self.colorimeter.blank_sensor(False)
                self.colorimeter.is_blanked = False
                self.colorimeter.screen_manager.set_not_blanked()
        elif self.left_button_pressed(buttons):
            if (self.colorimeter.serial_count > 0):
                self.colorimeter.serial_count = 0
            if (not self.colorimeter.is_talking):
                self.colorimeter.last_transmission_time = 0
            self.colorimeter.serial_manager.serial_talking(not self.colorimeter.is_talking)
        elif self.menu_button_pressed(buttons):
            self.colorimeter.mode = Mode.MENU
            self.colorimeter.screen_manager.transition_to_menu()
        elif self.gain_button_pressed(buttons):
            self.colorimeter.light_sensor.gain = next(self.colorimeter.gain_cycle)
            self.colorimeter.is_blanked = False
            self.colorimeter.screen_manager.set_not_blanked()
        elif self.itime_button_pressed(buttons):
            self.colorimeter.light_sensor.integration_time = next(self.colorimeter.itime_cycle)
            self.colorimeter.is_blanked = False
            self.colorimeter.screen_manager.set_not_blanked()

    def _handle_menu_mode(self, buttons):
        if self.menu_button_pressed(buttons) or self.right_button_pressed(buttons) or self.left_button_pressed(buttons):
            selected_item = self.colorimeter.menu_items[self.colorimeter.menu_item_pos]
            if selected_item == self.colorimeter.ABOUT_STR:
                self.colorimeter.screen_manager.show_about_message(f"firmware version {constants.__version__}")
                self.colorimeter.mode = Mode.MESSAGE
            elif selected_item == self.colorimeter.SETTINGS_STR:
                self.colorimeter.to_use_gain_asB = True
                self.colorimeter.mode = Mode.SETTINGS
                self.colorimeter.screen_manager.transition_to_settings()
            elif selected_item == self.colorimeter.CONCENTRATION_STR:
                self.colorimeter.to_use_gain_asB = True
                self.colorimeter.mode = Mode.CONCENTRATION
                self.colorimeter.screen_manager.transition_to_concentration()
            else:
                self.colorimeter.measurement_name = selected_item
                self.colorimeter.to_use_gain_asB = False
                self.colorimeter.mode = Mode.MEASURE
                self.colorimeter.screen_manager.transition_to_measure()
        elif self.up_button_pressed(buttons):
            self.decr_menu_item_pos()
        elif self.down_button_pressed(buttons):
            self.incr_menu_item_pos()

    def _handle_settings_mode(self, buttons):
        if self.menu_button_pressed(buttons):
            values = self.colorimeter.screen_manager.get_settings_values()
            if not values:
                self.colorimeter.screen_manager.show_error_message("Failed to retrieve settings values")
                return
            self.colorimeter.timeout_value = values["timeout_value"]
            self.colorimeter.timeout_unit = values["timeout_unit"]
            self.colorimeter.transmission_interval_value = values["interval_value"]
            self.colorimeter.transmission_interval_unit = values["interval_unit"]
            if (self.colorimeter.timeout_value and
                self.colorimeter._convert_to_seconds(self.colorimeter.timeout_value, self.colorimeter.timeout_unit) <=
                self.colorimeter._convert_to_seconds(self.colorimeter.transmission_interval_value, self.colorimeter.transmission_interval_unit)):
                self.colorimeter.timeout_value = values.get("prev_timeout_value", constants.DEFAULT_TIMEOUT_VALUE)
                self.colorimeter.timeout_unit = values.get("prev_timeout_unit", constants.DEFAULT_TIMEOUT_UNIT)
                self.colorimeter.transmission_interval_value = values.get("prev_interval_value", constants.DEFAULT_TRANSMISSION_INTERVAL_VALUE)
                self.colorimeter.transmission_interval_unit = values.get("prev_interval_unit", constants.DEFAULT_TRANSMISSION_INTERVAL_UNIT)
                self.colorimeter.screen_manager.show_error_message("Invalid timing values! Timeout is smaller than interval time.")
                return
            self.colorimeter.to_use_gain_asB = False
            self.colorimeter.screen_manager.show_message("Settings saved.", is_error=False)
            
        elif self.left_button_pressed(buttons):
            self.colorimeter.to_use_gain_asB = False
            self.colorimeter.mode = Mode.MENU
            self.colorimeter.screen_manager.transition_to_menu()
        elif self.up_button_pressed(buttons):
            self.colorimeter.screen_manager.increment_setting_value()
        elif self.down_button_pressed(buttons):
            self.colorimeter.screen_manager.decrement_setting_value()
        elif self.right_button_pressed(buttons):
            self.colorimeter.screen_manager.move_setting_down()
        elif self.itime_button_pressed(buttons):
            self.colorimeter.screen_manager.cycle_setting_unit()
        elif self.blank_button_pressed(buttons):
            self.colorimeter.screen_manager.revert_settings_to_saved()
        elif self.gain_button_pressed(buttons):
            self.colorimeter.screen_manager.set_timeout_none()

    def _handle_concentration_mode(self, buttons):
        if self.menu_button_pressed(buttons):
            self.colorimeter.concentration = self.colorimeter.screen_manager.get_concentration_value()
            self.colorimeter.to_use_gain_asB = False
            if self.colorimeter.concentration is not None:
                self.colorimeter.screen_manager.show_message(f"Concentration saved: {self.colorimeter.concentration} ng/µL", is_error=False)
            else:
                self.colorimeter.screen_manager.show_message(f"Concentration saved: None ng/µL", is_error=False)
        elif self.blank_button_pressed(buttons):
            self.colorimeter.screen_manager.set_concentration_to_none()
        elif self.up_button_pressed(buttons):
            self.colorimeter.screen_manager.adjust_concentration(1)
        elif self.down_button_pressed(buttons):
            self.colorimeter.screen_manager.adjust_concentration(-1)
        elif self.left_button_pressed(buttons):
            self.colorimeter.screen_manager.adjust_concentration(-10)
        elif self.right_button_pressed(buttons):
            self.colorimeter.screen_manager.adjust_concentration(10)
        elif self.itime_button_pressed(buttons):
            self.colorimeter.screen_manager.adjust_concentration(100)
        elif self.gain_button_pressed(buttons):
            self.colorimeter.screen_manager.adjust_concentration(-100)

    def _handle_message_mode(self, buttons):
        if buttons:
            self.colorimeter.mode = Mode.MENU
            self.colorimeter.screen_manager.transition_to_menu()
        elif not self.colorimeter.calibrations_checked and self.colorimeter.calibrations.has_errors:
            self.colorimeter.screen_manager.show_error_message(self.colorimeter.calibrations.pop_error())
            self.colorimeter.calibrations_checked = True