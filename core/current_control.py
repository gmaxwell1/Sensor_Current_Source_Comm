
import os.path as path
import sys
import threading
from time import sleep, time

import numpy as np

try:
    from IT6432.it6432connection import IT6432Connection
except BaseException:
    pass
finally:
    sys.path.insert(1, path.join(sys.path[0], '..'))
    from IT6432.it6432connection import IT6432Connection

    from core.main_comm_new import closeConnection, openConnection
    from core.meas_parallelization import flags, inputThread, threadLock


class currentController(object):
    def __init__(
        self,
        connection: IT6432Connection,
        current_set,
        **kwargs
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

        self.connection = connection
        self.I_setpoint = current_set

        if 'prop_gain' in kwargs.keys():
            self.prop_gain = kwargs['prop_gain']
        else:
            self.prop_gain = 0.1

        if 'int_gain' in kwargs.keys():
            self.int_gain = kwargs['int_gain']
        else:
            self.int_gain = 0

        self.threadID = self.connection.channel()
        self.name = 'currentController_' + str(self.threadID)

        self.control_enable = False

    def piControl(self, turn_off_after_disable, print_params, auto_disable):

        # if false, stop controller
        self.control_enable = True

        I_limit = self.connection.currentLim
        if abs(self.I_setpoint) < 0.002:
            self.I_setpoint = 0

        if self.connection.query("output?") == "0":
            self.connection.clrOutputProt()
            self.connection._write(f"voltage 0V;:current {I_limit}A;:output 1")

        # parameters for PI control:
        Kp = self.prop_gain
        Ki = self.int_gain
        integrator = 0
        hold = True
        reset = False
        Kff = 0.4
        # control input & error
        v_control = 0
        i_error = 0

        # this voltage (2.33 to be precise) leads to maximum output current.
        v_cmax = 2.4

        v_meas = self.getMeasurement(meas_quantity="voltage")[0]
        i_meas = self.getMeasurement(meas_quantity="current")[0]

        # print(f"actual voltage: {v_meas}V, actual current: {i_meas}A")
        if print_params:
            print(f"desired current {self.connection.channel()}: {self.I_setpoint}A")

        v_control += Kff * self.I_setpoint
        self.rampVoltageSimple(v_meas, v_control, 0.1)

        i_error = self.I_setpoint - i_meas

        v_repeat_count = 0
        sat_count = 0
        stability_count = 0
        v_meas_queue = [v_meas, 0]

        while self.control_enable:
            self.connection._write(f'voltage {v_control}V')

            v_control += Kp * i_error

            if not hold:
                integrator += i_error

            v_control += Ki * integrator

            if v_control > v_cmax:
                v_control = v_cmax
                sat_count += 1
            else:
                if not reset:
                    sat_count = 0

            if print_params:
                print(
                    f'\rerror: {i_error:.4f}A, integrator: {integrator:.4f}, control voltage: {v_control:.4f}V, {hold} {reset}',
                    sep='',
                    end='',
                    flush=True)

            v_meas_queue.insert(0, self.getMeasurement(meas_quantity="voltage")[0])
            v_meas_queue.pop(2)
            i_meas = self.getMeasurement(meas_quantity="current")[0]
            i_error = self.I_setpoint - i_meas

            hold = abs(i_error) > Kp or abs(i_error) <= 0.003 or reset

            if abs(i_error) <= 0.003:
                stability_count += 1
            else:
                stability_count = 0

            if auto_disable and stability_count >= 10:
                self.control_enable = False
            # check if integrator needs to be reset
            if abs(v_meas_queue[0] - v_control) > 0.25:
                v_repeat_count += 1
            else:
                if not reset:
                    v_repeat_count = 0

            reset = v_repeat_count > 5 or sat_count > 5

            if reset:
                if integrator != 0:
                    integrator -= (integrator / 5.0)
                else:
                    reset = 0

        if print_params:
            print('')

        if turn_off_after_disable:
            self.rampVoltageSimple(self.getMeasurement(meas_quantity='voltage')[0], 0, 0.1)
            while self.getMeasurement(meas_quantity='current')[0] >= 0.01:
                pass
            self.connection._write('output 0;:current 0.002A')

    def rampVoltageSimple(self, set_voltage, new_voltage, step_size=0.01):
        """
        Helper function to take care of setting the voltage.

        Args:
            set_voltage (float): Voltage that is set right now.
            new_voltage (float): Target voltage.
            step_size (float, optional): Defaults to 0.01.
            threshold (float, optional): Defaults to 0.02.
        """
        threshold = 2 * step_size
        self.connection._write(f"voltage {set_voltage}")
        diff_v = new_voltage - set_voltage
        sign = np.sign(diff_v)
        while abs(diff_v) >= threshold:
            set_voltage = set_voltage + sign * step_size
            self.connection._write(f"voltage {set_voltage}V")
            diff_v = new_voltage - set_voltage
            sign = np.sign(diff_v)

        self.connection._write(f"voltage {new_voltage}V")

    def getMeasurement(self, meas_type="", meas_quantity="current"):
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
            command += ":" + meas_type
        command += "?"

        measured = []
        res = self.connection.query(command)
        if isinstance(res, list):
            res = res[0]
        measured.append(float(res))

        return measured

    def setNewCurrent(self, new_current):
        self.control_enable = False
        self.I_setpoint = new_current


class currControlThread(threading.Thread):
    pass


if __name__ == "__main__":

    channel_1 = IT6432Connection(1)
    openConnection(channel_1)
    c = currentController(channel_1, 1, prop_gain=0.03, int_gain=0)
    currents = [0.757, -0.420, 1.453, 4.5, -3.421, -0.03, 3.193]

    for ix, item in enumerate(currents):
        c.setNewCurrent(item)
        task = threading.Thread(target=c.piControl,
                                name=f'currentController{ix}',
                                args=[ix == len(currents) - 1])
        task.start()
        i = 0
        while i != '':
            i = input('next current: press enter.\n')
        c.control_enable = False

        task.join()

    closeConnection(channel_1)
