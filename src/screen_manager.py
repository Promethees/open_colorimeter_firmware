import gc
import displayio
from menu_screen import MenuScreen
from message_screen import MessageScreen
from measure_screen import MeasureScreen
from settings_screen import SettingsScreen
from concentration_screen import ConcentrationScreen
from light_sensor import LightSensorOverflow
from mode import Mode
import time
import microcontroller
import board

class ScreenManager:
    __slots__ = [
        'colorimeter',
        'menu_screen',
        'message_screen',
        'measure_screen',
        'settings_screen',
        'concentration_screen',
        'active_screen',
        '_error_handling'
    ]

    def __init__(self, colorimeter):
        self.colorimeter = colorimeter
        self.menu_screen = None
        self.message_screen = None
        self.measure_screen = None
        self.settings_screen = None
        self.concentration_screen = None
        self.active_screen = None
        self._error_handling = False
        gc.collect()

    def _try_allocate(self, screen_class, error_message, max_retries=2, *args, **kwargs):
        retry_count = 0
        while retry_count < max_retries:
            gc.collect()
            try:
                return screen_class(*args, **kwargs)
            except MemoryError:
                self.clear_all_screens()
                time.sleep(0.1)
                retry_count += 1
        if not self._error_handling:
            self._error_handling = True
            self._show_fallback_error(error_message)
            self._error_handling = False
        return None

    def _show_fallback_error(self, message):
        self.colorimeter.mode = Mode.MESSAGE
        self.clear_all_screens()
        if self.message_screen is None:
            try:
                self.message_screen = MessageScreen()
            except MemoryError:
                board.DISPLAY.root_group = None
                microcontroller.reset()
                return
        self.message_screen.set_message(f"Error: {message}")
        self.message_screen.set_to_error()
        self.active_screen = self.message_screen

    def clear_all_screens(self):
        for screen in (self.measure_screen, self.menu_screen, self.settings_screen, self.concentration_screen, self.message_screen):
            if screen and hasattr(screen, 'clear'):
                screen.clear()
            elif screen and hasattr(screen, 'group'):
                while len(screen.group) > 0:
                    screen.group.pop()
                if board.DISPLAY.root_group == screen.group:
                    board.DISPLAY.root_group = None
        self.measure_screen = None
        self.menu_screen = None
        self.settings_screen = None
        self.concentration_screen = None
        self.message_screen = None
        gc.collect()

    def transition_to_measure(self, raw_sensor=False):
        if self.colorimeter.mode != Mode.MEASURE:
            return
        if not self.measure_screen:
            self.clear_all_screens()
            self.measure_screen = self._try_allocate(MeasureScreen, "Memory allocation failed for MeasureScreen", raw_sensor=raw_sensor)
            if self.measure_screen and self.colorimeter.is_blanked:
                self.measure_screen.set_blanked()
        self.active_screen = self.measure_screen

    def transition_to_menu(self):
        if self.colorimeter.mode != Mode.MENU:
            return
        if not self.menu_screen:
            self.clear_all_screens()
            self.menu_screen = self._try_allocate(MenuScreen, "Memory allocation failed for MenuScreen")
        self.active_screen = self.menu_screen

    def transition_to_settings(self):
        if self.colorimeter.mode != Mode.SETTINGS:
            return
        if not self.settings_screen:
            self.clear_all_screens()
            self.settings_screen = self._try_allocate(SettingsScreen, "Memory allocation failed for SettingsScreen")
            if self.settings_screen:
                self.settings_screen.set_values(
                    self.colorimeter.timeout_value,
                    self.colorimeter.timeout_unit,
                    self.colorimeter.transmission_interval_value,
                    self.colorimeter.transmission_interval_unit
                )
        self.active_screen = self.settings_screen

    def transition_to_concentration(self):
        if self.colorimeter.mode != Mode.CONCENTRATION:
            return
        if not self.concentration_screen:
            self.clear_all_screens()
            self.concentration_screen = self._try_allocate(
                ConcentrationScreen,
                "Memory allocation failed for Concentration Screen",
                concen_val=self.colorimeter.concentration
            )
        self.active_screen = self.concentration_screen

    def show_error_message(self, message):
        if self._error_handling:
            return
        self._error_handling = True
        self._show_fallback_error(message)
        self._error_handling = False

    def show_abort_message(self, message):
        if self._error_handling:
            return
        self._error_handling = True
        self.colorimeter.mode = Mode.ABORT
        self.clear_all_screens()
        self.message_screen = self._try_allocate(MessageScreen, "Memory allocation failed for Message Screen")
        if self.message_screen:
            self.message_screen.set_message(message, ok_to_continue=False)
            self.message_screen.set_to_abort()
            self.active_screen = self.message_screen
        else:
            board.DISPLAY.root_group = None
            microcontroller.reset()
        self._error_handling = False

    def show_message(self, message, is_error=False):
        if self._error_handling:
            return
        self._error_handling = True
        self.colorimeter.mode = Mode.MESSAGE
        self.clear_all_screens()
        self.message_screen = self._try_allocate(MessageScreen, "Memory allocation failed for Message Screen")
        if self.message_screen:
            self.message_screen.set_message(message)
            if is_error:
                self.message_screen.set_to_error()
            else:
                self.message_screen.set_to_about()
            self.active_screen = self.message_screen
        self._error_handling = False

    def show_about_message(self, message):
        self.show_message(message, is_error=False)

    def set_blanking(self):
        if self.measure_screen:
            self.measure_screen.set_blanking()

    def set_blanked(self):
        if self.measure_screen:
            self.measure_screen.set_blanked()

    def set_not_blanked(self):
        if self.measure_screen:
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
            view_items = view_items[:self.menu_screen.items_per_screen // 2]
            self.menu_screen.set_menu_items(view_items)
        pos = self.colorimeter.menu_item_pos - self.colorimeter.menu_view_pos
        self.menu_screen.set_curr_item(pos)

    def get_settings_values(self):
        return self.settings_screen.get_values() if self.settings_screen else None

    def increment_setting_value(self):
        if self.settings_screen:
            self.settings_screen.increment_value()

    def decrement_setting_value(self):
        if self.settings_screen:
            self.settings_screen.decrement_value()

    def move_setting_down(self):
        if self.settings_screen:
            self.settings_screen.move_down()

    def cycle_setting_unit(self):
        if self.settings_screen:
            self.settings_screen.cycle_unit()

    def revert_settings_to_saved(self):
        if self.settings_screen:
            self.settings_screen.revert_to_saved()

    def set_timeout_none(self):
        if self.settings_screen:
            self.settings_screen.set_timeout_none()

    def get_concentration_value(self):
        return self.concentration_screen.concen_val if self.concentration_screen else None

    def set_concentration_to_none(self):
        if self.concentration_screen:
            self.concentration_screen.set_to_none()

    def adjust_concentration(self, value):
        if self.concentration_screen:
            self.concentration_screen.add(value)

    def update_screens(self):
        if self.active_screen and self.colorimeter.mode in (Mode.MEASURE, Mode.MENU, Mode.SETTINGS, Mode.CONCENTRATION, Mode.MESSAGE, Mode.ABORT):
            if self.colorimeter.mode == Mode.MEASURE and self.active_screen == self.measure_screen:
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
                    if self.colorimeter.is_raw_sensor:
                        self.measure_screen.set_blanked()
                        self.measure_screen.set_gain(self.colorimeter.light_sensor.gain)
                        self.measure_screen.set_integration_time(self.colorimeter.light_sensor.integration_time)
                    else:
                        if self.colorimeter.is_blanked:
                            self.measure_screen.set_blanked()
                        else:
                            self.measure_screen.set_not_blanked()
                        self.measure_screen.clear_gain()
                        self.measure_screen.clear_integration_time()
                    self.active_screen.show()
                except MemoryError:
                    self.show_error_message("Memory allocation failed for Measure Screen")
                except LightSensorOverflow:
                    self.measure_screen.set_measurement(self.colorimeter.measurement_name, None, "overflow", None)
                    self.active_screen.show()
            elif self.colorimeter.mode == Mode.MENU and self.active_screen == self.menu_screen:
                self.update_menu_screen()
                self.active_screen.show()
            elif self.colorimeter.mode == Mode.SETTINGS and self.active_screen == self.settings_screen:
                self.active_screen.show()
            elif self.colorimeter.mode == Mode.CONCENTRATION and self.active_screen == self.concentration_screen:
                self.active_screen.show()
            elif self.colorimeter.mode in (Mode.MESSAGE, Mode.ABORT) and self.active_screen == self.message_screen:
                self.active_screen.show()
        else:
            mode_to_transition = {
                Mode.MEASURE: self.transition_to_measure,
                Mode.MENU: self.transition_to_menu,
                Mode.SETTINGS: self.transition_to_settings,
                Mode.CONCENTRATION: self.transition_to_concentration,
                Mode.MESSAGE: lambda: self.show_message("Mode restored", is_error=False),
                Mode.ABORT: lambda: self.show_abort_message("Mode restored")
            }
            transition = mode_to_transition.get(self.colorimeter.mode)
            if transition:
                transition()
        gc.collect()