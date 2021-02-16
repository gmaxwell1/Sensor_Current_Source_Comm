# filename: magnet_control_functions.py
#
# Set currents manually, or by specifying a magnetic field vector, or a list of either.
# Manages measurements of B-field and temperature as well as user inputs and saving data.
#
# Author: Maxwell Guerne-Kieferndorf (QZabre)
#         gmaxwell at student.ethz.ch
#
# Date: 15.10.2020
# latest update: 12.02.2021

import csv
import math
import os
import sys
import threading
from datetime import datetime
from time import sleep, time

import numpy as np
import pandas as pd

########## local imports ##########
try:
    from metrolabTHM1176.thm1176 import MetrolabTHM1176Node
except ModuleNotFoundError:
    pass
finally:
    sys.path.insert(1, os.path.join(sys.path[0], '..'))

    from IT6432.it6432connection import IT6432Connection
    from metrolabTHM1176.thm1176 import MetrolabTHM1176Node
    from other_useful_functions.arduinoPythonInterface import (ArduinoUno,
                                                               saveTempData)
    from other_useful_functions.general_functions import ensure_dir_exists
    from other_useful_functions.general_functions import \
        save_time_resolved_measurement as strm
    from other_useful_functions.general_functions import \
        sensor_to_magnet_coordinates

    import core.field_current_tr as tr
    import core.meas_parallelization as p
    from core.current_control import PowerSupplyCommands
    from core.main_comm_new import (closeConnection, demagnetizeCoils,
                                    disableCurrents, getMeasurement,
                                    openConnection, setCurrents)
    from core.measurement_functions import (gotoPosition, measure,
                                            saveDataPoints,
                                            timeResolvedMeasurement)

##########  Current parameters ##########
desCurrents = [0, 0, 0]  # in amps

##########  Vector magnet properties ##########
windings = 508  # windings per coil
resistance = 0.47  # resistance per coil


def gridSweep(
        node: MetrolabTHM1176Node,
        inpFile=r'config_files\configs_numvals2_length4.csv',
        datadir='config_tests',
        factor=1,
        ramp_steps=5,
        BField=False,
        demagnetize=False,
        sub_remanence=False,
        temp_meas=True):
    """
    Reads current configurations/values from a csv file, depending on the file the configurations need to be multiplied by a current,
    otherwise factor can be 1000 to convert A to mA (or 1 if values are given in mA) and the actual numbers will be set as current
    on each coil. Optionally, a file with a list of B field vectors can be read in and currents will be computed with the model that
    we created (for this case, set factor to 1).

    Args:
        node (MetrolabTHM1176Node): an instance of the MetrolabTHM1176Node class.
        inpFile (str): file path to the csv file with a list of current configs/magnetic field vectors to be read in.
        datadir (str): directory where results will be saved.
        factor (int, optional): factor to multiply current configs by. Defaults to 1.
        ramp_steps (int, optional): Number of steps to make ramping up the current. Default: 5.
        BField (bool, optional): if the csv file being read in contains a list of B vectors (sphrerical), this should be true. Default: False.
        demagnetize (bool, optional): If true, demagnetization protocol will run after each vector is tested. Default: False.
        sub_remanence (bool, optional): Subtract remanent field vectorially from desired field if true. Default: False.
        temp_meas (bool, optional): Whether or not to measure temperature during B field measurement. Default: True.
    """
    global desCurrents

    psu = PowerSupplyCommands(num_steps=ramp_steps)
    psu.openConnection()

    # initialization of all arrays
    # all_curr_steps = np.linspace(start_val, end_val, steps)
    mean_values = []
    stdd_values = []
    expected_fields = []
    all_curr_vals = []

    if temp_meas:
        # initialize temperature sensor and measurement routine and start measuring
        arduino = ArduinoUno('COM7')
        measure_temp = threading.Thread(
            target=arduino.getTemperatureMeasurements, kwargs={
                'print_meas': False})
        measure_temp.start()

    ##########################################################################
    input_list = []
    with open(inpFile, 'r') as f:
        contents = csv.reader(f)
        next(contents)
        input_list = list(contents)

    meas_duration = 22
    # if not demagnetize:
    #     meas_duration = 22
    time_estimate = len(input_list) * meas_duration
# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    for i, row in enumerate(input_list):

        config = np.array(
            [float(row[0]), float(row[1]), float(row[2])])

        if sub_remanence:
            remanence_values, _ = measure(node, N=10, average=True)

        if BField:
            B_vector = np.array(
                [float(row[0]), float(row[1]), float(row[2])])
            # we already know the expected field values
            expected_fields.append(B_vector)
            if sub_remanence:
                B_vector -= remanence_values
            config = tr.computeCoilCurrents(B_vector)

        else:
            # estimate of resulting B field
            B_expected = tr.computeMagField(config * factor, windings)
            expected_fields.append(B_expected)

        for k in range(3):
            desCurrents[k] = config[k] * factor

        psu.setCurrents(desCurrents)
        # Let the field stabilize
        sleep(2)

        time_estimate = time_estimate - meas_duration
        print(
            f'\rmeasurement nr. {i+1}; approx. time remaining: {time_estimate//3600} hours, {time_estimate//60 % 60} '
            f'minutes and {time_estimate%60:.0f} seconds',
            end='',
            sep='',
            flush=False)

        # collect measured and expected magnetic field (of the specified sensor in measurements)
        # see measurements.py for more details
        mean_data, std_data = measure(node, N=15, average=True)
        meas_currents = []
        sign_mask = np.array([1, np.sign(desCurrents[1]), 1])

        for i in range(3):
            meas_currents.append(psu.power_supplies[i].getMeasurement(meas_quantity='current'))
        meas_currents = np.array(meas_currents * sign_mask)

        mean_values.append(mean_data)
        stdd_values.append(std_data)
        all_curr_vals.append(meas_currents)

        if demagnetize:
            psu.demagnetizeCoils(current_config=desCurrents)
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
    if temp_meas:
        # save temperature measurements
        arduino.stop = True
        measure_temp.join()
        saveTempData(
            arduino.data_stack,
            directory=r'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\1_data_analysis_interpolation\Data_Analysis_For_VM\temperature_measurements',
            filename_suffix='temp_meas_repeatability')
    ##########################################################################
    # create/find subdirectory to save measurements
    fileprefix = 'field_meas'
    # folder,
    # now = datetime.now().strftime('%y_%m_%d')
    filePath = rf'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\1_data_analysis_interpolation\Data_Analysis_For_VM\data_sets\{datadir}'

    # saving data section (prepared for plotting)
    saveDataPoints((np.array(all_curr_vals)), np.array(mean_values),
                   np.array(stdd_values), np.array(expected_fields), filePath, fileprefix)

    if demagnetize:
        psu.demagnetizeCoils(all_curr_vals[-1])
    # end of measurements
    psu.closeConnection()


def runCurrents(config_list, t=[], subdir='default_location', demagnetize=False, temp_meas=False):
    """
    Set arbitrary currents on each channel. Includes timed mode, magnetic field and temperature measurements
    and setting new currents.

    Args:
        config_list (list of (np.array() size 3)): list of current configs in [A]. Make sure not to give more than 3!
        t (int): timer duration list. multiple timers -> different currents will be set for different
                           amounts of time. If zero, user can decide whether to change the current or deactivate it. Defaults to [].
        subdir (str, optional): Default location where measurements are stored. Defaults to 'default_location'.
        demagnetize (bool, optional): if true, demagnetization will run every time the field is deactivated.
        temp_meas (bool, optional): if true, temperature will be measured.
    """
    global desCurrents

    channel_1 = IT6432Connection(1)
    channel_2 = IT6432Connection(2)
    channel_3 = IT6432Connection(3)
    openConnection(channel_1, channel_2, channel_3)

    # on until interrupted by user
    if len(t) == 0 or t[0] == 0:
        channels = config_list[0]
        for i in range(len(channels)):
            desCurrents[i] = round(channels[i], 3)

        setCurrents(channel_1, channel_2, channel_3, desCurrents)
        # wait until user presses enter
        c1 = '0'
        while c1 != 'q':
            c1 = input(
                '[q] to disable currents\n[c]: get currents\n[r]: Set new currents\n[s]: monitor magnetic field')
            if c1 == 'c':
                currentsList = getMeasurement(channel_1, channel_2, channel_3)
                print(
                    f'current 1: {currentsList[0]:.3f}, current 2: {currentsList[1]:.3f}, current 3: {currentsList[2]:.3f}')
            elif c1 == 'r':
                channels[0] = input('Channel 1 current: ')
                channels[1] = input('Channel 2 current: ')
                channels[2] = input('Channel 3 current: ')
                # handle new inputs
                for i in range(len(channels)):
                    try:
                        desCurrents[i] = round(channels[i], 3)
                    except BaseException:
                        print(
                            "non-integer value entered, setting channel {} to 0".format(i + 1))
                        desCurrents[i] = 0

                setCurrents(channel_1, channel_2, channel_3, desCurrents)
