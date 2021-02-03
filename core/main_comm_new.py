# filename: main_comm_new.py
#
# This code is meant to bundle the communication with the IT6432 current sources.
#
# Author: Maxwell Guerne-Kieferndorf (QZabre)
#         gmaxwell at student.ethz.ch
#
# Date: 13.01.2021
# latest update: 25.01.2021

import csv
import logging
import math
import sys
import threading
from os import getcwd, path
from pathlib import Path
from time import sleep, time

########## Standard library imports ##########
import numpy as np

# current source
try:
    from IT6432.it6432connection import IT6432Connection
except ModuleNotFoundError:
    sys.path.insert(1, path.join(sys.path[0], ".."))
    from IT6432.it6432connection import IT6432Connection

    from core.current_control import currControlThread, currentController


class voltageRamper(threading.Thread):
    """
    A thread that simply runs the function rampVoltage.

    Args:
        connection (IT6432Connection): Current source object which is to be controlled
        new_voltage (float): Target voltage
        new_current (float): Target current
        threadID (int, optional): number of thread for keeping track of which threads are
                                    running. Defaults to 0.
    """

    def __init__(
        self,
        connection: IT6432Connection,
        new_voltage,
        new_current,
        *args,
        step_size=0.01,
        threadID=0
    ):

        threading.Thread.__init__(self)

        self.connection = connection
        self.targetV = new_voltage
        self.targetI = new_current
        self.step_size = step_size
        self.threadID = threadID
        if args[0]:
            self.threadID = connection.channel()
        self.name = 'VoltageRamper' + str(self.threadID)

    def run(self):

        try:
            rampVoltage(self.connection, self.targetV, self.targetI, step_size=self.step_size)

        except Exception as e:
            print(f'There was a problem on {self.name}: {e}')


def openConnection(channel_1: IT6432Connection, channel_2=None, channel_3=None):
    """
    Open a connection to a IT6432 current source.

    Returns:
        IT6432Connection: Instances of connection objects representing each channel.
    """
    channel_1.connect()
    channel_1._write("system:remote")

    if channel_2 is not None:
        channel_2.connect()
        channel_2._write("system:remote")

    if channel_3 is not None:
        channel_3.connect()
        channel_3._write("system:remote")


def closeConnection(channel_1: IT6432Connection, channel_2=None, channel_3=None):
    """Close the connection with the current sources."""
    channel_1._write("system:local")
    channel_1.close()

    if channel_2 is not None:
        channel_2._write("system:local")
        channel_2.close()

    if channel_3 is not None:
        channel_3._write("system:local")
        channel_3.close()


def disableCurrents(channel_1: IT6432Connection, channel_2=None, channel_3=None):
    """Disable current controllers."""
    thread_pool = []

    worker_1 = voltageRamper(channel_1, 0, 0, True)
    thread_pool.append(worker_1)

    if channel_2 is not None:
        worker_2 = voltageRamper(channel_2, 0, 0, True)
        thread_pool.append(worker_2)

    if channel_3 is not None:
        worker_3 = voltageRamper(channel_3, 0, 0, True)
        thread_pool.append(worker_3)

    for thread in thread_pool:
        thread.start()
    for thread in thread_pool:
        thread.join()


