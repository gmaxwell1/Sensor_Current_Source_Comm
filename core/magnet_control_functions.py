"""
filename: magnet_control_functions.py

This collection of functions has functions that can be used to manipulate the currents on the ECB channels. 
The user can choose from various methods to set currents on the different channels and thus generate a magnetic 
field with the vector magnet. For example, we can sweep through current values on the different channels and
simultaneously measure the actual magnetic field to compare the theory with the actual results.

Author: Maxwell Guerne-Kieferndorf (QZabre)
        gmaxwell@student.ethz.ch

Date: 15.12.2020
latest update: 20.01.2021
"""

########## Standard library imports ##########
import numpy as np
import math
from time import time, sleep
from datetime import datetime
import threading
import matplotlib.pyplot as plt
import sys

########## local imports ##########
try:
    import core.field_current_tr as tr
    from core.main_comm_new import *
    from core.measurement_functions import *
    from metrolabTHM1176.thm1176 import MetrolabTHM1176Node
    from other_useful_functions.general_functions import save_time_resolved_measurement as strm, ensure_dir_exists, sensor_to_magnet_coordinates
    from other_useful_functions.arduinoPythonInterface import ArduinoUno, saveTempData

except ModuleNotFoundError:
    import os
    sys.path.insert(1, os.path.join(sys.path[0], '..'))
    import core.field_current_tr as tr
    from core.main_comm_new import *
    from core.measurement_functions import *
    from metrolabTHM1176.thm1176 import MetrolabTHM1176Node
    from other_useful_functions.general_functions import save_time_resolved_measurement as strm, ensure_dir_exists, sensor_to_magnet_coordinates
    from other_useful_functions.arduinoPythonInterface import ArduinoUno, saveTempData

##########  Current parameters ##########
desCurrents = [0, 0, 0]  # in milliamps

##########  Vector magnet properties ##########
windings = 508  # windings per coil
resistance = 0.47  # resistance per coil

########## list for storing measured values ##########
returnDict = {'Bx': 0, 'By': 0, 'Bz': 0, 'time': 0, 'temp': 0}
# order of data: Bx list, By list, Bz list, time list
threadLock = threading.Lock()
flags = [1]


class myMeasThread(threading.Thread):
    """
    Start a new thread for measuring magnetic field over time with the Metrolab sensor.
    Thread has a name name and multiple member variables.

    kwargs:
        name (str): thread name (default: 'MeasureThread')
        period (float): trigger period, should be in the interval (122e-6, 2.79)
                        (default: 0.1)
        averaging (int): number of measured values to average over.
                            (default: 1)            
        block_size (int): number of measured values to fetch at once.
                            (default: 1)
        duration (float): duration of measurement series
                            (default: 10)
    """

    def __init__(self, threadID, **kwargs):
        threading.Thread.__init__(self)
        keys = kwargs.keys()

        self.threadID = threadID

        if 'name' in keys:
            self.name = kwargs['name']
        else:
            self.name = 'MeasureThread'

        if 'period' in keys:
            self.period = kwargs['period']
        else:
            self.period = 0.1

        if 'averaging' in keys:
            self.averaging = kwargs['averaging']
        else:
            self.averaging = 1

        if 'block_size' in keys:
            self.block_size = kwargs['block_size']
        else:
            self.block_size = 1

        if 'duration' in keys:
            self.duration = kwargs['duration']
        else:
            self.duration = 10

    def run(self):
        global returnDict

        # threadLock.acquire()
        print("Starting " + self.name)

        try:
            returnDict = timeResolvedMeasurement(period=self.period, average=self.averaging,
                                                 block_size=self.block_size, duration=self.duration)
        except Exception as e:
            print('There was a problem!')
            print(e)
        # threadLock.release()
        print("Finished measuring. {} exiting.".format(self.name))


