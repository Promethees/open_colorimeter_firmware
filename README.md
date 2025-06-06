# Open Colorimeter Firmware for Easy Sensor for colorimetric assay 

![alt text](/images/open_colorimeter.png)

This document provides details of our solution for a low-cost, handy colorimetric assay based on [IORodeo Open Colorimeter](https://iorodeo.com/products/open-colorimeter) 

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

## Navigation (Adafruit PyBadge)
### Menu
* How should it look like <img src="/images/Menu.jpeg" width="100">. 
* On the Colorimeter Device, use Up, Down buttons to navigate, Menu (white button on the top left), Left and Right to select the respective item.

### Measure
* How should it look like <img src="/images/Measure.jpeg" width="100">.
* Define and modify the setup parameters for this mode in `calibrations.json`. 
* Left button is designated to send data to the host machine, ***BEFORE*** attempt to do so, please read the rest of this passage thoroughly!. WARNING: The mechanism of sending message from the Colorimeter (Adafruit PyBadge) to the host computer is akin to having a ***keyboard*** typing to your computer. To read the data sent, we either do:
- If you wish to read the raw data sent by the PyBadge, please create a text file with the active cursor in it <img src="/images/sendingmsgs.gif" width="200">, but your computer is now "controlled" by the PyBadge unless you stop the Message sending by clicking the Left button again.
- Execute `log_hid_data.py` (follow the instruction below) to prevent the aformentioned phenomenon and save data to desired location on your computer in csv format.

### Message
* Has two forms, About <img src="/images/About.jpeg" width="100"> and Error <img src="/images/Error.jpeg" width="100">. Press any button to get back to Menu mode.

## Running *log_hid_data.py* to record the data sent from PyBadge (Hosting System)
Data recorded will be saved in `\data` folder by default

### MacOS
* Compile the code by: `chmod +x log_hid_data.py`, then run with administrator right (important!) 
* `sudo python3 log_hid_data.py` to save recorded file to `data` folder in the same location with the name format of `colorimeter_data_xx.csv` by default
* To modify the saving location and file name's format, use this syntax `sudo python3 log_hid_data.py --base-dir </path/to/saving/location> --base-name <>` 
* Example: In terminal, execute `sudo python3 log_hid_data.py --base-dir /Users/tqmthong/Desktop/data --base-name hello`
* Understand the log: 
- This verifies that the PyBadge is found with correct VID (vendor ID), PID (product ID) set <img src="/images/foundPyBadge.png">
- When you press Left button on the PyBadge, the host computer recognise and create Folder for it <img src="/images/firstLocation.png">
- `log_hid_data.py` then echoes data sent by PyBadge to the host computer <img src="/images/DataSent.png">
- You stop, then press again, `log_hid_data.py` will automatically knows to rename the saving file to avoid overwritten (hello_1 instead of hello_0) <img src="/images/secondLocation.png">

### Windows 
* Open **Start** Menu, type `cmd`, right click > "Run as Administrator", key in `cd C:\Path\To\Your\Script`. Execute by `python log_hid_data.py` to save to `data` with filename format of `colorimeter_data_xx.csv`
* `python log_hid_data.py --base-dir <> --base-name <>` to specify your desired location and naming convention.

### Changing Transmission interval and data recording time (Adafruit PyBadge)
* We can modify those parameters by modifying values of `DATA_TRANSMISSION_INTERVAL` (in seconds) and TIMEOUT_IN_MINUTES `src/constant.py` in the ***CIRCUITPY*** drive
* After changing them, and save the file, PyBadge'll automatically load these changes to the code

### (Optional) Syncing in real-time read data to Google Drive.
* Download Google Drive Desktop application from [](https://support.google.com/a/users/answer/13022292?hl=en)
* Create an empty folder on local computer to host the synced folder to Google Drive.
* Open Google Drive Desktop applications, sign in, select **Settings** (the Gear Icon) > **Preferences**. We now have **Google Drive Preferences** panel opening <img src="/images/Drive_Preferences.png" width="200">. Select **Add Folder** to select the just created empty Folder for syncing. 
* Retrieving directory name of the synced folder: On Windows, open it in File Explorer, get the path on the File Browser search bar. On Mac, locate the folder in **Finder**, right click on the folder, go to "Services" (last row)> "New Terminal at Folder", type ```pwd``` in the Terminal to get the path.
* Set `--base-dir` to the path to the synced Drive folder

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

