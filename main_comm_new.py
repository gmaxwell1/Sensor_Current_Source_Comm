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
from IT6432.it6432connection import IT6432Connection


###########  global parameters ##########


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
    channel_1._write('output 0')
  
    if channel_2 is not None:
        channel_2._write('output 0')
        
    if channel_3 is not None:
        channel_3._write('output 0')
          

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
    v_set_1 = signs[idx_1] * 5
    # current may not be set to less than 2 mA, in this case we just leave that coil off.
    if current_1 < 0.002:
        channel_1._write('output 0')
    else:
        channel_1._write('voltage ' + str(v_set_1) + 'V;:current ' + str(current_1) + 'A')
        channel_1._write('output 1')
    c = channel_1.query('output?')
    print(f'output {idx_1 + 1}: {c}')

    if channel_2 is not None:
        idx_2 = channel_2._channel - 1
        current_2 =  signs[idx_2] * desCurrents[idx_2] / 1000 if abs(desCurrents[idx_2]) <= 5000 else 5.0
        v_set_2 = signs[idx_2] * 5
        
        if current_2 < 0.002:
            channel_2._write('output 0')
        else:
            channel_2._write('voltage ' + str(v_set_2) + 'V;:current ' + str(current_2) + 'A')
            channel_2._write('output 1')
        c = channel_2.query('output?')
        print(f'output {idx_2 + 1}: {c}')

    if channel_3 is not None:
        idx_3 = channel_3._channel - 1
        current_3 =  signs[idx_3] * desCurrents[idx_3] / 1000 if abs(desCurrents[idx_3]) <= 5000 else 5.0
        v_set_3 = signs[idx_3] * 5

        if current_3 < 0.002:
            channel_3._write('output 0')
        else:
            channel_3._write('voltage ' + str(v_set_3) + 'V;:current ' + str(current_3) + 'A')
            channel_3._write('output 1')
        c = channel_3.query('output?')
        print(f'output {idx_3 + 1}: {c}')


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
        
    measured_I = []
    res = channel_1.query(command)
    if isinstance(res,list):
        res = res[0]
    measured_I.append(float(res))
    
    if channel_2 is not None:
        res = channel_2.query(command)
        if isinstance(res,list):
            res = res[0]
        measured_I.append(float(res))

    if channel_3 is not None:
        res = channel_3.query(command)
        if isinstance(res,list):
            res = res[0]
        measured_I.append(float(res))
        
    return measured_I


def demagnetizeCoils(channel_1: IT6432Connection, channel_2=IT6432Connection, channel_3=IT6432Connection, current_config=np.array([1000,1000,1000])):
    """
    Try to eliminate any hysteresis effects by applying a slowly oscillating and decaying electromagnetic field to the coils.
    
    Args:
        - previous_amp (int, optional): the maximum current value (directly) previously applied to coils
    """
    channel_1._write('INITiate:NAME transient')
    channel_1._write('INITiate:CONTinuous:NAME transient 1')
    channel_2._write('INITiate:NAME transient')
    channel_2._write('INITiate:CONTinuous:NAME transient 1')
    channel_3._write('INITiate:NAME transient')
    channel_3._write('INITiate:CONTinuous:NAME transient 1')
    
    channel_1._write('output 1')
    channel_2._write('output 1')
    channel_3._write('output 1')
    
    tspan = np.linspace(0, 12*np.pi, 50)
    func1 = current_config[0] * np.cos(tspan) * np.exp(-0.2*tspan)
    func2 = current_config[1] * np.cos(tspan) * np.exp(-0.2*tspan)
    func3 = current_config[2] * np.cos(tspan) * np.exp(-0.2*tspan)

    # print(func1)
    desCurrents = [0, 0, 0, 0, 0, 0, 0, 0]
    sleep(1 - time() % 1)
    for k in range(len(tspan)):
        desCurrents[0] = int(func1[k])
        desCurrents[1] = int(func2[k])
        desCurrents[2] = int(func3[k])




########## operate the ECB in the desired mode (test stuff out) ##########
if __name__ == '__main__':
    channel_1 = IT6432Connection(1)
    channel_2 = IT6432Connection(2)
    channel_3 = IT6432Connection(3)
    openConnection(channel_1, channel_2, channel_3)
   
    # print(channel_1._write('OUTPut:speed:time 0.05'))
    # print(channel_2._write('OUTPut:speed:time 0.05'))
    # print(channel_3._write('OUTPut:speed:time 0.05'))
    
    # print(channel_1.getMaxMinOutput())
    # print(channel_2.getMaxMinOutput())
    # print(channel_3.getMaxMinOutput())
    #getMaxMinOutput()
    #setMaxCurrVolt(5.02)

    # setCurrents(channel_1,channel_2,channel_3, [5000,5000,5000])
    # setCurrents(channel_1, channel_2, channel_3, desCurrents=[0,0,2973])
    # disableCurrents(channel_1, channel_2, channel_3)
    # channel_1._write('OUTPut:PROTection:CLEar')
    # setCurrents(channel_1,channel_2,channel_3, [-1330,2828,-100])
    # channel_2._write('current:limit 5;:voltage:limit 5')
    # channel_2._write('output 1')
    # channel_3._write('current:limit 5;:voltage:limit 5')
    # channel_3._write('output 1')
    
    # # channel_1._write('system:clear')
    # print('output 1: ' + channel_1.query('output?'))
    # print('output 2: ' + channel_2.query('output?'))
    # print('output 3: ' + channel_3.query('output?'))
    stat = channel_1.getStatus()
    print(f'status 1: {stat}')
    stat = channel_2.getStatus()
    print(f'status 2: {stat}')
    stat = channel_3.getStatus()
    print(f'status 3: {stat}')

    # sleep(18000)
    # currentsList = [0,0,0]
    # k = 0
    # while k < 10:
    #     sleep()
    #     currentsList = getMeasurement(channel_1, channel_2, channel_3)
    #     k += 1
    #     # print(currentsList)
    #     print(f'current 1: {currentsList[0]:.3f}, current 2: {currentsList[1]:.3f}, current 3: {currentsList[2]:.3f}')

    disableCurrents(channel_1, channel_2, channel_3)
    closeConnection(channel_1)
    closeConnection(channel_2)
    closeConnection(channel_3)