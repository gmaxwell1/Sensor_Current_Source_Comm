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
6. install required packages using `pip install ...`: `numpy, pyserial, pythonnet, matplotlib, pandas, pyUSB, python-usbtmc, scikit-learn`

* **Prepare devices for use (Windows):**
1. If using the Metrolab sensor: Plug in the device and install `libusb-win32` driver using [Zadig](https://zadig.akeo.ie/).
    Otherwise, comment out all dependencies and function calls having to do with the sensor. Mainly in core/magnet_control_funcitons.py
    and core/measurement_functions.py
2. Using Temperature Sensors: 

## Notes:
If you are using an IDE, make sure to choose the `python.exe` file in your virtual environment as an interpreter!
