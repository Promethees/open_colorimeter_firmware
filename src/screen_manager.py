import gc
import displayio
import time
import microcontroller
import board
from menu_screen import MenuScreen
from message_screen import MessageScreen
from measure_screen import MeasureScreen
from mode import Mode
from light_sensor import LightSensorOverflow
import constants

class ScreenManager:
    __slots__ = [
        'colorimeter',
        'menu_screen',
        'message_screen',
        'measure_screen',
        'active_screen',
        '_error_handling'
    ]

    def __init__(self, colorimeter):
        self.colorimeter = colorimeter
        self.menu_screen = None
        self.message_screen = None
        self.measure_screen = None
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
        self.message_screen = self._try_allocate(MessageScreen, "Memory allocation failed for Message Screen")
        if self.message_screen:
            self.message_screen.set_message(f"Error: {message}")
            self.message_screen.set_to_error()
            self.active_screen = self.message_screen
        else:
            board.DISPLAY.root_group = None
            microcontroller.reset()

    def clear_all_screens(self):
        for screen in (self.measure_screen, self.menu_screen, self.message_screen):
            if screen and hasattr(screen, 'clear'):
                screen.clear()
        self.measure_screen = None
        self.menu_screen = None
        self.message_screen = None
        gc.collect()

    def transition_to_measure(self):
        if self.colorimeter.mode != Mode.MEASURE:
            return
        self.clear_all_screens()
        self.measure_screen = self._try_allocate(MeasureScreen, "Memory allocation failed for MeasureScreen")
        if self.measure_screen and self.colorimeter.is_blanked:
            self.measure_screen.set_blanked()
        self.active_screen = self.measure_screen

    def transition_to_menu(self):
        if self.colorimeter.mode != Mode.MENU:
            return
        self.clear_all_screens()
        self.menu_screen = self._try_allocate(MenuScreen, "Memory allocation failed for MenuScreen")
        if self.menu_screen:
            self.colorimeter.menu_view_pos = 0
            self.colorimeter.menu_item_pos = self.colorimeter.menu_items.index(self.colorimeter.measurement_name)
            self.update_menu_screen()
        self.active_screen = self.menu_screen

    def show_error_message(self, message):
        if self._error_handling:
            return
        self._error_handling = True
        self.colorimeter.mode = Mode.MESSAGE
        self.clear_all_screens()
        self.message_screen = self._try_allocate(MessageScreen, "Memory allocation failed for Message Screen")
        if self.message_screen:
            self.message_screen.set_message(message)
            self.message_screen.set_to_error()
            self.active_screen = self.message_screen
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

    def show_about_message(self, message):
        if self._error_handling:
            return
        self._error_handling = True
        self.colorimeter.mode = Mode.MESSAGE
        self.clear_all_screens()
        self.message_screen = self._try_allocate(MessageScreen, "Memory allocation failed for Message Screen")
        if self.message_screen:
            self.message_screen.set_message(message)
            self.message_screen.set_to_about()
            self.active_screen = self.message_screen
        self._error_handling = False

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
            self.measure_screen.set_battery(voltage)

    def update_menu_screen(self):
        if not self.menu_screen:
            return
        n0 = self.colorimeter.menu_view_pos
        n1 = n0 + self.menu_screen.items_per_screen
        view_items = []
        for i, item in enumerate(self.colorimeter.menu_items[n0:n1]):
            led = self.colorimeter.calibrations.led(item)
            chan = self.colorimeter.calibrations.channel(item)
            if led is None and chan is None:
                item_text = f"{n0+i} {item}"
            elif chan is None:
                item_text = f"{n0+i} {item} ({led})"
            elif led is None:
                chan_str = constants.CHANNEL_TO_STR[chan]
                item_text = f"{n0+i} {item} ({chan_str})"
            else:
                chan_str = constants.CHANNEL_TO_STR[chan]
                item = item[:8]
                item_text = f"{n0+i} {item} ({led},{chan_str})"
            view_items.append(item_text)
        try:
            self.menu_screen.set_menu_items(view_items)
        except MemoryError:
            view_items = view_items[:self.menu_screen.items_per_screen // 2]
            self.menu_screen.set_menu_items(view_items)
        pos = self.colorimeter.menu_item_pos - self.colorimeter.menu_view_pos
        self.menu_screen.set_curr_item(pos)

    def update_screens(self):
        if self.active_screen and self.colorimeter.mode in (Mode.MEASURE, Mode.MENU, Mode.MESSAGE, Mode.ABORT):
            if self.colorimeter.mode == Mode.MEASURE and self.active_screen == self.measure_screen:
                try:
                    self.measure_screen.set_measurement(
                        self.colorimeter.measurement_name,
                        self.colorimeter.measurement_units,
                        self.colorimeter.measurement_value,
                        self.colorimeter.configuration.precision,
                        constants.CHANNEL_TO_STR[self.colorimeter.channel]
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
                    self.measure_screen.set_channel(self.colorimeter.channel)
                    self.active_screen.show()
                except MemoryError:
                    self.show_error_message("Memory allocation failed for Measure Screen")
                except LightSensorOverflow:
                    self.measure_screen.set_overflow(self.colorimeter.measurement_name)
                    self.active_screen.show()
            elif self.colorimeter.mode == Mode.MENU and self.active_screen == self.menu_screen:
                self.update_menu_screen()
                self.active_screen.show()
            elif self.colorimeter.mode in (Mode.MESSAGE, Mode.ABORT) and self.active_screen == self.message_screen:
                self.active_screen.show()
        else:
            mode_to_transition = {
                Mode.MEASURE: self.transition_to_measure,
                Mode.MENU: self.transition_to_menu,
                Mode.MESSAGE: lambda: self.show_error_message("Mode restored"),
                Mode.ABORT: lambda: self.show_abort_message("Mode restored")
            }
            transition = mode_to_transition.get(self.colorimeter.mode)
            if transition:
                transition()
        gc.collect()