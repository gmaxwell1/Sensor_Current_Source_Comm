
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


class PowerSupplyCommands(object):
    """
    To be used for controlling the three power supplies for each channel of the VM.
    Functions for setting the current or demagnetizing the coils are wrapped by this class.

    Args:
        step_size (float, optional): Voltage increment for ramping voltage. Defaults to 0.05.
    """

    def __init__(self, **kwargs):
        self.__channel_1 = IT6432Connection(1)
        self.__channel_2 = IT6432Connection(2)
        self.__channel_3 = IT6432Connection(3)

        self.power_supplies = (self.__channel_1, self.__channel_2, self.__channel_3)

        self.__set_currents = [0, 0, 0]

        if 'step_size' in kwargs.keys():
            self.__ramp_step_size = kwargs['step_size']
        else:
            self.__ramp_step_size = 0.05

    @property
    def rampStepSize(self) -> float:
        return self.__ramp_step_size

    @rampStepSize.setter
    def rampStepSize(self, step_size: float):
        self.__ramp_step_size = step_size

    @property
    def setCurrentValues(self) -> list:
        return self.__set_currents

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

    def setCurrents(self, des_currents: list = [0, 0, 0]):
        """
        Set current values for each channel. Voltage is limited as well to prevent very fast current changes due to inductance.

        Args:
            des_currents (list, optional):  list of length 3 containing int values of currents (units: A), Defaults to [0,0,0].
        """
        thread_pool = []

        signs = np.sign(des_currents)

        for ix, power_supply in enumerate(self.power_supplies):
            des_current_ix = (signs[ix] * des_currents[ix]
                              if abs(des_currents[ix]) <= power_supply.current_lim
                              else power_supply.current_lim)
            # conservative estimate of coil resistance: 0.472 ohm -> ensure current compliance
            # (actual value is probably closer to 0.46)
            v_set_ix = signs[ix] * 0.472 * des_current_ix
            worker_ix = VoltageRamper(power_supply, v_set_ix, des_current_ix, self.__ramp_step_size)
            thread_pool.append(worker_ix)

        for thread in thread_pool:
            thread.start()
        for thread in thread_pool:
            thread.join()

        self.__set_currents = des_currents

    def demagnetizeCoils(self, current_config: list = [1, 1, 1], step_size: float = 0.06):
        """
        Try to eliminate any hysteresis effects by applying a slowly oscillating and decaying
        (triangle wave) voltage to the coils.

        Args:
            current_config (list, optional): The starting configuration in which the current
                                             sources begin before ramping down the voltage.
                                             Defaults to [1,1,1].
            step_size (float, optional): The voltage increment used when ramping voltage for
                                         demagnetization. The step size 0.06 is somewhat arbitrary
                                         but has worked well so far, so it is hard to say how
                                         useful changing it may be. Defaults to 0.06.
        """

        steps = np.array([0, 1, 2, 3, 4])
        bounds = 0.475 * np.outer(current_config, np.exp(-steps))

        for power_supply in self.power_supplies:
            if power_supply.channel == 2:
                power_supply._write('current 5.01')
            else:
                power_supply._write('current 5.01A')

        thread_pool = [None, None, None]
        target_func = rampVoltageSimple
        sign = 1

        for i in range(bounds.shape[1]):
            voltages = []
            sign *= -1

            for ix, power_supply in enumerate(self.power_supplies):
                voltages.append(power_supply.getMeasurement(meas_quantity='voltage'))
                kwargs_ix = {'step_size': step_size,
                             'set_voltage': voltages[ix], 'new_voltage': sign * bounds[ix, i]}

                thread_pool[ix] = threading.Thread(target=target_func,
                                                   name=f'VoltageRamper_{ix + 1}',
                                                   args=(power_supply,),
                                                   kwargs=kwargs_ix)

            for thread in thread_pool:
                thread.start()

            for thread in thread_pool:
                thread.join()

            sleep(0.1)

        self.disableCurrents()

    def disableCurrents(self):
        """Disable current controllers."""
        thread_pool = []

        for power_supply in self.power_supplies:
            worker_ix = VoltageRamper(power_supply, 0, 0, self.__ramp_step_size)
            thread_pool.append(worker_ix)

        for thread in thread_pool:
            thread.start()
        for thread in thread_pool:
            thread.join()