class inputThread(threading.Thread):
    def __init__(self, threadID):
        """
        Waits for the user to press enter.

        Args:
            threadID (int): An identifier number assigned to the newly created thread.
        """
        threading.Thread.__init__(self)
        self.threadID = threadID

    def run(self):
        # global variable flags is modified and can then be read/modified
        # by other threads. Only this thread will append a zero to flags.
        global flags
        c = input("Hit Enter to quit.\n")
        #make sure there are no concurrency issues
        threadLock.acquire()
        flags.insert(0, c)
        threadLock.release()
        
        print('exiting...')
        
        
class timerThread(threading.Thread):
    def __init__(self, threadID, duration):
        """
        Serves as a timer in the background.

        Args:
            threadID (int): An identifier number assigned to the newly created thread.
            duration (float): timer duration
        """
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.startTime = time()
        self.countdownDuration = duration

    def run(self):
        timeDiff = time() - self.startTime
        while timeDiff < self.countdownDuration:
            print(f'\rtime remaining: {int((self.countdownDuration - timeDiff))//3600} hours, {int((self.countdownDuration - timeDiff))//60 % 60} '
                  f'minutes and {(self.countdownDuration - timeDiff)%60:.0f} seconds', end='', sep='', flush=False)
            
            timeDiff = time() - self.startTime
            sleep(0.096)



