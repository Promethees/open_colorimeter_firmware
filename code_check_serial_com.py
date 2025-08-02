import usb_cdc
import time

serial = usb_cdc.data
buffer = b""

while True:
    if serial.in_waiting:
        buffer += serial.read(serial.in_waiting)
        if b"\n" in buffer:
            lines = buffer.split(b"\n")
            for line in lines[:-1]:
                command = line.decode().strip()
                print(f"Got command: {command}")  # Shows up in REPL
                response = f"ACK: {command}\n"
                serial.write(response.encode())
            buffer = lines[-1]  # Save the leftover
    time.sleep(0.05)
