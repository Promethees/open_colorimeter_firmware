import board
import displayio
import constants
import fonts
import adafruit_itertools
from adafruit_display_text import label
import gc

class CountMeasurementScreen:
    __slots__ = [
        'palette',
        'bitmap',
        'tile_grid',
        'header1_label',
        'value1_label',
        'gain1_label',
        'itime1_label',
        'header2_label',
        'value2_label',
        'gain2_label',
        'itime2_label',
        'bat_label',
        'group',
        'header_labels',
        'value_labels',
        'selected_sensor',
        'selected_sensor_cycle'
    ]

    TOP_MARGIN = 5
    BOTTOM_MARGIN = 5
    BBOX_HEIGHT_INDEX = 3
    HEADER_TO_VALUE_X_OFFSET = 0  # Horizontal offset between header and value labels
    GAIN_TO_ITIME_X_OFFSET = 75   # Horizontal offset between gain and itime labels
    LEFT_MARGIN = 5
    RIGHT_MARGIN = 5
    HEADER_SPACING = 10

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
        self.gain1_label = None
        self.itime1_label = None
        self.header2_label = None
        self.value2_label = None
        self.gain2_label = None
        self.itime2_label = None
        self.bat_label = None
        self.group = displayio.Group()
        self.header_labels = None
        self.value_labels = None
        self.selected_sensor = None
        self.selected_sensor_cycle = None

        self.setup_selected_sensor_cycle()

        self.palette = displayio.Palette(len(constants.COLOR_TO_RGB))
        for i, (color, rgb) in enumerate(constants.COLOR_TO_RGB.items()):
            self.palette[i] = rgb

        display_height = min(board.DISPLAY.height, 64)
        self.bitmap = displayio.Bitmap(board.DISPLAY.width, display_height, len(constants.COLOR_TO_RGB))
        self.bitmap.fill(0)
        self.tile_grid = displayio.TileGrid(self.bitmap, pixel_shader=self.palette)

        font_scale = 1
        left_anchor = (0.0, 1.0)
        right_anchor = (1.0, 1.0)

        self.header1_label = label.Label(
            fonts.font_10pt,
            text="header1",
            color=constants.COLOR_TO_RGB["white"],
            scale=font_scale,
            anchor_point=left_anchor,
            padding_right=40
        )

        self.value1_label = label.Label(
            fonts.font_10pt,
            text="0.00",
            color=constants.COLOR_TO_RGB["white"],
            scale=font_scale,
            anchor_point=right_anchor,
            padding_right=40
        )

        self.gain1_label = label.Label(
            fonts.font_10pt,
            text="gain xxx",
            color=constants.COLOR_TO_RGB["orange"],
            scale=font_scale,
            anchor_point=left_anchor,
            padding_right=40
        )

        self.itime1_label = label.Label(
            fonts.font_10pt,
            text="time xxxms",
            color=constants.COLOR_TO_RGB["orange"],
            scale=font_scale,
            anchor_point=left_anchor,
            padding_right=40
        )

        self.header2_label = label.Label(
            fonts.font_10pt,
            text="header2",
            color=constants.COLOR_TO_RGB["white"],
            scale=font_scale,
            anchor_point=left_anchor,
            padding_right=40
        )

        self.value2_label = label.Label(
            fonts.font_10pt,
            text="0.00",
            color=constants.COLOR_TO_RGB["white"],
            scale=font_scale,
            anchor_point=right_anchor,
            padding_right=40
        )

        self.gain2_label = label.Label(
            fonts.font_10pt,
            text="gain xxx",
            color=constants.COLOR_TO_RGB["orange"],
            scale=font_scale,
            anchor_point=left_anchor,
            padding_right=40
        )

        self.itime2_label = label.Label(
            fonts.font_10pt,
            text="time xxxms",
            color=constants.COLOR_TO_RGB["orange"],
            scale=font_scale,
            anchor_point=left_anchor,
            padding_right=40
        )

        self.bat_label = label.Label(
            fonts.font_10pt,
            text="battery 0.0V",
            color=constants.COLOR_TO_RGB["gray"],
            scale=font_scale,
            anchor_point=(0.5, 1.0),
            padding_right=40
        )

        self.group.append(self.tile_grid)
        self.group.append(self.header1_label)
        self.group.append(self.value1_label)
        self.group.append(self.gain1_label)
        self.group.append(self.itime1_label)
        self.group.append(self.header2_label)
        self.group.append(self.value2_label)
        self.group.append(self.gain2_label)
        self.group.append(self.itime2_label)
        self.group.append(self.bat_label)

        self.header_labels = (self.header1_label, self.header2_label)
        self.value_labels = (self.value1_label, self.value2_label)

        self._position_labels()
        gc.collect()

    def clear(self):
        while len(self.group) > 0:
            self.group.pop()
        self.bitmap = None
        self.palette = None
        self.tile_grid = None
        self.header1_label = None
        self.value1_label = None
        self.gain1_label = None
        self.itime1_label = None
        self.header2_label = None
        self.value2_label = None
        self.gain2_label = None
        self.itime2_label = None
        self.bat_label = None
        self.group = displayio.Group()
        self.header_labels = None
        self.value_labels = None
        self.selected_sensor = None
        self.selected_sensor_cycle = None
        if board.DISPLAY.root_group == self.group:
            board.DISPLAY.root_group = None
        gc.collect()

    @property
    def has_selected_sensor(self):
        return True

    def setup_selected_sensor_cycle(self):
        select_sensor_values = [None] + self.SENSOR_INDICES
        self.selected_sensor_cycle = adafruit_itertools.cycle(select_sensor_values)
        while next(self.selected_sensor_cycle) != self.selected_sensor:
            continue

    def selected_sensor_next(self):
        self.selected_sensor = next(self.selected_sensor_cycle)

    def set_measurement(self, measurement):
        measurement_items = (
            self.SENSOR_INDICES,
            measurement.label,
            measurement.value,
            self.header_labels,
            self.value_labels,
        )
        for index, name, value, header_label, value_label in zip(*measurement_items):
            if index == self.selected_sensor:
                mark = '|'
            else:
                mark = ' '
            header_label.text = f'{mark}{name}'
            if measurement.units is None:
                if isinstance(value, float):
                    value_text = f'{value:1.2f}'
                else:
                    value_text = f'{value}'
            else:
                if isinstance(value, float):
                    value_text = f'{value:1.2f} {measurement.units}'
                else:
                    value_text = f'{value} {measurement.units}'
            value_label.text = value_text.replace('0', 'O')
            if value == constants.OVERFLOW_STR:
                color = constants.COLOR_TO_RGB['red']
            else:
                color = constants.COLOR_TO_RGB['white']
            value_label.color = color

        self._position_labels()

    def set_gain(self, values):
        labels = (self.gain1_label, self.gain2_label)
        for value, label in zip(values, labels):
            if value is not None:
                value_str = constants.GAIN_TO_STR[value]
                label.text = f'gain={value_str}'
            else:
                label.text = ''

        self._position_labels()

    def set_integration_time(self, values):
        labels = (self.itime1_label, self.itime2_label)
        for value, label in zip(values, labels):
            if value is not None:
                value_str = constants.INTEGRATION_TIME_TO_STR[value]
                label.text = f'time={value_str}'
            else:
                label.text = ''

        self._position_labels()

    def set_bat(self, value):
        self.bat_label.text = f'battery {value:1.1f}V'
        self._position_labels()

    def show(self):
        if self.group:
            board.DISPLAY.root_group = self.group

    def update(self, measurement, battery_monitor):
        self.set_measurement(measurement)
        self.set_gain((
            measurement.sensor_90.gain,
            measurement.sensor_180.gain,
        ))
        self.set_integration_time((
            measurement.sensor_90.integration_time,
            measurement.sensor_180.integration_time,
        ))
        self.set_bat(battery_monitor.voltage_lowpass)

    def _get_active_labels(self):
        active_labels = []
        line_count = 0
        labels = [
            self.header1_label,
            self.value1_label,
            self.gain1_label,
            self.itime1_label,
            self.header2_label,
            self.value2_label,
            self.gain2_label,
            self.itime2_label
        ]

        for label in labels:
            if label.text and label.text.strip():
                active_labels.append(label)
                if label not in (self.value1_label, self.itime1_label, self.value2_label, self.itime2_label):
                    line_count += 1

        return active_labels, line_count

    def _position_labels(self):
        active_labels, line_count = self._get_active_labels()

        bat_height = self.bat_label.bounding_box[self.BBOX_HEIGHT_INDEX]
        bat_y = board.DISPLAY.height - self.BOTTOM_MARGIN
        self.bat_label.anchored_position = (board.DISPLAY.width // 2, bat_y)

        header1_height = self.header1_label.bounding_box[self.BBOX_HEIGHT_INDEX]
        header1_y = self.TOP_MARGIN + header1_height
        self.header1_label.anchored_position = (self.LEFT_MARGIN, header1_y)

        available_height = board.DISPLAY.height - header1_y - bat_height - self.BOTTOM_MARGIN
        total_label_height = sum(
            label.bounding_box[self.BBOX_HEIGHT_INDEX]
            for label in active_labels
            if label not in (self.header1_label, self.value1_label, self.itime1_label, self.header2_label, self.value2_label, self.itime2_label)
        )
        spacing = (available_height - total_label_height - self.HEADER_SPACING) / (line_count + 1) if line_count > 0 else 0

        current_y = header1_y
        for label in active_labels:
            if label is self.header1_label:
                self.header1_label.anchored_position = (self.LEFT_MARGIN, current_y)
            elif label is self.value1_label:
                self.value1_label.anchored_position = (board.DISPLAY.width - self.RIGHT_MARGIN, current_y)
            elif label is self.gain1_label:
                label_height = label.bounding_box[self.BBOX_HEIGHT_INDEX]
                current_y += spacing + label_height
                self.gain1_label.anchored_position = (self.LEFT_MARGIN, current_y)
            elif label is self.itime1_label:
                self.itime1_label.anchored_position = (self.LEFT_MARGIN + self.GAIN_TO_ITIME_X_OFFSET, current_y)
            elif label is self.header2_label:
                label_height = label.bounding_box[self.BBOX_HEIGHT_INDEX]
                current_y += spacing + label_height + self.HEADER_SPACING
                self.header2_label.anchored_position = (self.LEFT_MARGIN, current_y)
            elif label is self.value2_label:
                self.value2_label.anchored_position = (board.DISPLAY.width - self.RIGHT_MARGIN, current_y)
            elif label is self.gain2_label:
                label_height = label.bounding_box[self.BBOX_HEIGHT_INDEX]
                current_y += spacing + label_height
                self.gain2_label.anchored_position = (self.LEFT_MARGIN, current_y)
            elif label is self.itime2_label:
                self.itime2_label.anchored_position = (self.LEFT_MARGIN + self.GAIN_TO_ITIME_X_OFFSET, current_y)