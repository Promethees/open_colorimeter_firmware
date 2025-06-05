# Open Colorimeter Firmware for low-cost MicroAlbumin measurement 

![alt text](/images/open_colorimeter.png)

This document provides details of our solution for a low-cost, handy MicroAlbumin measurement based on [IORodeo Open Colorimeter](https://iorodeo.com/products/open-colorimeter) 

## Requirements (Adafruit PyBadge)

* circuitpython >= 9.2.7
* adafruit_bitmap_font
* adafruit_bus_device
* adafruit_display_text
* adafruit_tsl2591
* adafruit_hid
* adafruit_display_shapes
* adatfruit_itertools

Copy [lib.zip](https://github.com/Promethees/open_colorimeter_firmware/blob/main/lib.zip) to ***CIRCUITPY*** Drive and unzip to get the dependencies.

## Requirements (Hosting System)
 * python 3
 * hidapi

## Installation (Adafruit PyBadge)

* Copy the `code.py` and all the .py files in `src` folder to the ***CIRCUITPY*** drive associated with
your feather development board. 

* Copy `assets` folder to the ***CIRCUITPY*** drive

* Copy `configuration.json`, `calibrations.json` to ***CIRCUITPY*** drive

## Installation (Hosting System)

### MacOS
* Open your terminal, navigate to the root folder, type in `chmod +x install_macos.sh` then `./install_macos.sh` to install the dependencies. 
This helps install `homebrew`, `python`, `pip`, `hidapi`. 

### Windows
* Right click on `install_windows.sh` > "Run as Administrator" or launch it in **Administrator Command Prompt** 

## Running *log_hid_data.py* to record the data sent from PyBadge (Hosting System)
Data recorded will be saved in `\data` folder

### MacOS
* Compile the code by: `chmod +x log_hid_data.py`, then run with administrator right (important!) `sudo python3 log_hid_data.py`

### Windows 
* Open **Start** Menu, type `cmd`, right click > "Run as Administrator", key in `cd C:\Path\To\Your\Script`. Execute by `python log_hid_data.py`

## Checking `usb_hid` availability (Adafruit PyBadge)
* Rename `code_check_keyboardHID.py` to `code.py`. If on the screen print out `HID enabled: True`, this means the `usb_hid` is available.
* Otherwise, rename `boot_forHID.py` to `boot.py`. Click on Reset button behind the Colorimeter <img src="/images/Reset_button.jpeg" width="100"> to reboot
* After rebooting, the `code.py` (orifinally `code_check_keyboardHID`) should print out `HID enabled: True`
* Then, you can use `usb_hid` as usual

## Debug (Adafruit PyBadge)
* In case you have any issue with the **CIRCUITPY** drive (either it's no writtable or not found), you might want to backup data somewhere else.
Then do the following steps:

- Double click on **Reset** button to enter boot mode
- In boot mode, a drive called ***PYTHONBADGE*** will appear instead of ***CIRCUITPY***. Drag `PyBadge_QSPI_Eraser.UF2` to this drive. 
- The display on the Colorimeter should be blank now, double click **Reset** to enter boot mode with ***PYTHONBADGE*** again. Drag `circuitpython 9.uf2` to this drive.
- This process helps reset the Drive to default mode (please don't get caught by surprise when you see ***CIRCUITPY*** is now cleaned as new)