########################### ONLY WITH METROLAB SENSOR ###########################
##########################################################################
            elif c1 == 's':
                with MetrolabTHM1176Node(period=0.05, range='0.3 T', average=20) as node:
                    test_thread = p.inputThread(1)
                    test_thread.start()
                    sleep(0.1)
                    while p.flags[0]:
                        newBMeasurement = sensor_to_magnet_coordinates(
                            np.array(node.measureFieldmT()))
                        # newBMeasurement = np.random.randn((3)) * 10
                        B_magnitude = np.linalg.norm(newBMeasurement)
                        theta = np.degrees(
                            np.arccos(newBMeasurement[2] / B_magnitude))
                        phi = np.degrees(np.arctan2(
                            newBMeasurement[1], newBMeasurement[0]))
                        if p.flags[0]:
                            print(
                                f'\rMeasured B field: ({newBMeasurement[0]:.2f}, {newBMeasurement[1]:.2f}, '
                                f'{newBMeasurement[2]:.2f}) / In polar coordinates: ({B_magnitude:.2f}, '
                                f'{theta:.2f}°, {phi:.2f}°)    ', sep='', end='', flush=True)
                        sleep(0.5)

                p.threadLock.acquire()
                p.flags.insert(0, 1)
                p.threadLock.release()
##########################################################################
    else:
        # initialize temperature sensor and measurement routine and start measuring
        if temp_meas:
            arduino = ArduinoUno('COM7')
            measure_temp = threading.Thread(
                target=arduino.getTemperatureMeasurements, kwargs={
                    'print_meas': False})
            measure_temp.start()

        # use only with Metrolab sensor
        try:
            duration = int(input('Duration of measurement (default is 10s): '))
        except BaseException:
            duration = 10
        try:
            period = float(input('Measurement trigger period (default is 0.5s, 0.01-2.2s): '))
        except BaseException:
            period = 0.5

        if period < 0.1:
            block_size = 10
        elif period < 0.05:
            block_size = 30
        elif period >= 0.5:
            block_size = 1

        # print(duration, period)
        params = {
            'name': 'BFieldMeasurement',
            'block_size': block_size,
            'period': period,
            'duration': duration,
            'averaging': 3}
        faden = p.myMeasThread(10, **params)

        gotoPosition()
        savedir = input('Name of directory where this measurement will be saved: ')

        faden.start()

        for index, timer in enumerate(t):
            channels = config_list[index]
            for i in range(len(channels)):
                desCurrents[i] = round(channels[i], 3)
            # print(desCurrents)
            setCurrents(channel_1, channel_2, channel_3, desCurrents)
            if timer < 500:
                countdown = p.timerThread(11, timer)
                countdown.start()
                sleep(timer)
                countdown.join()
            else:
                countdown = p.timerThread(11, timer)
                countdown.start()
                starttime = time()
                while time() - starttime < timer:
                    pause = min(500, timer - (time() - starttime))
                    sleep(pause)
                    getMeasurement(channel_1, channel_2, channel_3)
                countdown.join()

        faden.join()

        if temp_meas:
            arduino.stop = True
            measure_temp.join()
            saveTempData(
                arduino.data_stack,
                directory=r'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\1_data_analysis_interpolation\Data_Analysis_For_VM\temperature_measurements',
                filename_suffix='temp_meas_repeatability')

        saveLoc = rf'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\1_data_analysis_interpolation\Data_Analysis_For_VM\data_sets\{savedir}'
        strm(p.return_dict(), saveLoc, now=True)

    if demagnetize:
        demagnetizeCoils(channel_1, channel_2, channel_3, config_list[-1])
    disableCurrents(channel_1, channel_2, channel_3)
    closeConnection(channel_1, channel_2, channel_3)


