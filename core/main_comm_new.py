"""
filename: main_comm_new.py

This code is meant to bundle the communication with the IT6432 current sources.
There may be some more functions that are necessary in the future

Author: Maxwell Guerne-Kieferndorf (QZabre)
        gmaxwell@student.ethz.ch

Date: 13.01.2021
"""
########## Standard library imports ##########
import numpy as np
import math
from time import time, sleep
import sys
from os import getcwd, path
from pathlib import Path
import csv

# current source
try:
    from IT6432.it6432connection import IT6432Connection
except ModuleNotFoundError:
    sys.path.insert(1, path.join(sys.path[0], '..'))
    from IT6432.it6432connection import IT6432Connection


def openConnection(channel_1: IT6432Connection, channel_2=None, channel_3=None):
    """
    Open a connection to a IT6432 current source.

    Returns:
        IT6432Connection: Instances of connection objects representing each channel.
    """
    channel_1.connect()
    channel_1._write('system:remote')
    
    if channel_2 is not None:
        channel_2.connect()
        channel_2._write('system:remote')
        
    if channel_3 is not None:
        channel_3.connect()
        channel_3._write('system:remote')


def closeConnection(channel_1: IT6432Connection, channel_2=None, channel_3=None):
    """
    Close the connection with the current sources.
    """
    channel_1._write('system:local')
    channel_1.close()
    
    if channel_2 is not None:
        channel_2._write('system:local')
        channel_2.close()
        
    if channel_3 is not None:
        channel_3._write('system:local')
        channel_3.close()
        

def disableCurrents(channel_1: IT6432Connection, channel_2=None, channel_3=None):
    """
    Disable current controllers.
    """
    
    rampVoltage(channel_1, 0, 0)    
  
    if channel_2 is not None:
        rampVoltage(channel_2, 0, 0)    
        
    if channel_3 is not None:
        rampVoltage(channel_3, 0, 0)    


def setCurrents(channel_1: IT6432Connection, channel_2=None, channel_3=None, desCurrents=[0,0,0]):
    """
    Set current values for each channel. Voltage is limited as well to prevent very fast current changes due to inductance.

    Args:
        channel_1 (IT6432Connection): the first passed current source object to modify
        channel_2 (IT6432Connection, optional): Defaults to None.
        channel_3 (IT6432Connection, optional): Defaults to None.
        desCurrents (list, optional):  list of length 3 containing int values of currents (unit: mA), Defaults to [0,0,0].
    """
    signs = np.sign(desCurrents)
    
    idx_1 = channel_1._channel - 1
    current_1 = signs[idx_1] * desCurrents[idx_1] / 1000 if abs(desCurrents[idx_1]) <= 5000 else 5.0
    v_set_1 = signs[idx_1] * 0.49 * current_1
    
    rampVoltage(channel_1, v_set_1, current_1)

    if channel_2 is not None:
        idx_2 = channel_2._channel - 1
        current_2 =  signs[idx_2] * desCurrents[idx_2] / 1000 if abs(desCurrents[idx_2]) <= 5000 else 5.0
        v_set_2 = signs[idx_2] * 0.49 * current_2
    
        rampVoltage(channel_2, v_set_2, current_2)

    if channel_3 is not None:
        idx_3 = channel_3._channel - 1
        current_3 =  signs[idx_3] * desCurrents[idx_3] / 1000 if abs(desCurrents[idx_3]) <= 5000 else 5.0
        v_set_3 = signs[idx_3] * 0.49 * current_3
    
        rampVoltage(channel_3, v_set_3, current_3)
        
        
def rampVoltage(connection: IT6432Connection, set_voltage, set_current):

    if connection.query('output?') == '0':
        connection._write(f'voltage 0V')
        connection._write('output 1')

    if set_current > connection.currentLim:
        set_current = connection.currentLim
    elif set_current < 0.002:
        set_current = 0.002
        set_voltage = 0
    if abs(set_voltage) > connection.voltageLim:
        set_voltage = connection.voltageLim
        
    print('desired voltage: ' + str(set_voltage) +'V, desired current: ' + str(set_current) + 'A')

    act_voltage = getMeasurement(connection, meas_quantity='voltage')[0]
    act_current = getMeasurement(connection, meas_quantity='current')[0]
    print('actual voltage: ' + str(act_voltage) +'V, actual current: ' + str(act_current) + 'A')
    connection._write(f'voltage {act_voltage}V')
    
    if set_current - abs(act_current):
        print('actual current (abs): ' + str(abs(act_current)) + ', desired current: ' + str(set_current))
        connection._write(f'current {set_current}A')
        
    diff_v = set_voltage - act_voltage
    sign = np.sign(diff_v)
    diff_i = sign * set_current - act_current
    print('voltage diff: ' + str(diff_v) + ', current diff: ' + str(diff_i))
    
    if abs(set_voltage) < 0.1:
        threshold = 0.01
    else:
        threshold = 0.1

    while abs(diff_v) > threshold and abs(diff_i) > threshold:
        # if abs(diff_v) > 0.1:
        #     step = 0.1
        # elif abs(diff_v) <= 0.1:
        #     step = 0.01
        act_voltage += sign * 0.01
        print('setting voltage: ' + str(act_voltage))
        connection._write(f'voltage {act_voltage}V')
        act_voltage = getMeasurement(connection, meas_quantity='voltage')[0]
        act_current = getMeasurement(connection, meas_quantity='current')[0]
        print('actual voltage: ' + str(act_voltage) +'V, actual current: ' + str(act_current) + 'A')
        diff_v = set_voltage - act_voltage
        diff_i = sign * set_current - act_current
        print('voltage diff: ' + str(diff_v) + ', current diff: ' + str(diff_i))
        # sleep(0.05)
        
    connection._write(f'voltage {set_voltage}V;:current {set_current}A')
    
    if set_current <= 0.002:
        connection._write('output 0')

        

