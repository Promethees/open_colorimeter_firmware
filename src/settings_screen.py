import displayio
import board
import constants
import fonts
from adafruit_display_text import label

class SettingsScreen:
    TOP_MARGIN = 5
    BOTTOM_MARGIN = 5
    BBOX_HEIGHT_INDEX = 3
    UNIT_CYCLE = ["sec", "min", "hour"]

    def __init__(self):
        self.group = displayio.Group()
        self.items = [
            {
                "name": "Timeout",
                "value": None,
                "unit": None,
                "min": 0.0,
                "max": 60.0,
                "step": 1.0,
                "saved_value": None,
                "saved_unit": None,
            },
            {
                "name": "Interval",
                "value": 0.0,
                "unit": "sec",
                "min": 0.0,
                "max": 60.0,
                "step": 1.0,
                "saved_value": 0.0,
                "saved_unit": "sec",
            },
        ]
        self.current_item = 0

        # Setup color palette and tile grid
        self.palette = displayio.Palette(len(constants.COLOR_TO_RGB))
        for i, (color, rgb) in enumerate(constants.COLOR_TO_RGB.items()):
            self.palette[i] = rgb

        self.bitmap = displayio.Bitmap(board.DISPLAY.width, board.DISPLAY.height, len(constants.COLOR_TO_RGB))
        self.bitmap.fill(0)  # Black
        self.tile_grid = displayio.TileGrid(self.bitmap, pixel_shader=self.palette)

        font_scale = 1
        center_x = board.DISPLAY.width // 2

        # Create title label
        self.title_label = label.Label(
            fonts.font_14pt,
            text="Settings",
            color=constants.COLOR_TO_RGB["white"],
            scale=font_scale,
            anchor_point=(0.5, 1.0),
        )
        self.title_label.anchored_position = (center_x, self.TOP_MARGIN + self.title_label.bounding_box[self.BBOX_HEIGHT_INDEX])

        # Create labels for settings
        self.setting_labels = []
        for i in range(len(self.items)):
            lbl = label.Label(
                fonts.font_10pt,
                text="",
                color=constants.COLOR_TO_RGB["white"],
                scale=font_scale,
                anchor_point=(0.5, 1.0),
            )
            self.setting_labels.append(lbl)

        # Create saved/unsaved label
        self.saved_label = label.Label(
            fonts.font_14pt,
            text="Saved",
            color=constants.COLOR_TO_RGB["green"],
            scale=font_scale,
            anchor_point=(0.5, 1.0),
        )
        self.setting_labels.append(self.saved_label)

        # Create group
        self.group.append(self.tile_grid)
        self.group.append(self.title_label)
        for lbl in self.setting_labels:
            self.group.append(lbl)

        # Initialize label text
        self._update_labels()

    def _update_constraints(self, item):
        """Update min, max, step based on unit, skip if unit is None."""
        if item["unit"] is None:
            return
        if item["name"] == "Timeout":
            if item["unit"] == "sec":
                item["min"], item["max"], item["step"] = 0, 3600, 10
            elif item["unit"] == "min":
                item["min"], item["max"], item["step"] = 0, 60, 1
            else:  # hour
                item["min"], item["max"], item["step"] = 0, 24, 1
        else:  # Interval
            if item["unit"] == "sec":
                item["min"], item["max"], item["step"] = 0, 3600, 10
            elif item["unit"] == "min":
                item["min"], item["max"], item["step"] = 0, 60, 1
            else:  # hour
                item["min"], item["max"], item["step"] = 0, 24, 1

        # Ensure value stays within new constraints if not None
        if item["value"] is not None:
            item["value"] = max(item["min"], min(item["value"], item["max"]))

    def _update_labels(self):
        """Update text and colors of setting labels."""
        for i, item in enumerate(self.items):
            # print(f"The {i} item is:")
            # print(item)
            if item["name"] == "Timeout" and (item["value"] is None or item["unit"] is None):
                text = f"{item['name']}: Infinite"
            else:
                text = f"{item['name']}: {item['value']} {item['unit']}"
            self.setting_labels[i].text = text
            self.setting_labels[i].color = constants.COLOR_TO_RGB["yellow" if i == self.current_item else "white"]

            # Update Saved/Unsaved label
            if item['value'] != item['saved_value'] or item['unit'] != item['saved_unit']:
                self.setting_labels[2].text = "Unsaved"
                self.setting_labels[2].color = constants.COLOR_TO_RGB["red"]
            else:
                if self.setting_labels[2].text == "Saved" or i == 0:
                    self.setting_labels[2].text = "Saved"
                    self.setting_labels[2].color = constants.COLOR_TO_RGB["green"]


        self._position_labels()

    def _position_labels(self):
        """Position labels dynamically based on active labels."""
        active_labels = [lbl for lbl in self.setting_labels if lbl.text]
        line_count = len(active_labels)

        title_height = self.title_label.bounding_box[self.BBOX_HEIGHT_INDEX]
        title_y = self.TOP_MARGIN + title_height
        self.title_label.anchored_position = (self.title_label.anchored_position[0], title_y)

        available_height = board.DISPLAY.height - title_y - self.BOTTOM_MARGIN
        total_label_height = sum(lbl.bounding_box[self.BBOX_HEIGHT_INDEX] for lbl in active_labels)
        spacing = (available_height - total_label_height) / (line_count + 1) if line_count > 0 else 0

        current_y = title_y
        for lbl in active_labels:
            label_height = lbl.bounding_box[self.BBOX_HEIGHT_INDEX]
            current_y += spacing + label_height
            lbl.anchored_position = (board.DISPLAY.width // 2, current_y)

    def set_values(self, timeout_value, timeout_unit, interval_value, interval_unit):
        """Set initial values and units, storing as saved values."""
        if timeout_value is None or timeout_unit is None:
            self.items[0]["value"] = None
            self.items[0]["unit"] = None
            self.items[0]["saved_value"] = None
            self.items[0]["saved_unit"] = None
        else:
            self.items[0]["value"] = timeout_value
            self.items[0]["unit"] = timeout_unit
            self.items[0]["saved_value"] = timeout_value
            self.items[0]["saved_unit"] = timeout_unit
            self._update_constraints(self.items[0])

        self.items[1]["value"] = interval_value
        self.items[1]["unit"] = interval_unit
        self.items[1]["saved_value"] = interval_value
        self.items[1]["saved_unit"] = interval_unit
        self._update_constraints(self.items[1])

        self._update_labels()

    def set_timeout_none(self):
        """Set timeout value and unit to None."""
        self.items[0]["value"] = None
        self.items[0]["unit"] = None
        self._update_labels()

    def cycle_unit(self):
        """Cycle the unit of the current item (sec -> min -> hour)."""
        item = self.items[self.current_item]
        if item["name"] == "Timeout" and (item["value"] is None or item["unit"] is None):
            item["value"] = constants.DEFAULT_TIMEOUT_VALUE
            item["unit"] = constants.DEFAULT_TIMEOUT_UNIT
        else:
            current_unit_index = self.UNIT_CYCLE.index(item["unit"])
            next_unit = self.UNIT_CYCLE[(current_unit_index + 1) % len(self.UNIT_CYCLE)]
            item["unit"] = next_unit
            # Round to nearest ten when switching to seconds
            if next_unit == "sec":
                item["value"] = round(item["value"], -1)
        self._update_constraints(item)
        self._update_labels()

    def revert_to_saved(self):
        for item in self.items:
            item["value"] = item["saved_value"]
            item["unit"] = item["saved_unit"]
        self._update_constraints(item)
        self._update_labels()

    def move_up(self):
        self.current_item = (self.current_item - 1) % len(self.items)
        self._update_labels()

    def move_down(self):
        self.current_item = (self.current_item + 1) % len(self.items)
        self._update_labels()

    def increment_value(self):
        item = self.items[self.current_item]
        if item["name"] == "Timeout" and (item["value"] is None or item["unit"] is None):
            item["value"] = constants.DEFAULT_TIMEOUT_VALUE
            item["unit"] = constants.DEFAULT_TIMEOUT_UNIT
            self._update_constraints(item)
        else:
            item["value"] = min(item["value"] + item["step"], item["max"])
        self._update_labels()

    def decrement_value(self):
        item = self.items[self.current_item]
        if item["name"] == "Timeout" and (item["value"] is None or item["unit"] is None):
            item["value"] = constants.DEFAULT_TIMEOUT_VALUE
            item["unit"] = constants.DEFAULT_TIMEOUT_UNIT
            self._update_constraints(item)
        else:
            item["value"] = max(item["value"] - item["step"], item["min"])
        self._update_labels()

    def get_values(self):
        """Return current values and units, updating saved values."""
        prev_item = {
            "timeout_value": self.items[0]["saved_value"],
            "timeout_unit": self.items[0]["saved_unit"],
            "interval_value": self.items[1]["saved_value"],
            "interval_unit": self.items[1]["saved_unit"]
        }

        for item in self.items:
            item["saved_value"] = item["value"]
            item["saved_unit"] = item["unit"]
        return {
            "timeout_value": self.items[0]["value"],
            "timeout_unit": self.items[0]["unit"],
            "interval_value": self.items[1]["value"],
            "interval_unit": self.items[1]["unit"],
            "prev_timeout_value": prev_item["timeout_value"],
            "prev_timeout_unit": prev_item["timeout_unit"],
            "prev_interval_value": prev_item["interval_value"],
            "prev_interval_unit": prev_item["interval_unit"]
        }

    def show(self):
        board.DISPLAY.root_group = self.group