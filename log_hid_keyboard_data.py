import pynput
from pynput.keyboard import Key, Listener
import time
import os
import sys
import re
import glob

class HIDDataCollector:
    def __init__(self, base_dir, base_name="colorimeter_data", extension=".csv"):
        self.base_dir = base_dir
        self.base_name = base_name
        self.extension = extension
        self.output_file = None  # Will be set in handle_header
        self.running = True
        self.buffer = ""
        self.header_pattern = r"^Timestamp,Measurement,Value,Units,Type\n$"
        self.data_pattern = r"^\d+\.\d{2},[A-Za-z]+,\d+\.\d{2},[,\w]*,[,\w]*\n$"
        self.session_started = False  # Track if a new session has started

    def on_press(self, key):
        try:
            # Handle printable characters
            if hasattr(key, 'char') and key.char is not None:
                self.buffer += key.char
            # Handle Enter key (maps to \n)
            elif key == Key.enter:
                self.buffer += '\n'
                # Process the buffer when a newline is received
                lines = self.buffer.split('\n')
                for line in lines[:-1]:
                    line_with_newline = line + '\n'
                    if self.is_header(line_with_newline):
                        self.handle_header()
                        self.session_started = True
                    elif self.is_valid_data(line_with_newline) and self.session_started:
                        self.process_data(line_with_newline)
                self.buffer = lines[-1]
        except AttributeError:
            pass

    def on_release(self, key):
        if key == Key.esc:
            self.running = False
            return False  # Stop the listener

    def is_header(self, line):
        return bool(re.match(self.header_pattern, line))

    def is_valid_data(self, line):
        return bool(re.match(self.data_pattern, line))

    def handle_header(self):
        # Generate a new filename for the session
        self.output_file = self.get_next_filename()
        # Ensure the directory exists
        os.makedirs(self.base_dir, exist_ok=True)
        # Write the header to the new file
        with open(self.output_file, "w") as f:
            f.write("Timestamp,Measurement,Value,Units,Type\n")
        print(f"New session started. Header written to {self.output_file}")

    def process_data(self, data):
        try:
            timestamp, measurement_name, value, units, type_tag = data.strip().split(',')
            print(f"Received: Timestamp: {timestamp}s, Measurement: {measurement_name}, Value: {value} {units}, Type: {type_tag}")
            # Append measurement data to the current output file
            with open(self.output_file, "a") as f:
                f.write(data)
        except ValueError as e:
            print(f"Error parsing data: {e}")

    def get_next_filename(self):
        # Find all files matching the pattern in the directory
        pattern = os.path.join(self.base_dir, f"{self.base_name}_*[0-9].csv")
        existing_files = glob.glob(pattern)
        
        # Extract numbers from filenames
        number_pattern = re.compile(rf"{self.base_name}_(\d+)\.csv$")
        numbers = []
        for file in existing_files:
            match = number_pattern.search(os.path.basename(file))
            if match:
                numbers.append(int(match.group(1)))
        
        # Determine the next number
        next_number = max(numbers, default=0) + 1
        
        # Form the new filename
        return os.path.join(self.base_dir, f"{self.base_name}_{next_number}{self.extension}")

    def start(self):
        print(f"Starting HID data collector. Press Esc to stop.")
        with Listener(on_press=self.on_press, on_release=self.on_release) as listener:
            listener.join()
        print("Stopped HID data collector.")

if __name__ == "__main__":
    base_dir = os.path.join(os.getcwd(), "../data")
    collector = HIDDataCollector(base_dir)
    collector.start()