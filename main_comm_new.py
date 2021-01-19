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


# ##########  Connection parameters ##########
# IT6432_ADDRESS1 = "192.168.237.47"
# IT6432_ADDRESS2 = "192.168.237.48"
# IT6432_ADDRESS3 = "192.168.237.49"

# IT6432_PORT1 = "30000"
# IT6432_PORT2 = "7071"
# IT6432_PORT3 = "7072"


def openConnection():
    """
    Open a connection to a IT6432 current source.

    Returns:
        IT6432Connection: Instances of connection objects representing each channel.
    """
    return IT6432Connection(1), IT6432Connection(2), IT6432Connection(3)
 


def closeConnection(connection: IT6432Connection):
    """
    Close the connection with the current sources.
    """
    connection.close()

def enableCurrents(channel_1: IT6432Connection, channel_2=None, channel_3=None):
    """
    Enable current controllers.

    Returns: error code iff an error occurs, otherwise True (whether ECB currents are enabled)
    """
    ans = channel_1._query(':output?')
    print(ans)
    if ans == '0':
        channel_1._write(':output 1;type LOW')
    else:
        channel_1._write('output:type LOW')  
    channel_1._write(':current:limit:state ON;:voltage:limit:state ON')
    setMaxCurrent(channel_1)
    
    if channel_2 is not None:
        ans = channel_2._query(':output?')
        if ans == '0':
            channel_2._write(':output 1;type LOW')
        else:
            channel_2._write('output:type LOW')
        channel_2._write(':current:limit:state ON;:voltage:limit:state ON')
        setMaxCurrent(channel_2)
    
    if channel_3 is not None:
        ans = channel_3._query(':output?')
        if ans == '0':
            channel_3._write(':output 1;type LOW')
        else:
            channel_3._write('output:type LOW')
        channel_3._write(':current:limit:state ON;:voltage:limit:state ON')
        setMaxCurrent(channel_3)
        

def disableCurrents(channel_1: IT6432Connection, channel_2=None, channel_3=None):
    """
    Disable current controllers.

    Returns: error code iff an error occurs, otherwise False (whether ECB currents are enabled)
    """
    channel_1._write(':output 0')
  
    if channel_2 is not None:
        channel_2._write(':output 0')
        
    if channel_3 is not None:
        channel_3._write(':output 0')
        

def setMaxCurrent(connection: IT6432Connection, maxValue=5000):
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
    connection._write(':current:limit ' + str(currentLim) + ';:voltage:limit ' + str(voltageLim))
    # connection._write(':current:protection:state ON;:voltage:protection:state ON')
    

def setCurrents(channel_1: IT6432Connection, channel_2=None, channel_3=None, desCurrents=[0,0,0]):
    """
    , channel_2: IT6432Connection, channel_3: IT6432Connection
    Set current values for each ECB channel. Not recommended, instead use setCurrents, since there the maximum step size
    is reduced to prevent mechanical shifting of the magnet, which could in turn cause a change in the magnetic field.

    Args:
    -desCurrents: list of length 3 containing int values, where the '0th' value is the desired current on channel 1 (units of mA),
    the '1st' is the desired current on channel 2 and so on.

    Returns: error code iff an error occurs
    """
    
    current1 = desCurrents[0] / 1000 if desCurrents[0] <= 5000 else 5.0
    # to limit the maximum current change (dI/dt) we can set a voltage limit. The voltage due to the coil resistance is 
    # approximately 0.5*current. The additional 0.5 V ensures that dI/dt <= 25A/s so that nothing is mechanically shifted.
    v_set1 = 0.5 * current1 + 0.5
    channel_1._write(':voltage ' + str(v_set1) + 'V;:current ' + str(current1) + 'A')

    if channel_2 is not None:
        current2 = desCurrents[1] / 1000 if desCurrents[1] <= 5000 else 5.0
        v_set2 = 0.5 * current2 + 0.5
        channel_2._write(':voltage ' + str(v_set2) + 'V;:current ' + str(current2) + 'A')

    if channel_3 is not None:
        current3 = desCurrents[2] / 1000 if desCurrents[2] <= 5000 else 5.0
        v_set3 = 0.5 * current3 + 0.5
        channel_3._write(':voltage ' + str(v_set3) + 'V;:current ' + str(current3) + 'A')

    
   

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

def getCurrent(connection: IT6432Connection) -> float:
    """
    Get current values from each ECB channel, print them to the console

    Returns: a list of all the currents (or an error code)
    """
    I1 = connection._query(':measure:current?')
    return float(I1)



def getTemps(verbose=False):
    """
    Get temperature values from each sensor, print them to the console

    returns: a tuple with all of the values of interest if no error occurs otherwise an error code is returned
    """
    pass


def getStatus(connection: IT6432Connection):
    """
    gets the current status of the current source by sending a status byte query 
    and checks for various errors.
    """
    connection._write('*STB?')
    status = connection.read(1)
    byte = int(status)
    print(bin(byte))

    # try:
    #     byte = int(status)
    # except:
    #     print('an unkown message format was received')
        
    if byte and 0b10000000:  
        print(f"An operation event has occurred.")
        connection._write('status:operation?')
        status = connection.read(1)
        print(bin(status))
    if byte and 0b01000000:  
        print(f"A service request has been made.")
    if byte and 0b00100000:  
        print(f"A standard event has occurred.")
        connection._write('*ESR?')
        status = connection.read(1)
        print(bin(status))
    if byte and 0b00010000:  
        print(f"There is available data at the output.")
    if byte and 0b00001000:  
        print(f"An enabled questionable event has occurred.")
        connection._write('status:questionable?')
        status = connection.read(1)
        print(bin(status))
        
    return status


def demagnetizeCoils(current_config=np.array([1000,1000,1000])):
    """
    Try to eliminate any hysterisis effects by applying a slowly oscillating and decaying electromagnetic field to the coils.
    
    Args:
        - previous_amp (int, optional): the maximum current value (directly) previously applied to coils
    """
    pass

########## operate the ECB in the desired mode (test stuff out) ##########
if __name__ == '__main__':
    # channel_1, channel_2, channel_3 = openConnection()
    with IT6432Connection(1) as channel_1:
        with IT6432Connection(2) as channel_2:
            # print(channel_1._write('SYSTem:local'))
            # setCurrents(channel_1,channel_2,channel_3, [5000,3141,2222])
            setCurrents(channel_1, channel_2, desCurrents=[3131,3141,2222])
            enableCurrents(channel_1, channel_2)
            # # sleep(10)
            currentsList = [0,0,0]
            k = 0
            while k < 10:
                sleep(1)
                currentsList[0] = getCurrent(channel_1)
                currentsList[1] = getCurrent(channel_2)
            #     # currentsList[2] = getCurrent(channel_3)
                
                print(f'current 1: {currentsList[0]:.3f}, current 2: {currentsList[1]:.3f}')

            disableCurrents(channel_1, channel_2)
            # getStatus(channel_1)
            closeConnection(channel_1)
            closeConnection(channel_2)
            # closeConnection(channel_3)