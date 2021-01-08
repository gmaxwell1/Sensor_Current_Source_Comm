"""
filename: utility_functions.py

This collection of functions has functions that can be used to manipulate the currents on the ECB channels. 
The user can choose from various methods to set currents on the different channels and thus generate a magnetic 
field with the vector magnet. For example, we can sweep through current values on the different channels and
simultaneously measure the actual magnetic field to compare the theory with the actual results.

Author: Maxwell Guerne-Kieferndorf (QZabre)
        gmaxwell@student.ethz.ch

Date: 15.12.2020
latest update: 08.01.2021
"""

########## Standard library imports ##########
import numpy as np
import math
from time import time, sleep
from datetime import datetime
import threading
import matplotlib.pyplot as plt

########## local imports ##########
import transformations as tr
from main_comm import *
from main_comm import _setCurrents_
from measurements import *
# from modules.analysis_tools import generate_plots
from MetrolabTHM1176.thm1176 import MetrolabTHM1176Node
from other_useful_functions.general_functions import save_time_resolved_measurement as strm, ensure_dir_exists, sensor_to_magnet_coordinates
from other_useful_functions.arduinoPythonInterface import ArduinoUno, saveTempData


##########  Current parameters ##########
desCurrents = [0, 0, 0, 0, 0, 0, 0, 0]  # in milliamps
currDirectParam = b'1'

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
              factor=0, BField=False, demagnetize=False, today=True):
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
        BField (bool, optional): if the csv file being read in contains a list of B vectors, this should be true. default: False
        demagnetize (bool, optional): If true, demagnetization protocol will run after each vector is tested. default: False
        today (bool, optional): today's date will be included in the output directory name. default: True
    """
    global currDirectParam
    global desCurrents
    
    # initialization of all arrays
    # all_curr_steps = np.linspace(start_val, end_val, steps)
    mean_values = []
    stdd_values = []
    expected_fields = []
    all_curr_vals = []
    
    # initialize temperature sensor and measurement routine and start measuring
    arduino = ArduinoUno('COM7')
    measure_temp = threading.Thread(target=arduino.getTemperatureMeasurements)
    measure_temp.start()
       
    enableCurrents()
    ##########################################################################
    input_list = []
    with open(inpFile, 'r') as f:
        contents = csv.reader(f)
        next(contents)
        input_list = list(contents)

    meas_duration = 22
    if not demagnetize:
        meas_duration = 0.5
    time_estimate = len(input_list) * meas_duration

    for i, row in enumerate(input_list):
        if demagnetize:
            demagnetizeCoils(current_config = 5000*np.ones(3))
        
        config = np.array(
                [float(row[0]), float(row[1]), float(row[2])])
        
        if BField:
            B_vector = np.array(
                [float(row[0]), float(row[1]), float(row[2])])
            config = tr.computeCoilCurrents(B_vector)
            
        for k in range(3):
            desCurrents[k] = config[k]*factor
        all_curr_vals.append(config*factor)
        
        setCurrents(desCurrents, currDirectParam)
        # Let the field stabilize
        sleep(0.5)
        
        time_estimate = time_estimate - i * 22
        print(f'\rmeasurement nr. {i+1}; approx. time remaining: {time_estimate//3600} hours, {time_estimate//60 % 60} '
                f'minutes and {time_estimate%60:.0f} seconds', end='', sep='', flush=False)
        
        # collect measured and expected magnetic field (of the specified sensor in measurements)
        # see measurements.py for more details
        mean_data, std_data = measure(node, N=7, average=True)
        mean_values.append(mean_data)
        stdd_values.append(std_data)
        # we already know the expected field values
        if BField:
            expected_fields.append(B_vector)
        else:
            # estimate of resulting B field
            B_expected = tr.computeMagField(config*factor, windings)
            expected_fields.append(B_expected)
    ##########################################################################
    # save temperature measurements
    arduino.stop = True
    measure_temp.join()
    saveTempData(arduino.data_stack,
                 directory=r'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_1_Vector_Magnet\2_ECB_Control_Code\ECB_Main_Comm_Measurement\temperature_measurements',
                 filename_suffix='temp_meas_during_gridsweep')
    ##########################################################################
    # create/find subdirectory to save measurements
    fileprefix = 'field_meas'
    # folder,
    if today:
        now = datetime.now().strftime('%y_%m_%d')
        filePath = rf'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\1_data_analysis_interpolation\Data_Analysis_For_VM\data_sets\{datadir}_{now}'
    else:
        filePath = rf'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\1_data_analysis_interpolation\Data_Analysis_For_VM\data_sets\{datadir}'

    if demagnetize:
        demagnetizeCoils(all_curr_vals[-1])
    # end of measurements
    disableCurrents()
    # saving data section (prepared for plotting)
    saveDataPoints((np.array(all_curr_vals) / 1000), np.array(mean_values),
                   np.array(stdd_values), np.array(expected_fields), filePath, fileprefix)



def runCurrents(config_list, t=[], subdir='default_location',demagnetize=False):
    """
    run arbitrary currents (less than maximum current) on each channel
    when running without a timer, the current can be changed in a menu and the magnetic field can
    be measured with the metrolab sensor.


    Args:
        config_list (np.array(list(int)), length 3): current values in [mA]. Make sure not to give more than 3!
        t (int, optional): timer duration list. multiple timers -> different currents will be set for different 
                           amounts of time.
            If zero, user can decide whether to change the current or deactivate it. Defaults to 0.
        direct (bytes, optional): current direct parameter (can usually be left alone). Defaults to b'1'.
        demagnetize (bool): if true, demagnetization will run after the field is deactivated.
    """
    global currDirectParam
    global desCurrents

    currDirectParam = b'1'
    # copy the computed current values (mA) into the desCurrents list (first 3 positions)
    # cast to int

    # user specified time
    enableCurrents()

    # on until interrupted by user
    if len(t) == 0 or t[0] == 0:
        channels = config_list[0]
        for i in range(len(channels)):
            desCurrents[i] = int(channels[i])
            
        setCurrents(desCurrents, currDirectParam)
        # wait until user presses enter
        c1 = '0'
        while c1 != 'q':
            c1 = input(
                '[q] to disable currents\n[c]: get currents\n[r]: Set new currents\n[s]: monitor magnetic field')
            if c1 == 'c':
                getCurrents()
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

                setCurrents(desCurrents, currDirectParam)
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
        arduino = ArduinoUno('COM7')
        measure_temp = threading.Thread(target=arduino.getTemperatureMeasurements)
        measure_temp.start()
        
        try:
            duration = int(input('Duration of measurement (default is 10s): '))
        except:
            duration = 10
        # use only with Metrolab sensor
        global returnDict
        params = {'name': 'BFieldMeasurement', 'block_size': 30, 'period': 1e-2, 'duration': duration, 'averaging': 5}

        faden = myMeasThread(10, **params)
        faden.start()

        for index, timer in enumerate(t):
            channels = config_list[index]
            for i in range(len(channels)):
                desCurrents[i] = int(channels[i])
            
            setCurrents(desCurrents, currDirectParam)
            # prevent the connection with the ECB from timing out for long measurements.
            if timer < 500:
                countdown = timerThread(11,timer)
                countdown.start()
                sleep(timer)
                countdown.join()
            else:
                countdown = timerThread(11,timer)
                countdown.start()
                starttime = time()
                while time() - starttime < timer:
                    pause = min(500, timer - (time() - starttime))
                    sleep(pause)
                    getCurrents()
                countdown.join()
                
        arduino.stop = True
        measure_temp.join()
        arduino.saveTempData(arduino.data_stack,
                             directory=r'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\1_data_analysis_interpolation\Data_Analysis_For_VM\temperature_measurements',
                             filename_suffix='temp_meas_timed_const_fields')
        
        savedir = input('Name of directory where this measurement will be saved: ')
        saveLoc = rf'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\1_data_analysis_interpolation\Data_Analysis_For_VM\data_sets\{savedir}'
        strm(returnDict, saveLoc, now=True)
        
    if demagnetize:
        demagnetizeCoils()
        
    disableCurrents()
        

def generateMagneticField(vectors, t=[], subdir='default_location', demagnetize=False):
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
    global currDirectParam
    global desCurrents

    enableCurrents()
    if len(t) == 0 or t[0] == 0:
        B_Field = vectors[0]
        B_Field_cartesian = tr.computeMagneticFieldVector(B_Field[0], B_Field[1], B_Field[2])
        channels = tr.computeCoilCurrents(B_Field_cartesian)
        for i in range(len(channels)):
            desCurrents[i] = int(channels[i])
            
        print(f'Currents on each channel: ({desCurrents[0]}, {desCurrents[1]}, {desCurrents[2]})')
        setCurrents(desCurrents, currDirectParam)
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
                setCurrents(desCurrents, currDirectParam)

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
                setCurrents(desCurrents, currDirectParam)
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
        arduino = ArduinoUno('COM7')
        measure_temp = threading.Thread(target=arduino.getTemperatureMeasurements)
        measure_temp.start()
        
        try:
            duration = int(input('Duration of measurement (default is 10s): '))
        except:
            duration = 10
        # use only with Metrolab sensor
        global returnDict
        params = {'name': 'BFieldMeasurement', 'block_size': 30, 'period': 1e-2, 'duration': duration, 'averaging': 5}

        faden = myMeasThread(10, **params)
        faden.start()

        for index, timer in enumerate(t):
            B_Field = vectors[index]
            B_Field_cartesian = tr.computeMagneticFieldVector(B_Field[0], B_Field[1], B_Field[2])
            channels = tr.computeCoilCurrents(B_Field_cartesian)
            for i in range(len(channels)):
                desCurrents[i] = int(channels[i])
            
            setCurrents(desCurrents, currDirectParam)
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
                    getCurrents()
                countdown.join()
        
        arduino.stop = True
        measure_temp.join()
        arduino.saveTempData(arduino.data_stack,
                             directory=r'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\1_data_analysis_interpolation\Data_Analysis_For_VM\temperature_measurements',
                             filename_suffix='temp_meas_timed_const_fields')
        
        savedir = input('Name of directory where this measurement will be saved: ')
        saveLoc = rf'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\1_data_analysis_interpolation\Data_Analysis_For_VM\data_sets\{savedir}'
        strm(returnDict, saveLoc, now=True)
        
    if demagnetize:
        demagnetizeCoils()
        
    disableCurrents()

    
    
if __name__ == "__main__":
    params = {'block_size': 40, 'period': 0.01, 'duration': 40, 'averaging': 1}
  
    faden = myMeasThread(1, **params)
    faden.start()

    openConnection()
    enableCurrents()
    sleep(10)
    demagnetizeCoils()
    disableCurrents()
    faden.join()

    closeConnection()
    
    strm(returnDict, r'data_sets\noise_test_THM', 'zero_field_close_withoutECB', now=True)
