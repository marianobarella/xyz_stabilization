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
from pyqtgraph.dockarea import Dock, DockArea
import pyqtgraph as pg
from shamrock_base import Shamrock
from tkinter import filedialog
import tkinter as tk
import time as tm
import os
import pylablib
pylablib.par["devices/dlls/andor_sdk2"] = "C:\\Program Files\\Andor SOLIS"
from pylablib.devices import Andor

# Spectrometer
DEVICE = 0
GRATING_300_LINES = 1
GRATING_500_LINES = 2
GRATING_MIRROR = 3
nameGrating = ['300 lines/mm', '500 lines/mm', 'Mirror']

# Camera Andor Newton DU920P-BEX2-DD
NumberofPixel = 1024
PixelWidth = 26 # um
acqModeList = ['Full Vertical Binning', 'Image']
initial_exp_time = 100 # in ms
initial_cam_temp_tickbox_state = False
tempTimer_update = 30000 # in ms

# other inputs
# initial filepath and filename
initial_filepath = 'D:\\daily_data\\spectra' # save in SSD for fast and daily use
initial_filename = 'spectrum'

######################################################################################
######################################################################################
######################################################################################

class Frontend(QtGui.QFrame):

    gratingFrontendSignal = pyqtSignal(str)
    zeroorderSignal = pyqtSignal()
    wavelengthSignal = pyqtSignal(float)
    shutterSignal = pyqtSignal(int)
    imageModeFrontendSignal = pyqtSignal(str)
    exposureChangedSignal = pyqtSignal(bool, float)
    liveSpecViewSignal = pyqtSignal(bool, float)
    takeSpectrumSignal = pyqtSignal(bool, float)
    filenameSignal = pyqtSignal(str)
    setWorkDirSignal = pyqtSignal()
    saveSpecContSignal = pyqtSignal(bool)
    saveSignal = pyqtSignal()
    closeSignal = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # set the title of the window
        title = "Spectrometer module"
        self.setWindowTitle(title)
        self.setUpGUI()
        self.camera_temp = 0.00
        self.spectrum_array = np.array([])
        self.set_working_dir()
        self.set_filename()
        return

    def setUpGUI(self):
        #Spectrometer Kymera        
        grating_label = QtGui.QLabel('Grating:')
        self.grating = QtGui.QComboBox()
        self.grating.addItems(nameGrating)
        self.grating.setCurrentIndex(0)
        self.grating.setFixedWidth(150)
        
        self.set_configuration_spectrometer_button = QtGui.QPushButton('Set configuration')
        self.set_configuration_spectrometer_button.clicked.connect(self.spectrum_configuration)
        self.set_configuration_spectrometer_button.setStyleSheet(
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

        lambda_label = QtGui.QLabel('Center λ (nm):')
        self.lambda_Edit = QtGui.QLineEdit('0.0')
        self.lambda_Edit.setValidator(QtGui.QDoubleValidator(0.0, 3000.0, 1))

        self.set_wavelength_button = QtGui.QPushButton('Set Wavelength')
        self.set_wavelength_button.clicked.connect(self.spectrum_set_wavelength)
        self.set_wavelength_button.setStyleSheet(
            "QPushButton:pressed { background-color: lightcoral; }")
        self.set_wavelength_button.setFixedWidth(150)
        
        # Camera widget parameters
        acq_mode_label = QtGui.QLabel('Acquisition mode:')
        self.acq_mode = QtGui.QComboBox()
        self.acq_mode.addItems(acqModeList)
        self.acq_mode.setCurrentIndex(0)
        self.acq_mode.setFixedWidth(150)

        self.set_configuration_camera_button = QtGui.QPushButton('Set configuration')
        self.set_configuration_camera_button.clicked.connect(self.camera_configuration)
        self.set_configuration_camera_button.setStyleSheet(
            "QPushButton:pressed { background-color: lightcoral; }")

        self.sensor_temp_label = QtGui.QLabel('Sensor temperature: ----- °C')

        # Exposure time
        exp_time_label = QtGui.QLabel('Exposure time (ms):')
        self.exp_time_edit = QtGui.QLineEdit(str(initial_exp_time))
        self.exp_time_edit.editingFinished.connect(self.exposure_changed_check)
        self.exp_time_edit.setValidator(QtGui.QDoubleValidator(0.001, 600000.000, 3))
        self.exp_time_edit.setToolTip('Minimum is 1 ms. Maximum is 600 s = 10 min.')
        
        self.live_spec_button = QtGui.QPushButton('Live spectra view')
        self.live_spec_button.setCheckable(True)
        self.live_spec_button.clicked.connect(self.live_spec_view_button_check)
        self.live_spec_button.setStyleSheet(
            "QPushButton:pressed { background-color: light-red; }"
            "QPushButton::checked { background-color: red; }")

        # Buttons and labels
        self.take_spectrum_button = QtGui.QPushButton('Take a spectrum')
        self.take_spectrum_button.setCheckable(False)
        self.take_spectrum_button.clicked.connect(self.take_spectrum_button_check)
        self.take_spectrum_button.setStyleSheet(
            "QPushButton:pressed { background-color: red; }")

        # Widget for the spectrum data
        self.plotWidget = pg.GraphicsLayoutWidget()
        self.spectrum_plot = self.plotWidget.addPlot(row = 1, col = 1, title = 'Spectrum signal')
        self.spectrum_plot.enableAutoRange(True, True)
        self.spectrum_plot.showGrid(x = True, y = True)
        self.spectrum_plot.setLabel('left', 'Integrated counts')
        self.spectrum_plot.setLabel('bottom', 'Wavelength (nm)')

        # Working folder
        self.working_dir_button = QtGui.QPushButton('Select directory')
        self.working_dir_button.clicked.connect(self.set_working_dir)
        self.working_dir_button.setStyleSheet(
            "QPushButton:pressed { background-color: palegreen; }")
        self.working_dir_label = QtGui.QLabel('Working directory')
        self.filepath = initial_filepath
        self.working_dir_path = QtGui.QLineEdit(self.filepath)
        self.working_dir_path.setFixedWidth(300)
        self.working_dir_path.setReadOnly(True)
        self.filename_label = QtGui.QLabel('Filename (.npy)')
        self.filename = initial_filename
        self.filename_name = QtGui.QLineEdit(self.filename)
        self.filename_name.setFixedWidth(300)
        self.filename_name.editingFinished.connect(self.set_filename)

        # Save data button
        self.saveButton = QtGui.QPushButton('Save last spectrum')
        self.saveButton.clicked.connect(self.save_spectrum)
        self.saveButton.setStyleSheet(
            "QPushButton:pressed { background-color: cornflowerblue; }")
        
        # Save continuously tick box
        self.saveAutomaticallyBox = QtGui.QCheckBox('Save automatically?')
        self.saveAutomaticallyBox.setChecked(False)
        self.saveAutomaticallyBox.stateChanged.connect(self.set_save_continuously)
        self.saveAutomaticallyBox.setToolTip('Set/Tick to save data continuously. Filenames will be sequential.')

        # Widget layout
        self.spectrumWidget = QtGui.QWidget()
        spectrum_parameters_layout = QtGui.QGridLayout()
        self.spectrumWidget.setLayout(spectrum_parameters_layout)
        spectrum_parameters_layout.addWidget(grating_label,                     0, 0)
        spectrum_parameters_layout.addWidget(self.grating,                      0, 1)
        spectrum_parameters_layout.addWidget(self.set_configuration_spectrometer_button,     1, 0, 1, 2)
        spectrum_parameters_layout.addWidget(lambda_label,                      2, 0)
        spectrum_parameters_layout.addWidget(self.lambda_Edit,                  2, 1)
        spectrum_parameters_layout.addWidget(self.set_wavelength_button,        3, 0)
        spectrum_parameters_layout.addWidget(self.zero_order_button,            3, 1)
        spectrum_parameters_layout.addWidget(self.shutter_button,               4, 0, 1, 2)

        self.camWidget = QtGui.QWidget()
        camera_parameters_layout = QtGui.QGridLayout()
        self.camWidget.setLayout(camera_parameters_layout)
        camera_parameters_layout.addWidget(acq_mode_label,                    0, 0)
        camera_parameters_layout.addWidget(self.acq_mode,                     0, 1)
        camera_parameters_layout.addWidget(self.set_configuration_camera_button,1, 0, 1, 2)
        camera_parameters_layout.addWidget(self.sensor_temp_label,            2, 0)
        camera_parameters_layout.addWidget(exp_time_label,                    3, 0)
        camera_parameters_layout.addWidget(self.exp_time_edit,                3, 1)
        camera_parameters_layout.addWidget(self.live_spec_button,             4, 0, 1, 2)
        camera_parameters_layout.addWidget(self.take_spectrum_button,         4, 2, 1, 2)
        camera_parameters_layout.addWidget(self.saveButton,                   5, 0)
        camera_parameters_layout.addWidget(self.saveAutomaticallyBox,         5, 1)
        camera_parameters_layout.addWidget(self.working_dir_label,            6, 0)
        camera_parameters_layout.addWidget(self.working_dir_path,             6, 1, 1, 2)
        camera_parameters_layout.addWidget(self.working_dir_button,           6, 2)
        camera_parameters_layout.addWidget(self.filename_label,               7, 0)
        camera_parameters_layout.addWidget(self.filename_name,                7, 1, 1, 2)

        # Place layouts and boxes
        dockArea = DockArea()
        hbox = QtGui.QHBoxLayout(self)

        spectrometerDock = Dock('Spectrometer parameters')
        spectrometerDock.addWidget(self.spectrumWidget)
        dockArea.addDock(spectrometerDock)

        camDock = Dock('Camera parameters')
        camDock.addWidget(self.camWidget)
        dockArea.addDock(camDock, 'right', spectrometerDock)
        
        plotDock = Dock('Spectrum')
        plotDock.addWidget(self.plotWidget)
        dockArea.addDock(plotDock, 'bottom')

        hbox.addWidget(dockArea)
        self.setLayout(hbox)
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

    def camera_configuration(self):
        acq_mode = str(self.acq_mode.currentText())
        self.imageModeFrontendSignal.emit(acq_mode) 
        return

    def exposure_changed_check(self):
        exposure_time_ms = float(self.exp_time_edit.text()) # in ms
        if self.live_spec_button.isChecked():
            self.exposureChangedSignal.emit(True, exposure_time_ms)
        else:
            self.exposureChangedSignal.emit(False, exposure_time_ms)
        return

    def live_spec_view_button_check(self):
        exposure_time_ms = float(self.exp_time_edit.text()) # in ms
        if self.live_spec_button.isChecked():
            self.liveSpecViewSignal.emit(True, exposure_time_ms)
        else:
            self.liveSpecViewSignal.emit(False, exposure_time_ms)
        return

    def take_spectrum_button_check(self):
        exposure_time_ms = float(self.exp_time_edit.text()) # in ms
        if self.live_spec_button.isChecked():
            self.takeSpectrumSignal.emit(True, exposure_time_ms)
        else:
            self.takeSpectrumSignal.emit(False, exposure_time_ms)            
        return

    @pyqtSlot(np.ndarray)
    def get_spectrum(self, spectrum_array):   
        # Add plot
        self.spectrum_plot.clear()
        self.spectrum_plot.plot(self.wavelength_array, spectrum_array)
        return

    @pyqtSlot(np.ndarray)
    def get_wavelength_calibration(self, wavelength_array):
        self.wavelength_array = wavelength_array
        self.spectrum_plot.setXRange(wavelength_array[0], wavelength_array[-1])
        return

    @pyqtSlot(float)
    def get_temperature(self, sensor_temp):   
        self.sensor_temp_label.setText('Sensor temperature: %.1f °C' % sensor_temp)
        return

    def set_filename(self):
        filename = self.filename_name.text()
        if filename != self.filename:
            self.filename = filename
            self.filenameSignal.emit(self.filename)    
        return

    def set_working_dir(self):
        self.setWorkDirSignal.emit()
        return

    def set_save_continuously(self):
        if self.saveAutomaticallyBox.isChecked():
            self.saveSpecContSignal.emit(True)
        else:
            self.saveSpecContSignal.emit(False) 
        return

    def save_spectrum(self):
        if self.saveButton.isChecked:
            self.saveSignal.emit()
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

    def make_connection(self, backend):
        backend.spectrumSignal.connect(self.get_spectrum)
        backend.wavelengthCalibrationSignal.connect(self.get_wavelength_calibration)
        backend.sensorTempSignal.connect(self.get_temperature)
        return

######################################################################################
######################################################################################
######################################################################################

class Backend(QtCore.QObject):
    
    gratingBackendSignal = pyqtSignal(str)
    spectrumSignal = pyqtSignal(np.ndarray)
    sensorTempSignal = pyqtSignal(float)
    wavelengthCalibrationSignal = pyqtSignal(np.ndarray)

    def __init__(self, mySpectrometer, myCamera, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.myCamera = myCamera
        self.mySpectrometer = mySpectrometer
        self.mySpectrometer.ShamrockSetNumberPixels(DEVICE, NumberofPixel)
        self.mySpectrometer.ShamrockSetPixelWidth(DEVICE, PixelWidth)
        self.mySpectrometer.ShamrockSetGrating(DEVICE, GRATING_300_LINES)
        self.grating = GRATING_300_LINES
        self.shutter_state = 0 # 0 = False, 1 = True
        self.wavelength = 0.0
        self.viewSpecTimer = QtCore.QTimer()
        self.tempTimer = QtCore.QTimer()
        self.spectrum = np.array([])
        self.temperature = -80 # in celcius
        self.start_camera()
        self.save_automatically_bool = False
        self.filepath = initial_filepath
        self.filename = initial_filename
        return
        
    def start_camera(self):
        print('Is camera opened?', self.myCamera.is_opened())
        self.myCamera.set_read_mode('fvb')
        fan_mode = 'full' # Options are 'full', 'low' or 'off'
        self.myCamera.set_fan_mode(fan_mode)
        self.myCamera.set_cooler(on = True)
        # temperature range is -120 °C to -10 °C
        self.myCamera.set_temperature(self.temperature, enable_cooler = True)
        print('Camera cooler is ON?',self.myCamera.is_cooler_on())
        self.camera_temp_timer()
        print('Camera status:', self.myCamera.get_status())
        return

    @pyqtSlot(str)
    def set_configuration(self, grating):
        print('Changing grating...')
        if grating == nameGrating[0]:
           ret = self.mySpectrometer.ShamrockSetGrating(DEVICE, GRATING_300_LINES)
           self.grating = GRATING_300_LINES
           print(datetime.now(), '[Kymera] Mode Grating =', nameGrating[0], ', Code', ret)
           self.gratingBackendSignal.emit(nameGrating[0])  #to StepandGlue set_wavelength_window
        elif grating == nameGrating[1]:
           ret = self.mySpectrometer.ShamrockSetGrating(DEVICE, GRATING_500_LINES)
           self.grating = GRATING_500_LINES
           self.gratingBackendSignal.emit(nameGrating[1]) #to StepandGlue set_wavelength_window
           print(datetime.now(), '[Kymera] Mode Grating =', nameGrating[1], ', Code', ret)
        else:
           ret = self.mySpectrometer.ShamrockSetGrating(DEVICE, GRATING_MIRROR)
           self.grating = GRATING_MIRROR
           print(datetime.now(), '[Kymera] Mode Grating =', nameGrating[2], ', Code', ret)

        (ret, Lines, Blaze, Home, Offset) = self.mySpectrometer.ShamrockGetGratingInfo(DEVICE, self.grating)
        print('Current grating information: ', Lines, 'lines/mm', Blaze.decode('UTF-8'), Home, Offset)
        return

    @pyqtSlot()
    def goto_zeroorder(self):
        print('Setting zero order...')
        self.mySpectrometer.ShamrockGotoZeroOrder(DEVICE)
        print(datetime.now(), '[Kymera] Wavelength =', self.mySpectrometer.ShamrockGetWavelength(DEVICE))
        return

    @pyqtSlot(float)
    def set_wavelength(self, wavelength):
        print('Changing wavelength...')
        self.mySpectrometer.ShamrockSetWavelength(DEVICE, wavelength)
        print(datetime.now(), '[Kymera] Wavelength = ', self.mySpectrometer.ShamrockGetWavelength(DEVICE))
        ret, calibration = self.mySpectrometer.ShamrockGetCalibration(DEVICE, NumberofPixel)
        self.wavelength_calibration = np.array(list(calibration))
        self.wavelengthCalibrationSignal.emit(self.wavelength_calibration)
        # print(datetime.now(), '[Kymera] Calibration wavelength array =', self.wavelength_calibration)
        print(datetime.now(), '[Kymera] Calibration wavelength window range = [ %.1f, %.1f ]' % (self.wavelength_calibration [0], self.wavelength_calibration [-1]))
        ret, wavelength_retrieved = self.mySpectrometer.ShamrockGetWavelength(DEVICE)
        print(datetime.now(), '[Kymera] Central wavelength = ', wavelength_retrieved)
        return

    @pyqtSlot(int)
    def set_shutter_state(self, shutter_state):
        # is shutter present?
        # ret = self.mySpectrometer.ShamrockShutterIsPresent(DEVICE)
        # print(ret)
        ret = self.mySpectrometer.ShamrockSetShutter(DEVICE, shutter_state)
        (ret, state) = self.mySpectrometer.ShamrockGetShutter(DEVICE)
        if state == 0:
            self.shutter_state = 'close'
        elif state == 1:
            self.shutter_state = 'open'
        else:
            self.shutter_state = 'error'
        print(datetime.now(), '[Kymera] Shutter action =', ret, ', Shutter state =', self.shutter_state)
        return  

    @pyqtSlot(bool, float)
    def set_exposure_time(self, live_spec_bool, exposure_time_ms):
        if live_spec_bool:
            self.stop_live_spec_view()
        self.exposure_time = exposure_time_ms/1000 # in ms, is float
        print('Setting exposure time to %.6f s' % self.exposure_time)
        self.myCamera.set_exposure(self.exposure_time)
        exp_time, self.frame_time = self.myCamera.get_frame_timings() # output in seconds
        self.frame_time_ms = self.frame_time*1000
        print('Exposure time set to %.3f ms. Frame time: %.3f ms' % (exp_time*1000, self.frame_time*1000))
        return

    @pyqtSlot(bool, float)
    def live_spec_view(self, live_spec_bool, exposure_time_ms):
        if live_spec_bool:
            self.start_live_spec_view(exposure_time_ms)
        else:
            self.stop_live_spec_view()
        return

    def start_live_spec_view(self, exposure_time_ms):
        print('\nLive spec view started at', datetime.now())
        self.set_exposure_time(False, exposure_time_ms)
        self.myCamera.start_acquisition()
        self.viewSpecTimer.start(round(self.frame_time_ms)) # ms
        return

    def stop_live_spec_view(self):
        print('\nLive spec view stopped at', datetime.now())
        self.myCamera.stop_acquisition()
        self.viewSpecTimer.stop()
        return

    def camera_temp_timer(self):
        print('Monitoring Newton camera temperature each {:.1f} s.'.format(tempTimer_update/1000))
        self.tempTimer.start(tempTimer_update) # ms
        return

    def update_temp(self):
        # Update temp of the camera
        sensor_temp = self.myCamera.get_temperature()
        # print('\nNewton camera temperature retrieved at', datetime.now())
        # print('Sensor temp: %.1f °C' % sensor_temp)
        self.sensorTempSignal.emit(sensor_temp)
        return

    def update_view(self):
        # update spectrum while in live spectrum view mode
        self.myCamera.wait_for_frame()
        spectrum = self.myCamera.read_oldest_image() # numpy array of size (1024,1) that is a 2D array
        self.spectrum = spectrum.ravel() # numpy array of size (1024,) that is a 1D array
        self.spectrumSignal.emit(self.spectrum)
        return

    @pyqtSlot(bool, float)
    def take_single_spectrum(self, live_spec_bool, exposure_time_ms):
        print('\nPicture taken at', datetime.now())
        if live_spec_bool:
            self.stop_live_spec_view()
        # acquire a single spectrum
        self.set_exposure_time(False, exposure_time_ms)
        spectrum = self.myCamera.snap() # numpy array of size (1024,1) that is a 2D array
        self.spectrum = spectrum.ravel() # numpy array of size (1024,) that is a 1D array
        # emit
        self.spectrumSignal.emit(self.spectrum)
        return

    @pyqtSlot()    
    def set_working_folder(self):
        root = tk.Tk()
        root.withdraw()
        filepath = filedialog.askdirectory()
        if not filepath:
            print('No folder selected!')
        else:
            self.filepath = filepath
            print('New folder selected:', self.filepath)
            self.filepathSignal.emit(self.filepath)
        return

    @pyqtSlot(str)
    def set_filename(self, new_filename):
        self.filename = new_filename
        print('New filename has been set:', self.filename)
        return

    @pyqtSlot(bool)
    def save_automatically_check(self, save_bool):
        if save_bool:
            print('Signal will be saved automatically.')
            self.save_automatically_bool = True
        else:
            print('Signal will not be saved automatically.')
            self.save_automatically_bool = False
        return

    @pyqtSlot()
    def save_spectrum(self, message_box = False):
        # prepare full filepath
        filepath = self.filepath
        if self.save_automatically_bool:
            if self.acquire_continuously_bool:
                self.suffix = '_{:04d}'.format(self.spectrum_number)
            else:
                self.suffix = self.spectrum_suffix
        else:
            self.suffix = ''
        filename = self.filename + self.suffix
        # add time string to the filename
        timestr = tm.strftime("%Y%m%d_%H%M%S_")
        filename_timestamped = timestr + filename
        filename_data = filename_timestamped + '_spectrum'
        # save data
        full_filepath_data = os.path.join(filepath, filename_data)    
        # it will save an ASCII encoded text file
        data_to_save = np.transpose(np.vstack((self.wavelength_calibration, self.spectrum)))
        header_txt = 'wavelength(nm) integrated_counts'
        ascii_full_filepath = full_filepath_data + '.dat'
        np.savetxt(ascii_full_filepath, data_to_save, fmt='%.2f', header=header_txt)
        # # save measurement parameters and comments
        # self.params_to_be_saved = self.get_params_to_be_saved()
        # with open(full_filepath_params, 'w') as f:
        #     print(self.params_to_be_saved, file = f)
        # print('Data %s has been saved.' % filename_timestamped)
        # # emit signal for any other module that is importing this function
        # self.fileSavedSignal.emit(full_filepath_data + '.npy', full_filepath_monitor + '.npy')
        return

    @pyqtSlot()    
    def close(self):
        print('Closing spectrometer...')
        self.mySpectrometer.ShamrockClose()
        print(datetime.now(), '[Kymera] Close')
        print('Closing camera...')
        self.myCamera.close()
        print('Stopping QtTimers...')
        self.viewSpecTimer.stop()
        self.tempTimer.stop()
        print('Exiting thread...')
        spectrumThread.exit()
        return     

    def make_connection(self, frontend): 
        frontend.gratingFrontendSignal.connect(self.set_configuration)
        frontend.zeroorderSignal.connect(self.goto_zeroorder) 
        frontend.wavelengthSignal.connect(self.set_wavelength)
        frontend.shutterSignal.connect(self.set_shutter_state)
        frontend.closeSignal.connect(self.close)
        frontend.exposureChangedSignal.connect(self.set_exposure_time)
        frontend.liveSpecViewSignal.connect(self.live_spec_view) 
        frontend.takeSpectrumSignal.connect(self.take_single_spectrum)
        frontend.saveSignal.connect(self.save_spectrum)
        frontend.setWorkDirSignal.connect(self.set_working_folder)
        frontend.saveSpecContSignal.connect(self.save_automatically_check)
        frontend.filenameSignal.connect(self.set_filename)
        return

######################################################################################
######################################################################################
######################################################################################

if __name__ == '__main__':

    app = QtGui.QApplication([])

    print('\nSpectrometer initialization...')

    camera = Andor.AndorSDK2Camera()
    mySpectrometer = Shamrock()
    inipath = 'C:\\Program Files\\Andor SOLIS\\SPECTROG.ini'
    mySpectrometer.ShamrockInitialize(inipath)
    ret, serial_number = mySpectrometer.ShamrockGetSerialNumber(DEVICE)
    print(datetime.now(), '[Kymera] Serial number: {}'.format(serial_number.decode('UTF-8')))
    print('Camera:', camera.get_device_info())

    gui = Frontend()
    worker = Backend(mySpectrometer, camera)

    worker.make_connection(gui)
    gui.make_connection(worker)

    # thread that run in background
    spectrumThread = QtCore.QThread()
    worker.moveToThread(spectrumThread)
    worker.viewSpecTimer.moveToThread(spectrumThread)
    worker.tempTimer.moveToThread(spectrumThread)
    
    # configure the connection to allow queued executions to avoid interruption of previous calls
    worker.viewSpecTimer.timeout.connect(worker.update_view, QtCore.Qt.QueuedConnection) 
    worker.tempTimer.timeout.connect(worker.update_temp)

    spectrumThread.start()

    gui.show()
    app.exec()

    