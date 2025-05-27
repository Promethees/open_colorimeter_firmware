import usb_hid
import storage
try:
    with open("/test.txt", "w") as f:
        f.write("Filesystem is writable\n")
    print("Filesystem is writable")
except OSError as e:
    print("Filesystem is read-only:", str(e))
print("HID enabled:", usb_hid.devices is not None)
print("CircuitPython Version:", __import__("sys").version)
while True:
    pass