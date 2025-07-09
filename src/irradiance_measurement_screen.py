import board
import displayio
import constants
import fonts
import adafruit_itertools
from adafruit_display_text import label
import gc

class IrradianceMeasurementScreen:
    __slots__ = [
        'palette',
        'bitmap',
        'tile_grid',
        'header1_label',
        'value1_label',
        'units1_label',
        'header2_label',
        'value2_label',
        'units2_label',
        'bat_label',
        'group',
        'header_labels',
        'value_labels',
        'units_labels'
    ]

    TOP_MARGIN = 5  # Margin at top
    BOTTOM_MARGIN = 5  # Margin at bottom
    BBOX_HEIGHT_INDEX = 3  # Index for height in bounding_box tuple
    VALUE_TO_UNITS_X_OFFSET = 70  # Horizontal offset between value and units labels
    LEFT_MARGIN = 5  # Left margin for labels
    HEADER_SPACING = 10  # Spacing between header1/value1 and header2/value2 blocks

    # Mapping of special messages to colors
    MESSAGE_COLORS = {
        "overflow": "red"
    }

    SENSOR_INDICES = [0, 1]

    def __init__(self):
        self.palette = None
        self.bitmap = None
        self.tile_grid = None
        self.header1_label = None
        self.value1_label = None
        self.units1_label = None
        self.header2_label = None
        self.value2_label = None
        self.units2_label = None
        self.bat_label = None
        self.group = displayio.Group()
        self.header_labels = None
        self.value_labels = None
        self.units_labels = None

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

        # Create header1 label
        self.header1_label = label.Label(
            fonts.font_10pt,
            text="header1",
            color=constants.COLOR_TO_RGB["white"],
            scale=font_scale,
            anchor_point=left_anchor,
            padding_right=40
        )

        # Create value1 label
        self.value1_label = label.Label(
            fonts.font_10pt,
            text="0.00",
            color=constants.COLOR_TO_RGB["orange"],
            scale=font_scale,
            anchor_point=left_anchor,
            padding_right=40
        )

        # Create units1 label
        self.units1_label = label.Label(
            fonts.font_10pt,
            text="",
            color=constants.COLOR_TO_RGB["orange"],
            scale=font_scale,
            anchor_point=left_anchor,
            padding_right=40
        )

        # Create header2 label
        self.header2_label = label.Label(
            fonts.font_10pt,
            text="header2",
            color=constants.COLOR_TO_RGB["white"],
            scale=font_scale,
            anchor_point=left_anchor,
            padding_right=40
        )

        # Create value2 label
        self.value2_label = label.Label(
            fonts.font_10pt,
            text="0.00",
            color=constants.COLOR_TO_RGB["orange"],
            scale=font_scale,
            anchor_point=left_anchor,
            padding_right=40
        )

        # Create units2 label
        self.units2_label = label.Label(
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
        self.group.append(self.header1_label)
        self.group.append(self.value1_label)
        self.group.append(self.units1_label)
        self.group.append(self.header2_label)
        self.group.append(self.value2_label)
        self.group.append(self.units2_label)
        self.group.append(self.bat_label)

        self.header_labels = (self.header1_label, self.header2_label)
        self.value_labels = (self.value1_label, self.value2_label)
        self.units_labels = (self.units1_label, self.units2_label)

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
        self.header1_label = None
        self.value1_label = None
        self.units1_label = None
        self.header2_label = None
        self.value2_label = None
        self.units2_label = None
        self.bat_label = None
        self.group = displayio.Group()
        self.header_labels = None
        self.value_labels = None
        self.units_labels = None
        if board.DISPLAY.root_group == self.group:
            board.DISPLAY.root_group = None
        gc.collect()

    @property
    def has_selected_sensor(self):
        return False

    def set_measurement(self, measurement):
        measurement_items = (
            measurement.label,
            measurement.value,
            self.header_labels,
            self.value_labels,
            self.units_labels,
        )
        for name, value, header_label, value_label, units_label in zip(*measurement_items):
            header_label.text = f"{name}"
            if isinstance(value, str) and value in self.MESSAGE_COLORS:
                value_label.text = value
                value_label.color = constants.COLOR_TO_RGB[self.MESSAGE_COLORS[value]]
                units_label.text = ""
            else:
                if isinstance(value, float):
                    value_text = f"{value:.3f}" if value <= 10 else f"{value:.2f}"
                else:
                    value_text = str(value)
                value_label.text = value_text.replace("0", "O")
                value_label.color = constants.COLOR_TO_RGB["orange" if value != constants.OVERFLOW_STR else "red"]
                units_label.text = measurement.units if measurement.units else ""

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
        labels = [
            self.header1_label,
            self.value1_label,
            self.units1_label,
            self.header2_label,
            self.value2_label,
            self.units2_label
        ]

        for label in labels:
            if label.text and label.text.strip():
                active_labels.append(label)
                if label not in (self.units1_label, self.units2_label):  # Units share line with value
                    line_count += 1

        return active_labels, line_count

    def _position_labels(self):
        """Position labels dynamically based on line count."""
        active_labels, line_count = self._get_active_labels()

        # Position battery
        bat_height = self.bat_label.bounding_box[self.BBOX_HEIGHT_INDEX]
        bat_y = board.DISPLAY.height - self.BOTTOM_MARGIN
        self.bat_label.anchored_position = (board.DISPLAY.width // 2, bat_y)

        # Position header1
        header1_height = self.header1_label.bounding_box[self.BBOX_HEIGHT_INDEX]
        header1_y = self.TOP_MARGIN + header1_height
        self.header1_label.anchored_position = (self.LEFT_MARGIN, header1_y)

        # Calculate available space and spacing
        available_height = board.DISPLAY.height - header1_y - bat_height - self.BOTTOM_MARGIN
        total_label_height = sum(
            label.bounding_box[self.BBOX_HEIGHT_INDEX]
            for label in active_labels
            if label not in (self.header1_label, self.units1_label, self.units2_label)
        )
        spacing = (available_height - total_label_height - self.HEADER_SPACING) / (line_count + 1) if line_count > 0 else 0

        # Position value1 and units1 on the same line
        current_y = header1_y
        for label in active_labels:
            if label is self.header1_label:
                continue
            if label is self.value1_label:
                label_height = label.bounding_box[self.BBOX_HEIGHT_INDEX]
                current_y += spacing + label_height
                self.value1_label.anchored_position = (self.LEFT_MARGIN, current_y)
            elif label is self.units1_label:
                self.units1_label.anchored_position = (self.LEFT_MARGIN + self.VALUE_TO_UNITS_X_OFFSET, current_y)
            elif label is self.header2_label:
                label_height = label.bounding_box[self.BBOX_HEIGHT_INDEX]
                current_y += spacing + label_height + self.HEADER_SPACING
                self.header2_label.anchored_position = (self.LEFT_MARGIN, current_y)
            elif label is self.value2_label:
                label_height = label.bounding_box[self.BBOX_HEIGHT_INDEX]
                current_y += spacing + label_height
                self.value2_label.anchored_position = (self.LEFT_MARGIN, current_y)
            elif label is self.units2_label:
                self.units2_label.anchored_position = (self.LEFT_MARGIN + self.VALUE_TO_UNITS_X_OFFSET, current_y)