def generateMagneticField(vectors, t=[], subdir='default_location',
                          demagnetize=False, temp_meas=False):
    """
    Set arbitrary currents on each channel. Includes timed mode, magnetic field and temperature measurements
    and setting new currents.

    Args:
        vectors (list of (np.array() size 3)): List of magnetic field vectors.
        t (int): Timer duration list. multiple timers -> different currents will be set for different
                 amounts of time. If zero, user can use the menu. Defaults to [].
        subdir (str, optional): Default location where measurements are stored. Defaults to 'default_location'.
        demagnetize (bool, optional): If true, demagnetization will run every time the field is deactivated.
        temp_meas (bool, optional): If true, temperature will be measured.
    """
    global desCurrents

    psu = PowerSupplyCommands()
    psu.openConnection()

    if len(t) == 0 or t[0] == 0:
        B_Field = vectors[0]
        B_Field_cartesian = tr.computeMagneticFieldVector(B_Field[0], B_Field[1], B_Field[2])
        channels = tr.computeCoilCurrents(B_Field_cartesian)
        for i in range(len(channels)):
            desCurrents[i] = round(channels[i], 3)

        print(f'Currents on each channel: ({desCurrents[0]}, {desCurrents[1]}, {desCurrents[2]})')
        psu.setCurrents(desCurrents)
        # wait until user presses q
        c1 = '0'
        while c1 != 'q':
            c1 = input('[q] to disable currents\n[c]: Set new currents\n[r]: Set new mag field\n'
                       '[s]: monitor magnetic field (does not work)\n'
                       '[f]: get magnetic field time-resolved measurement series (does not work)\n')

            if c1 == 'c':
                channels = [0, 0, 0]
                channels[0] = input('Channel 1 current: ')
                channels[1] = input('Channel 2 current: ')
                channels[2] = input('Channel 3 current: ')
                # handle new inputs
                for i in range(len(channels)):
                    try:
                        desCurrents[i] = round(channels[i], 3)
                    except BaseException:
                        print(
                            f"non-integer value entered, setting channel {i+1} to 0")
                        desCurrents[i] = 0
                print(
                    f'Currents on each channel: ({desCurrents[0]}, {desCurrents[1]}, {desCurrents[2]})')
                psu.setCurrents(desCurrents)

            elif c1 == 'r':
                inp1 = input('New magnitude: ')
                inp2 = input('New polar angle (theta): ')
                inp3 = input('New azimuthal angle (phi): ')
                # handle new inputs
                try:
                    magnitude = float(inp1)
                except BaseException:
                    print("non-integer value entered, setting magnitude to 0")
                    magnitude = 0
                try:
                    theta = float(inp2)
                except BaseException:
                    print("non-integer value entered, setting theta to 0")
                    theta = 0
                try:
                    phi = float(inp3)
                except BaseException:
                    print("non-integer value entered, setting phi to 0")
                    phi = 0

                B_vector = tr.computeMagneticFieldVector(magnitude, theta, phi)
                I_vector = tr.computeCoilCurrents(B_vector, windings, resistance)
                # copy the computed current values (mA) into the desCurrents list (first 3 positions)
                # cast to int
                for i in range(len(I_vector)):
                    desCurrents[i] = round(I_vector[i], 3)
                print(
                    f'Currents on each channel: ({desCurrents[0]}, {desCurrents[1]}, {desCurrents[2]})')
                psu.setCurrents(desCurrents)
########################### ONLY WITH METROLAB SENSOR ###########################
##########################################################################
            elif c1 == 's':
                with MetrolabTHM1176Node(period=0.05, range='0.3 T', average=20) as node:
                    test_thread = p.inputThread(1)
                    test_thread.start()
                    sleep(0.1)
                    while p.flags[0]:
                        newBMeasurement = sensor_to_magnet_coordinates(
                            np.array(node.measureFieldmT()))
                        # newBMeasurement = np.random.randn((3)) * 10
                        B_magnitude = np.linalg.norm(newBMeasurement)
                        theta = np.degrees(
                            np.arccos(newBMeasurement[2] / B_magnitude))
                        phi = np.degrees(np.arctan2(
                            newBMeasurement[1], newBMeasurement[0]))
                        if p.flags[0]:
                            print(
                                f'\rMeasured B field: ({newBMeasurement[0]:.2f}, {newBMeasurement[1]:.2f}, '
                                f'{newBMeasurement[2]:.2f}) / In polar coordinates: ({B_magnitude:.2f}, '
                                f'{theta:.2f}°, {phi:.2f}°)    ', sep='', end='', flush=True)
                        sleep(0.5)

                p.threadLock.acquire()
                p.flags.insert(0, 1)
                p.threadLock.release()
