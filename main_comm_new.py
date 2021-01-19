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



# def enableCurrents(channel_1: IT6432Connection, channel_2=None, channel_3=None):
#     """
#     Enable current controllers.
#     """
#     global DO_NOT_ENABLE
    
#     idx_1 = channel_1._channel - 1
#     if not DO_NOT_ENABLE[idx_1]:
#         channel_1._write('output 1')
#     c = channel_1.query('output?')
#     print(f'output {idx_1}: {c}')

    
#     if channel_2 is not None:
#         idx_2 = channel_2._channel - 1
#         if not DO_NOT_ENABLE[idx_2]:
#             channel_2._write('output 1')
#         c = channel_2.query('output?')
#         print(f'output {idx_2}: {c}')

    
#     if channel_3 is not None:
#         idx_3 = channel_3._channel - 1
#         if not DO_NOT_ENABLE[idx_3]:
#             channel_3._write('output 1')
#         c = channel_3.query('output?')
#         print(f'output {idx_3}: {c}')
        

def disableCurrents(channel_1: IT6432Connection, channel_2=None, channel_3=None):
    """
    Disable current controllers.
    """
    channel_1._write('output 0')
  
    if channel_2 is not None:
        channel_2._write('output 0')
        
    if channel_3 is not None:
        channel_3._write('output 0')
        

def setMaxCurrent(connection: IT6432Connection, maxValue=5000, verbose=False):
    """
    Set maximum current values for each ECB channel, as long as they are under the threshold specified in the API source code.
    Args:
    -maxValue

    Returns: error code iff an error occurs
    """
    if maxValue > 5000:
        maxValue = 5000
        print('current cannot be higher than 5A')
    currentLim = maxValue/1000
    voltageLim = maxValue/1000
    connection._write('current:limit:state ON;:voltage:limit:state ON')
    connection._write(f'current:limit {currentLim};:voltage:limit {currentLim}')


def getMaxMinOutput(connection: IT6432Connection):
    """
    Set maximum current values for each ECB channel, as long as they are under the threshold specified in the API source code.
    Args:
    -maxValue

    Returns: error code iff an error occurs
    """
    max_curr = connection.query('current:maxset?')
    max_volt = connection.query('voltage:maxset?')
    min_curr = connection.query('current:minset?')
    min_volt = connection.query('voltage:minset?')
    return max_curr, max_volt
    

def setCurrents(channel_1: IT6432Connection, channel_2=None, channel_3=None, desCurrents=[0,0,0]):
    """
    Set current values for each channel. Voltage is limited as well to prevent very fast current changes due to inductance.

    Args:
        channel_1 (IT6432Connection): the first passed current source object to modify
        channel_2 (IT6432Connection, optional): [description]. Defaults to None.
        channel_3 (IT6432Connection, optional): [description]. Defaults to None.
        desCurrents (list, optional):  list of length 3 containing int values of currents (unit: mA), Defaults to [0,0,0].
    """
    signs = np.sign(desCurrents)
    
    idx_1 = channel_1._channel - 1
    current_1 = signs[idx_1] * desCurrents[idx_1] / 1000 if abs(desCurrents[idx_1]) <= 5000 else 5.0
    # to limit the maximum current change (dI/dt) we can set a voltage limit. The voltage due to the coil resistance is 
    # approximately 0.5*current.
    v_set_1 = signs[idx_1] * 3
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
        v_set_2 = signs[idx_2] * 3
        
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
        v_set_3 = signs[idx_3] * 3

        if current_3 < 0.002:
            channel_3._write('output 0')
        else:
            channel_3._write('voltage ' + str(v_set_3) + 'V;:current ' + str(current_3) + 'A')
            channel_3._write('output 1')
        c = channel_3.query('output?')
        print(f'output {idx_3 + 1}: {c}')


