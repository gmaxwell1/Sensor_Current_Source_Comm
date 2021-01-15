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
        self._channel = 1
        self._chunk_size = 1024
        self.host = ip_address
        self.port = int(port)
        self.connected = False
        self.read_termination = '\n'

        self._timeout = 50000
        self.timeout(self._timeout)


    def connect(self, channel: int) -> None:
        """Connects to the server (IP address and port number)"""
        try:
            self.session.connect((self.host, self.port))
            self.connected = True
            self._channel = channel
            # clean slate for beginning
            self.session.sendall(b'*CLS')
        except Exception as exc:
            print(f'A problem occured while trying to connect: {exc}')
            self.close()
		

    def timeout(self) -> int:
        """Read and Write timeout"""
        return self._timeout

	
    def timeout(self, timeout: int) -> None:
        """Read and Write timeout"""
        self._timeout = timeout
        tout_float = float(self._timeout / 1000)
        self.session.settimeout(tout_float)

    def channel(self):
        """
        print the channel that this current source is
        """
        return self._channel

    def write(self, cmd: str) -> None:
        """Writes command as string to the instrument"""
        # add command termination
        cmd += self.read_termination
        self.session.sendall(cmd.encode('ascii'))
  
  
    def read(self, chunk_size=None) -> str:
        """
        Reads message sent from the instrument from the connection

        Args:
            chunk_size (int, optional): expected chunk size to be received. Defaults to None.

        Returns:
            the decoded received message (a string)
        """
        term_char_detected = False
        read_len = 0
        chunk = bytes()
        _chunk_size = chunk_size if chunk_size is not None else self._chunk_size

        try:
            while True:
                to_read_len = _chunk_size - read_len
                if to_read_len <= 0:
                    break
                data = self.session.recv(to_read_len)
                chunk += data
                read_len += len(data)				
                term_char = self.read_termination.encode()
                if term_char in data:
                    term_char_ix = data.index(term_char)
                    read_len = term_char_ix + 1
                    term_char_detected = True
                    break
                else:
                    pass

        except socket.timeout:
            print('timeout occurred!')

        if read_len < _chunk_size:
            # Less than required data arrived, no more available
            more_data_available = False
        else:
            # MaxCount data arrived, possibly more data available
            if self.read_termination is not None:
                more_data_available = not term_char_detected
            else:
                more_data_available = True

        res = chunk.decode('ascii').strip('\n')
        return res

    
    def formatMsg(self, msg: str) -> str:
        """
        Format the message received from the device

        Args:
            msg (str): the message received

        Returns:
            str: The formatted message
        """
        pass      


    def close(self) -> None:
        """Closes the socket connection"""
        self.session.close()
  
    # context manager
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

IT6432_PORT1 = "30000"
IT6432_PORT2 = "7071"
IT6432_PORT3 = "7072"


def openConnection(connection: IT6432Connection, channel: int):
    """
    Open a connection to a IT6432 current sources.

    Args:
        connection (IT6432Connection): A connection object
        channel (int): The channel used will decide which address/port is
                       used for communication.

    Returns:
        IT6432Connection: Instances of cconnection objects representing each channel.
    """
    connection.connect(channel)
    # check device ID
    connection.write('*IDN?')
    id_info = connection.read(connection._chunk_size)
    print(id_info)


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
    print(ans)
    if ans == '0':
        connection.write(':output 1;type LOW')
    else:
        connection.write('output:type LOW')
    # ans = connection.read()
    # ans_str = ans.decode('ascii')
    # if ans != 'NORM':
    #     connection.write('output:relay:mode normal')
        
    connection.write(':current:limit:state ON;:voltage:limit:state ON')
    setMaxCurrent(connection)
    

def disableCurrents(connection: IT6432Connection):
    """
    Disable current controllers.

    Returns: error code iff an error occurs, otherwise False (whether ECB currents are enabled)
    """
    connection.write(':output?')
    ans = connection.read()
    print(ans)

    connection.write(':output 0')


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
    connection.write(':current:limit ' + str(currentLim) + ';:voltage:limit ' + str(voltageLim))
    # connection.write(':current:protection:state ON;:voltage:protection:state ON')
    

def _setCurrents_(connection: IT6432Connection, desCurrent=0):
    """
    , channel_2: IT6432Connection, channel_3: IT6432Connection
    Set current values for each ECB channel. Not recommended, instead use setCurrents, since there the maximum step size
    is reduced to prevent mechanical shifting of the magnet, which could in turn cause a change in the magnetic field.

    Args:
    -desCurrents: list of length 3 containing int values, where the '0th' value is the desired current on channel 1 (units of mA),
    the '1st' is the desired current on channel 2 and so on.

    Returns: error code iff an error occurs
    """
    current = desCurrent / 1000 if desCurrent <= 5000 else 5.0
    
    # to limit the maximum current change (dI/dt) we can set a voltage limit. The voltage due to the coil resistance is 
    # approximately 0.5*current. The additional 0.5 V ensures that dI/dt <= 25A/s so that nothing is mechanically shifted.
    # This may not be 100% necessary
    v_set = 0.5 * current + 0.5
    connection.write(':voltage ' + str(v_set) + 'V;:current ' + str(current) + 'A')
   

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

def getCurrents(connection: IT6432Connection):
    """
    Get current values from each ECB channel, print them to the console

    Returns: a list of all the currents (or an error code)
    """
    connection.write(':measure:current?')
    I1 = connection.read()
    print(I1)
    return I1



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
    connection.write('*STB?')
    status = connection.read(1)
    byte = int(status)
    print(bin(byte))

    # try:
    #     byte = int(status)
    # except:
    #     print('an unkown message format was received')
        
    if byte and 0b10000000:  
        print(f"An operation event has occurred.")
        connection.write('status:operation?')
        status = connection.read(1)
        print(bin(status))
    if byte and 0b01000000:  
        print(f"A service request has been made.")
    if byte and 0b00100000:  
        print(f"A standard event has occurred.")
        connection.write('*ESR?')
        status = connection.read(1)
        print(bin(status))
    if byte and 0b00010000:  
        print(f"There is available data at the output.")
    if byte and 0b00001000:  
        print(f"An enabled questionable event has occurred.")
        connection.write('status:questionable?')
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
    currentSource = IT6432Connection(IT6432_ADDRESS1, IT6432_PORT1)
    openConnection(currentSource, 1)
    # voltage/ curretn need A/V appended for the actual value to be set
    # currentSource.write('current 4.5A;:voltage -3V')
    
    # currentSource.write('output?')
    # ans = currentSource.read()
    # print(ans)
    # if ans == '0':
    #     currentSource.write('output 1')
    currentSource.write('output 0')
    getStatus(currentSource)
    closeConnection(currentSource)

    

