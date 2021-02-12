"""
filename: 2d_scan.py

This script is meant to perform a 2d scan of the magnetic field using a single sensor,
specifically for use with the Hall Sensor cube.

Author: Nicholas Meinhardt (QZabre)
        nmeinhar@student.ethz.ch


Date: 13.10.2020
"""

import os
from time import sleep, time

# %%
########## Standard library imports ##########
import numpy as np
import serial

########## local imports ##########
try:
    from conexCC.conexcc_control import reset_to, setup
except ModuleNotFoundError:
    import sys
    sys.path.insert(1, os.path.join(sys.path[0], '..'))
finally:
    from conexCC.conexcc_control import reset_to, setup
    from core.current_control import PowerSupplyCommands
    from metrolabTHM1176.thm1176 import MetrolabTHM1176Node

    from stage_setup.calibration import grid_2D

# %%
# set measurement parameters and folder name
sampling_size = 20  # number of measurements per sensor for averaging

directory = r'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\1_data_analysis_interpolation\Data_Analysis_For_VM\data_sets\2d_scans_different_fields\set7'

# number of grid points per dimension
grid_number = 16

# %%
# initialize actuators
init_pos = np.array([11, 4, 11.8])
# ports for Magnebotix PC
COM_ports = ['COM4', 'COM5', 'COM6']
CC_X, CC_Y, CC_Z = setup(init_pos, COM_ports=COM_ports)


# %%
# manually adjust stage position
# z_offset = 8.3
# new_pos =
# _ = reset_to(new_pos, CC_X, CC2=CC_Y, CC3=CC_Z)


# %%
# set the bounds for x and y that are used for the scan
limits_x = [7, 15]
limits_y = [0, 8]

# set the bounds for x and y that are used for the scan, relative to mid position
# mid = [7.8866, 0.0166]
# distance = 2
# limits_x = [mid[0] - distance, mid[0] + distance]
# limits_y = [0, 4]
# set currents in coils
currentConfig = [1, 1, 1]
# integer value, mA
currentStrength = 2

desCurr = []
for i in range(len(currentConfig)):
    desCurr.append(currentStrength * currentConfig[i])
print(f'the currents are: {desCurr[0]} A, {desCurr[1]} A, {desCurr[2]} A')

psu = PowerSupplyCommands()
psu.openConnection()
sleep(0.3)
psu.setCurrents(desCurr)

# %%
# perform actual 2d scan
# with MetrolabTHM1176Node(block_size=30, period=0.01, range='0.3 T', average=1) as node:
node = MetrolabTHM1176Node(block_size=30, period=0.01, range='0.1 T', average=1)

filename_suffix = f'2d_scan_({currentConfig[0]}_{currentConfig[1]}_{currentConfig[2]})'
positions_corrected, B_field, filepath = grid_2D(CC_X, CC_Y, node, 11.8, xlim=limits_x, ylim=limits_y, grid_number=grid_number,
                                                 sampling_size=sampling_size, save_data=True, suffix=filename_suffix, directory=directory)
psu.demagnetizeCoils()

psu.closeConnection()

# %%
# this part uses the Calibration Cube as Sensor
# --------------------------------------------------------------------

# # initialize sensor
# specific_sensor = 55
# port_sensor = 'COM4'

# # establish permanent connection to calibration cube: open serial port; baud rate = 256000
# with serial.Serial(port_sensor, 256000, timeout=2) as cube:

#     positions_corrected, B_field, filepath = grid_2D_cube(CC_X, CC_Y, cube, specific_sensor, z_offset,
#                                       xlim=limits_x, ylim=limits_y, grid_number=grid_number,
# sampling_size=sampling_size, save_data=True, directory=directory)
