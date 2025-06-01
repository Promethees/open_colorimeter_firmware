import hid
import time
import os
import re
import glob
import threading
import queue

class HIDDataCollector:
    def __init__(self, base_dir, vid=0x239A, pid=0x8034, base_name="colorimeter_data", extension=".csv", read_timeout=5.0):
        self.base_dir = base_dir
        self.vid = vid  # Adafruit VID
        self.pid = pid  # PyBadge PID
        self.base_name = base_name
        self.extension = extension
        self.output_file = None
        self.running = True
        self.buffer = ""
        self.header_pattern = r"^Timestamp,Measurement,Value,Units,Type\n$"
        self.data_pattern = r"^\d+\.\d{2},[A-Za-z]+,\d+\.\d{2},[,\w]*,[,\w]*\n$"
        self.session_started = False
        self.data_queue = queue.Queue()
        self.read_timeout = read_timeout  # Increased timeout to catch reports
        self.handshake_received = False

    def find_device(self):
        """Find the PyBadge HID device."""
        print("Enumerating all HID devices:")
        for device in hid.enumerate():
            print(f"VID: {device['vendor_id']:04x}, PID: {device['product_id']:04x}, "
                  f"Product: {device['product_string']}, Path: {device['path']}")
            if device['vendor_id'] == self.vid and device['product_id'] == self.pid:
                print(f"Found target device: {device['product_string']} at path {device['path']}")
                try:
                    dev = hid.device()
                    dev.open_path(device['path'])
                    dev.set_nonblocking(1)  # Set non-blocking mode
                    print("Device opened successfully in non-blocking mode.")
                    return dev
                except Exception as e:
                    print(f"Error opening device: {e}")
                    return None
        print(f"No device found with VID={self.vid:04x}, PID={self.pid:04x}")
        return None

    def wait_for_handshake(self, device):
        """Wait for the 'Hello' report from the PyBadge to start data collection."""
        print("Waiting for handshake signal ('Hello') from PyBadge...")
        while self.running and not self.handshake_received:
            read_time = time.time()
            data = device.read(64, timeout_ms=int(self.read_timeout * 1000))
            print(f"Read attempt at {read_time:.3f}s")
            if data is not None and len(data) > 0:
                print(f"Raw data received at {read_time:.3f}s: {data}")
                data_str = bytes(data).rstrip(b'\x00').decode('ascii', errors='ignore')
                if data_str == "Hello":
                    print("Handshake received: 'Hello' report detected.")
                    self.handshake_received = True
                    break
            else:
                print("No data received, waiting for handshake...")
            time.sleep(0.1)  # Small sleep to prevent excessive polling

    def read_hid_data(self):
        """Read data from the HID device and put it in the queue after handshake."""
        device = self.find_device()
        if not device:
            print("PyBadge not found. Stopping.")
            self.running = False
            return

        try:
            while self.running:
                # Wait for handshake if not yet received
                if not self.handshake_received:
                    self.wait_for_handshake(device)
                    if not self.handshake_received:
                        print("Handshake failed. Stopping.")
                        break

                print("Starting data collection after successful handshake.")
                while self.handshake_received and self.running:
                    read_time = time.time()
                    data = device.read(64, timeout_ms=int(self.read_timeout * 1000))
                    print(f"Read attempt at {read_time:.3f}s")
                    if data is not None and len(data) > 0:
                        print(f"Raw data received at {read_time:.3f}s: {data}")
                        data_str = bytes(data).rstrip(b'\x00').decode('ascii', errors='ignore')
                        if data_str == "Goodbye":
                            print("Goodbye report received. Ending data collection session.")
                            self.handshake_received = False
                            self.session_started = False
                            self.buffer = ""
                            break
                        if data_str:
                            self.data_queue.put(data_str)
                    else:
                        print("No data received, retrying...")
                    time.sleep(0.1)  # Small sleep to prevent excessive polling
        except Exception as e:
            print(f"Error reading HID data: {e}")
        finally:
            device.close()
            print("HID device closed.")

    def process_data(self, data_str):
        """Process received data, handling headers and data lines."""
        self.buffer += data_str
        if '\n' in self.buffer:
            lines = self.buffer.split('\n')
            for line in lines[:-1]:
                line_with_newline = line + '\n'
                if self.is_header(line_with_newline):
                    self.handle_header()
                    self.session_started = True
                elif self.is_valid_data(line_with_newline) and self.session_started:
                    self.handle_data(line_with_newline)
            self.buffer = lines[-1]

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
        next_number = max(numbers, default=-1) + 1
        return os.path.join(self.base_dir, f"{self.base_name}_{next_number}{self.extension}")

    def start(self):
        """Start the HID data collector."""
        print(f"Starting HID data collector (VID={self.vid:04x}, PID={self.pid:04x}). Press Ctrl+C to stop.")
        hid_thread = threading.Thread(target=self.read_hid_data)
        hid_thread.daemon = True
        hid_thread.start()

        try:
            while self.running:
                try:
                    data_str = self.data_queue.get(timeout=1.0)
                    self.process_data(data_str)
                except queue.Empty:
                    pass
                except Exception as e:
                    print(f"Error processing queue: {e}")
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