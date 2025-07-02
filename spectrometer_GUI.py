# -*- coding: utf-8 -*-
"""
Created on Mon June 30, 2025

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland
"""

from datetime import datetime
import numpy as np
from pyqtgraph.Qt import QtCore, QtGui
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from shamrock_base import Shamrock
import time as tm

DEVICE = 0
GRATING_300_LINES = 1
GRATING_500_LINES = 2
GRATING_MIRROR = 3

nameGrating = ['300 lines/mm', '500 lines/mm', 'Mirror']
# Camera Andor Newton DU920P-BEX2-DD
NumberofPixel = 1024
PixelWidth = 26 # um

class Frontend(QtGui.QFrame):

    gratingFrontendSignal = pyqtSignal(str)
    zeroorderSignal = pyqtSignal()
    wavelengthSignal = pyqtSignal(float)
    shutterSignal = pyqtSignal(int)
    closeSignal = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # set the title of the window
        title = "Spectrometer module"
        self.setWindowTitle(title)
        self.setUpGUI()
        return

    def setUpGUI(self):
        #Spectrometer Kymera        
        grating_Label = QtGui.QLabel('Grating:')
        self.grating = QtGui.QComboBox()
        self.grating.addItems(nameGrating)
        self.grating.setCurrentIndex(0)
        self.grating.setFixedWidth(150)
        
        self.set_configuration_button = QtGui.QPushButton('Set configuration')
        self.set_configuration_button.clicked.connect(self.spectrum_configuration)
        self.set_configuration_button.setStyleSheet(
            "QPushButton:pressed { background-color: lightcoral; }")

        self.zero_order_button = QtGui.QPushButton('Go to zero order')
        self.zero_order_button.clicked.connect(self.zero_order_check)
        self.zero_order_button.setStyleSheet(
            "QPushButton:pressed { background-color: cornflowerblue; }")

        self.shutter_button = QtGui.QPushButton('Shutter CLOSED')
        self.shutter_button.clicked.connect(self.shutter_action)
        self.shutter_button.setCheckable(True)
        self.shutter_button.setStyleSheet(
            "QPushButton:pressed { background-color: lightcoral; }")

        lambda_Label = QtGui.QLabel('Center λ (nm):')
        self.lambda_Edit = QtGui.QLineEdit('0.0')
        self.lambda_Edit.setValidator(QtGui.QDoubleValidator(0.0, 3000.0, 1))

        self.set_wavelength_button = QtGui.QPushButton('Set Wavelength')
        self.set_wavelength_button.clicked.connect(self.spectrum_set_wavelength)
        self.set_wavelength_button.setStyleSheet(
            "QPushButton:pressed { background-color: lightcoral; }")
        self.set_wavelength_button.setFixedWidth(150)
                  
        self.spectrum = QtGui.QWidget()
        spectrum_parameters_layout = QtGui.QGridLayout()
        self.spectrum.setLayout(spectrum_parameters_layout)
        
        spectrum_parameters_layout.addWidget(grating_Label,                     0, 0)
        spectrum_parameters_layout.addWidget(self.grating,                      0, 1)
        spectrum_parameters_layout.addWidget(self.set_configuration_button,     1, 0, 1, 2)
        spectrum_parameters_layout.addWidget(lambda_Label,                      2, 0)
        spectrum_parameters_layout.addWidget(self.lambda_Edit,                  2, 1)
        spectrum_parameters_layout.addWidget(self.set_wavelength_button,        3, 0)
        spectrum_parameters_layout.addWidget(self.zero_order_button,            3, 1)
        spectrum_parameters_layout.addWidget(self.shutter_button,               4, 0, 1, 2)

        # GUI layout
        grid = QtGui.QGridLayout()
        self.setLayout(grid)
        grid.addWidget(self.spectrum)
        return

    def spectrum_configuration(self):
        grating = str(self.grating.currentText())       
        self.gratingFrontendSignal.emit(grating) 
        return
        
    def spectrum_set_wavelength(self):
        wavelength = float(self.lambda_Edit.text())
        self.wavelengthSignal.emit(wavelength)
        return

    def zero_order_check(self):
        self.zeroorderSignal.emit()
        return

    def shutter_action(self):
        if self.shutter_button.isChecked():
            self.shutter_button.setText('Shutter OPEN')
            self.shutterSignal.emit(1)
        else:
            self.shutter_button.setText('Shutter CLOSED')
            self.shutterSignal.emit(0)
        return

    # re-define the closeEvent to execute an specific command
    def closeEvent(self, event, *args, **kwargs):
        super(QtGui.QFrame, self).closeEvent(event, *args, **kwargs)
        # dialog box
        reply = QtGui.QMessageBox.question(self, 'Exit', 'Are you sure you want to exit the program?',
                                           QtGui.QMessageBox.No |
                                           QtGui.QMessageBox.Yes)
        if reply == QtGui.QMessageBox.Yes:
            event.accept()
            # self.displayDataTimer.stop()
            print('Closing GUI...')
            self.close()
            self.closeSignal.emit()
            tm.sleep(1) # needed to close properly all modules
            app.quit()
        else:
            event.ignore()
            print('Back in business...')    
        return

