"""
Simple Hello World example with PyQt5.
"""

# imports
import os
import sys
import threading
import traceback
from datetime import datetime
from time import sleep, time

import matplotlib as mpl
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from PyQt5 import QtGui
from PyQt5.QtCore import (QObject, QRunnable, Qt, QThreadPool, pyqtSignal,
                          pyqtSlot)
from PyQt5.QtWidgets import (QApplication, QCheckBox, QFormLayout, QHBoxLayout,
                             QLabel, QLineEdit, QMessageBox, QPushButton,
                             QToolBar, QVBoxLayout, QWidget)

from core.current_control import PowerSupplyCommands
from core.field_current_tr import (computeCoilCurrents,
                                   computeMagneticFieldVector)
from IT6432.it6432connection import IT6432Connection

#from qs3.utils import logger


# %%


class WorkerSignals(QObject):
    '''
    Defines the signals available from a running worker thread.

    Supported signals are:

    finished
        No data

    error
        tuple (exctype, value, traceback.format_exc() )

    result
        object data returned from processing, anything

    progress
        int indicating % progress

    '''
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)


class Worker(QRunnable):
    '''
    Worker thread

    Inherits from QRunnable to handle worker thread setup, signals and wrap-up.

    :param callback: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    '''

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()

        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''

        # Retrieve args/kwargs here; and fire processing using them
        try:
            result = self.fn(*self.args, **self.kwargs)
        except BaseException:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            if result is not None:
                self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done