##########################################################################
    else:
        if temp_meas:
            arduino = ArduinoUno('COM7')
            measure_temp = threading.Thread(
                target=arduino.getTemperatureMeasurements, kwargs={
                    'print_meas': False})
            measure_temp.start()

        # use only with Metrolab sensor
        try:
            duration = int(input('Duration of measurement (default is 10s): '))
        except BaseException:
            duration = 10
        try:
            period = float(input('Measurement trigger period (default is 0.5s, 0.01-2.2s): '))
        except BaseException:
            period = 0.5

        if period < 0.1:
            block_size = 10
        elif period < 0.05:
            block_size = 30
        elif period >= 0.5:
            block_size = 1

        # print(duration, period)
        params = {
            'name': 'BFieldMeasurement',
            'block_size': block_size,
            'period': period,
            'duration': duration,
            'averaging': 3}
        faden = p.myMeasThread(10, **params)

        gotoPosition()
        savedir = input('Name of directory where this measurement will be saved: ')

        faden.start()

        for index, timer in enumerate(t):
            B_Field = vectors[index]
            B_Field_cartesian = tr.computeMagneticFieldVector(B_Field[0], B_Field[1], B_Field[2])
            channels = tr.computeCoilCurrents(B_Field_cartesian)
            for i in range(len(channels)):
                desCurrents[i] = int(channels[i])

            psu.setCurrents(desCurrents)
            # prevent the connection from timing out for long measurements.
            if timer < 500:
                countdown = p.timerThread(0, timer)
                countdown.start()
                sleep(timer)
                countdown.join()
            else:
                countdown = p.timerThread(0, timer)
                countdown.start()
                starttime = time()
                while time() - starttime < timer:
                    pause = min(500, timer - (time() - starttime))
                    sleep(pause)
                    for power_supply in psu.power_supplies:
                        power_supply.getMeasurement()
                countdown.join()

        faden.join()

        if temp_meas:
            arduino.stop = True
            measure_temp.join()
            saveTempData(
                arduino.data_stack,
                directory=r'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\1_data_analysis_interpolation\Data_Analysis_For_VM\temperature_measurements',
                filename_suffix='temp_meas_timed_const_fields')

        saveLoc = rf'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\1_data_analysis_interpolation\Data_Analysis_For_VM\data_sets\{savedir}'
        strm(p.returnDict, saveLoc, now=True)

    if demagnetize:
        psu.demagnetizeCoils([psu.setCurrentValues])
    else:
        psu.disableCurrents()
    psu.closeConnection()


# if __name__ == "__main__":
#     psu = PowerSupplyCommands()

#     psu.openConnection()

#     # arduino = ArduinoUno('COM7')
#     # measure_temp = threading.Thread(
#     #     target=arduino.getTemperatureMeasurements, kwargs={
#     #         'print_meas': False})
#     # measure_temp.start()

#     params = {'block_size': 20, 'period': 0.05, 'duration': 120, 'averaging': 5}
#     BFields = [np.array([6, -50, 20]), np.array([-30, 30, -30]), np.array(
#                [-43, -90, 0]), np.array([0, -10, 80]), np.array([36.3, 0, -18]),
#                np.array([-27, -3.141, 30]), np.array([0, 10, 50])]
#     returnDict = {}

#     k = 4

#     for ix, B in enumerate(BFields):
#         B_Field_cartesian = B  # - B_rem
#         channels = tr.computeCoilCurrents(B_Field_cartesian)
#         print(
#             f'\r({channels[0]:.3f}, {channels[1]:.3f}, {channels[2]:.3f})A; '
#             f'({B_Field_cartesian[0]:.3f}, {B_Field_cartesian[1]:.3f}, '
#             f'{B_Field_cartesian[2]:.3f})mT')

#         with MetrolabTHM1176Node(period=0.05, block_size=20, range='0.3 T', average=5, unit='MT') as node:
#             measureB = threading.Thread(target=node.start_acquisition, name='Meas_Thread')
#             measureB.start()

#             psu.setCurrents(channels)

#             starttime = time()  # = 0
#             while time() - starttime < 10:
#                 pass

#             psu.demagnetizeCoils(channels, 5)

#             node.stop = True