def gridSweep(node: MetrolabTHM1176Node, inpFile=r'config_files\configs_numvals2_length4.csv', datadir='config_tests',
              factor=0, BField=False, demagnetize=False, today=True, temp_meas=True):
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
        BField (bool, optional): if the csv file being read in contains a list of B vectors (sphrerical), this should be true. default: False
        demagnetize (bool, optional): If true, demagnetization protocol will run after each vector is tested. default: False
        today (bool, optional): today's date will be included in the output directory name. default: True
    """
    global desCurrents
    
    channel_1 = IT6432Connection(1)
    channel_2 = IT6432Connection(2)
    channel_3 = IT6432Connection(3)
    openConnection(channel_1, channel_2, channel_3)
    
    # initialization of all arrays
    # all_curr_steps = np.linspace(start_val, end_val, steps)
    mean_values = []
    stdd_values = []
    expected_fields = []
    all_curr_vals = []
    
    if temp_meas:
        # initialize temperature sensor and measurement routine and start measuring
        arduino = ArduinoUno('COM7')
        measure_temp = threading.Thread(target=arduino.getTemperatureMeasurements, kwargs={'print_meas': False})
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
        if demagnetize:
            demagnetizeCoils(channel_1, channel_2, channel_3, current_config = 5000*np.ones(3))
        
        config = np.array(
                [float(row[0]), float(row[1]), float(row[2])])
        
        if BField:
            B_vector = np.array(
                [float(row[0]), float(row[1]), float(row[2])])
            config = tr.computeCoilCurrents(B_vector)
            
        for k in range(3):
            desCurrents[k] = config[k]*factor
        
        setCurrents(channel_1, channel_2, channel_3, desCurrents)
        # Let the field stabilize
        sleep(2)
        
        time_estimate = time_estimate - meas_duration
        print(f'\rmeasurement nr. {i+1}; approx. time remaining: {time_estimate//3600} hours, {time_estimate//60 % 60} '
                f'minutes and {time_estimate%60:.0f} seconds', end='', sep='', flush=False)
        
        # collect measured and expected magnetic field (of the specified sensor in measurements)
        # see measurements.py for more details
        mean_data, std_data = measure(node, N=10, average=True)
        meas_currents = getMeasurement(channel_1, channel_2, channel_3, meas_quantity='current')
        # meas_power = getMeasurement(channel_1, channel_2, channel_3, meas_quantity='power')
        mean_values.append(mean_data)
        stdd_values.append(std_data)
        all_curr_vals.append(np.array(meas_currents))
        # we already know the expected field values
        if BField:
            expected_fields.append(B_vector)
        else:
            # estimate of resulting B field
            B_expected = tr.computeMagField(config*factor, windings)
            expected_fields.append(B_expected)
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<     
    if temp_meas:
        # save temperature measurements
        arduino.stop = True
        measure_temp.join()
        saveTempData(arduino.data_stack,
                    directory=r'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\1_data_analysis_interpolation\Data_Analysis_For_VM\temperature_measurements',
                    filename_suffix='temp_meas_during_Bsweep')
    ##########################################################################
    # create/find subdirectory to save measurements
    fileprefix = 'field_meas'
    # folder,
    if today:
        now = datetime.now().strftime('%y_%m_%d')
        filePath = rf'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\1_data_analysis_interpolation\Data_Analysis_For_VM\data_sets\{datadir}_{now}'
    else:
        filePath = rf'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\1_data_analysis_interpolation\Data_Analysis_For_VM\data_sets\{datadir}'
    # saving data section (prepared for plotting)
    saveDataPoints((np.array(all_curr_vals) / 1000), np.array(mean_values),
                   np.array(stdd_values), np.array(expected_fields), filePath, fileprefix)
    
    if demagnetize:
        demagnetizeCoils(channel_1, channel_2, channel_3, all_curr_vals[-1])
    # end of measurements
    disableCurrents(channel_1, channel_2, channel_3)
    closeConnection(channel_1, channel_2, channel_3)
    



def runCurrents(config_list, t=[], subdir='default_location',demagnetize=False, temp_meas=False):
    """
    set arbitrary currents on each channel.
    when running without a timer, the current can be changed in a menu and the magnetic field can
    be measured with the metrolab sensor.

    Args:
        config_list (list of (np.array(), length 3)): list of current configs in [mA]. Make sure not to give more than 3!
        t (int, optional): timer duration list. multiple timers -> different currents will be set for different 
                           amounts of time. If zero, user can decide whether to change the current or deactivate it. Defaults to [].
        subdir (str, optional): Default location where measurements are stored. Defaults to 'default_location'.
        demagnetize (bool): if true, demagnetization will run every time the field is deactivated.
        temp_meas (bool): if true, temperature will be measured.
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
            desCurrents[i] = int(channels[i])
            
        setCurrents(channel_1, channel_2, channel_3, desCurrents)
        # wait until user presses enter
        c1 = '0'
        while c1 != 'q':
            c1 = input(
                '[q] to disable currents\n[c]: get currents\n[r]: Set new currents\n[s]: monitor magnetic field')
            if c1 == 'c':
                currentsList = getMeasurement(channel_1, channel_2, channel_3)
                print(f'current 1: {currentsList[0]:.3f}, current 2: {currentsList[1]:.3f}, current 3: {currentsList[2]:.3f}')
            elif c1 == 'r':
                channels[0] = input('Channel 1 current: ')
                channels[1] = input('Channel 2 current: ')
                channels[2] = input('Channel 3 current: ')
                # handle new inputs
                for i in range(len(channels)):
                    try:
                        desCurrents[i] = int(channels[i])
                    except:
                        print(
                            "non-integer value entered, setting channel {} to 0".format(i+1))
                        desCurrents[i] = 0

                setCurrents(channel_1, channel_2, channel_3, desCurrents)
########################### ONLY WITH METROLAB SENSOR ###########################
#############################################################################################################################
            elif c1 == 's':
                with MetrolabTHM1176Node(period=0.05, range='0.3 T', average=20) as node:
                    test_thread = inputThread(1)
                    test_thread.start()
                    sleep(0.1)
                    while flags[0]:
                        newBMeasurement = sensor_to_magnet_coordinates(
                            np.array(node.measureFieldmT()))
                        # newBMeasurement = np.random.randn((3)) * 10
                        B_magnitude = np.linalg.norm(newBMeasurement)
                        theta = np.degrees(
                            np.arccos(newBMeasurement[2]/B_magnitude))
                        phi = np.degrees(np.arctan2(
                            newBMeasurement[1], newBMeasurement[0]))
                        if flags[0]:
                            print(f'\rMeasured B field: ({newBMeasurement[0]:.2f}, {newBMeasurement[1]:.2f}, '
                                    f'{newBMeasurement[2]:.2f}) / In polar coordinates: ({B_magnitude:.2f}, '
                                    f'{theta:.2f}°, {phi:.2f}°)    ', sep='', end='', flush=True)
                        sleep(0.5)

                threadLock.acquire()
                flags.insert(0, 1)
                threadLock.release()
