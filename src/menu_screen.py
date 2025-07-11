import board
import displayio
import terminalio
import constants
import fonts
from adafruit_display_text import label
from adafruit_display_shapes import line
import gc

class MenuScreen:
    __slots__ = [
        'group',
        'bitmap',
        'palette',
        'tile_grid',
        'header_label',
        'menu_line',
        'item_labels',
        'items_per_screen',
        'color_to_index'
    ]

    PADDING_HEADER = 4
    PADDING_ITEM = 5
    MAX_ITEMS = 4  # Limit to 4 items to reduce memory usage

    def __init__(self):
        self.group = displayio.Group()
        self.bitmap = None
        self.palette = None
        self.tile_grid = None
        self.header_label = None
        self.menu_line = None
        self.item_labels = []
        self.items_per_screen = 0
        self.color_to_index = {k: i for i, k in enumerate(constants.COLOR_TO_RGB)}
        
        # Use fixed display height to save memory
        display_height = 64
        display_width = board.DISPLAY.width

        # Create palette
        self.palette = displayio.Palette(len(constants.COLOR_TO_RGB))
        for i, (color, rgb) in enumerate(constants.COLOR_TO_RGB.items()):
            self.palette[i] = rgb

        # Create bitmap with reduced size
        self.bitmap = displayio.Bitmap(display_width, display_height, len(constants.COLOR_TO_RGB))
        self.bitmap.fill(self.color_to_index['black'])
        self.tile_grid = displayio.TileGrid(self.bitmap, pixel_shader=self.palette)
        
        font_scale = 1
        # Create header label
        header_str = 'Menu'
        self.header_label = label.Label(
            fonts.font_14pt,
            text=header_str,
            color=constants.COLOR_TO_RGB['white'],
            scale=font_scale,
            anchor_point=(0.5, 1.0)
        )
        header_x = display_width // 2
        header_y = self.header_label.bounding_box[3] + self.PADDING_HEADER
        self.header_label.anchored_position = (header_x, header_y)

        # Create menu line
        menu_line_y = header_y + self.PADDING_HEADER
        self.menu_line = line.Line(
            x0=0,
            y0=menu_line_y,
            x1=display_width,
            y1=menu_line_y,
            color=constants.COLOR_TO_RGB['gray']
        )

        # Calculate items_per_screen
        vert_pix_remaining = display_height - (menu_line_y + 1)
        test_label = label.Label(fonts.font_10pt, text='test', scale=font_scale)
        label_dy = test_label.bounding_box[3] + self.PADDING_ITEM
        # self.items_per_screen = min(vert_pix_remaining // label_dy, self.MAX_ITEMS)
        self.items_per_screen = 6

        # Create item labels
        for i in range(self.items_per_screen):
            pos_x = 2
            pos_y = menu_line_y + (i + 1) * label_dy
            label_tmp = label.Label(
                fonts.font_10pt,
                text='',
                color=constants.COLOR_TO_RGB['white'],
                scale=font_scale,
                anchor_point=(0.0, 1.0),
                anchored_position=(pos_x, pos_y),
                padding_right=40
            )
            self.item_labels.append(label_tmp)

        # Add elements to group
        self.group.append(self.tile_grid)
        self.group.append(self.header_label)
        self.group.append(self.menu_line)
        for item_label in self.item_labels:
            self.group.append(item_label)

        self.set_curr_item(0)
        gc.collect()

    def clear(self):
        # Clear displayio resources without slice assignment
        while len(self.group) > 0:
            self.group.pop()
        self.bitmap = None
        self.palette = None
        self.tile_grid = None
        self.header_label = None
        self.menu_line = None
        self.item_labels = []
        self.group = displayio.Group()
        if board.DISPLAY.root_group == self.group:
            board.DISPLAY.root_group = None
        gc.collect()

    def set_menu_items(self, text_list):
        for item_label, item_text in zip(self.item_labels, text_list[:self.items_per_screen]):
            item_label.text = item_text

    def set_curr_item(self, num):
        for i, item_label in enumerate(self.item_labels):
            if i == num:
                item_label.color = constants.COLOR_TO_RGB['black']
                item_label.background_color = constants.COLOR_TO_RGB['orange']
            else:
                item_label.color = constants.COLOR_TO_RGB['white']
                item_label.background_color = constants.COLOR_TO_RGB['black']

    def show(self):
        if self.group:
            board.DISPLAY.root_group = self.group