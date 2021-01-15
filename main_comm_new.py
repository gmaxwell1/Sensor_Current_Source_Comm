"""
filename: main_comm_new.py

This code is meant to bundle the communication with the ECB-820, by simplifying the most basic necessary functions.
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
import socket



class IT6432Connection:

	def __init__(self, ip_address, port):
		self.session = socket.socket()
        self._chunk_size = 1024
		self.host = ip_address
		self.port = int(port)
        self.connected = False
        
        self.connect()
        self._timeout = 5000
        self.timeout(self._timeout)
        # check device ID
        self.write(b'*IDN?')
        id_info = self.read(self._chunk_size)
        print(id_info)
        
        self.session.send(b'*STB?')
        status = self.read(1)
        print(''.join([format(ord(c), '08b') for c in status]))
        try:
            if int(status) != 0:
                statusCheck(int(status))
        except:
            print('an unkown message format was received')


	def connect(self) -> None:
		"""Connects to the server (IP address and port number)"""
		self.session.connect((self.host, self.port))
        self.connected = True


	def timeout(self) -> int:
		"""Read and Write timeout"""
		return self._timeout

	
	def timeout(self, timeout: int) -> None:
		"""Read and Write timeout"""
		self._timeout = timeout
		tout_float = float(self._timeout / 1000)
		self.session.settimeout(tout_float)


	def write(self, cmd: str) -> None:
		"""Writes command as string to the instrument"""
        # add command termination
        cmd += '\n'
		self.session.send(cmd.encode('ascii'))
  
  
    def read(self, chunk_size=None) -> None:
		"""Reads message sent from the instrument from the connection"""
        if chunk_size is None:
    		received = self.session.recv(self._chunk_size)
        else:
            received = self.session.recv(chunk_size)
        return received.decode('ascii')
    
    
    def formatMsg(self, msg: str) -> str:
        """Reads information sent from the instrument"""
        pass
    
    
    def statusCheck(self, byte: int) -> None:
    """
    gets the current status of the current source and checks for various errors
    """
        if byte and 0
                
            print(f"Unhandled error number: {msg}.\nSee DCx_User_and_SDK_Manual.pdf for details")


	def close(self) -> None:
		"""Closes the socket connection"""
		self.session.close()
  
    # context manager to ba able to use a with...as... statement
    def __enter__(self):
        if not self.session.connected:
            self.connect()
        return self

    def __exit__(self, type, value, traceback):
        if self.session.connected:
            self.session.close()
            return not self.session.connected
        else:
            return isinstance(value, TypeError)


##########  Connection parameters ##########
IT6432_ADDRESS1 = "192.168.237.47"
IT6432_ADDRESS2 = "192.168.237.48"
IT6432_ADDRESS3 = "192.168.237.49"

IT6432_PORT1 = "7070"
IT6432_PORT2 = "7071"
IT6432_PORT3 = "7072"


def openConnections(IPAddresses=(IT6432_ADDRESS1,IT6432_ADDRESS2,IT6432_ADDRESS3), ports=(IT6432_PORT1,IT6432_PORT2,IT6432_PORT3)):
    """
    Open a connection to each of the IT6432 current sources.

    Args:
        IPAddresses (tuple, optional): The IP addresses of each device. This must be configured in the Menu of the respective
                                       devices before trying to connect. Defaults to (IT6432_ADDRESS1,IT6432_ADDRESS2,IT6432_ADDRESS3).
        ports (tuple, optional): The ports of each device. This must be configured in the Menu of the respective
                                 devices before trying to connect. Defaults to (IT6432_PORT1,IT6432_PORT2,IT6432_PORT3).

    Returns:
        IT6432Connection: Instances of cconnection objects representing each channel.
    """
    channel_1 = IT6432Connection(IPAddresses[0], ports[0])
    channel_2 = IT6432Connection(IPAddresses[1], ports[1])
    channel_3 = IT6432Connection(IPAddresses[2], ports[2])
    
    return channel_1, channel_2, channel_3


def closeConnection(connection: IT6432Connection):
    """
    Close the connection with the ECB.
    """
    connection.close()

def enableCurrents(connection: IT6432Connection):
    """
    Enable current controllers.

    Returns: error code iff an error occurs, otherwise True (whether ECB currents are enabled)
    """
    connection.write(':output?')
    ans = connection.read()
    if ans == b'0':
        connection.write(':output ON;relay:mode?')
    else:
        connection.write('output:relay:mode?')
    ans = connection.read()
    ans_str = ans.decode('ascii')
    if ans_str != 'NORMal':
        connection.write('output:relay:mode normal')
        
    connection.write(':current:limit:state ON;:voltage:limit:state ON')
    setMaxCurrent(connection)
    

def disableCurrents(connection: IT6432Connection):
    """
    Disable current controllers.

    Returns: error code iff an error occurs, otherwise False (whether ECB currents are enabled)
    """
    connection.write(':output OFF')


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
    arg = maxValue/1000
    connection.write(':current:limit:state ON;limit ' + str(arg) + ':voltage:limit:state ON')
    connection.write(':current:protection:state ON;:voltage:protection:state ON')
    

def _setCurrents_(channel_1: IT6432Connection, channel_2: IT6432Connection, channel_3: IT6432Connection, desCurrents=[0, 0, 0]):
    """
    Set current values for each ECB channel. Not recommended, instead use setCurrents, since there the maximum step size
    is reduced to prevent mechanical shifting of the magnet, which could in turn cause a change in the magnetic field.

    Args:
    -desCurrents: list of length 3 containing int values, where the '0th' value is the desired current on channel 1 (units of mA),
    the '1st' is the desired current on channel 2 and so on.

    Returns: error code iff an error occurs
    """
    arg1 = desCurrents[0] / 1000 if desCurrents[0] <= 5000 else 5.0
    arg2 = desCurrents[1] / 1000 if desCurrents[0] <= 5000 else 5.0
    arg3 = desCurrents[2] / 1000 if desCurrents[0] <= 5000 else 5.0
    
    # to limit the maximum current change (dI/dt) we can set a voltage limit. The voltage due to the coil resistance is 
    # approximately 0.5*current. The additional 0.5 V ensures that dI/dt <= 25A/s so that nothing is mechanically shifted.
    # This may not be 100% necessary
    v_lim = 0.5*max(desCurrents) + 0.5
    channel_1.write(':voltage:limit ' + v_lim)
    channel_2.write(':voltage:limit ' + v_lim)
    channel_3.write(':voltage:limit ' + v_lim)

    channel_1.write(':current ' + str(arg1))
    channel_2.write(':current ' + str(arg2))
    channel_3.write(':current ' + str(arg3))
   

def setCurrents(desCurrents=[0, 0, 0, 0, 0, 0, 0, 0], direct=b'0'):
    """
    Set current values for each ECB channel. The 'slew rate' (maximum dI/dt) limits the maximum current change to 500mA/50ms
    Args:
        desCurrents (list, optional): The desired currents on channels 1,2,3,4,5,6,7 and 8 (in that order).
                                      Defaults to [0, 0, 0, 0, 0, 0, 0, 0].
        direct (bytes, optional): if 1, the existing ECB buffer will be cleared and desCurrents will be directly applied.
                                  If 0, the desired currents will be appended to the buffer. Defaults to b'0'.

    Returns:
        [type]: error code iff an error occurs
    """
    pass

def getCurrents():
    """
    Get current values from each ECB channel, print them to the console

    Returns: a list of all the currents (or an error code)
    """
    pass


def getTemps(verbose=False):
    """
    Get temperature values from each sensor, print them to the console

    returns: a tuple with all of the values of interest if no error occurs otherwise an error code is returned
    """
    pass


def getStatus():
    """
    Get ECB status (Number)

    returns: status, or error code iff there is an error
    """
    pass


def demagnetizeCoils(current_config=np.array([1000,1000,1000])):
    """
    Try to eliminate any hysterisis effects by applying a slowly oscillating and decaying electromagnetic field to the coils.
    
    Args:
        - previous_amp (int, optional): the maximum current value (directly) previously applied to coils
    """
    pass

########## operate the ECB in the desired mode (test stuff out) ##########
if __name__ == '__main__':
    print(initECBapi(ECB_ADDRESS, ECB_PORT))
    print(enableECBCurrents())
    # setCurrents(desCurrents=[1, 0, 0, 0, 0, 0, 0, 0], direct=b'0')
    # sleep(20)
    # print("Channel: \t 1 \t 2 \t 3 \t 4 \t 5 \t 6 \t 7 \t 8")
    # for i in range(15):
    #     (result, hall_list, currents_list, coil_status) = getTemps()
    #     print(f"\rTemperature [°C]: {result[0]} \t {result[1]} \t {result[2]} \t {result[3]} \t {result[4]} \t {result[5]} \t {result[6]} \t {result[7]}",end='',flush=True)
    #     sleep(1 - time() % 1)
    # disableECBCurrents()
    
    # enableECBCurrents()
    demagnetizeCoils()
    disableECBCurrents()
    exitECBapi()
