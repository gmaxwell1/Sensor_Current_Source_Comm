# filename: measurement_functions.py
#
# This script is meant to be used to measure magnetic field values with the Hall
# sensor cube/Metrolab THM1176. It is adapted to interface with the ECB, e.g. to set current values and
# measure the generated magnetic field of the vector magnet.
#
# Author: Nicholas Meinhardt, Maxwell Guerne-Kieferndorf (QZabre)
#         nmeinhar at student.ethz.ch, gmaxwell at student.ethz.ch
#
# Date: 20.10.2020
# latest update: 12.02.2021

import os
import threading
from datetime import datetime
from time import sleep, time

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

########## local imports ##########
try:
    import core.field_current_tr as tr
except ModuleNotFoundError:
    pass
finally:
    import sys
    sys.path.insert(1, os.path.join(sys.path[0], '..'))
    from conexcc.conexcc_class import *
    from MetrolabTHM1176.thm1176 import MetrolabTHM1176Node
    from other_useful_functions.general_functions import (
        ensure_dir_exists, sensor_to_magnet_coordinates)

    import core.field_current_tr as tr

########## Conexcc ports ##########

z_COM_port = 'COM6'  # z-coordinate controller
y_COM_port = 'COM5'
x_COM_port = 'COM4'


class MeasurementException(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args)


def newMeasurementFolder(defaultDataDir='data_sets', sub_dir_base='z_field_meas', verbose=False):
    """
    This function creates a new directory to store data from a measurement run.

    Args:
        defaultDataDir (str, optional): The directory where you want to store the subdirectories containing the actual data files. Defaults to 'data_sets'.
        sub_dir_base (str, optional): The specific subdirectory base name that will be suffixed with a number. Defaults to 'z_field_meas'.
        verbose (bool, optional): Whether it should tell you everything that's going on. Defaults to False.

    Returns:
        sub_dirname, dataDir (str): name of subdirectory where data is stored and the absolute path to it.
    """
    index = 1
    cwd = os.getcwd()
    if verbose:
        print(cwd)
    sub_dirname = sub_dir_base + '_' + str(index)
    dataDir = os.path.join(cwd, defaultDataDir, sub_dirname)
    if verbose:
        print(dataDir)
    # iterate though postfixes until a new directory name is found
    while ensure_dir_exists(dataDir, verbose=verbose):
        index = index + 1
        sub_dirname = sub_dir_base + '_' + str(index)
        dataDir = os.path.join(cwd, defaultDataDir, sub_dirname)
        if verbose:
            print(dataDir)

    return sub_dirname, dataDir


def gotoPosition(meas_x=10.85, meas_y=3.7, meas_height=11.8):
    """
    move the stage into position to measure with the sensor.
    Note: Be sure that the position parameters here correspond to the actual setup
    before measuring for the first time!

    Args:
        meas_height (float): height of sensor above the electromagnet's pole pieces
    """
    # initialize actuators
    CC_Z = ConexCC(com_port=z_COM_port, velocity=0.4,
                   set_axis='z', verbose=False)
    CC_Y = ConexCC(com_port=y_COM_port, velocity=0.4,
                   set_axis='y', verbose=False)
    CC_X = ConexCC(com_port=x_COM_port, velocity=0.4,
                   set_axis='x', verbose=False)
    CC_Z.wait_for_ready()
    CC_Y.wait_for_ready()
    CC_X.wait_for_ready()

    meas_offset_z = meas_height
    start_pos_z = CC_Z.read_cur_pos()
    total_distance_z = abs(meas_offset_z - start_pos_z)

    meas_offset_y = meas_y
    start_pos_y = CC_Y.read_cur_pos()
    total_distance_y = abs(meas_offset_y - start_pos_y)

    meas_offset_x = meas_x
    start_pos_x = CC_X.read_cur_pos()
    total_distance_x = abs(meas_offset_x - start_pos_x)

    CC_Z.move_absolute(new_pos=meas_offset_z)
    CC_Y.move_absolute(new_pos=meas_offset_y)
    CC_X.move_absolute(new_pos=meas_offset_x)

    if (total_distance_y > total_distance_z) and (total_distance_y > total_distance_x):
        progressBar(CC_Y, start_pos_y, total_distance_y)
    elif (total_distance_x > total_distance_z) and (total_distance_x > total_distance_y):
        progressBar(CC_X, start_pos_x, total_distance_x)
    else:
        progressBar(CC_Z, start_pos_z, total_distance_z)


