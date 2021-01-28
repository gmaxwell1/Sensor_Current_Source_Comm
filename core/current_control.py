from IT6432.it6432connection import IT6432Connection
import threading
import sys
import os.path as path

import numpy as np
sys.path.insert(1, path.join(sys.path[0], '..'))

threadLock = threading.Lock()
control_on = False


class currentController(threading.Thread):
    def __init__(
        self,
        connection: IT6432Connection,
        current_set,
        **kwargs
    ):
        """
        A thread that simply runs the function rampVoltage.

        Args:
            connection (IT6432Connection): Current source object which is to be controlled
            new_voltage (float): Target voltage
            new_current (float): Target current
            threadID (int, optional): number of thread for keeping track of which threads are
                                      running. Defaults to 0.
        """
        threading.Thread.__init__(self)

        self.connection = connection
        self.I_setpoint = current_set

        if 'prop_gain' in kwargs.keys():
            self.prop_gain = kwargs['prop_gain']
        else:
            self.prop_gain = 0.1

        if 'int_gain' in kwargs.keys():
            self.int_gain = kwargs['prop_gain']
        else:
            self.int_gain = 0

        self.threadID = self.connection.channel()
        self.name = 'currentController_' + str(self.threadID)

    def run(self):

        try:
            piControl(
                self.connection,
                self.I_setpoint,
                prop_gain=self.prop_gain,
                int_gain=self.int_gain)

        except Exception as e:
            print(f'There was a problem on {self.name}: {e}')


def rampVoltageSimple(
    connection: IT6432Connection,
    set_voltage,
    new_voltage,
    step_size=0.01
):
    """
    Helper function to take care of setting the voltage.

    Args:
        connection (IT6432Connection):
        set_voltage (float): Voltage that is set right now.
        new_voltage (float): Target voltage.
        step_size (float, optional): Defaults to 0.01.
        threshold (float, optional): Defaults to 0.02.
    """
    threshold = 2 * step_size
    connection._write(f"voltage {set_voltage}")
    diff_v = new_voltage - set_voltage
    sign = np.sign(diff_v)
    while abs(diff_v) >= threshold:
        set_voltage = set_voltage + sign * step_size
        connection._write(f"voltage {set_voltage}V")
        diff_v = new_voltage - set_voltage
        sign = np.sign(diff_v)

    connection._write(f"voltage {new_voltage}V")


def piControl(connection: IT6432Connection,
              I_setpoint,
              prop_gain=0.1, int_gain=0):

    # if false, stop control
    global control_on
    threadLock.acquire()
    control_on = True
    threadLock.release()

    I_limit = connection.currentLim
    if I_setpoint < 0.002:
        I_setpoint = 0

    if connection.query("output?") == "0":
        connection._write(f"voltage 0V;:current {I_limit}A;:output 1")

    # parameters for PI control:
    Kp = prop_gain
    Ki = int_gain
    integrator = 0
    hold = 1
    reset = 0
    Kff = 0.475  # coil resistance
    # control input & error
    v_control = 0
    i_error = 0

    # this voltage (2.33 to be precise) leads to maximum output current.
    v_cmax = 2.45

    v_meas = getMeasurement(connection, meas_quantity="voltage")[0]
    i_meas = getMeasurement(connection, meas_quantity="current")[0]

    print(f"actual voltage: {v_meas}V, actual current: {i_meas}A")
    print(f"desired current: {I_setpoint}A")

    v_control += Kff * I_setpoint
    rampVoltageSimple(connection, v_meas, v_control, 0.025)

    i_error = I_setpoint - i_meas
    v_control += Kp * i_error

    v_repeat_count = 0
    sat_count = 0
    v_meas_queue = [v_meas, 0]
    # v_control_queue = [v_control, 0]
    # i_repeat_count = 0
    # current_meas_queue = [i_meas, 0]

    while control_on:

        connection._write(f'voltage {v_control}V')

        v_control += Kp * i_error
        if not hold:
            integrator += i_error

        v_control += Ki * integrator

        if v_control > v_cmax:
            v_control = v_cmax
            sat_count += 1
        else:
            sat_count = 0

        v_meas_queue.insert(0, getMeasurement(connection, meas_quantity="voltage")[0])
        v_meas_queue.pop(2)
        i_meas = getMeasurement(connection, meas_quantity="current")[0]
        i_error = I_setpoint - i_meas

        hold = i_error > Kp or i_error <= 0.001

        if abs(v_meas_queue[0] - v_control) > Kp:
            v_repeat_count += 1
        else:
            v_repeat_count = 0
        reset = v_repeat_count > 5 or sat_count > 5
        if reset:
            integrator = 0


def getMeasurement(
    channel_1: IT6432Connection,
    channel_2=None,
    channel_3=None,
    meas_type=[""],
    meas_quantity=["current"]
):
    """
    Get DC current/power/voltage values from each channel

    Returns: a list of all the currents (or an error code)
    """
    command = "measure:"
    quantities = ["current", "voltage", "power"]
    types = ["", "acdc", "max", "min"]
    if meas_quantity not in quantities:
        meas_quantity = "current"
    if meas_type not in types:
        meas_type = ""

        command += meas_quantity
        if meas_type != "":
            command += ":" + meas_type[0]
        command += "?"

    measured = []
    res = channel_1.query(command)
    if isinstance(res, list):
        res = res[0]
    measured.append(float(res))

    if channel_2 is not None:
        res = channel_2.query(command)
        if isinstance(res, list):
            res = res[0]
        measured.append(float(res))

    if channel_3 is not None:
        res = channel_3.query(command)
        if isinstance(res, list):
            res = res[0]
        measured.append(float(res))

    return measured
