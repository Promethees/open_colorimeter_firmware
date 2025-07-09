import board
import displayio
import constants
import fonts
from adafruit_display_text import label
import gc

class ReferenceUnitScreen:
    __slots__ = [
        'palette',
        'bitmap',
        'tile_grid',
        'header_label',
        'value_label',
        'units_label',
        'bat_label',
        'group'
    ]

    TOP_MARGIN = 5  # Margin at top
    BOTTOM_MARGIN = 5  # Margin at bottom
    BBOX_HEIGHT_INDEX = 3  # Index for height in bounding_box tuple
    VALUE_TO_UNITS_X_OFFSET = 70  # Horizontal offset between value and units labels
    LEFT_MARGIN = 5  # Left margin for labels

    # Mapping of special messages to colors
    MESSAGE_COLORS = {
        "overflow": "red"
    }

    def __init__(self):
        self.palette = None
        self.bitmap = None
        self.tile_grid = None
        self.header_label = None
        self.value_label = None
        self.units_label = None
        self.bat_label = None
        self.group = displayio.Group()

        # Setup color palette
        self.palette = displayio.Palette(len(constants.COLOR_TO_RGB))
        for i, (color, rgb) in enumerate(constants.COLOR_TO_RGB.items()):
            self.palette[i] = rgb

        # Create bitmap with reduced height if possible
        display_height = min(board.DISPLAY.height, 64)  # Cap height to save memory
        self.bitmap = displayio.Bitmap(board.DISPLAY.width, display_height, len(constants.COLOR_TO_RGB))
        self.bitmap.fill(0)  # Black
        self.tile_grid = displayio.TileGrid(self.bitmap, pixel_shader=self.palette)

        font_scale = 1
        left_anchor = (0.0, 1.0)  # Anchor point for left-aligned labels

        # Create header label
        self.header_label = label.Label(
            fonts.font_10pt,
            text="header",
            color=constants.COLOR_TO_RGB["white"],
            scale=font_scale,
            anchor_point=left_anchor,
            padding_right=40
        )

        # Create value label
        self.value_label = label.Label(
            fonts.font_10pt,
            text="0.00",
            color=constants.COLOR_TO_RGB["orange"],
            scale=font_scale,
            anchor_point=left_anchor,
            padding_right=40
        )

        # Create units label
        self.units_label = label.Label(
            fonts.font_10pt,
            text="",
            color=constants.COLOR_TO_RGB["orange"],
            scale=font_scale,
            anchor_point=left_anchor,
            padding_right=40
        )

        # Create battery label
        self.bat_label = label.Label(
            fonts.font_10pt,
            text="battery 0.0V",
            color=constants.COLOR_TO_RGB["gray"],
            scale=font_scale,
            anchor_point=(0.5, 1.0),
            padding_right=40
        )

        # Add elements to group
        self.group.append(self.tile_grid)
        self.group.append(self.header_label)
        self.group.append(self.value_label)
        self.group.append(self.units_label)
        self.group.append(self.bat_label)

        # Position labels initially
        self._position_labels()

        gc.collect()

    def clear(self):
        # Clear displayio resources
        while len(self.group) > 0:
            self.group.pop()
        self.bitmap = None
        self.palette = None
        self.tile_grid = None
        self.header_label = None
        self.value_label = None
        self.units_label = None
        self.bat_label = None
        self.group = displayio.Group()
        if board.DISPLAY.root_group == self.group:
            board.DISPLAY.root_group = None
        gc.collect()

    @property
    def has_selected_sensor(self):
        return False

    def set_measurement(self, measurement):
        name = measurement.label
        value = measurement.value
        units = measurement.units
        self.header_label.text = name

        # Handle special messages
        if isinstance(value, str) and value in self.MESSAGE_COLORS:
            self.value_label.text = value
            self.value_label.color = constants.COLOR_TO_RGB[self.MESSAGE_COLORS[value]]
            self.units_label.text = ""
        else:
            if isinstance(value, float):
                if value <= 10:
                    value_text = f"{value:.3f}"
                else:
                    value_text = f"{value:.2f}"
            else:
                value_text = str(value)
            self.value_label.text = value_text.replace("0", "O")
            self.value_label.color = constants.COLOR_TO_RGB["orange" if value != constants.OVERFLOW_STR else "red"]
            self.units_label.text = units if units else ""

        self._position_labels()

    def set_bat(self, value):
        self.bat_label.text = f"battery {value:1.1f}V"
        self._position_labels()

    def show(self):
        if self.group:
            board.DISPLAY.root_group = self.group

    def update(self, measurement, battery_monitor):
        self.set_measurement(measurement)
        self.set_bat(battery_monitor.voltage_lowpass)

    def _get_active_labels(self):
        """Return list of labels with non-empty text and count of display lines."""
        active_labels = []
        line_count = 0
        labels = [self.header_label, self.value_label, self.units_label]

        for label in labels:
            if label.text and label.text.strip():
                active_labels.append(label)
                if label is not self.units_label:  # Units shares line with value
                    line_count += 1

        return active_labels, line_count

    def _position_labels(self):
        """Position labels dynamically based on line count."""
        active_labels, line_count = self._get_active_labels()

        # Position header
        header_height = self.header_label.bounding_box[self.BBOX_HEIGHT_INDEX]
        header_y = self.TOP_MARGIN + header_height
        self.header_label.anchored_position = (self.LEFT_MARGIN, header_y)

        # Position battery
        bat_height = self.bat_label.bounding_box[self.BBOX_HEIGHT_INDEX]
        bat_y = board.DISPLAY.height - self.BOTTOM_MARGIN
        self.bat_label.anchored_position = (board.DISPLAY.width // 2, bat_y)

        # Calculate available space and spacing
        available_height = board.DISPLAY.height - header_y - bat_height - self.BOTTOM_MARGIN
        total_label_height = sum(
            label.bounding_box[self.BBOX_HEIGHT_INDEX]
            for label in active_labels
            if label is not self.header_label and label is not self.units_label
        )
        spacing = (available_height - total_label_height) / (line_count + 1) if line_count > 0 else 0

        # Position value and units on the same line
        current_y = header_y
        for label in active_labels:
            if label is self.header_label:
                continue
            if label is self.value_label:
                label_height = label.bounding_box[self.BBOX_HEIGHT_INDEX]
                current_y += spacing + label_height
                # self.value_label.anchored_position = (self.LEFT_MARGIN, current_y)
                self.value_label.anchored_position = (board.DISPLAY.width // 6, board.DISPLAY.height // 2)
            elif label is self.units_label:
                # self.units_label.anchored_position = (self.LEFT_MARGIN + self.VALUE_TO_UNITS_X_OFFSET, current_y)
                self.units_label.anchored_position = (board.DISPLAY.width * 0.6, board.DISPLAY.height // 2)