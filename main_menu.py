# filename: main_menu.py
#
# This script is meant to be used as an interface with the Vector Magnet. The user can choose from various
# methods to set currents on the different channels and thus communicate with the current sources. The standard
# interface for now is the command line, but the ultimate goal is to integrate this into QS3.
#
# Author: Maxwell Guerne-Kieferndorf (QZabre)
#         gmaxwell at student.ethz.ch
#
# Date: 09.10.2020
# latest update: 22.01.2021

########## Standard library imports ##########
import numpy as np
import math
from time import time, sleep
import csv
import os
from scipy import stats

########## local imports ##########
from core.magnet_control_functions import *
from core.measurement_functions import gotoPosition
import other_useful_functions.feedback as fb
from metrolabTHM1176.thm1176 import MetrolabTHM1176Node


def MainMenu():
    """
    Main menu for Vector magnet operation. An arbitrary combination of currents can be set with this menu, thus
    any magnetic field may be generated as well.
    """

    c1 = "0"
    while c1 != "x":
        print("----------- Main Menu -----------")
        print("[x] to exit\n")
        print(
            "[1]: read currents or magnetic field vectors to set from file and record measurements"
            '\n\twith sensor ("gridSweep")'
        )
        print(
            "[2]: generate magnetic field (specify polar and azimuthal angles, magnitude)"
            "\n\t(specify polar and azimuthal angles, magnitude range or rotational axis)"
        )
        print("[3]: set currents manually on the 3 channels (in mA)")

        # print('[h] do a hysteresis test.\n')
        # print('[t]: measure temperature and field for constant, nonzero currents in first half and zero currents in second half\n')

        c1 = input()

        if c1 == "1":
            c1 = input("Automatic exit after finish? (x for yes): ")
            print("initialising gridSweep function...")
            callGridSweep()

        elif c1 == "2":
            c1 = input("Automatic exit after finish? (x for yes): ")
            callGenerateVectorField()

        elif c1 == "3":
            c1 = input("Automatic exit after finish? (x for yes): ")
            callRunCurrents()


def callGridSweep():
    """
    Setup function to call the utility function 'sweepCurrents', see 'utility_functions.py'. Manages necessary inputs.
    """
    # must be a .csv file!
    inpFile = input("Enter a valid configuration file path: ")
    inp1 = input(
        "current factor (if file contains B fields: 1, if currents are in file, choose a current value that brings it to ): "
    )

    # the values for each measurement run should be the same for consistent results
    try:
        start_val = int(inp1)
    except BaseException:
        print("expected numerical value, defaulting to -4500")
        start_val = -4500

    # with MetrolabTHM1176Node(
    #     block_size=30, range="0.3 T", period=0.01, average=1
    # ) as node:
    node = MetrolabTHM1176Node(block_size=30, range='0.1 T', period=0.01, average=1)

    gotoPosition()
    # doing gridSweep
    inp = input("Use current config or B vector file as input? (i/b) ")
    if inp == "b":
        use_B_vectors_as_input = True
    else:
        use_B_vectors_as_input = False

    # inp5 = input('demagnetize after each measurement? (y/n) ')
    inp5 = input("measure temperature? (y/n): ")
    inp6 = input("append today`s date to directory name? (y/n) ")
    datadir = input("Enter a valid directory name to save measurement data in: ")

    gridSweep(
        node,
        inpFile,
        datadir=datadir,
        factor=start_val,
        BField=use_B_vectors_as_input,
        demagnetize=False,
        today=(inp6 == "y"),
        temp_meas=(inp5 == "y"),
    )