def progressBar(CC: ConexCC, start_pos, total_distance):
    while not CC.is_ready():
        sleep(0.02)
        pos = CC.read_cur_pos()
        ratio = (abs(pos - start_pos) / total_distance)
        left = int(ratio * 30)
        right = 30 - left
        print('\r[' + '#' * left + ' ' * right + ']',
              f' {ratio * 100:.0f}%', sep='', end='', flush=True)

    print('')


def measure(node: MetrolabTHM1176Node, N=10, max_num_retrials=5, average=False):
    """
    Measures the magnetic field with the Metrolab sensor. Returns either raw measured values of field components (x, y, z)
    or mean and standard deviation in each direction.

    Args:
        node (MetrolabTHM1176Node): represents the Metrolab THM 1176 sensor
        N (int, optional): number of data points collected for each average. Defaults to 10.
        max_num_retrials (int, optional): How many times to reattempt measurement before raising an exception. Defaults to 5.
        average (bool, optional): Average over the N measurements. Defaults to False.

    Raises:
        MeasurementError: a problem occured during measurement.

    Returns:
        tuple of 2 np.array(3): This is returned if average is true. mean and std of the three field componenents over N measurements.
        tuple (np.ndarray((N,3)), 0): This is returned if average is false. N measured values of each component are contained. Second return is 0.
    """
    # if dataDir is not None:
    #     ensure_dir_exists(dataDir, verbose=False)

    # perform measurement and collect the raw data
    for _ in range(max_num_retrials):
        try:
            # an N by 3 array
            meas_data = np.array(node.measureFieldArraymT(N)).swapaxes(0, 1)
        except BaseException:
            pass
        else:
            break

    try:
        # due to the setup, transform sensor coordinates to magnet coordinates
        meas_data = sensor_to_magnet_coordinates(meas_data)
    # if it was not possible to obtain valid measurement results after
    # max_num_retrials, raise MeasurementError, too
    except BaseException:
        raise MeasurementException()

    if average:
        # compute the mean and std from raw data for each sensor
        mean_data = np.mean(meas_data, axis=0)
        std_data = np.std(meas_data, axis=0)
        ret1, ret2 = mean_data, std_data
    else:
        # This option is more for getting time-field measurements.
        ret1, ret2 = meas_data, 0

    return ret1, ret2


def timeResolvedMeasurement(block_size=20, period=0.01, average=5, duration=10):
    """
    Measure magnetic flux density over time.

    Args:
        period (float, optional): Trigger period in seconds. Defaults to 0.001 (1 ms).
        averaging (int, optional): The arithmetic mean of this number of measurements is taken before they are fetched.
                                   Results in smoother measurements. Defaults to 1.
        block_size (int, optional): How many measurements should be fetched at once. Defaults to 1.
        duration (int, optional): Total duration of measurement. Defaults to 10.

    Raises:
        ValueError: If for some reason the number of time values and B field values is different.

    Returns:
        dictionary containing lists of floats: Bx, By, Bz, timeline, temp
        (x, y and z components of B field, times of measurements, temperature values
        are dimensionless values between 0 and 64k)
    """
    with MetrolabTHM1176Node(period=period, block_size=block_size, range='auto', average=average, unit='MT') as node:
        # gotoPosition(node, meas_height=1.5)
        # node = MetrolabTHM1176Node(period=period, block_size=block_size, range='0.3 T', average=average, unit='MT')
        thread = threading.Thread(target=node.start_acquisition, name=__name__ + 'dataCollector')
        thread.start()
        sleep(duration)
        node.stop = True
        thread.join()
        # Sensor coordinates to preferred coordinates transformation
        xValues = np.array(node.data_stack['Bx'])
        xValues = -xValues
        # Sensor coordinates to preferred coordinates transformation, offset correction
        yValues = np.array(node.data_stack['Bz'])
        #yOffset = 2.40
        # Sensor coordinates to preferred coordinates transformation, offset correction
        zValues = node.data_stack['By']
        # zValues = np.subtract(zValues, -1.11)

        timeline = node.data_stack['Timestamp']

        t_offset = timeline[0]
        for ind in range(len(timeline)):
            timeline[ind] = round(timeline[ind] - t_offset, 3)

    try:
        if (len(node.data_stack['Bx']) != len(timeline) or len(node.data_stack['By']) != len(
                timeline) or len(node.data_stack['Bz']) != len(timeline)):
            raise ValueError(
                "length of Bx, By, Bz do not match that of the timeline")
        else:
            return {'Bx': xValues.tolist(), 'By': yValues.tolist(), 'Bz': zValues.tolist(),
                    'temp': node.data_stack['Temperature'], 'time': timeline}
    except Exception as e:
        print(e)
        return {'Bx': 0, 'By': 0, 'Bz': 0, 'time': 0, 'temp': 0}