class VectorMagnetDialog(QWidget):

    """
    Test window of GUI part for controlling vector magnet.
    """

    def __init__(self, parent=None):
        """Initialize widget. It is recommended to use it inside a with statement."""
        super().__init__(parent)

        # will probably be changed/removed
        self.gui_image_folder = r'C:\Users\Magnebotix\Desktop\Qzabre_Vector_Magnet\1_Version_2_Vector_Magnet\2_Current_Source_Contol\Sensor_Current_Source_Comm\gui_images'
        self.icon_file = 'window_icon.png'

        self.setWindowTitle('Vector Magnet Control')
        self.setWindowIcon(QtGui.QIcon(os.path.join(self.gui_image_folder, self.icon_file)))

        # set class variables
        self.magnet_is_on = False

        # connect to power supplies
        self.commander = PowerSupplyCommands()
        # logger
        # print('open connection to power supplies')
        self.threads = QThreadPool()
        # set up required widgets
        self._create_widgets()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """ Ensure that connection to channels is closed. """
        self.commander.closeConnection()
        print('connection closed.')

    def _create_widgets(self):
        """ Create all widgets needed for the graphical interface. """
        # set layout of window
        generalLayout = QVBoxLayout()

        # add input fields to enter spherical coordinates
        upperLayout = QHBoxLayout()

        entriesLayout = QFormLayout()
        self.input_polar_coords = [
            QLineEdit(parent=self),
            QLineEdit(parent=self),
            QLineEdit(parent=self)]
        labels_polar_coords = [
            '|\U0001D435| [mT]:',
            '\U0001D717 [°]:',
            '\U0001D719 [°]:']  # magnitude, theta, phi
        for i in range(3):
            entriesLayout.addRow(labels_polar_coords[i], self.input_polar_coords[i])
            self.input_polar_coords[i].setAlignment(Qt.AlignRight)
            self.input_polar_coords[i].returnPressed.connect(self._onSetValues)

        upperLayout.addLayout(entriesLayout)
        # add a label to display set magnetic field values
        setBField = QHBoxLayout()
        self.label_BField = QLabel('')
        self.label_BField.setText('B field setpoint:\n' +
                                  f'|\U0001D435| = 0.0 mT\n' +
                                  f'\U0001D717 = 0.0°\n' +
                                  f'\U0001D719 = 0.0°\n')
        setBField.addWidget(self.label_BField)

        upperLayout.addLayout(setBField)
        # add a label to display measured current values
        currentsLayout = QHBoxLayout()
        self.label_currents = QLabel('')
        self.label_currents.setText('actual currents:\n' +
                                    f'\U0001D43C\u2081 = 0.000A\n' +
                                    f'\U0001D43C\u2082 = 0.000A\n' +
                                    f'\U0001D43C\u2083 = 0.000A\n')
        currentsLayout.addWidget(self.label_currents)

        upperLayout.addLayout(currentsLayout)
        generalLayout.addLayout(upperLayout)

        # add button for setting field values
        self.btn_set_values = QPushButton('set field values')
        self.btn_set_values.clicked.connect(self._onSetValues)
        generalLayout.addWidget(self.btn_set_values)

        # add label for error messages related to setting field values
        self.msg_values = QLabel('')
        generalLayout.addWidget(self.msg_values)
        try:
            self.commander.openConnection()
            self.msg_values.setText("Connected to power supplies.")
        except BaseException:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.updateErrorMessage((exctype, value, traceback.format_exc()))

        # add button for switching on/off field, disable at first
        fieldLayout = QHBoxLayout()
        self.btn_set_field = QPushButton('switch on field')
        self.btn_set_field.clicked.connect(self._SwitchOnField)
        self.btn_set_field.setDisabled(True)
        fieldLayout.addWidget(self.btn_set_field)

        # add a disabled button that shows whether magnet is on or off, could also
        # be replaced by something else
        self.lab_field_status = QLabel('off')
        self.lab_field_status.setAlignment(Qt.AlignCenter)
        self.lab_field_status.setStyleSheet("border: 1px solid black;")
        self.lab_field_status.setFixedWidth(50)
        fieldLayout.addWidget(self.lab_field_status)
        generalLayout.addLayout(fieldLayout)

        # add checkbox to enable/disable demagnetization
        self.check_demag = QCheckBox('demagnetize')

        generalLayout.addWidget(self.check_demag)

        self.setLayout(generalLayout)

    def updateErrorMessage(self, args):
        """
        Keep track of errors which occurred in the GUI. A different logfile may be used.

        Args:
            args (tuple): (exctype, value, traceback.format_exc()) The information about
                          the exception which will be written to the log file.
        """
        self.msg_values.setText(f"{args[0]}: {args[1]}")

        with open('GUI_exceptions.log', 'a') as logfile:
            logfile.write(f"{datetime.now().strftime('%d-%m-%y_%H:%M:%S')}: "
                          f"{args[0]}, {args[1]}\n{args[2]}\n")

    def _onSetValues(self):
        """Read input coordinates, check validity and switch on magnet."""
        # get input polar coordinates
        coords = [input_field.text() for input_field in self.input_polar_coords]

        # check validity, enable field if valid and refuse if not valid
        if self.valid_inputs(coords):
            self.field_coords = [float(coords[0]), float(coords[1]), float(coords[2])]
            self.msg_values.setText('')
            self.btn_set_field.setEnabled(True)

            self.label_BField.setText('B field setpoint:\n' +
                                      f'|\U0001D435| = {self.field_coords[0]:.3f} mT\n' +
                                      f'\U0001D717 = {self.field_coords[1]}°\n' +
                                      f'\U0001D719 = {self.field_coords[2]}°\n')

            if self.magnet_is_on:
                self._SwitchOnField()

        else:
            self.msg_values.setText('Invalid values, check inputs!')

            if not self.magnet_is_on:
                self.btn_set_field.setDisabled(True)

    @staticmethod
    def valid_inputs(values):
        """
        Test whether all values are valid float values and whether the angles are correct.

        Args:
            values (list): [magnitude, theta, phi] is a list of length 3 containing spherical
                           coordinates of desired field. Accepted ranges: 0 <= magnitude;
                           0 <= theta <= 180; 0 <= phi < 360

        Returns:
            bool: True if all values are valid and False else
        """
        # test whether all values are float
        try:
            [float(v) for v in values]
        except BaseException:
            return False
        else:
            # check magnitude and polar angle individually, since here values are bounded
            if float(values[0]) < 0:
                return False
            if float(values[1]) > 180 or float(values[1]) < 0:
                return False
            if float(values[2]) >= 360 or float(values[1]) < 0:
                return False

            return True

    def _SwitchOnField(self):
        """Switch on vector magnet and set field values that are currently set as class variables."""
        # update variables
        self.magnet_is_on = True

        # re-define button for switching on/off magnet
        self.lab_field_status.setStyleSheet('border: 1px solid black; background-color: lime')
        self.lab_field_status.setText('on')
        self.btn_set_field.setText('switch off field')
        try:
            self.btn_set_field.clicked.disconnect()
        except BaseException:
            pass
        self.btn_set_field.clicked.connect(self._SwitchOffField)

        # actual magic
        demagnetize = self.check_demag.isChecked()
        self._setMagField(
            self.field_coords[0],
            self.field_coords[1],
            self.field_coords[2],
            demagnetize)

        # update the currents continuously
        current_updater = Worker(self.contCurrentFetch)
        current_updater.signals.error.connect(self.updateErrorMessage)

        self.threads.start(current_updater)

    def _SwitchOffField(self):
        """ Switch off vector magnet. """
        # update variables
        self.magnet_is_on = False

        # re-define button for switching on/off magnet
        self.lab_field_status.setStyleSheet('border: 1px solid black; background-color: None')
        self.lab_field_status.setText('off')
        self.btn_set_field.setDisabled(True)
        self.btn_set_field.setText('switch on field')
        try:
            self.btn_set_field.clicked.disconnect()
        except BaseException:
            pass
        self.btn_set_field.clicked.connect(self._SwitchOnField)

        # actual magic
        demagnetize = self.check_demag.isChecked()
        self._disableField(demagnetize)
        self.btn_set_field.setEnabled(True)

        # update the currents to be 0 again.
        self._DisplayCurrents()

    def _DisplayCurrents(self):
        """
        Method called when checking or unchecking checkbox. Display currents below if checked, hide else.
        """
        currents = self._getCurrents()

        if self.magnet_is_on:
            text = 'actual currents:\n' + \
                f'\U0001D43C\u2081 = {currents[0]:.3f}A\n' + \
                f'\U0001D43C\u2082 = {currents[1]:.3f}A\n' + \
                f'\U0001D43C\u2083 = {currents[2]:.3f}A\n'

        else:
            text = 'actual currents:\n' + \
                f'\U0001D43C\u2081 = 0.000A\n' + \
                f'\U0001D43C\u2082 = 0.000A\n' + \
                f'\U0001D43C\u2083 = 0.000A\n'

        self.label_currents.setText(text)

    def contCurrentFetch(self):
        while self.magnet_is_on:
            self._DisplayCurrents()
            sleep(0.8)

    def contStatusFetch(self):

        important_msgs = ['QER0', 'QER1', 'QER3', 'QER4', 'QER5', 'ESR3', 'OSR1']

        while self.magnet_is_on:
            message_dicts = []
            for i in range(3):
                message_dicts.append(self.commander.power_supplies[i].getStatus())

                for key in important_msgs:
                    if key in message_dicts[i].keys():
                        self.msg_values.setText('%s - on channel %d' % (message_dicts[i][key], i))

            sleep(5)

    def _setMagField(self, magnitude: float, theta: float, phi: float, demagnetize: bool):
        self.msg_values.setText(f'setting field ({magnitude} mT, {theta}°, {phi}°)')

        # get magnetic field in Cartesian coordinates
        B_fieldVector = computeMagneticFieldVector(magnitude, theta, phi)
        currents = computeCoilCurrents(B_fieldVector)

        try:
            if demagnetize:
                self.msg_values.setText('Demagnetizing...')
                starting_currents = self.commander.setCurrentValues
                self.commander.demagnetizeCoils(starting_currents)
                self.commander.setCurrents(des_currents=currents)
        except BaseException:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.updateErrorMessage((exctype, value, traceback.format_exc()))

        else:
            self.msg_values.setText('Currents have been set.')

    def _disableField(self, demagnetize: bool):
        print('do stuff to disable field')
        # use self.msg_magnet.setText() to output any error messages
        if demagnetize:
            self.msg_values.setText('Demagnetizing...')
            starting_currents = self.commander.setCurrentValues
            try:
                self.commander.demagnetizeCoils(starting_currents)
            except BaseException:
                traceback.print_exc()
                exctype, value = sys.exc_info()[:2]
                self.updateErrorMessage((exctype, value, traceback.format_exc()))

        else:
            self.commander.disableCurrents()
            self.msg_values.setText('Power supplies ready.')

    def _getCurrents(self):
        # print('read current values')
        currents = [0, 0, 0]
        try:
            for i, psu in enumerate(self.commander.power_supplies):
                currents[i] = psu.getMeasurement(meas_quantity='current')
        except BaseException:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.updateErrorMessage((exctype, value, traceback.format_exc()))

        return currents


if __name__ == '__main__':

    app = QApplication(sys.argv)

    with VectorMagnetDialog(parent=None) as dialog:
        dialog.show()

        sys.exit(app.exec_())
# %%