def callRunCurrents():
    """
    Setup function to call the utility function 'runCurrents', see 'utility_functions.py'. Manages necessary inputs.
    """
    inp0 = input("timed mode? (y/n) ")
    configs = []
    timers = []
    char = ""
    while char != "x":
        inp1 = input("configuration 1\nChannel 1: ")
        inp2 = input("Channel 2: ")
        inp3 = input("Channel 3: ")
        inp4 = input("timer duration: ")
        try:
            a1 = float(inp1)
            b1 = float(inp2)
            c1 = float(inp3)
            configs.append(np.array([a1, b1, c1]))
            timers.append(float(inp4))
        except BaseException:
            print("expected numerical value, defaulting to (0,0,1)")
            configs.append(np.array([0, 0, 1]))
            timers.append(0)

        print(configs)

        if inp0 == "y":
            char = input("another config (enter x to end) ")
        else:
            char = "x"

    inp5 = input("measure temperature? (y/n): ")

    subdir = "default_location"
    if inp0 == "":
        subdir = input("Which subdirectory should measurements be saved to? ")

    runCurrents(
        configs, timers, subdir=subdir, demagnetize=False, temp_meas=(inp5 == "y")
    )


def callGenerateVectorField():
    """
    Setup function to call the utility function 'generateMagneticField', see 'utility_functions.py'. Manages necessary inputs.
    """
    inp0 = input("timed mode? (y/n) ")
    vector = []
    timers = []
    char = ""
    while char != "x":
        inp1 = input("configuration 1\nmagnitude: ")
        inp2 = input("polar angle (theta): ")
        inp3 = input("azimuthal angle (phi): ")
        inp4 = input("timer duration: ")
        try:
            a1 = float(inp1)
            b1 = float(inp2)
            c1 = float(inp3)
            vector.append(np.array([a1, b1, c1]))
            timers.append(float(inp4))
        except BaseException:
            print("expected numerical value, defaulting to (0,0,10)")
            vector.append(np.array([0, 0, 10]))
            timers.append(0)

        if inp0 == "y":
            char = input("another config (enter x to end)")
        else:
            char = "x"

    inp5 = input("measure temperature? (y/n): ")

    subdir = "default_location"
    if inp0 == "":
        subdir = input("Which subdirectory should measurements be saved to? ")

    generateMagneticField(vector, timers, subdir, False, (inp5 == "y"))


def feedbackMode():
    """
    Setup function to call the utility function 'callableFeedback', see 'feedback.py'. Manages necessary inputs.
    """
    import pandas as pd

    print("Enter the magnetic Field vector info:")
    source = input("With an input file? (y/n) ")
    if source != "y":
        coordinates = input("coordinate system: ")
        B_0 = input("Component 1 = ")
        B_1 = input("Component 2 = ")
        B_2 = input("Component 3 = ")
        B_info_arr = [[coordinates, np.array([float(B_0), float(B_1), float(B_2)])]]

    else:
        inpFile = input("Enter a valid configuration file path: ")
        B_info_arr = []
        with open(inpFile, "r") as f:
            contents = csv.reader(f)
            next(contents)
            for row in contents:
                B_info_arr.append(
                    [row[0], np.array([float(row[1]), float(row[2]), float(row[3])])]
                )

    BVectors = []
    currConfigs = []
    for k in range(len(B_info_arr)):
        B_info = B_info_arr[k]
        BVector, dBdI, cur = fb.callableFeedback(
            B_info, maxCorrection=20, threshold=1, calibrate=True, ECB_active=True
        )
        BVectors.append(BVector)
        currConfigs.append(cur)

    BVectors = np.array(BVectors)
    currConfigs = np.array(currConfigs)

    subdir = input("Which directory should the output file be saved in? ")
    filename = input("Enter a valid filename(no special chars): ")

    if subdir == "":
        subdir = r"data_sets\linearization_matrices"
    if filename == "" or filename[0] == " ":
        filename = "dataset1"

    now = datetime.now().strftime("%y_%m_%d_%H%M%S")
    filename = f"{now}-{filename}.csv"

    filepath = os.path.join(subdir, filename)

    df = pd.DataFrame(
        {
            "expected Bx [mT]": BVectors[:, 0],
            "expected By [mT]": BVectors[:, 1],
            "expected Bz [mT]": BVectors[:, 2],
            "channel 1 [A]": currConfigs[:, 0],
            "channel 2 [A]": currConfigs[:, 1],
            "channel 3 [A]": currConfigs[:, 2],
        }
    )
    df.to_csv(filepath, index=False, header=True)


if __name__ == "__main__":
    MainMenu()