class VoltageRamper(threading.Thread):
    """
    A thread that simply runs the function rampVoltage. Enables parallel operation of
    power supplies.

    Args:
        channel (int): Current source which is to be controlled
        new_voltage (float): Target voltage
        new_current (float): Target current
        step_size (float, optional): Voltage increment. Defaults to 0.05.
    """

    def __init__(
        self,
        channel: IT6432Connection,
        new_voltage: float,
        new_current: float,
        step_size: float = 0.05,
    ):
        threading.Thread.__init__(self)
        self._channel = channel
        self._new_voltage = new_voltage
        self._new_current = new_current
        self._step_size = step_size

        self._name = 'VoltageRamper_' + str(self._channel.channel)

    def run(self):
        try:
            rampVoltage(
                self._channel,
                self._new_voltage,
                self._new_current,
                self._step_size)
        except BaseException as e:
            print(f'There was an error! {e}')


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
    if connection.channel != 2:
        postfix_v = "V"
    else:
        postfix_v = ""
    threshold = 2 * step_size
    connection._write(f"voltage {set_voltage}" + postfix_v)
    diff_v = new_voltage - set_voltage
    sign = np.sign(diff_v)
    while abs(diff_v) >= threshold:
        set_voltage = set_voltage + sign * step_size
        connection._write(f"voltage {set_voltage}" + postfix_v)
        diff_v = new_voltage - set_voltage
        sign = np.sign(diff_v)

    connection._write(f"voltage {new_voltage}" + postfix_v)


def rampVoltage(
    connection: IT6432Connection,
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
    # logging.info("now ramping current in channel %s", connection.channel)

    connection.clrOutputProt()

    if connection.channel != 2:
        postfix_v = "V"
        postfix_i = "A"
    else:
        postfix_v = ""
        postfix_i = ""

    if connection.query("output?") == "0":
        connection._write("voltage 0" + postfix_v + ";:output 1")

    if new_current > connection.current_lim:
        new_current = connection.current_lim
    if new_current < 0.002 or abs(new_voltage) < 0.001:
        new_current = 0.002
        new_voltage = 0
    if abs(new_voltage) > connection.voltage_lim:
        new_voltage = connection.voltage_lim

    meas_voltage = connection.getMeasurement(meas_quantity="voltage")
    meas_current = connection.getMeasurement(meas_quantity="current")

    # logging.debug(f"actual voltage: {meas_voltage}V, actual current: {meas_current}A")
    # logging.debug(f"target voltage: {new_voltage}V, desired current: {new_current}A")

    if new_current - abs(meas_current) < 0:
        intermediate_step = 0.4 * new_current if new_current > 0.01 else 0
        rampVoltageSimple(connection, meas_voltage, intermediate_step, step_size)

    repeat_count = 0
    meas_current_queue = [meas_current, 0]
    while not (abs(meas_current) < new_current or repeat_count >= 5):
        meas_current_queue.insert(0, connection.getMeasurement(meas_quantity="current"))
        meas_current_queue.pop(2)
        repeat = abs(meas_current_queue[0] - meas_current_queue[1]) < 0.002
        if repeat:
            repeat_count += 1
        else:
            repeat_count = 0

    connection._write(f"current {new_current}" + postfix_i)

    if new_current < 0.002 or abs(new_voltage) < 0.001:
        connection._write("output 0")
    else:
        meas_voltage = connection.getMeasurement(meas_quantity="voltage")
        rampVoltageSimple(connection, meas_voltage, new_voltage, step_size)

    # messages = connection.getStatus()
    # if "QER0" in messages.keys():
    #     logging.info(messages["QER0"] + ", channel: %s", connection.channel)
    # if "QER4" in messages.keys():
    #     logging.info(messages["QER4"] + ", channel: %s", connection.channel)
    # if "OSR1" in messages.keys():
    #     logging.info(messages["OSR1"] + ", channel: %s", connection.channel)


if __name__ == "__main__":

    psu = PowerSupplyCommands()

    psu.openConnection()
    psu.setCurrents([1, 3, 2.3])

    sleep(10)

    psu.demagnetizeCoils(psu.setCurrentValues)

    psu.closeConnection()
