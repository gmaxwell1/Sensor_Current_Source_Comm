# filename: field_current_tr.py
#
# The following helper functions provide the calculation of magnetic fields and associated currents,
# using a cubic model for the relation between the current and magnetic field (and vice versa).
#
# Author: Maxwell Guerne-Kieferndorf (QZabre)
#            gmaxwell at student.ethz.ch
#
# Date: 09.10.2020
# latest update: 06.01.2021

########## Standard library imports ##########
import math
import pickle

import joblib
import numpy as np
import pandas as pd
from sklearn import linear_model
from sklearn.preprocessing import PolynomialFeatures

# Lookup table for current/magnetic field values
# LookupTable = {}
# filepathLUT = r'data_sets\linearization_matrices\20_11_16_180159-86LUT.csv'
# def buildLUT(path=filepathLUT):
#     global LookupTable

#     dataLUT = pd.read_csv(path).to_numpy()
#     directionsB = dataLUT[:,0:3]
#     currentConfigs = dataLUT[:,3:6]

#     for i in range(len(directionsB)):
#         unit = np.around(directionsB[i]/20, 3)
#         unitCurrents = np.around(currentConfigs[i]/20, 3)

#         LookupTable[f'direction {i+1}'] = (unit.tolist(), unitCurrents.tolist())


def read_fitting_parameters(filepath):
    """Extract fitting paramters A from file."""
    # extract data and convert to ndarray
    A = pd.read_csv(filepath).to_numpy().T

    return A


def evaluate_fit(A, xdata):
    """
    Given the paramters A, estimate the outputs for the provided xdata.

    Args:
        A (ndarray of shape (k,3)): fitting paramters for the three components individually.
                                    The size k of the first dimension depends on the fitting degree.
                                    Currently implemented are k=3,9,19 only.
        xdata (ndarray of shape (N,3)): Input data for which the corresponding output data should be computed.

    Returns:
        ndarray of shape (N,3): Estimated outputs based on the inputs and fitting paramters
    """
    # initialize array for fits
    fits = np.zeros_like(xdata)

    # linear fit
    if A.shape[1] == 3:
        for i in range(len(xdata)):
            fits[i] = A @ xdata[i]

    elif A.shape[1] == 9:
        # estimate expected fields based on fits

        for i in range(len(xdata)):
            # linear part
            fits[i] = A[:, :3] @ xdata[i]

            # quadratic part
            fits_quadratic = np.zeros(3)
            for component in range(3):
                A_tri = np.zeros((3, 3))
                A_tri[np.triu_indices(3)] = A[component, 3:]
                fits_quadratic[component] = xdata[i].reshape(1, 3) @ A_tri @ xdata[i].reshape(3, 1)

            fits[i] += fits_quadratic

    # cubic fit including cross terms
    elif A.shape[1] == 19:
        for i in range(len(xdata)):
            # linear part
            fits[i] = A[:, :3] @ xdata[i]

            # quadratic part
            fits_quadratic = np.zeros(3)
            for component in range(3):
                A_tri = np.zeros((3, 3))
                A_tri[np.triu_indices(3)] = A[component, 3:9]
                fits_quadratic[component] = xdata[i].reshape(1, 3) @ A_tri @ xdata[i].reshape(3, 1)
            fits[i] += fits_quadratic

            # cubic part
            combis = np.array([[0, 0, 0], [0, 0, 1], [0, 0, 2], [0, 1, 1], [0, 1, 2],
                               [0, 2, 2], [1, 1, 1], [1, 1, 2], [1, 2, 2], [2, 2, 2]])
            fits_cubic = np.zeros(3)
            for component in range(3):
                for k in range(10):
                    fits_cubic[component] += A[component, k + 9] * xdata[i, combis[k, 0]] * \
                        xdata[i, combis[k, 1]] *   \
                        xdata[i, combis[k, 2]]
            fits[i] += fits_cubic

    return fits


def computeMagneticFieldVector(magnitude: float, theta: float, phi: float):
    """
    Compute the cartesian coordinates of a magnetic field with an arbitrary direction
    and an arbitrary magnitude, given the spherical coordinates.

    Args:
        magnitude: of the B-field, units: [mT]
        theta: polar angle, between desired field direction and z axis
        phi: azimuthal angle (angle measured counter clockwise from the x axis)

    Returns:
        Vector of 3 B field components (Bx,By,Bz), as a np.array, units: [mT]
    """

    x = math.sin(math.radians(theta)) * math.cos(math.radians(phi))
    y = math.sin(math.radians(theta)) * math.sin(math.radians(phi))
    z = math.cos(math.radians(theta))

    unitVector = np.array((x, y, z))
    unitVector = unitVector / np.linalg.norm(unitVector)

    return np.around(unitVector * magnitude, 3)


def computeCoilCurrents(B_fieldVector):
    """
    Compute coil currents (in mA) required to generate the desired magnetic field vector.
    Actuation matrix derived from simulations so far

    Args:
        B_fieldVector: np.array containing the B-field, in cartesian coordinates, magnitude units: [mT]

    Returns:
        Vector of 3 current values, as a np.array, units: [A]
    """
    filename = r'fitting_parameters\model_poly3_final_B2I.sav'
    # load the model from disk
    [loaded_model, loaded_poly] = pickle.load(open(filename, 'rb'))
    # preprocess test vectors, st. they have correct shape for model
    B_fieldVector_reshape = B_fieldVector.reshape((1, 3))
    test_vectors_ = loaded_poly.fit_transform(B_fieldVector_reshape)
    # estimate prediction
    currVector = loaded_model.predict(test_vectors_)
    currVector = currVector.reshape(3)  # in amps
    currVector = np.round(currVector, 3)  # round to nearest milliamp

    return currVector


