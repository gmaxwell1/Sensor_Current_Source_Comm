def rampVoltageSimple(
    connection: IT6432Connection,
    set_voltage,
    new_voltage,
    step_size=0.01
):
    """
    Helper function to take care of setting the voltage.

    Args:
        connection (IT6432Connection):
        set_voltage (float): Voltage that is set right now.
        new_voltage (float): Target voltage.
        step_size (float, optional): Defaults to 0.01.
        threshold (float, optional): Defaults to 0.02.
    """
    threshold = 2 * step_size
    connection._write(f"voltage {set_voltage}")
    diff_v = new_voltage - set_voltage
    sign = np.sign(diff_v)
    while abs(diff_v) >= threshold:
        set_voltage = set_voltage + sign * step_size
        connection._write(f"voltage {set_voltage}V")
        diff_v = new_voltage - set_voltage
        sign = np.sign(diff_v)

    connection._write(f"voltage {new_voltage}V")