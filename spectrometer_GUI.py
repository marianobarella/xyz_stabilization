﻿# -*- coding: utf-8 -*-
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
import viewbox_tools
from PIL import Image

# Spectrometer Kymera 328i
DEVICE = 0
gratingList = ['300 lines/mm', '500 lines/mm', 'Mirror']
# DO NOT MODIFIED THE FOLLOWING DICT
GRATING = {'300 lines/mm': 1, '500 lines/mm': 2, 'Mirror': 3}
OPEN_SHUTTER = 1
CLOSE_SHUTTER = 0

# Camera Andor Newton DU920P-BEX2-DD
NumberofPixel = 1024
PixelWidth = 26 # um
acqModeList = ['Full Vertical Binning', 'Image', 'Single-Track']
initial_exp_time = 100 # in ms
initial_cam_temp_tickbox_state = False
initial_focus_mirror_steps = 228 # found to be the best on 15/July/2025
tempTimer_update = 30000 # in ms
preampList = ['1', '2', '4']
hsspeedList = ['3.0', '1.0', '0.05']
# DO NOT MODIFIED THE FOLLOWING DICTS
HSSPEED = {'3.0': 0, '1.0': 1, '0.05': 2}
PREAMP = {'1': 0, '2': 1, '4': 2}
ACQMODE = {'Full Vertical Binning': 'fvb', 'Image': 'image', 'Single-Track': 'single_track'}
initial_center_row = 128
initial_track_width = 71

# other inputs
# initial filepath and filename
initial_filepath = 'D:\\daily_data\\spectra' # save in SSD for fast and daily use
initial_filename = 'nanostructure_X'
initial_wavelength_array = np.arange(NumberofPixel)
initial_image = 128*np.ones((256, 1024))
initial_spectrum = np.ones(1024) # 1D array of size 1024
initial_autolevel_state = False

######################################################################################
######################################################################################
######################################################################################