def setCurrents(
    channel_1: IT6432Connection,
    channel_2=None,
    channel_3=None,
    desCurrents=[0, 0, 0]
):
    """
    Set current values for each channel. Voltage is limited as well to prevent very fast current changes due to inductance.

    Args:
        channel_1 (IT6432Connection): the first passed current source object to modify
        channel_2 (IT6432Connection, optional): Defaults to None.
        channel_3 (IT6432Connection, optional): Defaults to None.
        desCurrents (list, optional):  list of length 3 containing int values of currents (unit: mA), Defaults to [0,0,0].
    """
    thread_pool = []

    signs = np.sign(desCurrents)

    idx_1 = channel_1._channel - 1
    current_1 = (
        signs[idx_1] * desCurrents[idx_1]
        if abs(desCurrents[idx_1]) <= channel_1.currentLim
        else channel_1.currentLim
    )
    # conservative estimation of coil resistance: 0.48 ohm
    v_set_1 = signs[idx_1] * 0.472 * current_1
    worker_1 = voltageRamper(channel_1, v_set_1, current_1, True, step_size=0.05)
    # controller_1 = currentController(channel_1, current_1, prop_gain=0.045)

    thread_pool.append(worker_1)
    #     threading.Thread(
    #         controller_1.piControl,
    #         name='currentController_1',
    #         args=[False, False]))

    if channel_2 is not None:
        idx_2 = channel_2._channel - 1
        current_2 = (
            signs[idx_2] * desCurrents[idx_2]
            if abs(desCurrents[idx_2]) <= channel_2.currentLim
            else channel_2.currentLim
        )
        # conservative estimation of coil resistance: 0.48 ohm
        v_set_2 = signs[idx_2] * 0.472 * current_2
        worker_2 = voltageRamper(channel_2, v_set_2, current_2, True, step_size=0.05)
        # controller_2 = currentController(channel_2, current_2, prop_gain=0.045)

        thread_pool.append(worker_2)
        #     threading.Thread(
        #         controller_2.piControl,
        #         name='currentController_2',
        #         args=[False, False]))

    if channel_3 is not None:
        idx_3 = channel_3._channel - 1
        current_3 = (
            signs[idx_3] * desCurrents[idx_3]
            if abs(desCurrents[idx_3]) <= channel_3.currentLim
            else channel_3.currentLim
        )
        # conservative estimation of coil resistance: 0.48 ohm
        v_set_3 = signs[idx_3] * 0.472 * current_3
        worker_3 = voltageRamper(channel_3, v_set_3, current_3, True, step_size=0.05)
        # controller_3 = currentController(channel_3, current_3, prop_gain=0.045)

        thread_pool.append(worker_3)
        #     threading.Thread(
        #         controller_3.piControl,
        #         name='currentController_3',
        #         args=[False, False]))

    for thread in thread_pool:
        thread.start()
    for thread in thread_pool:
        thread.join()


def rampVoltage(
    connection: IT6432Connection,
    new_voltage,
    new_current,
    step_size=0.01
):
    """
    Ramp voltage to a new specified value. The current should not be directly set, due
    to the load inductance instead it is a limit for the voltage increase. Like this, it
    is possible to ensure that the current takes the exact desired value without causing
    the voltage protection to trip.

    Args:
        connection (IT6432Connection):
        new_voltage (float): Target voltage
        new_current (float): Target current
        step_size (float, optional): Voltage increment. Defaults to 0.01.
    """
    logging.basicConfig(filename="voltage_ramp.log", level=logging.DEBUG, force=True)
    logging.info("now ramping current in channel %s", connection.channel())

    connection.clrOutputProt()

    if connection.query("output?") == "0":
        connection._write("voltage 0V;:output 1")

    if new_current > connection.currentLim:
        new_current = connection.currentLim
    if new_current < 0.002 or abs(new_voltage) < 0.001:
        new_current = 0.002
        new_voltage = 0
    if abs(new_voltage) > connection.voltageLim:
        new_voltage = connection.voltageLim

    meas_voltage = getMeasurement(connection, meas_quantity="voltage")[0]
    meas_current = getMeasurement(connection, meas_quantity="current")[0]

    logging.debug(f"actual voltage: {meas_voltage}V, actual current: {meas_current}A")
    logging.debug(f"target voltage: {new_voltage}V, desired current: {new_current}A")

    if new_current - abs(meas_current) < 0:
        intermediate_step = 0.4 * new_current if new_current > 0.01 else 0
        rampVoltageSimple(connection, meas_voltage, intermediate_step, step_size)

    repeat_count = 0
    meas_current_queue = [meas_current, 0]
    while not (abs(meas_current) < new_current or repeat_count >= 5):
        meas_current_queue.insert(0, getMeasurement(connection, meas_quantity="current")[0])
        meas_current_queue.pop(2)
        repeat = abs(meas_current_queue[0] - meas_current_queue[1]) < 0.002
        if repeat:
            repeat_count += 1
        else:
            repeat_count = 0

    connection._write(f"current {new_current}A")

    if new_current < 0.002 or abs(new_voltage) < 0.001:
        connection._write("output 0")
    else:
        meas_voltage = getMeasurement(connection, meas_quantity="voltage")[0]
        rampVoltageSimple(connection, meas_voltage, new_voltage, step_size)

    messages = connection.getStatus()
    if "QER0" in messages.keys():
        logging.info(messages["QER0"] + ", channel: %s", connection.channel())
    if "QER4" in messages.keys():
        logging.info(messages["QER4"] + ", channel: %s", connection.channel())
    if "OSR1" in messages.keys():
        logging.info(messages["OSR1"] + ", channel: %s", connection.channel())
        # print(f'{messages}')
        # connection.checkError()


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
    connection._write(f"voltage {set_voltage}V")
    diff_v = new_voltage - set_voltage
    sign = np.sign(diff_v)
    while abs(diff_v) >= threshold:
        set_voltage = set_voltage + sign * step_size
        connection._write(f"voltage {set_voltage}V")
        diff_v = new_voltage - set_voltage
        sign = np.sign(diff_v)

    connection._write(f"voltage {new_voltage}V")


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