#############################################################################################################################
    else:
        # initialize temperature sensor and measurement routine and start measuring
        if temp_meas:
            arduino = ArduinoUno('COM7')
            measure_temp = threading.Thread(target=arduino.getTemperatureMeasurements, kwargs={'print_meas': False})
            measure_temp.start()
        
        # use only with Metrolab sensor
        try:
            duration = int(input('Duration of measurement (default is 10s): '))
        except:
            duration = 10
        try:
            period = float(input('Measurement trigger period (default is 0.5s, 0.01-2.2s): '))
        except:
            period = 0.5
        
        if period < 0.1:
            block_size = 10
        elif period < 0.05:
            block_size = 30
        elif period >= 0.5:
            block_size = 1

        # print(duration, period)
        global returnDict
        params = {'name': 'BFieldMeasurement', 'block_size': block_size, 'period': period, 'duration': duration, 'averaging': 3}
        faden = myMeasThread(10, **params)
        
        gotoPosition()
        savedir = input('Name of directory where this measurement will be saved: ')

        faden.start()

        for index, timer in enumerate(t):
            channels = config_list[index]
            for i in range(len(channels)):
                desCurrents[i] = int(channels[i])
            # print(desCurrents)
            setCurrents(channel_1, channel_2, channel_3, desCurrents)
            # prevent the connection with the ECB from timing out for long measurements.
            if timer < 500:
                countdown = timerThread(11, timer)
                countdown.start()
                sleep(timer)
                countdown.join()
            else:
                countdown = timerThread(11, timer)
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
            saveTempData(arduino.data_stack,
                                directory=r'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\1_data_analysis_interpolation\Data_Analysis_For_VM\temperature_measurements',
                                filename_suffix='temp_meas_timed_const_field')
        
        saveLoc = rf'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\1_data_analysis_interpolation\Data_Analysis_For_VM\data_sets\{savedir}'
        strm(returnDict, saveLoc, now=True)
        
    # if demagnetize:
    #     demagnetizeCoils()
    disableCurrents(channel_1, channel_2, channel_3)
    closeConnection(channel_1, channel_2, channel_3)
        

