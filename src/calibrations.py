import os
import ulab
import json
import constants
from collections import OrderedDict
from json_settings_file import JsonSettingsFile

class CalibrationsError(Exception):
    pass

class Calibrations(JsonSettingsFile):

    FILE_TYPE = 'calibrations'
    FILE_NAME = constants.CALIBRATIONS_FILE
    LOAD_ERROR_EXCEPTION = CalibrationsError
    ALLOWED_FIT_TYPES = ['linear', 'polynomial']

    def __init__(self):
        super().__init__()

    def check(self):
        # Check each calibration for errors
        for name, calibration in self.data.items():
            error_list = []
            error_list.extend(self.check_fit(name, calibration))
            error_list.extend(self.check_range(name, calibration))
            if error_list:
                self.error_dict[name] = error_list

        # Remove calibrations with errors
        for name in self.error_dict:
            del self.data[name]

    def check_fit(self, name, calibration): 
        error_list = []
        try:
            fit_type = calibration['fit_type']
        except KeyError:
            fit_type = None
            error_msg = f'{name} missing fit_type'
            error_list.append(error_msg)
        else:
            if not fit_type in self.ALLOWED_FIT_TYPES:
                error_msg = f'{name} unknown fit_type {fit_type}'
                error_list.append(error_msg)
        try:
            fit_coef = calibration['fit_coef']
        except KeyError:
            fit_coef = None
            error_msg = f'{name} missing fit_coef' 
            error_list.append(error_msg)
        else:
            try:
                fit_coef = ulab.numpy.array(fit_coef)
            except (ValueError, TypeError):
                error_msg = f'{name} fit coeff format incorrect'
                error_list.append(error_msg)
        if fit_type == 'linear' and fit_coef.size > 2:
            error_msg = f'{name} too many fit_coef for linear fit'
            error_list.append(error_msg)
        return error_list

    def check_range(self, name, calibration):
        error_list = []
        try:
            units = calibration['units']
        except KeyError:
            units = None
            error_msg = f'{name} missing units'
            error_list.append(error_msg)

        # Check classification and type_ranges
        classification = calibration.get('classification')
        if classification is not None:
            if not isinstance(classification, str):
                error_msg = f'{name} classification must be a string'
                error_list.append(error_msg)
                return error_list
            try:
                type_ranges = calibration['type_ranges']
            except KeyError:
                error_msg = f'{name} missing type_ranges for classification {classification}'
                error_list.append(error_msg)
                return error_list

            if not isinstance(type_ranges, list):
                error_msg = f'{name} type_ranges must be a list'
                error_list.append(error_msg)
                return error_list

            if not type_ranges:
                error_msg = f'{name} type_ranges is empty'
                error_list.append(error_msg)
                return error_list

            # Validate each range and check for overlaps or gaps
            previous_max = None
            for i, range_data in enumerate(type_ranges):
                if not isinstance(range_data, dict):
                    error_msg = f'{name} type_ranges[{i}] must be a dict'
                    error_list.append(error_msg)
                    continue

                try:
                    min_value = float(range_data['min'])
                except KeyError:
                    error_msg = f'{name} type_ranges[{i}] min missing'
                    error_list.append(error_msg)
                    continue
                except (ValueError, TypeError):
                    error_msg = f'{name} type_ranges[{i}] min not float'
                    error_list.append(error_msg)
                    continue

                try:
                    max_value = float(range_data['max'])
                except KeyError:
                    error_msg = f'{name} type_ranges[{i}] max missing'
                    error_list.append(error_msg)
                    continue
                except (ValueError, TypeError):
                    error_msg = f'{name} type_ranges[{i}] max not float'
                    error_list.append(error_msg)
                    continue

                try:
                    tag = range_data['tag']
                    if not isinstance(tag, str):
                        error_msg = f'{name} type_ranges[{i}] tag must be a string'
                        error_list.append(error_msg)
                        continue
                except KeyError:
                    error_msg = f'{name} type_ranges[{i}] tag missing'
                    error_list.append(error_msg)
                    continue

                if min_value >= max_value:
                    error_msg = f'{name} type_ranges[{i}] min >= max'
                    error_list.append(error_msg)
                    continue

                # Check for gaps or overlaps
                if previous_max is not None and min_value > previous_max:
                    error_msg = f'{name} gap between type_ranges[{i-1}] max {previous_max} and [{i}] min {min_value}'
                    error_list.append(error_msg)
                if previous_max is not None and min_value < previous_max:
                    error_msg = f'{name} overlap between type_ranges[{i-1}] max {previous_max} and [{i}] min {min_value}'
                    error_list.append(error_msg)
                previous_max = max_value

        else:
            # Validate range for non-classified calibrations
            try:
                range_data = calibration['range']
            except KeyError:
                if calibration.get('fit_type') != 'linear':
                    error_msg = f'{name} range data missing'
                    error_list.append(error_msg)
            else:
                if not isinstance(range_data, dict):
                    error_msg = f'{name} range_data must be dict'
                    error_list.append(error_msg)
                    return error_list

                try:
                    min_value = float(range_data['min'])
                except KeyError:
                    error_msg = f'{name} range min missing'
                    error_list.append(error_msg)
                except (ValueError, TypeError): 
                    error_msg = f'{name} range min not float' 
                    error_list.append(error_msg)

                try:
                    max_value = float(range_data['max'])
                except KeyError:
                    error_msg = f'{name} range max missing'
                    error_list.append(error_msg)
                except (ValueError, TypeError): 
                    error_msg = f'{name} range max not float' 
                    error_list.append(error_msg)

                if min_value is not None and max_value is not None:
                    if min_value >= max_value:
                        error_msg = f'{name} range min >= max'
                        error_list.append(error_msg)

        return error_list

    def led(self, name):
        try:
            led = self.data[name]['led']
        except KeyError:
            led = None
        return led

    def units(self, name):
        try:
            return self.data[name]['units']
        except KeyError:
            return None

    def classification(self, name):
        return self.data[name].get('classification')

    def apply(self, name, absorbance):
        fit_type = self.data[name]['fit_type']
        fit_coef = ulab.numpy.array(self.data[name]['fit_coef'])
        classification = self.data[name].get('classification')

        # Apply fit to get numeric value
        if fit_type in ('linear', 'polynomial'):
            numeric_value = ulab.numpy.polyval(fit_coef, [absorbance])[0]
        else:
            raise CalibrationsError(f'{fit_type} fit type not implemented')

        if classification is not None:
            # Return both numeric value and type tag
            try:
                type_ranges = self.data[name]['type_ranges']
            except KeyError:
                raise CalibrationsError(f'{name} missing type_ranges for classification {classification}')

            # Find the range that contains the numeric value
            type_tag = None
            for range_data in type_ranges:
                min_value = float(range_data['min'])
                max_value = float(range_data['max'])
                if min_value <= numeric_value < max_value:
                    type_tag = range_data['tag']
                    break
            if type_tag is None:
                type_tag = "Unclassified"
            return (numeric_value, type_tag)
        else:
            # Original logic for non-classified calibrations
            try:
                range_min = self.data[name]['range']['min']
                range_max = self.data[name]['range']['max']
            except KeyError:
                range_min = None
                range_max = None

            is_inside_range = True 
            if range_min is not None:
                is_inside_range &= absorbance >= range_min
            if range_max is not None:
                is_inside_range &= absorbance <= range_max

            if is_inside_range:
                return (numeric_value, None)
            else:
                return (None, None)