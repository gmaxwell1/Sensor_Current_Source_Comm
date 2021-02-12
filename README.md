# Sensor_Current_Source_Comm
For controlling a Vector Magnet with IT6432 current sources

## Instructions on how to use this package:
After cloning this repository follow these steps (this is for Windows, but it shouldn't differ too much on Linux/Unix).
* **Create a virtual environment:**
1. open your current working directory in the command line/terminal (I would recommend using _this_ folder, i.e. `.\Sensor_Current_Source_Comm\`)
2. type `virtualenv --version` and ensure that this package is installed
  (2a. if not, install it by typing `pip install virtualenv`)
3. use the command `python -m venv [environment]`, replace [environment] with any name you like
4. activate the virtual environment by typing `[environment]\Scripts\activate`
5. make sure you have the latest vesion of pip: `python -m pip install --upgrade pip`
6. install required packages using `pip install ...`: `numpy, pyserial, pythonnet, matplotlib, pandas, pyUSB, python-usbtmc, scikit-learn, pyqt5`

* **Prepare devices for use (Windows):**
1. If using the Metrolab sensor: Plug in the device and install `libusb-win32` driver using [Zadig](https://zadig.akeo.ie/).
    Otherwise, comment out all dependencies and function calls having to do with the sensor (MetrolabTHM1176Node class). Mainly in core/magnet_control_funcitons.py
    and core/measurement_functions.py
2. Using Temperature Sensors: make sure the sensor wiring conforms to the following [schematic]().
   Then run the .ino file in the "other_useful_functions" folder on the arduino board, make sure there are no errors (e.g. using the serial monitor in the arduino IDE)
   and finally run the script for collecting measurement data.
3. The IT6432 current sources must be configured to have the IP addresses `192.168.237.47, 192.168.237.48, 192.168.237.49` for coils 1, 2 and 3 respectively,
   check this by selecting "Menu" -> "System" -> "Sys Comm" -> "LAN". The IP addresses could alternatively be changed in the `IT6432Connection` class.
   Also ensure that the current sources are connected to the same local network as the computer you are working on (e.g. with a switch) -> the computer should have an
   extra Ethernet port configured to have the IP address `192.168.237.1` or similar. The gateway address also needs to be set.

## Notes:
If you are using an IDE, make sure to choose the `python.exe` file in your virtual environment as an interpreter!
