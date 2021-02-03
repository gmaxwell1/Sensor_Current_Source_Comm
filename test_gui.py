"""
Simple Hello World example with PyQt5.
"""

# %%
# imports
import sys

import matplotlib as mpl
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from PyQt5 import QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import *

# # local imports
# from core.field_current_tr import computeMagneticFieldVector, computeCoilCurrents
# from core.main_comm_new import setCurrents, disableCurrents, openConnection, closeConnection
# from IT6432.it6432connection import IT6432Connection

# %%


class VectorMagnetDialog(QWidget):

    """
    Test window of GUI part for controlling vector magnet.
    """

    def __init__(self, parent=None):
        """Initialize widget. It is recommended to use it inside a with statement."""
        super().__init__(parent)

        self.setWindowTitle('Vector Magnet Control')

        # set class variables
        self.magnet_is_on = False

        # connect to power supplies
        # self.commander = powerSupplyCommands()
        # openConnection(*self.channels)
        print('open connection to power supplies')

        # set up required widgets
        self._create_widgets()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """ Ensure that connection to channels is closed. """
        print('make sure that connection with power supplies is closed')
        # [closeConnection(chnl) for chnl in self.channels]

    def _create_widgets(self):
        """ Create all widgets needed for the graphical interface. """
        # set layout of window
        generalLayout = QVBoxLayout()

        # add input fields to enter spherical coordinates
        entriesLayout = QFormLayout()
        self.input_polar_coords = [
            QLineEdit(
                parent=self), QLineEdit(
                parent=self), QLineEdit(
                parent=self)]
        labels_polar_coords = [
            '|\U0001D435| [mT]:',
            '\U0001D717 [°]:',
            '\U0001D719 [°]:']  # magnitude, theta, phi
        for i in range(3):
            entriesLayout.addRow(labels_polar_coords[i], self.input_polar_coords[i])
            self.input_polar_coords[i].setAlignment(Qt.AlignRight)
            self.input_polar_coords[i].returnPressed.connect(self._onSetValues)
        generalLayout.addLayout(entriesLayout)

        # add button for setting field values
        self.btn_set_values = QPushButton('set field values')
        self.btn_set_values.clicked.connect(self._onSetValues)
        generalLayout.addWidget(self.btn_set_values)

        # add label for error messages related to setting field values
        self.msg_values = QLabel('')
        generalLayout.addWidget(self.msg_values)

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

        # add label for error messages related to magnet
        self.msg_magnet = QLabel('')
        generalLayout.addWidget(self.msg_magnet)

        # add a checkbox and label to allow displaying set current values
        currentsLayout = QHBoxLayout()
        self.check_currents = QCheckBox('display currents')
        self.check_currents.stateChanged.connect(self._DisplayCurrents)
        self.label_currents = QLabel('\n\n')
        currentsLayout.addWidget(self.check_currents)
        currentsLayout.addWidget(self.label_currents)
        generalLayout.addLayout(currentsLayout)

        # add checkbox to enable/disable demagnetization
        self.check_demag = QCheckBox('demagnetize')

        generalLayout.addWidget(self.check_demag)

        self.setLayout(generalLayout)

    def _onSetValues(self):
        """ Read input coordinates, check validity and switch on magnet."""
        # get input polar coordinates
        coords = [input_field.text() for input_field in self.input_polar_coords]

        # check validity, enable field if valid and refuse if not valid
        if self.valid_inputs(coords):
            self.field_coords = [float(coords[0]), float(coords[1]), float(coords[2])]
            self.msg_values.setText('')
            self.btn_set_field.setEnabled(True)

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

        Arg: values = [magnitude, theta, phi] is a list of length 3 containing spherical coordinates of desired field

        Return True if all values are valid and False else
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

            return True

    def _SwitchOnField(self):
        """ Switch on vector magnet and set field values that are currently set as class variables. """
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
        self._do_stuff_to_enable_field(
            self.field_coords[0],
            self.field_coords[1],
            self.field_coords[2])

        # update the currents in case they are displayed
        self._DisplayCurrents()

    def _SwitchOffField(self):
        """ Switch off vector magnet. """
        # update variables
        self.magnet_is_on = False

        # re-define button for switching on/off magnet
        self.lab_field_status.setStyleSheet('border: 1px solid black; background-color: None')
        self.lab_field_status.setText('off')
        self.btn_set_field.setText('switch on field')
        try:
            self.btn_set_field.clicked.disconnect()
        except BaseException:
            pass
        self.btn_set_field.clicked.connect(self._SwitchOnField)

        # actual magic
        demagnetize = self.check_demag.isChecked()
        self._do_stuff_to_disable_field()

        # update the currents in case they are displayed
        self._DisplayCurrents()

    def _DisplayCurrents(self):
        """
        Method called when checking or unchecking checkbox. Display currents below if checked, hide else.
        """
        if self.check_currents.isChecked():
            currents = self._do_stuff_to_get_currents()
            text = f'\U0001D43C\u2081 = {currents[0]:7.4f} A\n' + \
                f'\U0001D43C\u2082 = {currents[1]:7.4f} A\n' + \
                f'\U0001D43C\u2083 = {currents[2]:7.4f} A'
            self.label_currents.setText(text)
        else:
            self.label_currents.setText('\n\n')

    def _do_stuff_to_enable_field(self, magnitude, theta, phi):
        print(f'do stuff to enable field with ({magnitude} mT, {theta}°, {phi}°)')

        # use self.msg_magnet.setText() to output any error messages

        # # get magnetic field in Carthesian coordinates
        # B_fieldVector = computeMagneticFieldVector(magnitude, theta, phi)
        # currents = computeCoilCurrents(B_fieldVector)

        # # demagnetizeCoils(*self.channels, [5,5,5])
        # setCurrents(*self.channels, desCurrents = currents)

    def _do_stuff_to_disable_field(self):
        print('do stuff to disable field')
        # use self.msg_magnet.setText() to output any error messages

        # disableCurrents(*self.channels)

    def _do_stuff_to_get_currents(self):
        print('read current values')
        # currents = getMeasurement(*self.channels, meas_quantity='current')
        currents = np.zeros(3)
        return currents


if __name__ == '__main__':

    app = QApplication(sys.argv)

    with VectorMagnetDialog(parent=None) as dialog:
        dialog.show()

        sys.exit(app.exec_())
# %%
