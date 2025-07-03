import gc
import time
import constants
from menu_screen import MenuScreen
from message_screen import MessageScreen
from settings_screen import SettingsScreen
from concentration_screen import ConcentrationScreen
from mode import Mode

class ButtonHandler:
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
        if not self.colorimeter.to_use_gain_asB:
            return 'gain' in buttons and self.colorimeter.is_raw_sensor
        else:
            return 'gain' in buttons

    def itime_button_pressed(self, buttons):
        return 'itime' in buttons

    def incr_menu_item_pos(self):
        self.colorimeter.menu_item_pos = (self.colorimeter.menu_item_pos + 1) % self.colorimeter.num_menu_items
        items_per_screen = self.colorimeter.screen_manager.menu_screen.items_per_screen
        if self.colorimeter.menu_item_pos < self.colorimeter.menu_view_pos:
            self.colorimeter.menu_view_pos = self.colorimeter.menu_item_pos
        elif self.colorimeter.menu_item_pos >= self.colorimeter.menu_view_pos + items_per_screen:
            self.colorimeter.menu_view_pos = self.colorimeter.menu_item_pos - items_per_screen + 1

    def decr_menu_item_pos(self):
        self.colorimeter.menu_item_pos = (self.colorimeter.menu_item_pos - 1) % self.colorimeter.num_menu_items
        items_per_screen = self.colorimeter.screen_manager.menu_screen.items_per_screen
        if self.colorimeter.menu_item_pos < self.colorimeter.menu_view_pos:
            self.colorimeter.menu_view_pos = self.colorimeter.menu_item_pos
        elif self.colorimeter.menu_item_pos >= self.colorimeter.menu_view_pos + items_per_screen:
            self.colorimeter.menu_view_pos = self.colorimeter.menu_item_pos - items_per_screen + 1

    def handle_button_press(self):
        pressed_buttons = set()
        while event := self.colorimeter.pad.events.get():
            if event.pressed:
                button_name = self.colorimeter.button_map.get(event.key_number)
                if button_name:
                    pressed_buttons.add(button_name)

        if not pressed_buttons or not self.check_debounce():
            return

        self.colorimeter.last_button_press = time.monotonic()

        if self.colorimeter.mode == Mode.MEASURE:
            self._handle_measure_mode(pressed_buttons)
        elif self.colorimeter.mode == Mode.MENU:
            self._handle_menu_mode(pressed_buttons)
        elif self.colorimeter.mode == Mode.SETTINGS:
            self._handle_settings_mode(pressed_buttons)
        elif self.colorimeter.mode == Mode.CONCENTRATION:
            self._handle_concentration_mode(pressed_buttons)
        elif self.colorimeter.mode in (Mode.MESSAGE, Mode.ABORT):
            self._handle_message_mode(pressed_buttons)

    def _handle_measure_mode(self, buttons):
        if self.blank_button_pressed(buttons):
            if not self.colorimeter.is_blanked:
                self.colorimeter.screen_manager.set_blanking()
                self.colorimeter.blank_sensor()
                if self.colorimeter.mode == Mode.MESSAGE:
                    return
                self.colorimeter.screen_manager.set_blanked()
            else:
                self.colorimeter.is_blanked = False
                self.colorimeter.screen_manager.set_not_blanked()
        elif self.left_button_pressed(buttons):
            self.colorimeter.serial_manager.serial_talking(not self.colorimeter.is_talking)
        elif self.menu_button_pressed(buttons):
            self.colorimeter.screen_manager.clear_measure_screen()
            self.colorimeter.menu_view_pos = 0
            self.colorimeter.menu_item_pos = 0
            gc.collect()
            self.colorimeter.screen_manager.init_menu_screen()
            self.colorimeter.mode = Mode.MENU
        elif self.gain_button_pressed(buttons):
            self.colorimeter.light_sensor.gain = next(self.colorimeter.gain_cycle)
            self.colorimeter.is_blanked = False
        elif self.itime_button_pressed(buttons):
            self.colorimeter.light_sensor.integration_time = next(self.colorimeter.itime_cycle)
            self.colorimeter.is_blanked = False

    def _handle_menu_mode(self, buttons):
        if self.menu_button_pressed(buttons) or self.right_button_pressed(buttons) or self.left_button_pressed(buttons):
            selected_item = self.colorimeter.menu_items[self.colorimeter.menu_item_pos]
            if selected_item == self.colorimeter.ABOUT_STR:
                self.colorimeter.screen_manager.show_about_message(f"firmware version {constants.__version__}")
                self.colorimeter.mode = Mode.MESSAGE
            elif selected_item == self.colorimeter.SETTINGS_STR:
                self.colorimeter.screen_manager.clear_menu_screen()
                self.colorimeter.to_use_gain_asB = True
                gc.collect()
                self.colorimeter.screen_manager.init_settings_screen()
                self.colorimeter.mode = Mode.SETTINGS
            elif selected_item == self.colorimeter.CONCENTRATION_STR:
                self.colorimeter.screen_manager.clear_menu_screen()
                self.colorimeter.to_use_gain_asB = True
                gc.collect()
                self.colorimeter.screen_manager.init_concentration_screen()
                self.colorimeter.mode = Mode.CONCENTRATION
            else:
                self.colorimeter.screen_manager.clear_menu_screen()
                gc.collect()
                self.colorimeter.measurement_name = self.colorimeter.menu_items[self.colorimeter.menu_item_pos]
                self.colorimeter.screen_manager.init_measure_screen()
                self.colorimeter.mode = Mode.MEASURE
        elif self.up_button_pressed(buttons):
            self.decr_menu_item_pos()
        elif self.down_button_pressed(buttons):
            self.incr_menu_item_pos()

    def _handle_settings_mode(self, buttons):
        if self.menu_button_pressed(buttons):
            values = self.colorimeter.screen_manager.get_settings_values()
            self.colorimeter.timeout_value = values["timeout_value"]
            self.colorimeter.timeout_unit = values["timeout_unit"]
            self.colorimeter.transmission_interval_value = values["interval_value"]
            self.colorimeter.transmission_interval_unit = values["interval_unit"]
            if self.colorimeter.timeout_value and self.colorimeter._convert_to_seconds(self.colorimeter.timeout_value, self.colorimeter.timeout_unit) <= self.colorimeter._convert_to_seconds(self.colorimeter.transmission_interval_value, self.colorimeter.transmission_interval_unit):
                self.colorimeter.timeout_value = values["prev_timeout_value"]
                self.colorimeter.timeout_unit = values["prev_timeout_unit"]
                self.colorimeter.transmission_interval_value = values["prev_interval_value"]
                self.colorimeter.transmission_interval_unit = values["prev_interval_unit"]
                self.colorimeter.screen_manager.clear_settings_screen()
                self.colorimeter.screen_manager.set_error_message("Invalid timing values! Timeout is smaller than interval time. Discard!")
                self.colorimeter.to_use_gain_asB = False
                return
            try:
                self.colorimeter.screen_manager.clear_settings_screen()
                self.colorimeter.screen_manager.show_message("Settings saved.", is_error=False)
                self.colorimeter.to_use_gain_asB = False
            except Exception as e:
                print(f"tell me the Exception {e}")
            except MemoryError:
                self.colorimeter.screen_manager.set_error_message("Memory allocation failed for message Screen")
                self.colorimeter.to_use_gain_asB = False


        elif self.left_button_pressed(buttons):
            self.colorimeter.mode = Mode.MENU
            self.colorimeter.screen_manager.clear_settings_screen()            
            self.colorimeter.to_use_gain_asB = False
            gc.collect()
            self.colorimeter.screen_manager.init_menu_screen()
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
            self.colorimeter.screen_manager.clear_concentration_screen()
            try:
                msg = f"Concen val is {self.colorimeter.concentration} nM/l"
                self.colorimeter.screen_manager.show_message(msg, is_error=False)
                self.colorimeter.to_use_gain_asB = False
            except MemoryError:
                self.colorimeter.screen_manager.set_error_message("Memory allocation failed for message Screen")
                self.colorimeter.to_use_gain_asB = False                
        elif self.blank_button_pressed(buttons):
            self.colorimeter.screen_manager.set_concentration_to_zero()
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
            self.colorimeter.screen_manager.clear_message_screen()
            self.colorimeter.mode = Mode.MENU
            self.colorimeter.screen_manager.init_menu_screen()
        elif not self.colorimeter.calibrations_checked and self.colorimeter.calibrations.has_errors:
            self.colorimeter.screen_manager.set_error_message(self.colorimeter.calibrations.pop_error())
            self.colorimeter.mode = Mode.MESSAGE
            self.colorimeter.calibrations_checked = True
        else:
            return