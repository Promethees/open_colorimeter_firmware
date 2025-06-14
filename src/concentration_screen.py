import displayio
import board
import constants
import fonts
from adafruit_display_text import label

class ConcentrationScreen:
    TOP_MARGIN = 5
    BOTTOM_MARGIN = 5
    BBOX_HEIGHT_INDEX = 3

    def __init__(self):
        self.group = displayio.Group()
        self.con_unit = " nM/l"
        self.concen_val = None

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
            text="Concentration",
            color=constants.COLOR_TO_RGB["white"],
            scale=font_scale,
            anchor_point=(0.5, 1.0),
        )
        self.title_label.anchored_position = (center_x, self.TOP_MARGIN + self.title_label.bounding_box[self.BBOX_HEIGHT_INDEX])

        # Create labels for settings
        self.concen_labels = []
        self.value_lbl = label.Label(
            fonts.font_14pt,
            text="",
            color=constants.COLOR_TO_RGB["orange"],
            scale=font_scale,
            anchor_point=(0.5, 1.0),
        )

        # Create group
        self.group.append(self.tile_grid)
        self.group.append(self.title_label)
        self.group.append(self.value_lbl)

        self._position_labels()

    def _position_labels(self, new_val = "Unknown"):
        self.value_lbl.text = str(new_val) + self.con_unit

        title_height = self.title_label.bounding_box[self.BBOX_HEIGHT_INDEX]
        title_y = self.TOP_MARGIN + title_height
        self.title_label.anchored_position = (self.title_label.anchored_position[0], title_y)
        available_height = board.DISPLAY.height - title_y - self.BOTTOM_MARGIN
        label_height = self.value_lbl.bounding_box[self.BBOX_HEIGHT_INDEX]
        spacing = (available_height - label_height) / 2 

        current_y = title_y + spacing + label_height
        self.value_lbl.anchored_position = (board.DISPLAY.width // 2, current_y)

    def set_to_zero(self):
        self.concen_val = None
        self._position_labels()

    def add(self, sub_val):
        self.concen_val = 0 if (self.concen_val is None) else max(0, self.concen_val + sub_val)
        self._position_labels(self.concen_val)

    def get_values(self):
        return self.concen_val

    def show(self):
        board.DISPLAY.root_group = self.group