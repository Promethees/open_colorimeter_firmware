import hid
import time
import os
import re
import glob
import threading
import queue

class HIDDataCollector:
    def __init__(self, base_dir, vid=0x239A, pid=0x8034, base_name="colorimeter_data", extension=".csv"):
        self.base_dir = base_dir
        self.vid = vid  # Adafruit VID
        self.pid = pid  # PyBadge PID (confirmed as 0x8034)
        self.base_name = base_name
        self.extension = extension
        self.output_file = None
        self.running = True
        self.buffer = ""
        self.header_pattern = r"^Timestamp,Measurement,Value,Units,Type\n$"
        self.data_pattern = r"^\d+\.\d{2},[A-Za-z]+,\d+\.\d{2},[,\w]*,[,\w]*\n$"
        self.session_started = False
        self.data_queue = queue.Queue()
        self.device = None

    def find_device(self):
        """Find and open the PyBadge HID device."""
        try:
            # Debug: List all HID devices before attempting to open
            print("Enumerating HID devices:")
            devices = hid.enumerate()
            for dev in devices:
                print(f"VID: {dev['vendor_id']:04x}, PID: {dev['product_id']:04x}, Product: {dev['product_string']}")
                if dev['vendor_id'] == self.vid and dev['product_id'] == self.pid:
                    print("PyBadge found!")

            self.device = hid.device()
            self.device.open(self.vid, self.pid)  # Use positional arguments
            print(f"Successfully opened HID device (VID={self.vid:04x}, PID={self.pid:04x})")
            return self.device
        except Exception as e:
            print(f"Error opening HID device (VID={self.vid:04x}, PID={self.pid:04x}): {e}")
            return None

    def read_hid_data(self):
        """Read data from the HID device and put it in the queue."""
        if not self.find_device():
            print("PyBadge not found. Stopping.")
            self.running = False
            return

        try:
            while self.running:
                data = self.device.read(64, timeout_ms = 5000)  # Read 64-byte report (blocks until data is available)
                if data:
                    print(f"Raw data received: {data}")  # Debug raw data
                    # Convert bytes to string, stopping at first null byte
                    data_str = bytes(data).rstrip(b'\x00').decode('ascii', errors='ignore')
                    print(f"Data string is: {data_str}")
                    if data_str:
                        self.data_queue.put(data_str)
                time.sleep(0.01)  # Small sleep to prevent CPU overload
        except Exception as e:
            print(f"HID read error: {e}")
        finally:
            if self.device:
                self.device.close()

    def process_data(self, data_str):
        """Process received data, handling headers and data lines."""
        self.buffer += data_str  # Append data to buffer
        # Process complete lines
        if '\n' in self.buffer:
            lines = self.buffer.split('\n')
            for line in lines[:-1]:
                line_with_newline = line + '\n'
                if self.is_header(line_with_newline):
                    self.handle_header()
                    self.session_started = True
                elif self.is_valid_data(line_with_newline) and self.session_started:
                    self.handle_data(line_with_newline)
            self.buffer = lines[-1]  # Keep the last incomplete line

    def is_header(self, line):
        return bool(re.match(self.header_pattern, line))

    def is_valid_data(self, line):
        return bool(re.match(self.data_pattern, line))

    def handle_header(self):
        """Generate a new filename and write the header."""
        self.output_file = self.get_next_filename()
        os.makedirs(self.base_dir, exist_ok=True)
        with open(self.output_file, "w") as f:
            f.write("Timestamp,Measurement,Value,Units,Type\n")
        print(f"New session started. Header written to {self.output_file}")

    def handle_data(self, data):
        """Append data to the current output file."""
        try:
            timestamp, measurement_name, value, units, type_tag = data.strip().split(',')
            print(f"Received: Timestamp: {timestamp}s, Measurement: {measurement_name}, Value: {value} {units}, Type: {type_tag}")
            with open(self.output_file, "a") as f:
                f.write(data)
        except ValueError as e:
            print(f"Error parsing data: {e}")

    def get_next_filename(self):
        """Generate the next filename based on existing files."""
        pattern = os.path.join(self.base_dir, f"{self.base_name}_*[0-9].csv")
        existing_files = glob.glob(pattern)
        number_pattern = re.compile(rf"{self.base_name}_(\d+)\.csv$")
        numbers = []
        for file in existing_files:
            match = number_pattern.search(os.path.basename(file))
            if match:
                numbers.append(int(match.group(1)))
        next_number = max(numbers, default=0) + 1
        return os.path.join(self.base_dir, f"{self.base_name}_{next_number}{self.extension}")

    def start(self):
        """Start the HID data collector."""
        print(f"Starting HID data collector (VID={self.vid:04x}, PID={self.pid:04x}). Press Ctrl+C to stop.")
        # Start HID reading in a separate thread
        hid_thread = threading.Thread(target=self.read_hid_data)
        hid_thread.daemon = True
        hid_thread.start()

        try:
            while self.running:
                try:
                    # Process data from the queue
                    data_str = self.data_queue.get()  # Blocks until data is available
                    self.process_data(data_str)
                except queue.Empty:
                    pass  # Should not occur with get(), but kept for robustness
                time.sleep(0.01)
        except KeyboardInterrupt:
            print("Stopping HID data collector.")
            self.running = False
        finally:
            hid_thread.join(timeout=1.0)
            print("HID data collector stopped.")

if __name__ == "__main__":
    base_dir = os.path.join(os.getcwd(), "../data")
    collector = HIDDataCollector(base_dir, vid=0x239A, pid=0x8034)
    collector.start()