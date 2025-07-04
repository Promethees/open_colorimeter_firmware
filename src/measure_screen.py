import board
import displayio
import constants
import fonts
from adafruit_display_text import label
import gc

class MeasureScreen:
    __slots__ = [
        'palette',
        'bitmap',
        'tile_grid',
        'header_label',
        'value_label',
        'type_label',
        'comm_label',
        'blank_label',
        'gain_label',
        'itime_label',
        'bat_label',
        'group'
    ]

    GAIN_LABEL_X_OFFSET = 5  # Left margin for gain label
    ITIME_LABEL_X_OFFSET = 5  # Right margin offset for itime label
    TOP_MARGIN = 5  # Margin at top
    BOTTOM_MARGIN = 5  # Margin at bottom
    BBOX_HEIGHT_INDEX = 3  # Index for height in bounding_box tuple
    ITIME_Y_OFFSET = -3  # Vertical offset for itime label alignment

    # Mapping of special messages to colors
    MESSAGE_COLORS = {
        "overflow": "red",
        "range error": "orange",
        "comm init": "yellow",  # Alias for comm ready
        "comm ready": "yellow",
        "connected": "green",
        "stopped": "red",
        " personally": "red"
    }

    def __init__(self):
        self.palette = None
        self.bitmap = None
        self.tile_grid = None
        self.header_label = None
        self.value_label = None
        self.type_label = None
        self.comm_label = None
        self.blank_label = None
        self.gain_label = None
        self.itime_label = None
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
        center_x = board.DISPLAY.width // 2

        # Create header label (measurement name)
        self.header_label = label.Label(
            fonts.font_14pt,
            text="Absorbance",
            color=constants.COLOR_TO_RGB["white"],
            scale=font_scale,
            anchor_point=(0.5, 1.0),
            padding_right=40  # Added to limit text buffer size
        )
        self.header_label.anchored_position = (center_x, self.TOP_MARGIN + self.header_label.bounding_box[self.BBOX_HEIGHT_INDEX])

        # Create value label (numeric value, units, or special message)
        self.value_label = label.Label(
            fonts.font_14pt,
            text="0.00",
            color=constants.COLOR_TO_RGB["white"],
            scale=font_scale,
            anchor_point=(0.5, 1.0),
            padding_right=40
        )
        self.value_label.anchored_position = (center_x, 0)

        # Create type label (type_tag)
        self.type_label = label.Label(
            fonts.font_10pt,
            text="",
            color=constants.COLOR_TO_RGB["blue"],
            scale=font_scale,
            anchor_point=(0.5, 1.0),
            padding_right=40
        )
        self.type_label.anchored_position = (center_x, 0)

        # Create communication status label
        self.comm_label = label.Label(
            fonts.font_10pt,
            text="",
            color=constants.COLOR_TO_RGB["green"],
            scale=font_scale,
            anchor_point=(0.5, 1.0),
            padding_right=40
        )
        self.comm_label.anchored_position = (center_x, 0)

        # Create blank label
        self.blank_label = label.Label(
            fonts.font_10pt,
            text="initializing",
            color=constants.COLOR_TO_RGB["orange"],
            scale=font_scale,
            anchor_point=(0.5, 1.0),
            padding_right=40
        )
        self.blank_label.anchored_position = (center_x, 0)

        # Create gain label
        self.gain_label = label.Label(
            fonts.font_10pt,
            text="gain xxx",
            color=constants.COLOR_TO_RGB["orange"],
            scale=font_scale,
            anchor_point=(0.0, 1.0),
            padding_right=40
        )
        self.gain_label.anchored_position = (self.GAIN_LABEL_X_OFFSET, 0)

        # Create integration time label
        self.itime_label = label.Label(
            fonts.font_10pt,
            text="time xxxms",
            color=constants.COLOR_TO_RGB["orange"],
            scale=font_scale,
            anchor_point=(0.0, 1.0),
            padding_right=40
        )
        itime_x = board.DISPLAY.width // 2 - self.ITIME_LABEL_X_OFFSET
        self.itime_label.anchored_position = (itime_x, 0)

        # Create battery label
        self.bat_label = label.Label(
            fonts.font_10pt,
            text="battery 0.0V",
            color=constants.COLOR_TO_RGB["gray"],
            scale=font_scale,
            anchor_point=(0.5, 1.0),
            padding_right=40
        )
        self.bat_label.anchored_position = (center_x, 0)

        # Add elements to group
        self.group.append(self.tile_grid)
        self.group.append(self.header_label)
        self.group.append(self.value_label)
        self.group.append(self.type_label)
        self.group.append(self.comm_label)
        self.group.append(self.blank_label)
        self.group.append(self.gain_label)
        self.group.append(self.itime_label)
        self.group.append(self.bat_label)

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
        self.type_label = None
        self.comm_label = None
        self.blank_label = None
        self.gain_label = None
        self.itime_label = None
        self.bat_label = None
        self.group = displayio.Group()
        if board.DISPLAY.root_group == self.group:
            board.DISPLAY.root_group = None
        gc.collect()

    def set_measurement(self, name, units, value, precision, type_tag=None, talking=False):
        """Update display with measurement or communication status."""
        self.header_label.text = name

        # Handle special messages
        if isinstance(value, str) and value in self.MESSAGE_COLORS:
            self.value_label.text = value
            self.value_label.color = constants.COLOR_TO_RGB[self.MESSAGE_COLORS[value]]
            self.type_label.text = ""
            self.comm_label.text = ""
        # Handle communication status
        elif isinstance(value, str):
            self.value_label.text = ""
            self.type_label.text = ""
            self.comm_label.text = value
            self.comm_label.color = constants.COLOR_TO_RGB[self.MESSAGE_COLORS.get(value, "yellow")]
        # Handle measurements
        else:
            if talking:
                self.comm_label.text = "sending msgs"
                self.comm_label.color = constants.COLOR_TO_RGB["green"]
            else:
                self.comm_label.text = ""
            if value is None:
                self.value_label.text = "range error"
                self.value_label.color = constants.COLOR_TO_RGB["orange"]
            else:
                label_text = f"{value:1.{precision}f}" if isinstance(value, (int, float)) else str(value)
                if units:
                    label_text += f" {units}"
                self.value_label.text = label_text.replace("0", "O")
                self.value_label.color = constants.COLOR_TO_RGB["white"]
            self.type_label.text = type_tag if (type_tag and type_tag != "None") else ""

        # Position labels
        active_labels, line_count = self._get_active_labels()
        self._position_labels(active_labels, line_count)

    def set_not_blanked(self):
        self.blank_label.text = "not blanked"

    def set_blanking(self):
        self.blank_label.text = "blanking"

    def set_blanked(self):
        self.blank_label.text = ""

    def set_gain(self, value):
        self.gain_label.text = f"gain={constants.GAIN_TO_STR[value]}" if value is not None else ""

    def clear_gain(self):
        self.gain_label.text = ""

    def set_integration_time(self, value):
        self.itime_label.text = f"time={constants.INTEGRATION_TIME_TO_STR[value]}" if value is not None else ""

    def clear_integration_time(self):
        self.itime_label.text = ""

    def set_bat(self, value):
        self.bat_label.text = f"battery {value:1.1f}V"

    def _get_active_labels(self):
        """Return list of labels with non-empty text and count of display lines."""
        active_labels = []
        line_count = 0
        labels = [
            self.value_label,
            self.comm_label,
            self.type_label,
            self.blank_label,
            self.gain_label,
            self.itime_label,
        ]
        gain_itime_added = False

        for label in labels:
            if label.text and label.text.strip():
                if label in (self.gain_label, self.itime_label):
                    if not gain_itime_added:
                        active_labels.append(label)
                        line_count += 1
                        gain_itime_added = True
                    continue
                active_labels.append(label)
                line_count += 1

        return active_labels, line_count

    def _position_labels(self, active_labels, line_count):
        """Position labels dynamically based on line count."""
        header_height = self.header_label.bounding_box[self.BBOX_HEIGHT_INDEX]
        header_y = self.TOP_MARGIN + header_height
        self.header_label.anchored_position = (self.header_label.anchored_position[0], header_y)

        bat_height = self.bat_label.bounding_box[self.BBOX_HEIGHT_INDEX]
        bat_y = board.DISPLAY.height - self.BOTTOM_MARGIN
        self.bat_label.anchored_position = (self.bat_label.anchored_position[0], bat_y)

        available_height = board.DISPLAY.height - header_y - bat_height - self.BOTTOM_MARGIN
        total_label_height = sum(
            label.bounding_box[self.BBOX_HEIGHT_INDEX]
            for label in active_labels
            if label not in [self.gain_label, self.itime_label]
        )
        if self.gain_label in active_labels or self.itime_label in active_labels:
            total_label_height += self.gain_label.bounding_box[self.BBOX_HEIGHT_INDEX]

        spacing = (available_height - total_label_height) / (line_count + 1) if line_count > 0 else 0

        current_y = header_y
        gain_itime_positioned = False
        for label in active_labels:
            label_height = label.bounding_box[self.BBOX_HEIGHT_INDEX]
            current_y += spacing + label_height
            if label in (self.gain_label, self.itime_label):
                if not gain_itime_positioned:
                    self.gain_label.anchored_position = (self.gain_label.anchored_position[0], current_y)
                    self.itime_label.anchored_position = (self.itime_label.anchored_position[0], current_y + self.ITIME_Y_OFFSET)
                    gain_itime_positioned = True
                    current_y += label_height
                continue
            label.anchored_position = (label.anchored_position[0], current_y)

    def show(self):
        if self.group:
            board.DISPLAY.root_group = self.group