#             measureB.join()
#         try:
#             xValues = -np.array(node.data_stack['Bx'])
#             yValues = np.array(node.data_stack['Bz'])
#             zValues = node.data_stack['By']

#             timeline = node.data_stack['Timestamp']
#             t_offset = timeline[0]
#             for ind in range(len(timeline)):
#                 timeline[ind] = round(timeline[ind] - t_offset, 3)
#             returnDict = {'Bx': xValues.tolist(),
#                           'By': yValues.tolist(),
#                           'Bz': zValues.tolist(),
#                           'temp': node.data_stack['Temperature'],
#                           'time': timeline}
#         except Exception as e:
#             print(f'{__name__}: {e}')

#         strm(
#             returnDict,
#             r'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\1_data_analysis_interpolation\Data_Analysis_For_VM\data_sets\testing_IT6432_demag\demagnetization',
#             f'demag_test_{k}',
#             now=True)
#         with MetrolabTHM1176Node(period=0.05, block_size=20, range='0.3 T', average=5, unit='MT') as node:
#             sleep(0.5)
#             B_rem = sensor_to_magnet_coordinates(node.measureFieldmT())
#         k += 1

#     psu.closeConnection()

    # arduino.stop = True
    # measure_temp.join()
    # saveTempData(
    #     arduino.data_stack,
    #     directory=r'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\1_data_analysis_interpolation\Data_Analysis_For_VM\temperature_measurements',
    #     filename_suffix='temp_meas_stbility_1-7')

if __name__ == '__main__':

    # setup measurements:
    x_axis_sweep_file = r'test_sets\sweep_x_50mT_size100.csv'
    y_axis_sweep_file = r'test_sets\sweep_y_50mT_size100.csv'
    z_axis_sweep_file = r'test_sets\sweep_z_50mT_size100.csv'

    x_axis_rot_file = r'test_sets\rotation_x_10mT_size100.csv'
    y_axis_rot_file = r'test_sets\rotation_y_10mT_size100.csv'
    z_axis_rot_file = r'test_sets\rotation_z_10mT_size100.csv'

    data_dir = 'repeatability_error_source_search'
    fast_ramp = 1
    slow_ramp = 15
    normal_ramp = 5

    # for i in range(5):
    #     with MetrolabTHM1176Node(period=0.05, block_size=20, range='0.1 T', average=1, unit='MT') as node:
    #         ramp = normal_ramp
    #         sub_rem = False
    #         if i == 2:
    #             ramp = slow_ramp
    #         if i == 3:
    #             ramp = fast_ramp
    #         if i == 4:
    #             sub_rem = True

    #         gridSweep(
    #             node,
    #             x_axis_sweep_file,
    #             data_dir,
    #             ramp_steps=ramp,
    #             sub_remanence=sub_rem,
    #             BField=True,
    #             demagnetize=True,
    #             temp_meas=True)
    #         sleep(60)
    #         gridSweep(
    #             node,
    #             y_axis_sweep_file,
    #             data_dir,
    #             ramp_steps=ramp,
    #             sub_remanence=sub_rem,
    #             BField=True,
    #             demagnetize=True,
    #             temp_meas=True)
    #         sleep(60)
    #         gridSweep(
    #             node,
    #             z_axis_sweep_file,
    #             data_dir,
    #             ramp_steps=ramp,
    #             sub_remanence=sub_rem,
    #             BField=True,
    #             demagnetize=True,
    #             temp_meas=True)
    #         sleep(60)

    # sleep(3600)

    for i in range(4):
        node = MetrolabTHM1176Node(period=0.05, block_size=20, range='0.1 T', average=1, unit='MT')
        sub_rem = False
        if i == 3:
            sub_rem = True

        if i > 1:
            sleep(3600)
        gridSweep(
            node,
            x_axis_rot_file,
            data_dir,
            sub_remanence=sub_rem,
            BField=True,
            demagnetize=True,
            temp_meas=True)
        if i > 1:
            sleep(3600)
        gridSweep(
            node,
            y_axis_rot_file,
            data_dir,
            sub_remanence=sub_rem,
            BField=True,
            demagnetize=True,
            temp_meas=True)
        if i > 1:
            sleep(3600)
        gridSweep(
            node,
            z_axis_rot_file,
            data_dir,
            sub_remanence=sub_rem,
            BField=True,
            demagnetize=True,
            temp_meas=True)
        node.sensor.close()
