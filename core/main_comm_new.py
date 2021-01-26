# filename: main_comm_new.py
#
# This code is meant to bundle the communication with the IT6432 current sources.
#
# Author: Maxwell Guerne-Kieferndorf (QZabre)
#         gmaxwell at student.ethz.ch
#
# Date: 13.01.2021
# latest update: 25.01.2021

########## Standard library imports ##########
import numpy as np
import math
from time import time, sleep
import sys
from os import getcwd, path
from pathlib import Path
import csv
import logging
import threading

# current source
try:
    from IT6432.it6432connection import IT6432Connection
except ModuleNotFoundError:
    sys.path.insert(1, path.join(sys.path[0], ".."))
    from IT6432.it6432connection import IT6432Connection


class voltageRamper(threading.Thread):
    def __init__(
        self,
        connection: IT6432Connection,
        new_voltage,
        new_current,
        *args,
        step_size=0.01,
        threadID=0
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

        self.threadID = threadID
        self.connection = connection
        self.targetV = new_voltage
        self.targetI = new_current
        self.step_size = step_size
        if args[0]:
            self.threadID = connection.channel()

    def run(self):

        try:
            rampVoltage(self.connection, self.targetV, self.targetI, step_size=self.step_size)

        except Exception as e:
            print("There was a problem!")
            print(e)


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
    v_set_1 = signs[idx_1] * 0.48 * current_1
    worker_1 = voltageRamper(channel_1, v_set_1, current_1, True, step_size=0.05)

    thread_pool.append(worker_1)

    if channel_2 is not None:
        idx_2 = channel_2._channel - 1
        current_2 = (
            signs[idx_2] * desCurrents[idx_2]
            if abs(desCurrents[idx_2]) <= channel_2.currentLim
            else channel_2.currentLim
        )
        # conservative estimation of coil resistance: 0.48 ohm
        v_set_2 = signs[idx_2] * 0.48 * current_2
        worker_2 = voltageRamper(channel_2, v_set_2, current_2, True, step_size=0.05)

        thread_pool.append(worker_2)

    if channel_3 is not None:
        idx_3 = channel_3._channel - 1
        current_3 = (
            signs[idx_3] * desCurrents[idx_3]
            if abs(desCurrents[idx_3]) <= channel_3.currentLim
            else channel_3.currentLim
        )
        # conservative estimation of coil resistance: 0.48 ohm
        v_set_3 = signs[idx_3] * 0.48 * current_3
        worker_3 = voltageRamper(channel_3, v_set_3, current_3, True, step_size=0.05)

        thread_pool.append(worker_3)

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
        connection._write("voltage 0V")
        connection._write("output 1")

    if new_current > connection.currentLim:
        new_current = connection.currentLim
    elif new_current < 0.002 or new_voltage == 0:
        new_current = 0.002
        new_voltage = 0
    if abs(new_voltage) > connection.voltageLim:
        new_voltage = connection.voltageLim

    meas_voltage = getMeasurement(connection, meas_quantity="voltage")[0]
    meas_current = getMeasurement(connection, meas_quantity="current")[0]

    logging.debug(f"actual voltage: {meas_voltage}V, actual current: {meas_current}A")
    logging.debug(f"target voltage: {new_voltage}V, desired current: {new_current}A")

    sign_new = np.sign(new_voltage)
    diff_v = new_voltage - meas_voltage

    if new_voltage == 0:
        rampVoltageSimple(connection, meas_voltage, 0, step_size)
        connection._write(f"voltage {new_voltage}V")
        sleep(0.1)
        connection._write(f"current {new_current}A")
        connection._write("output 0")

    else:
        if new_current - abs(meas_current) < 0 and sign_new == np.sign(meas_voltage):
            print(f'{sign_new} == {np.sign(meas_voltage)}, ')
            lower_bound = np.sign(new_voltage) * 0.1 if new_voltage > 0.1 else new_voltage
            rampVoltageSimple(
                connection, meas_voltage, new_voltage - lower_bound, step_size
            )
        elif new_current - abs(meas_current) < 0 and sign_new != np.sign(meas_voltage):
            rampVoltageSimple(connection, meas_voltage, 0, step_size)

        while not abs(meas_current) < new_current:
            meas_current = getMeasurement(connection, meas_quantity="current")[0]
            meas_voltage = getMeasurement(connection, meas_quantity="voltage")[0]

        connection._write(f"current {new_current}A")
        rampVoltageSimple(connection, meas_voltage, new_voltage, step_size)
        connection._write(f"voltage {new_voltage}V")

    messages = connection.getStatus()
    if "QER0" in messages.keys():
        logging.info(messages["QER0"] + ", channel: %s", connection.channel())
    if "QER4" in messages.keys():
        logging.info(messages["QER4"] + ", channel: %s", connection.channel())
    if "OSR1" in messages.keys():
        logging.info(messages["OSR1"] + ", channel: %s", connection.channel())
        print(f'{messages}')
        connection.checkError()


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
    print(f'Ramping voltage from {set_voltage}V to {new_voltage}V')
    while abs(diff_v) >= threshold:
        set_voltage = set_voltage + sign * step_size
        connection._write(f"voltage {set_voltage}V")
        diff_v = new_voltage - set_voltage


def getMeasurement(
    channel_1: IT6432Connection,
    channel_2=None,
    channel_3=None,
    meas_type="",
    meas_quantity="current"
):
    """
    Get DC current/power/voltage values from each channel

    Returns: a list of all the currents (or an error code)
    """
    basecmd = "measure:"
    quantities = ["current", "voltage", "power"]
    types = ["", "acdc", "max", "min"]
    if not meas_quantity in quantities:
        meas_quantity = "current"
    if not meas_type in types:
        meas_type = ""

    command = basecmd + meas_quantity
    if meas_type != "":
        command += ":" + meas_type
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
    channel_2=IT6432Connection,
    channel_3=IT6432Connection,
    current_config=np.array([1000, 1000, 1000])
):
    """
    Try to eliminate any hysteresis effects by applying a slowly oscillating and decaying electromagnetic field to the coils.

    Args:
        - previous_amp (int, optional): the maximum current value (directly) previously applied to coils
    """
    # channel_1._write('output 1')
    # channel_2._write('output 1')
    # channel_3._write('output 1')

    tspan = np.linspace(0, 5, 5)
    func1 = current_config[0] * np.exp(-0.2 * tspan)
    func2 = current_config[1] * np.exp(-0.2 * tspan)
    func3 = current_config[2] * np.exp(-0.2 * tspan)

    sign = 1
    # channel_1._write('INITiate:name transient')
    # channel_2._write('INITiate:name transient')
    # channel_3._write('INITiate:name transient')
    # # print(func1)
    # desCurrents = [0, 0, 0]
    for k in range(len(tspan)):
        desCurrents[0] = func1[k]
        desCurrents[1] = func2[k]
        desCurrents[2] = func3[k]
        sign = sign * -1
        rampVoltage(channel_1, sign * current_config[0], func1[k])
        rampVoltage(channel_2, sign * current_config[1], func2[k])
        rampVoltage(channel_3, sign * current_config[2], func3[k])
    #     sleep(1 - time() * 1 % 1)


