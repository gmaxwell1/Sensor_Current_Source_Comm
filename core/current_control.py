
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
        A thread that can be used as a PI controller for the power supplies, such that
        they work as voltage controlled current sources.

        Args:
            connection (IT6432Connection): Current source object which is to be controlled
            current_set (float): Target current
            prop_gain (float, optional): Proportional gain
            int_gain (float, optional): Integral gain
        """
        # threading.Thread.__init__(self)

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

        self.lock = threading.Lock()
        # self.threadID = self.connection.channel()
        # self.name = 'currentController_' + str(self.threadID)

        self.control_enable = False

    def piControl(self, turn_off_after_disable, print_params, auto_disable):
        """
        Basic PI controller for voltage controlled current.

        Args:
            turn_off_after_disable (bool): the current source will be turned off after
                                           the controller is disabled.
            print_params (bool): the control/error parameters will be continuously printed
                                 and updated.
            auto_disable (bool): Current source will be disabled when the desired set
                                 point is reached.
        """
        # if false, stop controller
        self.lock.acquire()
        try:
            self.control_enable = True

            I_limit = self.connection.currentLim
            if abs(self.I_setpoint) < 0.002:
                self.I_setpoint = 0

            if self.connection.query("output?") == "0":
                self.connection.clrOutputProt()
                self.connection._write(f"voltage 0V;:current {I_limit}A;:output 1")
            else:
                self.connection._write(f"current {I_limit}A")
        finally:
            self.lock.release()

        # parameters for PI control:
        Kp = self.prop_gain
        Ki = self.int_gain
        integrator = 0
        hold = True
        reset = False
        Kff = 0.45
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
        self.rampVoltageSimple(v_meas, v_control, 0.05)

        i_error = self.I_setpoint - i_meas

        v_repeat_count = 0
        sat_count = 0
        stability_count = 0
        v_meas_queue = [v_meas, 0]

        # control loop
        while self.control_enable:
            try:
                self.connection._write(f'voltage {v_control}V')
                # allow automatic turning off
                if auto_disable and stability_count >= 10:
                    self.control_enable = False
            except BaseException as e:
                print(e)

            v_control += Kp * i_error

            if not hold:
                integrator += i_error
            v_control += Ki * integrator
            # anti-windup
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

            hold = abs(i_error) > Kp or abs(i_error) <= 0.002 or reset

            if abs(i_error) <= 0.002:
                stability_count += 1
            else:
                stability_count = 0

            if abs(v_meas_queue[0] - v_control) > 0.25:
                v_repeat_count += 1
            else:
                if not reset:
                    v_repeat_count = 0
            # check if integrator needs to be reset
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
        try:
            self.connection._write(f"voltage {set_voltage}")
            diff_v = new_voltage - set_voltage
            sign = np.sign(diff_v)
            while abs(diff_v) >= threshold:
                set_voltage = set_voltage + sign * step_size
                self.connection._write(f"voltage {set_voltage}V")
                diff_v = new_voltage - set_voltage
                sign = np.sign(diff_v)

            self.connection._write(f"voltage {new_voltage}V")
        except BaseException as e:
            print(e)

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

        try:
            res = self.connection.query(command)
            if isinstance(res, list):
                res = res[0]
            measured.append(float(res))
        except BaseException as e:
            print(e)
        return measured

    def updateSetCurrent(self, new_current):
        i_diff = abs(self.getMeasurement(meas_quantity='current')[0] - self.I_setpoint)
        while i_diff > 0.01:
            i_diff = abs(self.getMeasurement(meas_quantity='current')[0] - self.I_setpoint)
        self.lock.acquire()
        try:
            self.I_setpoint = new_current
        finally:
            self.lock.release()

    def setNewCurrent(self, new_current):
        self.lock.acquire()
        try:
            self.control_enable = False
            self.I_setpoint = new_current
        finally:
            self.lock.release()


class currControlThread(threading.Thread):
    def __init__(
            self,
            controller: currentController,
            turn_off_after_disable=False,
            print_params=False,
            auto_disable=False):
        super.__init__()
        self.controller = controller
        self.name = f'currentController_{controller.connection.channel()}'
        self.args = (turn_off_after_disable, print_params, auto_disable)

    def run(self):
        self.controller.piControl(self.args[0], self.args[1], self.args[2])


class powerSupplyCommands(object):
    """
    To be used for controlling the three power supplies for each channel of the VM.
    Functions for setting the current or demagnetizing the coils are wrapped by this class.
    """

    def __init__(self, **kwargs):
        self.__channel_1 = IT6432Connection(1)
        self.__channel_2 = IT6432Connection(2)
        self.__channel_3 = IT6432Connection(3)

    class voltageRamper(threading.Thread):
        """
        A thread that simply runs the function rampVoltage. Enables parallel operation of
        power supplies.

        Args:
            channel (int): Current source which is to be controlled
            new_voltage (float): Target voltage
            new_current (float): Target current
            step_size (float, optional): Voltage increment. Defaults to 0.01.
        """

        def __init__(
            self,
            channel: int,
            new_voltage: float,
            new_current: float,
            step_size: float = 0.01,
        ):
            threading.Thread.__init__(self)

            self._channel = channel
            self._new_voltage = new_voltage
            self._new_current = new_current
            self._step_size = step_size

            self._name = 'VoltageRamper' + str(self._channel)

            self.target = powerSupplyCommands.rampVoltage
            self.args = (self._channel, self._new_voltage, self._new_current, self._step_size)

    def openConnection(self):
        """
        Open a connection to each IT6432 current source.
        """
        self.__channel_1.connect()
        self.__channel_1._write("system:remote")

        self.__channel_2.connect()
        self.__channel_2._write("system:remote")

        self.__channel_3.connect()
        self.__channel_3._write("system:remote")

    def closeConnection(self):
        """
        Close the connection with the current sources.
        """
        self.__channel_1._write("system:local")
        self.__channel_1.close()

        self.__channel_2._write("system:local")
        self.__channel_2.close()

        self.__channel_3._write("system:local")
        self.__channel_3.close()

    @staticmethod
    def rampVoltageSimple(
        connection: IT6432Connection,
        set_voltage: float = 0,
        new_voltage: float = 0.3,
        step_size: float = 0.01
    ):
        """
        Helper function to take care of ramping the voltage.

        Args:
            connection (IT6432Connection):
            set_voltage (float): Voltage that is set right now.
            new_voltage (float): Target voltage.
            step_size (float, optional): Defaults to 0.01.
        """
        threshold = 2 * step_size
        connection._write(f"voltage {set_voltage}V")
        diff_v = new_voltage - set_voltage
        sign = np.sign(diff_v)
        while abs(diff_v) >= threshold:
            set_voltage = set_voltage + sign * step_size
            connection._write(f"voltage {set_voltage}V")
            diff_v = new_voltage - set_voltage
            sign = np.sign(diff_v)

        connection._write(f"voltage {new_voltage}V")

    def getMeasurement(self, channels: list, meas_type: str = "",
                       meas_quantity: str = "current") -> list:
        """
        Get DC current/power/voltage values from each channel

        Args:
            channels (list): channels on which to measure the requested quantity
            meas_type (str, optional): Any of the types {"", "acdc", "max", "min"}. These are either
                                       a DC measurement, an RMS value or minimum/maximum.
                                       Defaults to "".
            meas_quantity (str, optional): Any of the types {"current", "voltage", "power"}.
                                           Defaults to "current".

        Returns:
            list: a list of all the currents (or an error code)
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
                command += ":" + meas_type[0]
            command += "?"

        measured = []
        if 1 in channels:
            res = self.__channel_1.query(command)
            if isinstance(res, list):
                res = res[0]
            measured.append(float(res))

        if 2 in channels:
            res = self.__channel_2.query(command)
            if isinstance(res, list):
                res = res[0]
            measured.append(float(res))

        if 3 in channels:
            res = self.__channel_3.query(command)
            if isinstance(res, list):
                res = res[0]
            measured.append(float(res))

        return measured

    def rampVoltage(
        self,
        channel: int,
        new_voltage: float,
        new_current: float,
        step_size: float = 0.01
    ):
        """
        Ramp voltage to a new specified value. The current should not be directly set, due
        to the load inductance instead it is a limit for the voltage increase. Like this, it
        is possible to ensure that the current takes the exact desired value without causing
        the voltage protection to trip.

        Args:
            channel (1,2 or 3): channel on which to change the voltage.
            new_voltage (float): Target voltage
            new_current (float): Target current
            step_size (float, optional): Voltage increment. Defaults to 0.01.
        """
        # logging.basicConfig(filename="voltage_ramp.log", level=logging.DEBUG, force=True)
        # logging.info("now ramping current in channel %s", connection.channel())

        if channel == 1:
            connection = self.__channel_1
        elif channel == 2:
            connection = self.__channel_2
        elif channel == 3:
            connection = self.__channel_3

        connection.clrOutputProt()

        if connection.query("output?") == "0":
            connection._write("voltage 0V;:output 1")

        if new_current > connection.currentLim:
            new_current = connection.currentLim
        if new_current < 0.002 or abs(new_voltage) < 0.001:
            new_current = 0.002
            new_voltage = 0
        if abs(new_voltage) > connection.voltageLim:
            new_voltage = connection.voltageLim

        meas_voltage = self.getMeasurement(channel, meas_quantity="voltage")[0]
        meas_current = self.getMeasurement(channel, meas_quantity="current")[0]

        # logging.debug(f"actual voltage: {meas_voltage}V, actual current: {meas_current}A")
        # logging.debug(f"target voltage: {new_voltage}V, desired current: {new_current}A")

        if new_current - abs(meas_current) < 0:
            intermediate_step = 0.4 * new_current if new_current > 0.01 else 0
            self.rampVoltageSimple(connection, meas_voltage, intermediate_step, step_size)

        repeat_count = 0
        meas_current_queue = [meas_current, 0]
        while not (abs(meas_current) < new_current or repeat_count >= 5):
            meas_current_queue.insert(0, self.getMeasurement(channel, meas_quantity="current")[0])
            meas_current_queue.pop(2)
            repeat = abs(meas_current_queue[0] - meas_current_queue[1]) < 0.002
            if repeat:
                repeat_count += 1
            else:
                repeat_count = 0

        connection._write(f"current {new_current}A")

        if new_current < 0.002 or abs(new_voltage) < 0.001:
            connection._write("output 0")
        else:
            meas_voltage = self.getMeasurement(channel, meas_quantity="voltage")[0]
            self.rampVoltageSimple(connection, meas_voltage, new_voltage, step_size)

        # messages = connection.getStatus()
        # if "QER0" in messages.keys():
        #     logging.info(messages["QER0"] + ", channel: %s", connection.channel())
        # if "QER4" in messages.keys():
        #     logging.info(messages["QER4"] + ", channel: %s", connection.channel())
        # if "OSR1" in messages.keys():
        #     logging.info(messages["OSR1"] + ", channel: %s", connection.channel())

    def setCurrents(self, desCurrents: list = [0, 0, 0]):
        """
        Set current values for each channel. Voltage is limited as well to prevent very fast current changes due to inductance.

        Args:
            desCurrents (list, optional):  list of length 3 containing int values of currents (unit: mA), Defaults to [0,0,0].
        """
        thread_pool = []

        signs = np.sign(desCurrents)

        current_1 = (
            signs[0] * desCurrents[0]
            if abs(desCurrents[0]) <= self.__channel_1.currentLim
            else self.__channel_1.currentLim
        )
        # conservative estimation of coil resistance: 0.48 ohm
        v_set_1 = signs[0] * 0.472 * current_1
        worker_1 = self.voltageRamper(1, v_set_1, current_1, 0.05)
        thread_pool.append(worker_1)

        current_2 = (
            signs[1] * desCurrents[1]
            if abs(desCurrents[1]) <= self.__channel_2.currentLim
            else self.__channel_2.currentLim
        )
        # conservative estimation of coil resistance: 0.48 ohm
        v_set_2 = signs[1] * 0.472 * current_2
        worker_2 = self.voltageRamper(2, v_set_2, current_2, 0.05)
        thread_pool.append(worker_2)

        current_3 = (
            signs[2] * desCurrents[2]
            if abs(desCurrents[2]) <= self.__channel_3.currentLim
            else self.__channel_3.currentLim
        )
        # conservative estimation of coil resistance: 0.48 ohm
        v_set_3 = signs[2] * 0.472 * current_3
        worker_3 = self.voltageRamper(3, v_set_3, current_3, 0.05)
        thread_pool.append(worker_3)

        for thread in thread_pool:
            thread.start()
        for thread in thread_pool:
            thread.join()

    def demagnetizeCoils(self, current_config: list = [1, 1, 1],):
        """
        Try to eliminate any hysteresis effects by applying a slowly oscillating and decaying
        (triangle wave) voltage to the coils.

        Args:
            current_config (list, optional): The starting configuration in which the current
                                             sources begin before ramping down the voltage.
        """

        steps = np.array([0, 1, 2, 3, 4])
        bounds = 0.475 * np.outer(current_config, np.exp(-steps))

        ch_1 = self.__channel_1
        ch_2 = self.__channel_2
        ch_3 = self.__channel_3

        ch_1._write('current 5.01A')
        ch_2._write('current 5.01A')
        ch_3._write('current 5.01A')

        thread_pool = [None, None, None]
        target_func = self.rampVoltageSimple
        sign = 1

        for i in range(bounds.shape[1]):
            voltages = self.getMeasurement([1, 2, 3], meas_quantity='voltage')
            sign *= -1
            kwargs_1 = {'step_size': 0.06,
                        'set_voltage': voltages[0], 'new_voltage': sign * bounds[0, i]}
            kwargs_2 = {'step_size': 0.06,
                        'set_voltage': voltages[1], 'new_voltage': sign * bounds[1, i]}
            kwargs_3 = {'step_size': 0.06,
                        'set_voltage': voltages[2], 'new_voltage': sign * bounds[2, i]}

            thread_pool[0] = threading.Thread(target=target_func,
                                              name='currentController_1',
                                              args=(ch_1),
                                              kwargs=kwargs_1)

            thread_pool[1] = threading.Thread(target=target_func,
                                              name='currentController_2',
                                              args=(ch_2),
                                              kwargs=kwargs_2)

            thread_pool[2] = threading.Thread(target=target_func,
                                              name='currentController_3',
                                              args=(ch_3),
                                              kwargs=kwargs_3)
            for thread in thread_pool:
                thread.start()

            for thread in thread_pool:
                thread.join()

            sleep(0.1)

        disableCurrents(channel_1, channel_2, channel_3)

    def disableCurrents(self):
        """Disable current controllers."""
        thread_pool = []

        worker_1 = self.voltageRamper(1, 0, 0)
        thread_pool.append(worker_1)

        worker_2 = self.voltageRamper(2, 0, 0)
        thread_pool.append(worker_2)

        worker_3 = self.voltageRamper(3, 0, 0)
        thread_pool.append(worker_3)

        for thread in thread_pool:
            thread.start()
        for thread in thread_pool:
            thread.join()


if __name__ == "__main__":

    channel_1 = IT6432Connection(1)
    openConnection(channel_1)
    c = currentController(channel_1, 1, prop_gain=0.03, int_gain=0.001)
    currents = [0.757, -0.420, 1.453, 4.5, -3.421, -0.03, 3.193]

    for ix, item in enumerate(currents):
        c.setNewCurrent(item)
        task = threading.Thread(target=c.piControl,
                                name=f'currentController{ix}',
                                args=[ix == len(currents) - 1, False, False])
        task.start()
        i = 0
        while i != '':
            i = input('next current: press enter.\n')
        c.control_enable = False

        task.join()

    closeConnection(channel_1)
