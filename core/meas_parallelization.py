import threading

try:
    # import core.field_current_tr as tr
    from core.main_comm_new import *
    from core.measurement_functions import *
    from metrolabTHM1176.thm1176 import MetrolabTHM1176Node
    # from other_useful_functions.general_functions import save_time_resolved_measurement as strm, ensure_dir_exists, sensor_to_magnet_coordinates
    # from other_useful_functions.arduinoPythonInterface import ArduinoUno, saveTempData

except ModuleNotFoundError:
    import os
    sys.path.insert(1, os.path.join(sys.path[0], '..'))
    # import core.field_current_tr as tr
    from core.main_comm_new import *
    from core.measurement_functions import *
    from metrolabTHM1176.thm1176 import MetrolabTHM1176Node
    # from other_useful_functions.general_functions import save_time_resolved_measurement as strm, ensure_dir_exists, sensor_to_magnet_coordinates
    # from other_useful_functions.arduinoPythonInterface import ArduinoUno, saveTempData


# order of data: Bx list, By list, Bz list, time list
returnDict = {'Bx': 0, 'By': 0, 'Bz': 0, 'time': 0, 'temp': 0}
flags = [1]
threadLock = threading.Lock()


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
        
class measThreadArbitrary(threading.Thread):
    """
    Start a new thread for measuring magnetic field over time with the Metrolab sensor.
    Thread has a name name and multiple member variables.

    kwargs:
        node
        name (str, optional): thread name (default: 'MeasureThread')
        period (float): trigger period, should be in the interval (122e-6, 2.79)
                        (default: 0.1)
        averaging (int): number of measured values to average over.
                            (default: 1)
        block_size (int): number of measured values to fetch at once.
                            (default: 1)
        duration (float): duration of measurement series
                            (default: None)
    """

    def __init__(self, node: MetrolabTHM1176Node, name='MeasureThread', **kwargs):
        threading.Thread.__init__(self, name=name)
        keys = kwargs.keys()

        self.sensor_node = node

    def run(self):
        global returnDict

        threadLock.acquire()
        self.sensor_node.stop = False
        threadLock.release()
        self.sensor_node.start_acquisition()
        
        # Sensor coordinates to preferred coordinates transformation
        xValues = np.array(self.sensor_node.data_stack['Bz'])
        xValues = -xValues  # np.subtract(-xValues, xOffset)

        yValues = np.array(self.sensor_node.data_stack['Bx'])
        yValues = -yValues

        zValues = self.sensor_node.data_stack['By']

        timeline = self.sensor_node.data_stack['Timestamp']

        t_offset = timeline[0]
        for ind in range(len(timeline)):
            timeline[ind] = round(timeline[ind] - t_offset, 3)

        threadLock.acquire()
        try:
            if (len(self.sensor_node.data_stack['Bx']) != len(
                    timeline) or len(self.sensor_node.data_stack['By']) != len(
                    timeline) or len(self.sensor_node.data_stack['Bz']) != len(timeline)):
                raise ValueError(
                    "length of Bx, By, Bz do not match that of the timeline")
            else:
                returnDict = {
                    'Bx': xValues.tolist(),
                    'By': yValues.tolist(),
                    'Bz': zValues.tolist(),
                    'temp': self.sensor_node.data_stack['Temperature'],
                    'time': timeline}
        except Exception as e:
            print(f'{__name__}: {e}')

        threadLock.release()

        print(f"Finished measuring. {self.name} exiting.")


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
        # make sure there are no concurrency issues
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
            print(
                f'\rtime remaining: {int((self.countdownDuration - timeDiff))//3600} hours, {int((self.countdownDuration - timeDiff))//60 % 60} '
                f'minutes and {(self.countdownDuration - timeDiff)%60:.0f} seconds',
                end='',
                sep='',
                flush=False)

            timeDiff = time() - self.startTime
            sleep(0.096)


def stopMeasThread(measThread: measThreadArbitrary):
    threadLock.acquire()
    measThread.sensor_node.stop = True
    threadLock.release()


def return_dict():
    global returnDict
    return returnDict