########## test stuff out ##########
if __name__ == "__main__":
    channel_1 = IT6432Connection(1)
    channel_2 = IT6432Connection(2)
    channel_3 = IT6432Connection(3)
    openConnection(channel_1, channel_2, channel_3)

    # print(channel_1.query('init:name tran'))
    # print(channel_2.query('SYSTem:COMMunicate:PROTocol?'))
    # print(channel_3.query('SYSTem:COMMunicate:PROTocol?'))
    # r1 = voltageRamper(channel_1,1,2, True)
    # r2 = voltageRamper(channel_2,1,2, True)
    # r3 = voltageRamper(channel_3,1,2, True)

    # r1.start()
    # r2.start()
    # r3.start()
    # r1.join()
    # r2.join()
    # r3.join()
    # print(channel_1.clrOutputProt())
    # print(channel_2.clrOutputProt())
    # print(channel_3.clrOutputProt())
    # getMaxMinOutput()
    # setMaxCurrVolt(5.02)

    # demagnetizeCoils(channel_1,channel_2,channel_3, [5,5,5])
    setCurrents(channel_1, channel_2, channel_3, desCurrents=[5, 5, 5])
    sleep(10)
    setCurrents(channel_1, channel_2, channel_3, desCurrents=[1.328, 0.940, 0.381])
    sleep(10)
    setCurrents(channel_1, channel_2, channel_3, desCurrents=[-1.228, 0.100, -1.381])
    sleep(10)

    # channel_1.query('init:name tran')
    # channel_1._write(':voltage:trigger 1.5')
    # channel_1._write('*TRG')

    # sleep(10)

    # volt_list = getMeasurement(channel_1, channel_2, channel_3, meas_quantity='voltage')
    # print(volt_list)
    # V = 0.4
    # channel_1._write(f'voltage {V}V;STEP 0.1V;:current 1A')
    # channel_2._write('INITiate:name transient')
    # channel_3._write('INITiate:name transient')

    # print(channel_1.query('system:err?'))
    # print('output 1: ' + channel_1.query('output?'))
    # print('output 2: ' + channel_2.query('output?'))
    # print('output 3: ' + channel_3.query('output?'))
    # stat = channel_1.getStatus()
    # print(f'status 1: {stat}')
    # stat = channel_2.getStatus()
    # print(f'status 2: {stat}')
    # stat = channel_3.getStatus()
    # print(f'status 3: {stat}')
    # for i in range(10):
    #     pwr_list = getMeasurement(channel_1, channel_2, channel_3, meas_quantity='power')
    #     print(f'power on channel 1/2/3: {pwr_list[0]:.3f}W, {pwr_list[1]:.3f}W, {pwr_list[2]:.3f}W')

    disableCurrents(channel_1, channel_2, channel_3)
    closeConnection(channel_1)
    closeConnection(channel_2)
    closeConnection(channel_3)