class Frontend(QtGui.QFrame):

    gratingFrontendSignal = pyqtSignal(str)
    focusMirrorFrontendSignal = pyqtSignal(int)
    zeroorderSignal = pyqtSignal()
    wavelengthSignal = pyqtSignal(float)
    shutterSignal = pyqtSignal(int)
    cameraModeFrontendSignal = pyqtSignal(str, str, str, int, int)
    exposureChangedSignal = pyqtSignal(bool, float)
    liveSpecViewSignal = pyqtSignal(bool, float)
    takeSpectrumSignal = pyqtSignal(bool, float)
    numAcqSignal = pyqtSignal(int)
    filenameSignal = pyqtSignal(str)
    setWorkDirSignal = pyqtSignal()
    saveSpecContSignal = pyqtSignal(bool)
    saveSignal = pyqtSignal()
    createTodayFolderSignal = pyqtSignal(str, str)
    takeBaselineSignal = pyqtSignal(bool, float)
    closeSignal = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # set the title of the window
        title = "Spectrometer module"
        self.setWindowTitle(title)
        self.setGeometry(5, 30, 1000, 700) # x pos, y pos, width, height
        self.setUpGUI()
        self.camera_temp = 0.00
        self.spectrum_array = np.array([])
        self.set_working_dir()
        self.set_filename()
        self.wavelength_array = initial_wavelength_array
        self.autolevel_bool = initial_autolevel_state
        self.get_image(initial_image)
        self.hist._updateView
        self.file_path = initial_filepath
        return

    def setUpGUI(self):
        ##################################### SPECTROMETER
        # Grating settings
        grating_label = QtGui.QLabel('Grating:')
        self.grating = QtGui.QComboBox()
        self.grating.addItems(gratingList)
        self.grating.setCurrentIndex(0)
        self.grating.setFixedWidth(150)

        self.set_grating_button = QtGui.QPushButton('Set grating')  
        self.set_grating_button.clicked.connect(self.spectrum_grating_configuration)
        self.set_grating_button.setStyleSheet(
            "QPushButton:pressed { background-color: lightcoral; }")

        # focus mirror accessory
        focus_mirror_label = QtGui.QLabel('Focus mirror step:')
        self.focus_mirror_edit = QtGui.QLineEdit(str(initial_focus_mirror_steps))
        self.focus_mirror_edit.setValidator(QtGui.QIntValidator(0, 550))
        self.focus_mirror_edit.setFixedWidth(150)
        self.focus_mirror_edit.setToolTip('Change position of the focusing mirror. Values range from 0 to 550.')

        self.set_focus_mirror_button = QtGui.QPushButton('Set focus mirror')
        self.set_focus_mirror_button.clicked.connect(self.spectrum_focus_mirror_configuration)
        self.set_focus_mirror_button.setStyleSheet(
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

        wavelength_label = QtGui.QLabel('Center λ (nm):')
        self.wavelength_edit = QtGui.QLineEdit('0.0')
        self.wavelength_edit.setValidator(QtGui.QDoubleValidator(0.0, 3000.0, 1))
        self.wavelength_edit.setFixedWidth(150)

        self.set_wavelength_button = QtGui.QPushButton('Set Wavelength')
        self.set_wavelength_button.clicked.connect(self.spectrum_set_wavelength)
        self.set_wavelength_button.setStyleSheet(
            "QPushButton:pressed { background-color: lightcoral; }")
        self.set_wavelength_button.setFixedWidth(150)

        ################################### CAMERA

        # Camera widget parameters
        acq_mode_label = QtGui.QLabel('Acquisition mode:')
        self.acq_mode = QtGui.QComboBox()
        self.acq_mode.addItems(acqModeList)
        self.acq_mode.setCurrentIndex(0)
        self.acq_mode.setFixedWidth(150)

        preamp_label = QtGui.QLabel('Pre-amp. gain:')
        self.preamp = QtGui.QComboBox()
        self.preamp.addItems(preampList)
        self.preamp.setCurrentIndex(0)
        self.preamp.setFixedWidth(150)
        self.preamp.setToolTip('Pre-amplifier gain of the readout register.')

        hsspeed_label = QtGui.QLabel('HS speed (MHz):')
        self.hsspeed = QtGui.QComboBox()
        self.hsspeed.addItems(hsspeedList)
        self.hsspeed.setCurrentIndex(0)
        self.hsspeed.setFixedWidth(150)
        self.hsspeed.setToolTip('Horizontal shift speed of the readout register.')

        # Sensor ROI entry for Single-Track mode
        define_roi = QtGui.QLabel('Define ROI (single-track mode):')
        center_row_label = QtGui.QLabel('Center row (pixel):')
        track_width_label = QtGui.QLabel('Track width (pixels):')
        self.center_row_edit = QtGui.QLineEdit(str(initial_center_row))
        self.track_width_edit = QtGui.QLineEdit(str(initial_track_width))
        self.center_row_edit.setValidator(QtGui.QIntValidator(1, 256))
        self.track_width_edit.setValidator(QtGui.QIntValidator(1, 256))
        self.center_row_edit.editingFinished.connect(self.roi_edit_changed)
        self.track_width_edit.editingFinished.connect(self.roi_edit_changed)

        self.set_configuration_camera_button = QtGui.QPushButton('Set configuration')
        self.set_configuration_camera_button.clicked.connect(self.camera_configuration)
        self.set_configuration_camera_button.setStyleSheet(
            "QPushButton:pressed { background-color: lightcoral; }")

        self.sensor_temp_label = QtGui.QLabel('Sensor temperature:')
        self.sensor_temp_value = QtGui.QLabel('----- °C')

        # Exposure time
        exp_time_label = QtGui.QLabel('Exposure time (ms):')
        self.exp_time_edit = QtGui.QLineEdit(str(initial_exp_time))
        self.exp_time_edit.editingFinished.connect(self.exposure_changed_check)
        self.exp_time_edit.setValidator(QtGui.QDoubleValidator(0.001, 600000.000, 3))
        self.exp_time_edit.setToolTip('Minimum is 1 ms. Maximum is 600 s = 10 min.')

        number_of_acq_label = QtGui.QLabel('Number of acquisitions:')
        self.number_of_acq_edit = QtGui.QLineEdit(str(1))
        self.number_of_acq_edit.editingFinished.connect(self.number_of_acq_change)
        self.number_of_acq_edit.setValidator(QtGui.QIntValidator(0, 1000))

        self.live_spec_button = QtGui.QPushButton('Live spectra view')
        self.live_spec_button.setCheckable(True)
        self.live_spec_button.clicked.connect(self.live_spec_view_button_check)
        self.live_spec_button.setStyleSheet(
            "QPushButton:pressed { background-color: light-red; }"
            "QPushButton:checked { background-color: red; }")

        # Buttons and labels
        self.take_spectrum_button = QtGui.QPushButton('Take a spectrum')
        self.take_spectrum_button.setCheckable(False)
        self.take_spectrum_button.clicked.connect(self.take_spectrum_button_check)
        self.take_spectrum_button.setStyleSheet(
            "QPushButton:pressed { background-color: red; }")

        self.take_baseline_button = QtGui.QPushButton('Take baseline')
        self.take_baseline_button.setCheckable(False)
        self.take_baseline_button.clicked.connect(self.take_baseline_button_check)
        self.take_baseline_button.setStyleSheet("background-color: cornflowerblue")
        self.take_baseline_button.setToolTip('It will close the shutter, acquire the background signal at the current temperature and the given exposure time. Data will be saved automatically with the background suffix.')

        # Working folder
        self.working_dir_button = QtGui.QPushButton('Select directory')
        self.working_dir_button.clicked.connect(self.set_working_dir)
        self.working_dir_button.setStyleSheet(
            "QPushButton:pressed { background-color: palegreen; }")
        self.create_today_folder_button = QtGui.QPushButton('Create today folder')
        self.create_today_folder_button.clicked.connect(self.create_today_folder)
        self.create_today_folder_button.setStyleSheet(
            "QPushButton:pressed { background-color: palegreen; }")
        self.working_dir_label = QtGui.QLabel('Working directory')
        self.filepath = initial_filepath
        self.working_dir_path = QtGui.QLineEdit(self.filepath)
        # self.working_dir_path.setFixedWidth(300)
        self.working_dir_path.setReadOnly(True)
        self.filename_label = QtGui.QLabel('Filename (.npy)')
        self.filename = initial_filename
        self.filename_name = QtGui.QLineEdit(self.filename)
        # self.filename_name.setFixedWidth(300)
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

        experiment_name_label = QtGui.QLabel('Experiment name:')
        self.experiment_name_edit = QtGui.QLineEdit('WRITE ME')

        ########################################## DATA VISUALIZATION
        # show ROI button
        self.show_ROI_button = QtGui.QPushButton('Show ROI')
        self.show_ROI_button.setCheckable(True)
        self.show_ROI_button.clicked.connect(self.show_ROI)
        self.show_ROI_button.setStyleSheet(
            "QPushButton:pressed { background-color: steelblue; }")

        # Widget for the spectrum data
        self.plotSpectrumWidget = pg.GraphicsLayoutWidget()
        self.spectrum_plot = self.plotSpectrumWidget.addPlot(row = 1, col = 1, title = 'Spectrum signal')
        self.spectrum_plot.enableAutoRange(True, True)
        self.spectrum_plot.showGrid(x = True, y = True)
        self.spectrum_plot.setLabel('left', 'Integrated counts')
        self.spectrum_plot.setLabel('bottom', 'Wavelength (nm)')

        # Image
        self.cameraSensorWidget = pg.GraphicsLayoutWidget()
        self.viewbox = self.cameraSensorWidget.addPlot()
        self.viewbox.setAspectLocked()
        self.cam_image = pg.ImageItem()
        self.cam_image.setOpts(axisOrder = 'row-major')
        # self.vb.invertY(True)
        # self.vb.invertX(True)
        self.viewbox.addItem(self.cam_image)
        self.hist = pg.HistogramLUTItem(image = self.cam_image, levelMode = 'mono')
        self.hist.gradient.loadPreset('grey')
        self.hist.disableAutoHistogramRange()
        # 'thermal', 'flame', 'yellowy', 'bipolar', 'spectrum', 'cyclic', 'greyclip', 'grey'
        self.hist.vb.setLimits(yMin = 0, yMax = 65536) # 16-bit camera
        self.cameraSensorWidget.addItem(self.hist, row = 0, col = 1)

        self.autolevel_tickbox = QtGui.QCheckBox('Autolevel')
        self.autolevel_tickbox.setChecked(initial_autolevel_state)
        self.autolevel_tickbox.setText('Autolevel')
        self.autolevel_tickbox.stateChanged.connect(self.autolevel)
        self.autolevel_bool = initial_autolevel_state

        # Widget layout
        self.spectrumWidget = QtGui.QWidget()
        spectrum_parameters_layout = QtGui.QGridLayout()
        self.spectrumWidget.setLayout(spectrum_parameters_layout)
        spectrum_parameters_layout.addWidget(grating_label,                     0, 0)
        spectrum_parameters_layout.addWidget(self.grating,                      0, 1)
        spectrum_parameters_layout.addWidget(self.set_grating_button,           1, 0, 1, 2)
        spectrum_parameters_layout.addWidget(focus_mirror_label,                2, 0)
        spectrum_parameters_layout.addWidget(self.focus_mirror_edit,            2, 1)
        spectrum_parameters_layout.addWidget(self.set_focus_mirror_button,      3, 0, 1, 2)
        spectrum_parameters_layout.addWidget(wavelength_label,                  4, 0)
        spectrum_parameters_layout.addWidget(self.wavelength_edit,              4, 1)
        spectrum_parameters_layout.addWidget(self.set_wavelength_button,        5, 0)
        spectrum_parameters_layout.addWidget(self.zero_order_button,            5, 1)
        spectrum_parameters_layout.addWidget(self.shutter_button,               6, 0, 1, 2)

        self.camWidget = QtGui.QWidget()
        camera_parameters_layout = QtGui.QGridLayout()
        self.camWidget.setLayout(camera_parameters_layout)
        camera_parameters_layout.addWidget(acq_mode_label,                      0, 0)
        camera_parameters_layout.addWidget(self.acq_mode,                       0, 1)
        camera_parameters_layout.addWidget(preamp_label,                        1, 0)
        camera_parameters_layout.addWidget(self.preamp,                         1, 1)
        camera_parameters_layout.addWidget(hsspeed_label,                       2, 0)
        camera_parameters_layout.addWidget(self.hsspeed,                        2, 1)
        camera_parameters_layout.addWidget(define_roi,                          0, 2)
        camera_parameters_layout.addWidget(center_row_label,                    1, 2)
        camera_parameters_layout.addWidget(self.center_row_edit,                1, 3)
        camera_parameters_layout.addWidget(track_width_label,                   2, 2)
        camera_parameters_layout.addWidget(self.track_width_edit,               2, 3)
        camera_parameters_layout.addWidget(self.show_ROI_button,                3, 3)
        camera_parameters_layout.addWidget(self.set_configuration_camera_button,3, 0, 1, 2)
        camera_parameters_layout.addWidget(self.sensor_temp_label,              5, 0)
        camera_parameters_layout.addWidget(self.sensor_temp_value,              5, 1)
        camera_parameters_layout.addWidget(exp_time_label,                      6, 0)
        camera_parameters_layout.addWidget(self.exp_time_edit,                  6, 1)
        camera_parameters_layout.addWidget(number_of_acq_label,                 7, 0)
        camera_parameters_layout.addWidget(self.number_of_acq_edit,             7, 1)
        camera_parameters_layout.addWidget(self.take_spectrum_button,           8, 0, 1, 2)
        camera_parameters_layout.addWidget(self.take_baseline_button,           8, 2, 1, 2)
        camera_parameters_layout.addWidget(self.saveButton,                     9, 0)
        camera_parameters_layout.addWidget(self.saveAutomaticallyBox,           9, 1)
        camera_parameters_layout.addWidget(self.working_dir_label,              10, 0)
        camera_parameters_layout.addWidget(self.working_dir_path,               10, 1, 1, 2)
        camera_parameters_layout.addWidget(self.working_dir_button,             10, 3)
        camera_parameters_layout.addWidget(experiment_name_label,               11, 0)
        camera_parameters_layout.addWidget(self.experiment_name_edit,           11, 1, 1, 2)
        camera_parameters_layout.addWidget(self.create_today_folder_button,     11, 3)
        camera_parameters_layout.addWidget(self.filename_label,                 12, 0)
        camera_parameters_layout.addWidget(self.filename_name,                  12, 1, 1, 2)
        camera_parameters_layout.addWidget(self.live_spec_button,               13, 0, 1, 3)
        camera_parameters_layout.addWidget(self.autolevel_tickbox,              13, 3)

        # Place layouts and boxes
        dockArea = DockArea()
        hbox = QtGui.QHBoxLayout(self)

        spectrometerParamDock = Dock('Spectrometer parameters', size = (10, 10))
        spectrometerParamDock.addWidget(self.spectrumWidget)
        dockArea.addDock(spectrometerParamDock)

        camParamDock = Dock('Camera parameters', size = (10, 10))
        camParamDock.addWidget(self.camWidget)
        dockArea.addDock(camParamDock, 'right', spectrometerParamDock)

        camSensorDock = Dock('Camera sensor', size = (10, 50))
        camSensorDock.addWidget(self.cameraSensorWidget)
        dockArea.addDock(camSensorDock, 'bottom')

        plotSpectrumDock = Dock('Spectrum', size = (10, 50))
        plotSpectrumDock.addWidget(self.plotSpectrumWidget)
        dockArea.addDock(plotSpectrumDock, 'above', camSensorDock)

        hbox.addWidget(dockArea)
        self.setLayout(hbox)
        return

    def spectrum_grating_configuration(self):
        grating = str(self.grating.currentText())       
        self.gratingFrontendSignal.emit(grating)
        return
        
    def spectrum_focus_mirror_configuration(self):
        focus_mirror_steps = int(self.focus_mirror_edit.text())
        self.focusMirrorFrontendSignal.emit(focus_mirror_steps)
        return

    def spectrum_set_wavelength(self):
        wavelength = float(self.wavelength_edit.text())
        self.wavelengthSignal.emit(wavelength)
        return

    def zero_order_check(self):
        self.wavelength_edit.setText('0.0')
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

    def autolevel(self):
        if self.autolevel_tickbox.isChecked():
            self.autolevel_bool = True
        else:
            self.autolevel_bool = False
        return

    @pyqtSlot(np.ndarray)
    def get_image(self, image):
        self.cam_image.setImage(image, autoLevels = self.autolevel_bool)
        return

    def camera_configuration(self):
        acq_mode = str(self.acq_mode.currentText())
        preamp_mode = str(self.preamp.currentText())
        hsspeed_mode = str(self.hsspeed.currentText())
        center_row = int(self.center_row_edit.text())
        track_width = int(self.track_width_edit.text())
        self.cameraModeFrontendSignal.emit(acq_mode, preamp_mode, hsspeed_mode, center_row, track_width) 
        return

    def exposure_changed_check(self):
        exposure_time_ms = float(self.exp_time_edit.text()) # in ms
        if self.live_spec_button.isChecked():
            self.exposureChangedSignal.emit(True, exposure_time_ms)
        else:
            self.exposureChangedSignal.emit(False, exposure_time_ms)
        return

    def number_of_acq_change(self):
        number_of_acquisitions = int(self.number_of_acq_edit.text())
        self.numAcqSignal.emit(number_of_acquisitions)
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

    def take_baseline_button_check(self):
        exposure_time_ms = float(self.exp_time_edit.text()) # in ms
        if self.live_spec_button.isChecked():
            self.takeBaselineSignal.emit(True, exposure_time_ms)
        else:
            self.takeBaselineSignal.emit(False, exposure_time_ms)
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
        self.sensor_temp_value.setText('%.1f °C' % sensor_temp)
        return

    def show_ROI(self):
        # show ROI for single-track
        if self.show_ROI_button.isChecked():
            center_pos = int(self.center_row_edit.text())
            roi_width = int(self.track_width_edit.text())
            box_size = (1024, roi_width) # (columns, rows)
            x_pos = center_pos - int(roi_width/2)
            y_pos = 0
            ROIpos = (y_pos, x_pos) # (column, row) of the bottom left corner of the box
            self.roi = viewbox_tools.ROI_rect(box_size, self.viewbox, ROIpos,
                                              handlePos = (1, 1),
                                              handleCenter = (0, 0), 
                                              scaleSnap = False,
                                              translateSnap = True)
        else:
            self.viewbox.removeItem(self.roi)
            self.roi.hide()
            self.roi = {}
        return

    def roi_edit_changed(self):
        if self.show_ROI_button.isChecked():
            print('ROI has changed.')
            self.viewbox.removeItem(self.roi)
            self.roi.hide()
            self.roi = {}
            self.show_ROI()
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

    def create_today_folder(self):
        experiment_name = self.experiment_name_edit.text()
        working_dir = self.working_dir_path.text()
        self.createTodayFolderSignal.emit(working_dir, experiment_name)
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

    @pyqtSlot(str)
    def get_file_path(self, file_path):
        self.file_path = file_path
        self.working_dir_path.setText(self.file_path)
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
        backend.imageSignal.connect(self.get_image)
        backend.spectrumSignal.connect(self.get_spectrum)
        backend.filepathSignal.connect(self.get_file_path)
        backend.wavelengthCalibrationSignal.connect(self.get_wavelength_calibration)
        backend.sensorTempSignal.connect(self.get_temperature)
        return

######################################################################################
######################################################################################
######################################################################################

class Backend(QtCore.QObject):
    
    imageSignal = pyqtSignal(np.ndarray)
    gratingBackendSignal = pyqtSignal(str)
    spectrumSignal = pyqtSignal(np.ndarray)
    sensorTempSignal = pyqtSignal(float)
    filepathSignal = pyqtSignal(str)
    wavelengthCalibrationSignal = pyqtSignal(np.ndarray)
    fileSavedSignal = pyqtSignal(str)

    def __init__(self, mySpectrometer, myCamera, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.myCamera = myCamera
        self.mySpectrometer = mySpectrometer
        self.viewSpecTimer = QtCore.QTimer()
        self.tempTimer = QtCore.QTimer()
        self.spectrum = initial_spectrum
        self.temperature = -70 # in celcius
        self.save_automatically_bool = False
        self.filepath = initial_filepath
        self.filename = initial_filename
        self.wavelength_array = initial_wavelength_array
        self.number_of_acquisitions = 1
        self.image = initial_image
        self.start_camera()
        self.start_spectrometer()
        self.live_flag = False
        self.sensor_temp = 99
        return
        
    def start_camera(self):
        print('Image ring buffer size:', self.myCamera.get_buffer_size())
        ret = self.mySpectrometer.ShamrockShutterIsPresent(DEVICE)
        print('Is camera shutter present?', ret)
        self.shutter_state = CLOSE_SHUTTER
        self.set_shutter_state(self.shutter_state)
        print('Is camera opened?', self.myCamera.is_opened())
        self.acq = 'Full Vertical Binning'
        self.preamp = '1'
        self.hsspeed = '3.0'
        self.center_row = initial_center_row
        self.track_width = initial_track_width
        self.set_camera_configuration(self.acq, self.preamp, self.hsspeed, self.center_row, self.track_width)
        fan_mode = 'full' # Options are 'full', 'low' or 'off'
        self.myCamera.set_fan_mode(fan_mode)
        self.myCamera.set_cooler(on = True)
        # temperature range is -120 °C to -10 °C
        self.myCamera.set_temperature(self.temperature, enable_cooler = True)
        print('Camera cooler is ON?',self.myCamera.is_cooler_on())
        self.camera_temp_timer()
        print('Camera status:', self.myCamera.get_status())
        return

    def start_spectrometer(self):
        self.mySpectrometer.ShamrockSetNumberPixels(DEVICE, NumberofPixel)
        self.mySpectrometer.ShamrockSetPixelWidth(DEVICE, PixelWidth)
        self.grating = '300 lines/mm'
        self.set_grating(self.grating)
        self.wavelength = 0.0
        (ret, present) = self.mySpectrometer.ShamrockFocusMirrorIsPresent(DEVICE)
        print('Is focus mirror present?', present)
        (ret, maxsteps) = self.mySpectrometer.ShamrockGetFocusMirrorMaxSteps(DEVICE)
        print('Max focus mirror steps: ', maxsteps)
        self.set_focus_mirror(initial_focus_mirror_steps)
        return
    
    @pyqtSlot(str)
    def set_grating(self, grating):
        print('Changing grating...')
        self.grating = grating
        self.grating_number = GRATING[self.grating]
        ret = self.mySpectrometer.ShamrockSetGrating(DEVICE, self.grating_number)
        print(datetime.now(), '[Kymera] Grating =', self.grating, ', Code', ret)
        tm.sleep(0.2)
        (ret, Lines, Blaze, Home, Offset) = self.mySpectrometer.ShamrockGetGratingInfo(DEVICE, self.grating_number)
        print('Current grating information: ', Lines, 'lines/mm', Blaze.decode('UTF-8'), Home, Offset)
        return

    @pyqtSlot(int)
    def set_focus_mirror(self, focus_mirror_steps):
        print('Setting new focus mirror position...')
        (ret, current_focus_mirror_steps) = self.mySpectrometer.ShamrockGetFocusMirror(DEVICE)
        relative_focus_mirror_steps = focus_mirror_steps - current_focus_mirror_steps
        ret = self.mySpectrometer.ShamrockSetFocusMirror(DEVICE, relative_focus_mirror_steps)
        tm.sleep(0.2)
        (ret, current_focus_mirror_steps) = self.mySpectrometer.ShamrockGetFocusMirror(DEVICE)
        print('Current focus mirror steps:', current_focus_mirror_steps)
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
        self.wavelength_array = np.array(list(calibration))
        self.wavelengthCalibrationSignal.emit(self.wavelength_array)
        # print(datetime.now(), '[Kymera] Calibration wavelength array =', self.wavelength_array)
        print(datetime.now(), \
            '[Kymera] Calibration wavelength window range = [ %.1f, %.1f ]' % (self.wavelength_array [0], \
                                                                               self.wavelength_array [-1]))
        ret, wavelength_retrieved = self.mySpectrometer.ShamrockGetWavelength(DEVICE)
        print(datetime.now(), '[Kymera] Central wavelength = ', wavelength_retrieved)
        return

    @pyqtSlot(int)
    def set_shutter_state(self, shutter_state):
        ret = self.mySpectrometer.ShamrockSetShutter(DEVICE, shutter_state)
        (ret, state) = self.mySpectrometer.ShamrockGetShutter(DEVICE)
        if state == CLOSE_SHUTTER:
            self.shutter_state = 'closed'
        elif state == OPEN_SHUTTER:
            self.shutter_state = 'open'
        else:
            self.shutter_state = 'error'
        print(datetime.now(), '[Kymera] Shutter action =', ret, ', Shutter state =', self.shutter_state)
        return  

    @pyqtSlot(str, str, str, int, int)
    def set_camera_configuration(self, acq_mode, preamp_mode, hsspeed_mode, center_row, track_width):
        print('Setting camera configuration...')
        self.acq_mode = ACQMODE[acq_mode]
        self.myCamera.set_read_mode(self.acq_mode)
        print('Read mode:', self.myCamera.get_read_mode())
        if self.acq_mode == 'single_track':
            self.myCamera.setup_single_track_mode(center = center_row, width = track_width)
            ret = self.myCamera.get_single_track_mode_parameters()
            print('Single-track parameters:', ret)
        self.preamp_value = PREAMP[preamp_mode]
        self.hsspeed_value = HSSPEED[hsspeed_mode]
        self.myCamera.set_amp_mode(channel = 0, oamp = 0, hsspeed = self.hsspeed_value, preamp = self.preamp_value)
        ret = self.myCamera.get_amp_mode()
        print('Camera amplifier configuration:', ret)
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
        # set frame timeout to +50% of the frame time
        self.frame_timeout = self.frame_time*1.5 
        return

    @pyqtSlot(bool, float)
    def live_spec_view(self, live_spec_bool, exposure_time_ms):
        if live_spec_bool:
            self.start_live_spec_view(exposure_time_ms)
        else:
            self.stop_live_spec_view()
        return

    def start_live_spec_view(self, exposure_time_ms):
        self.live_flag = True
        self.spectrum_number = 0
        print('\nLive spec view started at', datetime.now())
        self.set_shutter_state(OPEN_SHUTTER) # opens shutter
        self.set_exposure_time(False, exposure_time_ms)
        self.myCamera.setup_acquisition(mode = 'cont', nframes = self.number_of_acquisitions)
        self.myCamera.start_acquisition()
        self.viewSpecTimer.start(round(self.frame_time_ms)) # ms
        return

    def stop_live_spec_view(self):
        self.live_flag = False
        print('\nLive spec view stopped at', datetime.now())
        self.myCamera.stop_acquisition()
        self.set_shutter_state(CLOSE_SHUTTER) # closes shutter
        self.viewSpecTimer.stop()
        return

    def camera_temp_timer(self):
        print('Monitoring Newton camera temperature each {:.1f} s.'.format(tempTimer_update/1000))
        self.tempTimer.start(tempTimer_update) # ms
        return

    def update_temp(self):
        # Update temp of the camera
        self.sensor_temp = self.myCamera.get_temperature()
        # print('\nNewton camera temperature retrieved at', datetime.now())
        # print('Sensor temp: %.1f °C' % sensor_temp)
        self.sensorTempSignal.emit(self.sensor_temp)
        return

    def update_view(self):
        # update spectrum while in live spectrum view mode
        self.myCamera.wait_for_frame(timeout = (self.frame_timeout*self.number_of_acquisitions, self.frame_timeout))
        spectrum = self.myCamera.read_newest_image() # numpy array of size (1, 1024) that is a 2D array
        if self.acq_mode == 'fvb' or self.acq_mode == 'single_track':
            self.spectrum = spectrum.ravel() # numpy array of size (1024,) that is a 1D array
            self.spectrumSignal.emit(self.spectrum)
        elif self.acq_mode == 'image':
            self.image = spectrum
            self.imageSignal.emit(self.image)
        else:
            print('ERROR in determining the acquisition mode. Acquisition stopped.')
            self.stop_live_spec_view()
        if self.save_automatically_bool:
            self.save_spectrum()
            self.spectrum_number += 1
        return

    @pyqtSlot(bool, float)
    def take_single_spectrum(self, live_spec_bool, exposure_time_ms):
        print('\nSpectrum taken at', datetime.now())
        if live_spec_bool:
            self.stop_live_spec_view()
        # acquire a single spectrum
        self.set_exposure_time(False, exposure_time_ms)
        self.myCamera.setup_acquisition(mode = 'single', nframes = self.number_of_acquisitions)
        self.set_shutter_state(OPEN_SHUTTER) # opens shutter
        if self.number_of_acquisitions == 1:
            # numpy array of size (1, 1024) that is a 2D array
            spectrum = self.myCamera.snap(timeout = self.frame_timeout)
        elif self.number_of_acquisitions > 1:
            # numpy array of size (1, 1024) that is a 2D array
            spectra_list = self.myCamera.grab(nframes = self.number_of_acquisitions, \
                                              frame_timeout = self.frame_timeout) 
            spectra_array = np.array(spectra_list)
            spectrum = np.mean(spectra_array, axis = 0) # single, averaged spectrum
        else:
            print('Error while taking a single spectrum! Number of acquisitions %i' % self.number_of_acquisitions)
        # emit
        if self.acq_mode == 'fvb' or self.acq_mode == 'single_track':
            self.spectrum = spectrum.ravel() # numpy array of size (1024,) that is a 1D array
            self.spectrumSignal.emit(self.spectrum)
        elif self.acq_mode == 'image':
            self.image = spectrum
            self.imageSignal.emit(self.image)
        else:
            print('ERROR in determining the acquisition mode. Acquisition stopped.')
        if self.save_automatically_bool:
            self.save_spectrum()
        self.set_shutter_state(CLOSE_SHUTTER) # close shutter
        return

    @pyqtSlot(bool, float)
    def take_baseline_spectrum(self, live_spec_bool, exposure_time_ms):
        self.set_shutter_state(CLOSE_SHUTTER) # closes shutter
        self.take_single_spectrum(live_spec_bool, exposure_time_ms)
        self.save_spectrum(baseline = True)
        return

    @pyqtSlot(int)
    def set_number_of_acquisitions(self, number_of_acquisitions):
        self.number_of_acquisitions = number_of_acquisitions
        print('Number of acquisitions to be averaged: %i' % self.number_of_acquisitions)
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

    @pyqtSlot(str, str)
    def create_folder(self, working_folder, experiment_name):
        timestr = tm.strftime("%Y%m%d")
        today_folder = '%s - %s' % (timestr, experiment_name)
        filepath = os.path.join(working_folder, today_folder)
        if not os.path.exists(filepath):
            print('Today\'s folder created:', filepath)
            os.makedirs(filepath)
            self.filepath = filepath
            self.filepathSignal.emit(self.filepath)
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
    def save_spectrum(self, message_box = False, baseline = False):
        # prepare full filepath
        filepath = self.filepath
        if self.live_flag:
            self.suffix = '_{:04d}'.format(self.spectrum_number)
        elif baseline:
            self.suffix = '_baseline'
        else:
            self.suffix = ''
        filename = self.filename + self.suffix
        # add time string to the filename
        timestr = tm.strftime("%Y%m%d_%H%M%S_")
        filename_timestamped = timestr + filename
        filename_data = filename_timestamped + '_spectrum'
        filename_params = filename_timestamped + '_params.txt'
        # save data
        full_filepath_data = os.path.join(filepath, filename_data)
        if self.acq_mode == 'image':
            image_full_filepath = full_filepath_data + '.jpg'
            image_to_save = Image.fromarray(self.spectrum)
            image_to_save.save(image_full_filepath) 
            print('Image %s saved' % filename)
        else:
            # it will save an ASCII encoded text file
            data_to_save = np.transpose(np.vstack((self.wavelength_array, self.spectrum)))
            header_txt = 'wavelength(nm) integrated_counts'
            ascii_full_filepath = full_filepath_data + '.dat'
            np.savetxt(ascii_full_filepath, data_to_save, fmt='%.2f', header=header_txt)
        # save measurement parameters and comments
        full_filepath_params = os.path.join(filepath, filename_params)
        self.params_to_be_saved = self.get_params_to_be_saved()
        with open(full_filepath_params, 'w') as f:
            print(self.params_to_be_saved, file = f)
        print('Data %s has been saved.' % filename_timestamped)
        # emit signal for any other module that is importing this function
        self.fileSavedSignal.emit(full_filepath_data + '.dat')
        return

    def get_params_to_be_saved(self):
        dict_to_be_saved = {}
        dict_to_be_saved["Acquisition mode"] = self.acq_mode
        dict_to_be_saved["Grating"] = self.grating
        dict_to_be_saved["Pre-amp"] = self.preamp_value
        dict_to_be_saved["HSSpeed"] = self.hsspeed_value
        dict_to_be_saved["Exposure time (s)"] = self.exposure_time
        dict_to_be_saved["Sensor temperature (°C)"] = self.sensor_temp
        dict_to_be_saved["Number of acquisitions"] = self.number_of_acquisitions
        return dict_to_be_saved

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
        frontend.gratingFrontendSignal.connect(self.set_grating)
        frontend.focusMirrorFrontendSignal.connect(self.set_focus_mirror)
        frontend.cameraModeFrontendSignal.connect(self.set_camera_configuration)
        frontend.zeroorderSignal.connect(self.goto_zeroorder) 
        frontend.wavelengthSignal.connect(self.set_wavelength)
        frontend.shutterSignal.connect(self.set_shutter_state)
        frontend.closeSignal.connect(self.close)
        frontend.exposureChangedSignal.connect(self.set_exposure_time)
        frontend.liveSpecViewSignal.connect(self.live_spec_view) 
        frontend.takeSpectrumSignal.connect(self.take_single_spectrum)
        frontend.takeBaselineSignal.connect(self.take_baseline_spectrum)
        frontend.numAcqSignal.connect(self.set_number_of_acquisitions)
        frontend.saveSignal.connect(self.save_spectrum)
        frontend.setWorkDirSignal.connect(self.set_working_folder)
        frontend.createTodayFolderSignal.connect(self.create_folder)
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

    