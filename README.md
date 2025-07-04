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

## Requirements (Hosting System)
 * python 3
 * hidapi

## Installation (Adafruit PyBadge)

* Copy the `code.py` and all the .py files in `src` folder to the ***CIRCUITPY*** drive associated with
your feather development board. 

* Copy `assets` folder to the ***CIRCUITPY*** drive

* Copy `configuration.json`, `calibrations.json` to ***CIRCUITPY*** drive

* Copy [lib.zip](https://github.com/Promethees/open_colorimeter_firmware/blob/main/lib.zip) to ***CIRCUITPY*** Drive and unzip to get the dependencies. Note: should only have one layer of `\lib` directory (in case after unzipping, you have something like `\lib\lib`)

## Installation (Hosting System)

* See installation guide from [microalbumin-Flask](https://github.com/Promethees/microalbumin-Flask)

## Navigation (Adafruit PyBadge)
### Menu
* How should it look like <img src="/images/Menu.jpeg" width="100">. 
* On the Colorimeter Device, use Up, Down buttons to navigate, Menu (white button on the top left), Left and Right to select the respective item.

### Measure
* How should it look like <img src="/images/Measure.jpeg" width="100">.
* Define and modify the setup parameters for this mode in `calibrations.json`. 
* Left button is designated to send data to the host machine, ***BEFORE*** attempt to do so, please read the rest of this passage thoroughly!

<img src="images/warning.svg" alt="IMPORTANT WARNING!!!">

* The mechanism of sending message from the Colorimeter (Adafruit PyBadge) to the host computer is akin to having a ***keyboard*** typing to your computer. To read the data sent, we either do:
	- **Recommended**: Navigate to [Web interface](https://github.com/Promethees/microalbumin-Flask/blob/main/README.md) instruction to run **log_hid_data.py** for more details.
	- If you wish to read the raw data sent by the PyBadge, please create a text file with the active cursor in it <img src="/images/sendingmsgs.gif" width="200">, but your computer is now "controlled" by the PyBadge unless you stop the Message sending by clicking the Left button again.
	- Execute `log_hid_data.py` (follow the instruction below) to prevent the aformentioned phenomenon and save data to desired location on your computer in csv format.

### Message
* Has two forms, About <img src="/images/About.jpeg" width="100"> and Error <img src="/images/Error.jpeg" width="100">. Press any button to get back to Menu mode.

### Settings
* Usage: to set timeout period for data collection as well as sampling rate.
* Values: can be initialized by configuration.json: [](/images/config.png), else will be set by default values in `constants.py` [](/images/DefaultTimings.png)
* Accessible as he last menu item. Layout: [](/images/TimingSettings.jpeg). Yellow line is the currently chosen values to get modified
* Buttons: 
	- `Right`: Switching between 2 selected lines of modification
	- `Up/Down`: Increase/Decrease the value of the current line (for units `min`, `hour`, step is 1; for `sec`, step is 10)
	- `Left`: Discard changes made, get back to Menu 
	- `Menu`: Save the changes made, validate values set
	- `Blank`: Discard all the changes made, remain in Settings
	- `A`: Change the units of the selected line
	- `B`: Set `Timeout value` to `Infinite` (so ```self.timeout_value = None```)

## Running *log_hid_data.py* to record the data sent from PyBadge (Hosting System)
* Data recorded will be saved in `\data` folder by default
* Now is available to execute on the web interface so this step becomes ***optional***

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
<img src="images/important.svg" alt="IMPORTANT!!!">

* In case you have any issue with the **CIRCUITPY** drive (either it's no writtable or not found), you might want to backup data somewhere else.
Then do the following steps:

- Double click on **Reset** button (at the behind of the colorimeter) to enter boot mode <img src="/images/Pybadgeboot.jpeg" width="100">.
- In boot mode, a drive called ***PYTHONBADGE*** will appear instead of ***CIRCUITPY***. Drag `PyBadge_QSPI_Eraser.UF2` to this drive. 
- The display on the Colorimeter should be blank now, double click **Reset** to enter boot mode with ***PYTHONBADGE*** again. Drag `circuitpython 9.uf2` to this drive.
- This process helps reset the Drive to default mode (please don't get caught by surprise when you see ***CIRCUITPY*** is now cleaned as new)
- Go back to [Installation](#installation-adafruit-pybadge) to get the latest code uploaded.