def demagnetizeCoils(
    channel_1: IT6432Connection,
    channel_2: IT6432Connection,
    channel_3: IT6432Connection,
    current_config=[1, 1, 1],
    # factor=0.5
):
    """
    Try to eliminate any hysteresis effects by applying a slowly oscillating and decaying
    voltage to the coils.

    Args:
        factor (float): A factor 0<factor<1 to reduce the applied field by.
    """
    # if factor >= 1:
    #     factor = 0.99
    steps = np.array([0, 1, 2, 3, 4])
    bounds = 0.475 * np.outer(current_config, np.exp(-steps))

    channel_1._write('current 5.01A')
    channel_2._write('current 5.01A')
    channel_3._write('current 5.01A')

    thread_pool = [None, None, None]
    sign = -1

    for i in range(bounds.shape[1]):
        voltages = getMeasurement(channel_1, channel_2, channel_3, meas_quantity='voltage')
        thread_pool[0] = threading.Thread(target=rampVoltageSimple,
                                          name='currentController_1',
                                          args=[channel_1, voltages[0], sign * bounds[0, i]],
                                          kwargs={'step_size': 0.06})

        thread_pool[1] = threading.Thread(target=rampVoltageSimple,
                                          name='currentController_2',
                                          args=[channel_2, voltages[1], sign * bounds[1, i]],
                                          kwargs={'step_size': 0.06})

        thread_pool[2] = threading.Thread(target=rampVoltageSimple,
                                          name='currentController_3',
                                          args=[channel_3, voltages[2], sign * bounds[2, i]],
                                          kwargs={'step_size': 0.06})
        for thread in thread_pool:
            thread.start()

        for thread in thread_pool:
            thread.join()
        sign *= -1
        sleep(0.1)

    disableCurrents(channel_1, channel_2, channel_3)


########## test stuff out ##########
if __name__ == "__main__":
    channel_1 = IT6432Connection(1)
    channel_2 = IT6432Connection(2)
    channel_3 = IT6432Connection(3)
    openConnection(channel_1, channel_2, channel_3)

    setCurrents(channel_1, channel_2, channel_3, np.array([1, 1, 1]))
    sleep(0.5)
    demagnetizeCoils(channel_1, channel_2, channel_3, np.array([1, 1, 1]))
    # disableCurrents(channel_1, channel_2, channel_3)

    closeConnection(channel_1, channel_2, channel_3)