def generateMagneticField(vectors, t=[], subdir='default_location', demagnetize=False, temp_meas=False):
    """
    A magnetic field is generated in an arbitrary direction which is specified by the user. The currents
    set on the different channels are computed with a linear model. See transformations.py.

    Args:
        vectors (list, optional): Nx3 vector of float values, containing N magnetic field vectors
                                  in spherical coordinates. Order: (B,theta,phi), theta is the polar
                                  angle and phi is the azimuthal angle.
        t (list, optional): timer durations for each field. May not be longer than 'vectors'. Defaults to [].
        subdir (str, optional): Subdirectory where any measurements will be saved. Defaults to 'serious_measurements_for_LUT'.
        demagnetize (bool, optional): If True, coils will be demagnetized after the magnetic field is deactivated. Defaults to False.
    """
    global desCurrents
    
    channel_1 = IT6432Connection(1)
    channel_2 = IT6432Connection(2)
    channel_3 = IT6432Connection(3)
    openConnection(channel_1, channel_2, channel_3)
    
    if len(t) == 0 or t[0] == 0:
        B_Field = vectors[0]
        B_Field_cartesian = tr.computeMagneticFieldVector(B_Field[0], B_Field[1], B_Field[2])
        channels = tr.computeCoilCurrents(B_Field_cartesian)
        for i in range(len(channels)):
            desCurrents[i] = int(channels[i])
            
        print(f'Currents on each channel: ({desCurrents[0]}, {desCurrents[1]}, {desCurrents[2]})')
        setCurrents(channel_1, channel_2, channel_3, desCurrents)
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
                        desCurrents[i] = int(channels[i])
                    except:
                        print(
                            f"non-integer value entered, setting channel {i+1} to 0")
                        desCurrents[i] = 0
                print(
                    f'Currents on each channel: ({desCurrents[0]}, {desCurrents[1]}, {desCurrents[2]})')
                setCurrents(channel_1, channel_2, channel_3, desCurrents)

            elif c1 == 'r':
                inp1 = input('New magnitude: ')
                inp2 = input('New polar angle (theta): ')
                inp3 = input('New azimuthal angle (phi): ')
                # handle new inputs
                try:
                    magnitude = float(inp1)
                except:
                    print("non-integer value entered, setting magnitude to 0")
                    magnitude = 0
                try:
                    theta = float(inp2)
                except:
                    print("non-integer value entered, setting theta to 0")
                    theta = 0
                try:
                    phi = float(inp3)
                except:
                    print("non-integer value entered, setting phi to 0")
                    phi = 0

                B_vector = tr.computeMagneticFieldVector(magnitude, theta, phi)
                I_vector = tr.computeCoilCurrents(B_vector, windings, resistance)
                # copy the computed current values (mA) into the desCurrents list (first 3 positions)
                # cast to int
                for i in range(len(I_vector)):
                    desCurrents[i] = int(I_vector[i])
                print(
                    f'Currents on each channel: ({desCurrents[0]}, {desCurrents[1]}, {desCurrents[2]})')
                setCurrents(channel_1, channel_2, channel_3, desCurrents)
########################### ONLY WITH METROLAB SENSOR ###########################
#############################################################################################################################
            elif c1 == 's':
                with MetrolabTHM1176Node(period=0.05, range='0.3 T', average=20) as node:
                    test_thread = inputThread(1)
                    test_thread.start()
                    sleep(0.1)
                    while flags[0]:
                        newBMeasurement = sensor_to_magnet_coordinates(
                            np.array(node.measureFieldmT()))
                        # newBMeasurement = np.random.randn((3)) * 10
                        B_magnitude = np.linalg.norm(newBMeasurement)
                        theta = np.degrees(
                            np.arccos(newBMeasurement[2]/B_magnitude))
                        phi = np.degrees(np.arctan2(
                            newBMeasurement[1], newBMeasurement[0]))
                        if flags[0]:
                            print(f'\rMeasured B field: ({newBMeasurement[0]:.2f}, {newBMeasurement[1]:.2f}, '
                                    f'{newBMeasurement[2]:.2f}) / In polar coordinates: ({B_magnitude:.2f}, '
                                    f'{theta:.2f}°, {phi:.2f}°)    ', sep='', end='', flush=True)
                        sleep(0.5)

                threadLock.acquire()
                flags.insert(0, 1)
                threadLock.release()
