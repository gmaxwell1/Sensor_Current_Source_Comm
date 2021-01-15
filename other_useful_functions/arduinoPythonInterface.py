"""
Script for communication with Arduino Uno using standard serial protocol. A sketch needs
to be uploaded to the board for communication to be possible. Data is simply written to/
fetched from the serial port, so this script is mainly good for obtaining data from the 
Arduino/whatever it is connected to.
Mainly for getting temperature measurements from ADT7410 sensors through the arduino.

Author: Maxwell Guerne-Kieferndorf
Date: 04.12.2020

"""
# standard libs
import serial
import time
from datetime import datetime
import os
import threading
import numpy as np
import pandas as pd
from other_useful_functions.general_functions import ensure_dir_exists


class ArduinoUno(serial.Serial):
    fetch_kinds = ['Timestamp', 'Sensor 1 Temp', 'Sensor 2 Temp', 'Sensor 3 Temp']
    def __init__(self, port):
        # Arduino Uno serial port
        self.serialPort = port
        # establish connection
        self.board = serial.Serial(self.serialPort, 9600)
        # data collection
        self.stop = False
        self.data_stack = {fetch_kind: [] for fetch_kind in self.fetch_kinds}

        # debug -- always include a debug message in Arduino setup function
        # readline = str(self.board.readline())
        # print(readline.strip('b\'\\rn')) #

    def setLED(self):
        """
        turn built in LED/ whatever is connected to digital pin 13 on or off
        """
        newValue = 0
        while newValue != '':
            newValue = input('Enter 0 or 1 to turn LED on or off or enter to exit.\n')
            
            if newValue == '0':
                self.board.write(b'0')
                time.sleep(1)
            elif newValue == '1':
                self.board.write(b'1')
                time.sleep(1)
            else:
                time.sleep(1)
            

    def getTemperatureMeasurements(self):
        """
        Only run when the Extended_ADT7410 sketch is running on the Arduino. It reads the values on the corresponding
        serial port and converts them into temperature/time values.
        Kinda ugly but it gets the job done.

        Args:
        Returns:
        """
        # self.board.readline()
        self.stop = False
        times = []
        temps = [[], [], []]
        
        # A synchronisation string containing the characters tx is sent before each set of measurements,
        # we ensure correct reading of the measurements by waiting for this string
        while str(self.board.readline()).strip('b\'\\rn') != 'tx':
            pass
                    
        while not self.stop:
            # A synchronisation string containing the characters tx is sent before each set of measurements
            tx = self.board.readline()
            if str(tx).strip('b\'\\rn') == 'tx':
                rawData1 = self.board.readline()
                rawData2 = self.board.readline()
                rawData3 = self.board.readline()
                rawData4 = self.board.readline()
            
            
                timeStamp = str(rawData1).strip('b\'\\rn')
                temp1 = str(rawData2).strip('b\'\\rn')
                temp2 = str(rawData3).strip('b\'\\rn')
                temp3 = str(rawData4).strip('b\'\\rn')
                try:
                    times.append(float(timeStamp) / 1000)
                    temps[0].append(float(temp1) / 128)
                    temps[1].append(float(temp2) / 128)
                    temps[2].append(float(temp3) / 128)
                    # display current temperature measurement, time
                    # print(f'\rtime: {float(timeStamp) / 1000:.2f} s, Temperature measured on sensor 1: {float(temp1) / 128:.2f} °C,'
                    #     f'sensor 2: {float(temp2) / 128:.2f} °C, sensor 3: {float(temp3) / 128:.2f} °C', sep='', end='', flush=True)
                except:
                    print(rawData1, rawData2, rawData3, rawData4)
        
        
        if self.stop:
            print('\nMeasurement finished...')
                
            self.data_stack[self.fetch_kinds[0]] = times
            self.data_stack[self.fetch_kinds[1]] = temps[0]
            self.data_stack[self.fetch_kinds[2]] = temps[1]
            self.data_stack[self.fetch_kinds[3]] = temps[2]
            
            if (len(self.data_stack['Sensor 1 Temp']) != len(times) or len(self.data_stack['Sensor 2 Temp']) != len(times) or len(self.data_stack['Sensor 3 Temp']) != len(times)):
                print("Warning: There may be some missing values!")
    
    
def saveTempData(dataset, directory=r'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\2_Misc_Code\Temperature Sensors\ADT7410_temperature_measurements\Measurement_over_time',
                 filename_suffix='temp_meas'):
    '''
    :param dataset: dictionary containing temperature measurements
    :param filename_suffix: name after date&time
    '''
    df = None
    if isinstance(dataset, dict):
        df = pd.DataFrame(dataset)
        
    ensure_dir_exists(directory)
    
    now = datetime.now().strftime('%y_%m_%d_%H-%M-%S')
    output_file_name = '{}_{}.csv'.format(now, filename_suffix)
    file_path = os.path.join(directory, output_file_name)
    df.to_csv(file_path, index=False, header=True)


if __name__ == "__main__":
    
    # dataset_name = 'ECB_measurement_during_10mA_gridtest_5Ademagnetize'
    # duration = 60
    
    arduino = ArduinoUno('COM7')
    # measure = threading.Thread(target=arduino.getTemperatureMeasurements)
    # measure.start()
    # time.sleep(duration)
    # arduino.stop = True
    # measure.join()
    
    # saveTempData(arduino.data_stack, directory=r'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\2_Misc_Code\Temperature Sensors\ADT7410_temperature_measurements\Measurement_over_time', filename_suffix=dataset_name)
    
    while True:
        # A synchronisation string containing the characters tx is sent before each set of measurements
        tx = arduino.board.readline()
        if str(tx).strip('b\'\\rn') == 'tx':
            rawData1 = arduino.board.readline()
            rawData2 = arduino.board.readline()
            rawData3 = arduino.board.readline()
            rawData4 = arduino.board.readline()
        
            timeStamp = str(rawData1).strip('b\'\\rn')
            temp1 = str(rawData2).strip('b\'\\rn')
            temp2 = str(rawData3).strip('b\'\\rn')
            temp3 = str(rawData4).strip('b\'\\rn')
            try:
                timeStamp = float(timeStamp)
                tempFloat1 = float(temp1) / 128
                tempFloat2 = float(temp2) / 128
                tempFloat3 = float(temp3) / 128
                print(f'\rtime: {timeStamp/1000:.2f} s, Temperature measured on sensor 1: {tempFloat1:.3f} °C,'
                      f'sensor 2: {tempFloat2:.3f} °C, sensor 3: {tempFloat3:.3f} °C', sep='', end='', flush=True)
            except:
                print(rawData_1, rawData_2, rawData_3, rawData_4)
        else:
            print(tx)