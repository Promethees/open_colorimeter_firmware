import gc
import time
import constants
from menu_screen import MenuScreen
from message_screen import MessageScreen
from measure_screen import MeasureScreen
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
        return 'menu' in buttons

    def up_button_pressed(self, buttons):
        return 'up' in buttons

    def down_button_pressed(self, buttons):
        return 'down' in buttons

    def right_button_pressed(self, buttons):
        return 'right' in buttons

    def channel_button_pressed(self, buttons):
        return 'left' in buttons

    def gain_button_pressed(self, buttons):
        return 'gain' in buttons and self.colorimeter.is_raw_sensor

    def itime_button_pressed(self, buttons):
        return 'itime' in buttons and self.colorimeter.is_raw_sensor

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
            if not event.pressed:
                for button_name, key_number in constants.BUTTON.items():
                    if event.key_number == key_number:
                        pressed_buttons.add(button_name)
                        break

        if not pressed_buttons or not self.check_debounce():
            return

        self.colorimeter.last_button_press = time.monotonic()

        mode_handlers = {
            Mode.MEASURE: self._handle_measure_mode,
            Mode.MENU: self._handle_menu_mode,
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
                self.colorimeter.is_blanked = False
                self.colorimeter.screen_manager.set_not_blanked()
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
        elif self.channel_button_pressed(buttons):
            self.colorimeter.channel = next(self.colorimeter.channel_cycle)

    def _handle_menu_mode(self, buttons):
        if self.menu_button_pressed(buttons) or self.right_button_pressed(buttons):
            selected_item = self.colorimeter.menu_items[self.colorimeter.menu_item_pos]
            if selected_item == constants.ABOUT_STR:
                self.colorimeter.screen_manager.show_about_message(f"firmware version {constants.__version__}")
                self.colorimeter.mode = Mode.MESSAGE
            else:
                self.colorimeter.measurement_name = selected_item
                self.colorimeter.mode = Mode.MEASURE
                self.colorimeter.screen_manager.transition_to_measure()
        elif self.up_button_pressed(buttons):
            self.decr_menu_item_pos()
        elif self.down_button_pressed(buttons):
            self.incr_menu_item_pos()

    def _handle_message_mode(self, buttons):
        if buttons and not self.colorimeter.calibrations.has_errors:
            self.colorimeter.mode = Mode.MENU
            self.colorimeter.screen_manager.transition_to_menu()
        elif self.colorimeter.calibrations.has_errors:
            self.colorimeter.screen_manager.show_error_message(self.colorimeter.calibrations.pop_error())