#############################################################################################################################
    else:
        # initialize temperature sensor and measurement routine and start measuring
        if temp_meas:
            arduino = ArduinoUno('COM7')
            measure_temp = threading.Thread(target=arduino.getTemperatureMeasurements, kwargs={'print_meas': False})
            measure_temp.start()

        # use only with Metrolab sensor
        try:
            duration = int(input('Duration of measurement (default is 10s): '))
            period = int(input('Measurement trigger period (default is 0.5s, 0.01-2.2s): '))
        except:
            duration = 10
            period = 0.5
        
        if period < 0.1:
            block_size = 10
        elif period < 0.05:
            block_size = 30
        elif period >= 0.5:
            block_size = 1
            
        global returnDict
        params = {'name': 'BFieldMeasurement', 'block_size': block_size, 'period': 0.5, 'duration': duration, 'averaging': 3}
        faden = myMeasThread(10, **params)
        
        gotoPosition()
        savedir = input('Name of directory where this measurement will be saved: ')

        faden.start()

        for index, timer in enumerate(t):
            B_Field = vectors[index]
            B_Field_cartesian = tr.computeMagneticFieldVector(B_Field[0], B_Field[1], B_Field[2])
            channels = tr.computeCoilCurrents(B_Field_cartesian)
            for i in range(len(channels)):
                desCurrents[i] = int(channels[i])
            
            setCurrents(channel_1, channel_2, channel_3, desCurrents)
            # prevent the connection with the ECB from timing out for long measurements.
            if timer < 500:
                countdown = timerThread(0,timer)
                countdown.start()
                sleep(timer)
                countdown.join()
            else:
                countdown = timerThread(0,timer)
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
            saveTempData(arduino.data_stack,
                                directory=r'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\1_data_analysis_interpolation\Data_Analysis_For_VM\temperature_measurements',
                                filename_suffix='temp_meas_timed_const_fields')
        
        saveLoc = rf'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\1_data_analysis_interpolation\Data_Analysis_For_VM\data_sets\{savedir}'
        strm(returnDict, saveLoc, now=True)
    
    # if demagnetize:
    #     demagnetizeCoils()
    disableCurrents(channel_1, channel_2, channel_3)
    closeConnection(channel_1, channel_2, channel_3)

    
    
if __name__ == "__main__":
    params = {'block_size': 20, 'period': 0.05, 'duration': 120, 'averaging': 5}
    
    # arduino = ArduinoUno('COM7')
    # measure_temp = threading.Thread(target=arduino.getTemperatureMeasurements)
    channel_1 = IT6432Connection(1)
    channel_2 = IT6432Connection(2)
    channel_3 = IT6432Connection(3)
    openConnection(channel_1, channel_2, channel_3)
    # disableCurrents(channel_1, channel_2, channel_3)

    faden = myMeasThread(1, **params)

    # measure_temp.start()

    # setCurrents(channel_1, channel_2, channel_3, desCurrents=[0,0,10])
    # sleep(2)
    # setCurrents(channel_1, channel_2, channel_3, desCurrents=[-34,0,100])
    # sleep(2)
    # setCurrents(channel_1, channel_2, channel_3, desCurrents=[0,569,500])
    # sleep(2)
    # setCurrents(channel_1, channel_2, channel_3, desCurrents=[200,0,1000])
    # sleep(2)
    # setCurrents(channel_1, channel_2, channel_3, desCurrents=[0,3000,1500])
    # sleep(2)
    # setCurrents(channel_1, channel_2, channel_3, desCurrents=[0,-222,2000])
    # sleep(2)
    # setCurrents(channel_1, channel_2, channel_3, desCurrents=[2930,0,2500])
    # sleep(2)
    # setCurrents(channel_1, channel_2, channel_3, desCurrents=[-3000,0,3000])
    # sleep(2)
    setCurrents(channel_1, channel_2, channel_3, desCurrents=[5000,5000,5000])
    faden.start()

    faden.join()
    disableCurrents(channel_1, channel_2, channel_3)

    # arduino.stop = True
    # measure_temp.join()
    # saveTempData(arduino.data_stack,
    #                         directory=r'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\1_data_analysis_interpolation\Data_Analysis_For_VM\temperature_measurements',
    #                         filename_suffix='temp_meas_temp_control_50mT')

    closeConnection(channel_1, channel_2, channel_3)
    
    strm(returnDict, r'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\1_data_analysis_interpolation\Data_Analysis_For_VM\data_sets\testing_IT6432_currents', 'testing_coil3ramp', now=True)