def computeMagField(currVector):
    """
    Compute magnetic field vector generated by the currents. Uses cubic regression model.

    Args:
        currVector: Vector of 3 current values, as a np.array, units: [A]

    Returns:
        Vector of 3 B field components (Bx,By,Bz), as a np.array, units: [mT]
    """
    filename = r'fitting_parameters\model_poly3_final_I2B.sav'

    # load the model from disk
    [loaded_model, loaded_poly] = pickle.load(open(filename, 'rb'))
    # preprocess test vectors, st. they have correct shape for model
    currVector = currVector  # in amps
    currVector_reshape = currVector.reshape((1, 3))
    test_vectors_ = loaded_poly.fit_transform(currVector_reshape)
    # estimate prediction
    B_fieldVector = loaded_model.predict(test_vectors_)

    return np.round(B_fieldVector.reshape(3), 3)


def rotationMatrix(inVector=np.array([1, 0, 0]),
                   theta: float = 90, psi: float = 0, alpha: float = 10.1):
    """
    Rotate a vector around any axis (defined by angles psi and theta), rotation around axis given by alpha

    Args:
        inVector: arbitrary cartesian R^3 vector
        psi: azimuthal angle, in degrees
        theta: polar angle (measured downward from z axis), in degrees
        alpha: counterclockwise rotation amount around the specified axis, in degrees

    Returns:
        Vector of 3 B field components (Bx,By,Bz), as a np.array, units: [mT]
    """

    a_x = math.sin(math.radians(theta)) * math.cos(math.radians(psi))
    a_y = math.sin(math.radians(theta)) * math.sin(math.radians(psi))
    a_z = math.cos(math.radians(theta))

    axis = np.array([a_x, a_y, a_z])
    #a_unit = a_unit / np.linalg.norm(a_unit)

    #print('Axis of rotation (Cartesian) : \n ', a_unit)

    rot_matrix = np.zeros((3, 3))
    rot_matrix[0, 0] = math.cos(math.radians(
        alpha)) + ((axis[0] ** 2) * (1 - math.cos(math.radians(alpha))))
    rot_matrix[1, 0] = axis[1] * axis[0] * \
        (1 - math.cos(math.radians(alpha))) + \
        a_z * math.sin(math.radians(alpha))
    rot_matrix[2, 0] = axis[2] * axis[0] * (1 - math.cos(math.radians(alpha))) - axis[1] * math.sin(
        math.radians(alpha))

    rot_matrix[0, 1] = axis[0] * axis[1] * \
        (1 - math.cos(math.radians(alpha))) - \
        a_z * math.sin(math.radians(alpha))
    rot_matrix[1, 1] = math.cos(math.radians(
        alpha)) + ((axis[1] ** 2) * (1 - math.cos(math.radians(alpha))))
    rot_matrix[2, 1] = axis[2] * axis[1] * (1 - math.cos(math.radians(alpha))) + axis[0] * math.sin(
        math.radians(alpha))

    rot_matrix[0, 2] = axis[0] * axis[2] * (1 - math.cos(math.radians(alpha))) + axis[1] * math.sin(
        math.radians(alpha))
    rot_matrix[1, 2] = axis[1] * axis[2] * (1 - math.cos(math.radians(alpha))) - axis[0] * math.sin(
        math.radians(alpha))
    rot_matrix[2, 2] = math.cos(math.radians(
        alpha)) + ((axis[2] ** 2) * (1 - math.cos(math.radians(alpha))))

    #print('Rotation Matrix:')
    #print('\t{}\t{}\t{}'.format(rot_matrix[0,0], rot_matrix[1,0], rot_matrix[2,0]))
    #print('\t{}\t{}\t{}'.format(rot_matrix[0,1], rot_matrix[1,1], rot_matrix[2,1]))
    #print('\t{}\t{}\t{}'.format(rot_matrix[0,2], rot_matrix[1,2], rot_matrix[2,2]))
    # self.magnetic_field_unit = rot_matrix.dot(self.magnetic_field_unit)
    return np.around(rot_matrix.dot(inVector), 3)


if __name__ == '__main__':
    # ------------------------Testing area--------------------------
    #
    # test the transformation functions
    # buildLUT()
    # print('Lookup table:')
    # for key in LookupTable:
    #     print(f'{key} = {LookupTable[key]}')
    # B1 = computeMagneticFieldVector(theta=0, phi=0, magnitude=50)
    B1 = np.array([13, 22, 69])
    print(f'Bx = {B1[0]}mT, By = {B1[1]}mT, Bz = {B1[2]}mT')
    currents = computeCoilCurrents(B1)
    print(f'I1 = {currents[0]}A, I2 = {currents[1]}A, I3 = {currents[2]}A')
    B2 = computeMagField(currents)
    print(f'Bx = {B2[0]:.3f}mT, By = {B2[1]:.3f}mT, By = {B2[2]:.3f}mT')
