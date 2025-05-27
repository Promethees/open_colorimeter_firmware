import board
import displayio
import constants
import fonts
from adafruit_display_text import label


class MeasureScreen:
    GAIN_LABEL_X_OFFSET = 5  # Left margin for gain label
    ITIME_LABEL_X_OFFSET = 5  # Right margin offset for itime label
    TOP_MARGIN = 5  # Margin at top
    BOTTOM_MARGIN = 5  # Margin at bottom
    BBOX_HEIGHT_INDEX = 3  # Index for height in bounding_box tuple
    ITIME_Y_OFFSET = -3  # Vertical offset for itime label alignment

    def __init__(self):
        # Setup color palette and tile grid
        self.palette = displayio.Palette(len(constants.COLOR_TO_RGB))
        for i, (color, rgb) in enumerate(constants.COLOR_TO_RGB.items()):
            self.palette[i] = rgb

        self.bitmap = displayio.Bitmap(board.DISPLAY.width, board.DISPLAY.height, len(constants.COLOR_TO_RGB))
        self.bitmap.fill(0)  # Black (assumes 'black' is at index 0)
        self.tile_grid = displayio.TileGrid(self.bitmap, pixel_shader=self.palette)

        font_scale = 1
        center_x = board.DISPLAY.width // 2

        # Create header label
        self.header_label = label.Label(
            fonts.font_14pt,
            text="Absorbance",
            color=constants.COLOR_TO_RGB["white"],
            scale=font_scale,
            anchor_point=(0.5, 1.0),
        )
        self.header_label.anchored_position = (center_x, self.TOP_MARGIN + self.header_label.bounding_box[self.BBOX_HEIGHT_INDEX])

        # Create value label
        self.value_label = label.Label(
            fonts.font_14pt,
            text="O.OO",
            color=constants.COLOR_TO_RGB["white"],
            scale=font_scale,
            anchor_point=(0.5, 1.0),
        )
        self.value_label.anchored_position = (center_x, 0)  # Placeholder, updated later

        # Create type label
        self.type_label = label.Label(
            fonts.font_10pt,
            text="",
            color=constants.COLOR_TO_RGB["blue"],
            scale=font_scale,
            anchor_point=(0.5, 1.0),
        )
        self.type_label.anchored_position = (center_x, 0)

        # Create blank label
        self.blank_label = label.Label(
            fonts.font_10pt,
            text="initializing",
            color=constants.COLOR_TO_RGB["orange"],
            scale=font_scale,
            anchor_point=(0.5, 1.0),
        )
        self.blank_label.anchored_position = (center_x, 0)

        # Create serial communication label
        self.talking_label = label.Label(
            fonts.font_10pt,
            text="establshing communication",
            color=constants.COLOR_TO_RGB["green"],
            scale=font_scale,
            anchor_point=(0.5, 1.0),
        )
        self.talking_label.anchored_position = (center_x, 0)

        # Create gain label
        self.gain_label = label.Label(
            fonts.font_10pt,
            text="gain xxx",
            color=constants.COLOR_TO_RGB["orange"],
            scale=font_scale,
            anchor_point=(0.0, 1.0),
        )
        self.gain_label.anchored_position = (self.GAIN_LABEL_X_OFFSET, 0)

        # Create integration time label
        self.itime_label = label.Label(
            fonts.font_10pt,
            text="time xxxms",
            color=constants.COLOR_TO_RGB["orange"],
            scale=font_scale,
            anchor_point=(0.0, 1.0),
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
        )
        self.bat_label.anchored_position = (center_x, 0)

        # Create display group
        self.group = displayio.Group()
        self.group.append(self.tile_grid)
        self.group.append(self.header_label)
        self.group.append(self.value_label)
        self.group.append(self.type_label)
        self.group.append(self.talking_label)
        self.group.append(self.blank_label)
        self.group.append(self.gain_label)
        self.group.append(self.itime_label)
        self.group.append(self.bat_label)

    def set_measurement(self, name, units, value, precision, type_tag=None):
        # Update header and value labels
        if value is None:
            self.header_label.text = name
            self.value_label.text = "range error"
            self.value_label.color = constants.COLOR_TO_RGB["orange"]
        elif value in ("overflow", "disconnected"):
            self.header_label.text = name
            self.value_label.text = value
            self.value_label.color = constants.COLOR_TO_RGB["red"]
        else:
            self.header_label.text = name
            label_text = f"{value:1.{precision}f}" if isinstance(value, (int, float)) else str(value)
            if units:
                label_text += f" {units}"
            self.value_label.text = label_text.replace("0", "O")
            self.value_label.color = constants.COLOR_TO_RGB["white"]

        # Update type label
        self.type_label.text = type_tag or ""

        # Get active labels and count lines
        active_labels, line_count = self._get_active_labels()

        # Position labels
        self._position_labels(active_labels, line_count)

    def set_overflow(self, name):
        self.header_label.text = name
        self.value_label.text = "overflow"
        self.value_label.color = constants.COLOR_TO_RGB["red"]
        self.type_label.text = ""

        # Get active labels and count lines
        active_labels, line_count = self._get_active_labels()

        # Position labels
        self._position_labels(active_labels, line_count)

    def _get_active_labels(self):
        """Return list of labels with non-empty text and count of display lines."""
        active_labels = []
        line_count = 0
        labels = [
            self.value_label,
            self.type_label,
            self.talking_label,
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
        """Position all labels dynamically based on line count."""
        # Position header at top
        header_height = self.header_label.bounding_box[self.BBOX_HEIGHT_INDEX]
        header_y = self.TOP_MARGIN + header_height
        self.header_label.anchored_position = (self.header_label.anchored_position[0], header_y)

        # Position battery at bottom
        bat_height = self.bat_label.bounding_box[self.BBOX_HEIGHT_INDEX]
        bat_y = board.DISPLAY.height - self.BOTTOM_MARGIN
        self.bat_label.anchored_position = (self.bat_label.anchored_position[0], bat_y)

        # Calculate height between bottom of header to top of battery label
        available_height = board.DISPLAY.height - header_y - bat_height - self.BOTTOM_MARGIN
        total_label_height = sum(
            label.bounding_box[self.BBOX_HEIGHT_INDEX]
            for label in active_labels
            if label not in [self.gain_label, self.itime_label]
        )
        if self.gain_label in active_labels or self.itime_label in active_labels:
            total_label_height += self.gain_label.bounding_box[self.BBOX_HEIGHT_INDEX]

        spacing = (available_height - total_label_height) / (line_count + 1) if line_count > 0 else 0

        # Position remaining labels
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
            # current_y += label_height

    def set_not_blanked(self):
        self.blank_label.text = " not blanked"

    def set_blanking(self):
        self.blank_label.text = "  blanking  "

    def set_blanked(self):
        self.blank_label.text = " "

    def set_stop_talking(self):
        self.talking_label.text = "stop talking"

    def set_not_talking(self):
        self.talking_label.text = " "

    def init_talking(self):
        self.talking_label.text = " comm ready  "

    def set_connected(self):
        self.talking_label.text = "connected!"

    def set_talking(self):
        self.talking_label.text = " sending msgs "

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

    def show(self):
        board.DISPLAY.root_group = self.group