# def setCurrents(desCurrents=[0, 0, 0, 0, 0, 0, 0, 0], direct=b'0'):
#     """
#     Set current values for each ECB channel. The 'slew rate' (maximum dI/dt) limits the maximum current change to 500mA/50ms
#     Args:
#         desCurrents (list, optional): The desired currents on channels 1,2,3,4,5,6,7 and 8 (in that order).
#                                       Defaults to [0, 0, 0, 0, 0, 0, 0, 0].
#         direct (bytes, optional): if 1, the existing ECB buffer will be cleared and desCurrents will be directly applied.
#                                   If 0, the desired currents will be appended to the buffer. Defaults to b'0'.

#     Returns:
#         [type]: error code iff an error occurs
#     """
#     pass

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



def getTemps(verbose=False):
    """
    Get temperature values from each sensor, print them to the console

    returns: a tuple with all of the values of interest if no error occurs otherwise an error code is returned
    """
    pass


def getStatus(connection: IT6432Connection):
    """
    gets the current status of the current source by sending a query 
    for the Standard Event Status register and checks.
    
    Returns:
        messages corresponding to any of the bits which were set.
    """
    status = int(connection.query('*ESR?'))
    messages = {}
    
    if status and 0b10000000:
        messages[7] = 'Power is On.'
    if status and 0b00100000:
        messages[5] = 'Command syntax or semantic error.'
    if status and 0b00010000:
        messages[4] = 'Parameter overflows or the condition is not right.'
    if status and 0b00001000:
        messages[3] = 'Data stored in register is missing or error occurs in preliminary checkout.'
    if status and 0b00000100:
        messages[2] = 'Data of output array is missing.'
    if status and 0b00000001:
        messages[0] = 'An operation completed.'
    
    return messages


def demagnetizeCoils(current_config=np.array([1000,1000,1000])):
    """
    Try to eliminate any hysterisis effects by applying a slowly oscillating and decaying electromagnetic field to the coils.
    
    Args:
        - previous_amp (int, optional): the maximum current value (directly) previously applied to coils
    """
    pass

########## operate the ECB in the desired mode (test stuff out) ##########
if __name__ == '__main__':
    channel_1 = IT6432Connection(1)
    channel_2 = IT6432Connection(2)
    channel_3 = IT6432Connection(3)
    openConnection(channel_1, channel_2, channel_3)
   
    # print(channel_1._write('SYSTem:local'))
    setCurrents(channel_1,channel_2,channel_3, [5000,5000,5000])
    # setCurrents(channel_1, channel_2, channel_3, desCurrents=[0,0,2973])
    # disableCurrents(channel_1, channel_2, channel_3)
    # channel_1._write('OUTPut:PROTection:CLEar')

    # channel_2._write('current:limit 5;:voltage:limit 5')
    # channel_2._write('output 1')
    # channel_3._write('current:limit 5;:voltage:limit 5')
    # channel_3._write('output 1')
    
    # print('output 1: ' + channel_1.query('current:minset?') + 'A, ' + channel_1.query('VOLTage:minset?') + 'V')
    # print('output 2: ' + channel_2.query('current:minset?') + 'A, ' + channel_2.query('VOLTage:minset?') + 'V')
    # print('output 3: ' + channel_3.query('current:minset?') + 'A, ' + channel_3.query('VOLTage:minset?') + 'V')
    
    # # channel_1._write('system:clear')
    # print('output 1: ' + channel_1.query('output?'))
    # print('output 2: ' + channel_2.query('output?'))
    # print('output 3: ' + channel_3.query('output?'))
    # stat = getStatus(channel_1)
    # print(f'status 1: {stat}')
    # stat = getStatus(channel_2)
    # print(f'status 2: {stat}')
    # stat = getStatus(channel_3)
    # print(f'status 3: {stat}')

    sleep(18000)
    # currentsList = [0,0,0]
    # k = 0
    # while k < 10:
    #     sleep()
    #     currentsList = getMeasurement(channel_1, channel_2, channel_3)
    #     k += 1
    #     # print(currentsList)
    #     print(f'current 1: {currentsList[0]:.3f}, current 2: {currentsList[1]:.3f}, current 3: {currentsList[2]:.3f}')

    disableCurrents(channel_1, channel_2, channel_3)
    # getStatus(channel_1)
    closeConnection(channel_1)
    closeConnection(channel_2)
    closeConnection(channel_3)