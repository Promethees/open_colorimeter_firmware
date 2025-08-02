import usb_cdc
import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS

# Disable USB CDC to prevent read-only filesystem
# usb_cdc.disable()

# Enable USB HID with keyboard device
keyboard = Keyboard(usb_hid.devices)
layout = KeyboardLayoutUS(keyboard)
usb_hid.enable((keyboard,))
import usb_cdc
usb_cdc.enable(console=False, data=True)