import serial
import serial.tools.list_ports
import time

def find_pybadge_port():
    """Find the serial port where PyBadge is connected"""
    pybadge_vid = 0x239A  # Adafruit's vendor ID
    pybadge_pid = 0x8034
    for port in serial.tools.list_ports.comports():
        if port.vid == pybadge_vid and port.pid == pybadge_pid:
            return port.device
    return None

def communicate_with_pybadge():
    port = find_pybadge_port()
    if not port:
        print("PyBadge not found. Please ensure it's connected via USB.")
        return
    
    print(f"Found PyBadge at {port}")
    
    with serial.Serial(port, baudrate=115200, timeout=1) as ser:
        time.sleep(2)  # Wait for connection
        
        # Clear any existing output
        ser.reset_input_buffer()
        
        while True:
            user_input = input("Enter command (red/green/blue/off/quit): ")

            if user_input.lower() == 'quit':
                break

            ser.write((user_input + "\n").encode())
            time.sleep(0.1)

            response = b""
            timeout = time.time() + 1  # wait up to 1 second
            while time.time() < timeout:
                if ser.in_waiting:
                    response += ser.read(ser.in_waiting)
                if response.endswith(b"\n"):
                    break
                time.sleep(0.05)

            if response:
                print("Response from PyBadge:", response.decode().strip())
            else:
                print("No response received.")

if __name__ == "__main__":
    communicate_with_pybadge()