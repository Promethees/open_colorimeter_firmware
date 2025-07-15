import displayio
import board
import constants
import fonts
from adafruit_display_text import label
import gc

class ConcentrationScreen:
    __slots__ = [
        'group',
        'con_unit',
        'concen_val',
        'palette',
        'bitmap',
        'tile_grid',
        'title_label',
        'concen_labels',
        'value_lbl'
    ]

    TOP_MARGIN = 5
    BOTTOM_MARGIN = 5
    BBOX_HEIGHT_INDEX = 3

    def __init__(self, concen_val=None):
        self.group = displayio.Group()
        self.con_unit = " ng/µL"
        self.concen_val = concen_val
        self.palette = None
        self.bitmap = None
        self.tile_grid = None
        self.title_label = None
        self.concen_labels = []
        self.value_lbl = None

        # Setup color palette
        self.palette = displayio.Palette(len(constants.COLOR_TO_RGB))
        for i, (color, rgb) in enumerate(constants.COLOR_TO_RGB.items()):
            self.palette[i] = rgb

        # Create bitmap with reduced height
        display_height = min(board.DISPLAY.height, 64)
        self.bitmap = displayio.Bitmap(board.DISPLAY.width, display_height, len(constants.COLOR_TO_RGB))
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
            padding_right=40
        )
        self.title_label.anchored_position = (center_x, self.TOP_MARGIN + self.title_label.bounding_box[self.BBOX_HEIGHT_INDEX])

        # Create value label
        self.value_lbl = label.Label(
            fonts.font_14pt,
            text="",
            color=constants.COLOR_TO_RGB["orange"],
            scale=font_scale,
            anchor_point=(0.5, 1.0),
            padding_right=40
        )
        self.concen_labels.append(self.value_lbl)

        # Create group
        self.group.append(self.tile_grid)
        self.group.append(self.title_label)
        self.group.append(self.value_lbl)

        self._position_labels(self.concen_val)
        gc.collect()

    def clear(self):
        # Clear displayio resources
        while len(self.group) > 0:
            self.group.pop()
        self.bitmap = None
        self.palette = None
        self.tile_grid = None
        self.title_label = None
        self.concen_labels = []
        self.value_lbl = None
        self.group = displayio.Group()
        if board.DISPLAY.root_group == self.group:
            board.DISPLAY.root_group = None
        gc.collect()

    def _position_labels(self, new_val="Unknown"):
        if new_val is not None:
            self.value_lbl.text = str(new_val) + self.con_unit
        else:
            self.value_lbl.text = "Unknown" + self.con_unit
        title_height = self.title_label.bounding_box[self.BBOX_HEIGHT_INDEX]
        title_y = self.TOP_MARGIN + title_height
        self.title_label.anchored_position = (self.title_label.anchored_position[0], title_y)
        available_height = board.DISPLAY.height - title_y - self.BOTTOM_MARGIN
        label_height = self.value_lbl.bounding_box[self.BBOX_HEIGHT_INDEX]
        spacing = (available_height - label_height) / 2

        current_y = title_y + spacing + label_height
        self.value_lbl.anchored_position = (board.DISPLAY.width // 2, current_y)

    def set_to_none(self):
        self.concen_val = None
        self._position_labels()

    def add(self, sub_val):
        self.concen_val = 0 if (self.concen_val is None) else max(0, self.concen_val + sub_val)
        self._position_labels(self.concen_val)

    def get_values(self):
        return self.concen_val

    def show(self):
        if self.group:
            board.DISPLAY.root_group = self.group