def getMeasurement(channel_1: IT6432Connection, channel_2=None, channel_3=None, meas_type='', meas_quantity='current'):
    """
    Get DC current/power/voltage values from each channel

    Returns: a list of all the currents (or an error code)
    """
    basecmd = 'measure:'
    quantities = ['current', 'voltage', 'power']
    types = ['', 'acdc', 'max', 'min']
    if not meas_quantity in quantities:
        meas_quantity = 'current'
    if not meas_type in types:
        meas_type = ''
    
    command = basecmd + meas_quantity
    if meas_type != '':
        command += ':' + meas_type
    command += '?'
        
    measured = []
    res = channel_1.query(command)
    if isinstance(res,list):
        res = res[0]
    measured.append(float(res))
    
    if channel_2 is not None:
        res = channel_2.query(command)
        if isinstance(res,list):
            res = res[0]
        measured.append(float(res))

    if channel_3 is not None:
        res = channel_3.query(command)
        if isinstance(res,list):
            res = res[0]
        measured.append(float(res))
        
    return measured


def demagnetizeCoils(channel_1: IT6432Connection, channel_2=IT6432Connection, channel_3=IT6432Connection, current_config=np.array([1000,1000,1000])):
    """
    Try to eliminate any hysteresis effects by applying a slowly oscillating and decaying electromagnetic field to the coils.
    
    Args:
        - previous_amp (int, optional): the maximum current value (directly) previously applied to coils
    """   
    # channel_1._write('output 1')
    # channel_2._write('output 1')
    # channel_3._write('output 1')
    
    tspan = np.linspace(0,6*np.pi,20)
    func1 = voltage_config[0] * np.cos(tspan)
    func2 = voltage_config[1] * np.cos(tspan)
    func3 = voltage_config[2] * np.cos(tspan)
    i_limit = 1/(tspan + 1)
    
    
    # channel_1._write('INITiate:name transient')
    # channel_2._write('INITiate:name transient')
    # channel_3._write('INITiate:name transient')
    # # print(func1)
    # desCurrents = [0, 0, 0]
    for k in range(len(tspan)):
        desCurrents[0] = func1[k]
        desCurrents[1] = func2[k]
        desCurrents[2] = func3[k]
        print(desCurrents)
        rampVoltage(channel_1, voltage_config[0], i_limit)
        
    #     sleep(1 - time() * 1 % 1)


########## test stuff out ##########
if __name__ == '__main__':
    channel_1 = IT6432Connection(1)
    channel_2 = IT6432Connection(2)
    channel_3 = IT6432Connection(3)
    openConnection(channel_1,channel_2,channel_3)
   
    # print(channel_1.query('VOLTage:PROTection:state 1'))
    # print(channel_2.query('VOLTage:PROTection:state 1'))
    # print(channel_3.query('VOLTage:PROTection:state 1'))
    
    print(channel_1.clrOutputProt())
    print(channel_2.clrOutputProt())
    print(channel_3.clrOutputProt())
    #getMaxMinOutput()
    #setMaxCurrVolt(5.02)

    # demagnetizeCoils(channel_1,channel_2,channel_3, [5,5,5])
    setCurrents(channel_1, channel_2, channel_3, desCurrents=[3000,-3000,1200])
    # disableCurrents(channel_1, channel_2, channel_3)
    
    setCurrents(channel_1, channel_2, channel_3, desCurrents=[5000, 0,-1200])
    
    setCurrents(channel_1, channel_2, channel_3, desCurrents=[-5000, 5000, 5000])


    # setCurrents(channel_1,channel_2,channel_3, [-1330,2828,-100])
    # channel_2._write('current:limit 5;:voltage:limit 5')
    # channel_2._write('output 1')
    # channel_3._write('current:limit 5;:voltage:limit 5')
    # channel_3._write('output 1')
    
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
    #     volt_list = getMeasurement(channel_1, channel_2, channel_3, meas_quantity='voltage')
    #     pwr_list = getMeasurement(channel_1, channel_2, channel_3, meas_quantity='power')
    #     print(f'power on channel 1/2/3: {pwr_list[0]:.3f}W, {pwr_list[1]:.3f}W, {pwr_list[2]:.3f}W')
        
    disableCurrents(channel_1, channel_2, channel_3)
    closeConnection(channel_1)
    closeConnection(channel_2)
    closeConnection(channel_3)