def saveDataPoints(I, mean_data, std_data, expected_fields,
                   directory='.\\data_sets', data_filename_postfix='B_field_vs_I'):
    """
    Saves input data points to a .csv file

    Args:
    - I, mean_values, std_values, expected_values are ndarrays of shape (#measurements, 3),
    containing applied current, experimentally estimated/expected mean values and standard deviations
    for x,y,z-directions.
    - directory: valid path of directory where the image should be saved
    - data_filename_postfix: The image is saved as '%y_%m_%d_%H-%M-%S_'+ data_filename_postfix +'.png'

    """
    print('saving file...')
    if directory is not None:
        ensure_dir_exists(directory, verbose=False)

    try:
        if len(I[0]) == 3:
            # depending on which function in main_menu.py was used to measure
            df = pd.DataFrame({'channel 1 [A]': I[:, 0],
                               'channel 2 [A]': I[:, 1],
                               'channel 3 [A]': I[:, 2],
                               'mean Bx [mT]': mean_data[:, 0],
                               'mean By [mT]': mean_data[:, 1],
                               'mean Bz [mT]': mean_data[:, 2],
                               'std Bx [mT]': std_data[:, 0],
                               'std By [mT]': std_data[:, 1],
                               'std Bz [mT]': std_data[:, 2],
                               'expected Bx [mT]': expected_fields[:, 0],
                               'expected By [mT]': expected_fields[:, 1],
                               'expected Bz [mT]': expected_fields[:, 2]})
            print('success!')

    except BaseException:
        df = pd.DataFrame({'I (all Channels) [A]': I,
                           'mean Bx [mT]': mean_data[:, 0],
                           'mean By [mT]': mean_data[:, 1],
                           'mean Bz [mT]': mean_data[:, 2],
                           'std Bx [mT]': std_data[:, 0],
                           'std By [mT]': std_data[:, 1],
                           'std Bz [mT]': std_data[:, 2],
                           'expected Bx [mT]': expected_fields[:, 0],
                           'expected By [mT]': expected_fields[:, 1],
                           'expected Bz [mT]': expected_fields[:, 2]})
        print('the current vector is 1D')

    now = datetime.now().strftime('%y_%m_%d_%H-%M-%S')
    output_file_name = f'{now}_{data_filename_postfix}.csv'
    file_path = os.path.join(directory, output_file_name)
    df.to_csv(file_path, index=False, header=True)


if __name__ == '__main__':

    gotoPosition(meas_x=10.9, meas_y=4.3)
    # thm = MetrolabTHM1176Node(period=0.05, block_size=20, range='0.1 T', average=1, unit='MT')
    # for i in range(10):
    #     B, B_std = measure(thm, 20, average=True)
    #     print(B, B_std)
    #     sleep(1)
    # thm.sensor.close()