class Backend(QtCore.QObject):
    
    gratingBackendSignal = pyqtSignal(str)
    
    def __init__(self, mySpectrometer, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mySpectrometer = mySpectrometer
        mySpectrometer.ShamrockSetNumberPixels(DEVICE, NumberofPixel)
        mySpectrometer.ShamrockSetPixelWidth(DEVICE, PixelWidth)
        mySpectrometer.ShamrockSetGrating(DEVICE, GRATING_300_LINES)
        self.grating = GRATING_300_LINES
        self.shutter_state = 0 # 0 = False, 1 = True
        self.wavelength = 0.0
        return
        
    @pyqtSlot(str)
    def set_configuration(self, grating):
        print('Changing grating...')
        if grating == nameGrating[0]:
           ret = self.mySpectrometer.ShamrockSetGrating(DEVICE, GRATING_300_LINES)
           self.grating = GRATING_300_LINES
           print(datetime.now(), '[Kymera] Mode Grating = ', nameGrating[0], ', Code', ret)
           self.gratingBackendSignal.emit(nameGrating[0])  #to StepandGlue set_wavelength_window
        elif grating == nameGrating[1]:
           ret = self.mySpectrometer.ShamrockSetGrating(DEVICE, GRATING_500_LINES)
           self.grating = GRATING_500_LINES
           self.gratingBackendSignal.emit(nameGrating[1]) #to StepandGlue set_wavelength_window
           print(datetime.now(), '[Kymera] Mode Grating = ', nameGrating[1], ', Code', ret)
        else:
           ret = self.mySpectrometer.ShamrockSetGrating(DEVICE, GRATING_MIRROR)
           self.grating = GRATING_MIRROR
           print(datetime.now(), '[Kymera] Mode Grating = ', nameGrating[2], ', Code', ret)

        (ret, Lines, Blaze, Home, Offset) = self.mySpectrometer.ShamrockGetGratingInfo(DEVICE, self.grating)
        print('Current grating information: ', Lines, 'lines/mm', Blaze.decode('UTF-8'), Home, Offset)
        return

    @pyqtSlot()
    def goto_zeroorder(self):
        print('Setting zero order...')
        self.mySpectrometer.ShamrockGotoZeroOrder(DEVICE)
        print(datetime.now(), '[Kymera] Wavelength = ', self.mySpectrometer.ShamrockGetWavelength(DEVICE))
        return

    @pyqtSlot(float)
    def set_wavelength(self, wavelength):
        print('Changing wavelength...')
        self.mySpectrometer.ShamrockSetWavelength(DEVICE, wavelength)
        print(datetime.now(), '[Kymera] Wavelength = ', self.mySpectrometer.ShamrockGetWavelength(DEVICE))
        ret, calibration = self.mySpectrometer.ShamrockGetCalibration(DEVICE, NumberofPixel)
        cal = np.array(list(calibration))
        print(datetime.now(), '[Kymera] Calibration wavelength array = ', cal)
        print(datetime.now(), '[Kymera] Calibration wavelength window range = [ %.1f, %.1f ]' % (cal[0], cal[-1]))
        ret, self.wavelength = self.mySpectrometer.ShamrockGetWavelength(DEVICE, wavelength)
        return cal 

    @pyqtSlot(int)
    def set_shutter_state(self, shutter_state):
        # is shutter present?
        # ret = self.mySpectrometer.ShamrockShutterIsPresent(DEVICE)
        # print(ret)
        ret = self.mySpectrometer.ShamrockSetShutter(DEVICE, shutter_state)
        print(datetime.now(), '[Kymera] Shutter action = ', ret)
        (ret, state) = self.mySpectrometer.ShamrockGetShutter(DEVICE)
        print(datetime.now(), '[Kymera] Shutter state = ', state)
        self.shutter_state = state
        return

    @pyqtSlot()    
    def close(self):
        print('Closing spectrometer...')
        self.mySpectrometer.ShamrockClose()
        print(datetime.now(), '[Kymera] Close')
        print('Exiting thread...')
        spectrumThread.exit()
        return     

    def make_connection(self, frontend): 
        frontend.gratingFrontendSignal.connect(self.set_configuration)
        frontend.zeroorderSignal.connect(self.goto_zeroorder) 
        frontend.wavelengthSignal.connect(self.set_wavelength)
        frontend.shutterSignal.connect(self.set_shutter_state)
        frontend.closeSignal.connect(self.close)
        return

if __name__ == '__main__':

    app = QtGui.QApplication([])

    print('\nSpectrometer initialization...')

    mySpectrometer = Shamrock()
    inipath = 'C:\\Program Files\\Andor SOLIS\\SPECTROG.ini'
    mySpectrometer.ShamrockInitialize(inipath)
    ret, serial_number = mySpectrometer.ShamrockGetSerialNumber(DEVICE)
    print(datetime.now(), '[Kymera] Serial number: {}'.format(serial_number.decode('UTF-8')))

    gui = Frontend()
    worker = Backend(mySpectrometer)

    worker.make_connection(gui)
    # gui.make_connection(worker)

    spectrumThread = QtCore.QThread()
    worker.moveToThread(spectrumThread)
    spectrumThread.start()

    gui.show()
    app.exec()

    