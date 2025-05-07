# -*- coding: utf-8 -*-
"""
Created on Thu May 12, 2022

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland
"""

import os
import numpy as np
from datetime import datetime
from timeit import default_timer as timer
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from pyqtgraph.dockarea import Dock, DockArea
from PIL import Image
from tkinter import filedialog
import tkinter as tk
import time as tm
import piezo_stage_xy_GUI
import viewbox_tools

import pco_camera_toolbox as pco
import drift_correction_toolbox as drift

#=====================================

# Initialize camera and useful variables

#=====================================

cam = pco.pco_camera()
# cam = pco.pco_camera(debug = 'verbose', timestamp_flag = 'on')
# cam = pco.pco_camera(debug = 'extra verbose', timestamp_flag = 'on')
initial_binning = 4
initial_pixel_size = 260 # in nm (with 4x4 binning)
initial_exp_time = 150.0 # in ms
initial_starting_col = 1 
initial_starting_row = 1
initial_final_col = 512 # with 4x4 binning
initial_final_row = 512 # with 4x4 binning
initial_roi_list = [initial_starting_col, initial_starting_row, initial_final_col, initial_final_row]
initial_filepath = 'D:\\daily_data\\pco_camera_pictures' # save in SSD for fast and daily use
initial_filename = 'image_pco'

# timers
tempTimer_update = 10000 # in ms
initial_tracking_period = 500 # in ms
initial_bix_size = 11 # always odd number pixels
initial_number_of_boxes = 8
driftbox_length = 10.0 # in seconds

# PID constants
# DO NOT CHANGE
initial_kp = 0.1 # proportinal factor of the PID
initial_ki = 0.015 # integral factor of the PID
initial_kd = 0.005 # derivative factor of the PID
# working values (tested with tracking periods of 100, 200, 300 and 500 ms)
# the shorter the time, the longer the transitory period
# initial_kp = 0.2 # proportinal factor of the PID
# initial_ki = 0.03 # integral factor of the PID
# initial_kd = 0.01 # derivative factor of the PID
# correction threshold in um
# above this value (distance) the software starts to apply a correction
# to compensate the drift
initial_correction_threshold = 0.000

#=====================================

# GUI / Frontend definition

#=====================================
   
class Frontend(QtGui.QFrame):

    liveViewSignal = pyqtSignal(bool, float)
    closeSignal = pyqtSignal(bool)
    roiChangedSignal = pyqtSignal(bool, list)
    exposureChangedSignal = pyqtSignal(bool, float)
    cameraTempMonitorSignal = pyqtSignal(bool)
    binningChangedSignal = pyqtSignal(bool, int, float)
    trackingPeriodChangedSignal = pyqtSignal(bool, int)
    takePictureSignal = pyqtSignal(bool, float)
    saveSignal = pyqtSignal()
    setWorkDirSignal = pyqtSignal()
    lockAndTrackSignal = pyqtSignal(bool)
    dataFiducialsSignal = pyqtSignal(int, dict, bool)
    savedriftSignal = pyqtSignal()
    correctDriftSignal = pyqtSignal(bool)
    pidParamChangedSignal = pyqtSignal(bool, list)
    correctionThresholdChangedSignal = pyqtSignal(float)
    
    def __init__(self, piezo_frontend, show_piezo_subGUI = True, main_app = True, \
                 connect_to_piezo_module = True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # set the title of the window
        title = "XY stabilization module"
        self.setWindowTitle(title)
        self.setGeometry(5, 30, 1900, 600) # x pos, y pos, width, height
        self.sensor_temp = 0.00
        self.cam_temp = 0.00
        self.power_temp = 0.00
        self.image = np.array([])
        self.roi = {}
        self.correct_drift_flag = False
        self.main_app = main_app
        self.connect_to_piezo_module = connect_to_piezo_module
        self.piezo_frontend = piezo_frontend
        self.setUpGUI(show_piezo_subGUI)
        return
            
    def setUpGUI(self, show_piezo_subGUI):
        # Image
        self.imageWidget = pg.GraphicsLayoutWidget()
        self.vb = self.imageWidget.addPlot()
        self.vb.setAspectLocked()
        self.img = pg.ImageItem()
        self.img.setOpts(axisOrder = 'row-major')
        self.vb.addItem(self.img)
        self.hist = pg.HistogramLUTItem(image = self.img, levelMode = 'mono')
        self.hist.gradient.loadPreset('grey')
        self.hist.disableAutoHistogramRange()
        # 'thermal', 'flame', 'yellowy', 'bipolar', 'spectrum',
        # 'cyclic', 'greyclip', 'grey'
        self.hist.vb.setLimits(yMin = 0, yMax = 65536) # 16-bit camera
        self.imageWidget.addItem(self.hist, row = 0, col = 1)
        # if performance is an issue, try scaleToImage
        # add centers of fiducials over camera image
        self.xy_fiducials = pg.ScatterPlotItem(size = 5, pen = pg.mkPen('r', width = 1), 
                                         symbol = 'o', brush = pg.mkBrush('r'))
        self.xy_fiducials.setZValue(2) # Ensure scatterPlotItem is always at top
        self.vb.addItem(self.xy_fiducials)
        
        # autolevel of image instesity
        self.autolevel_tickbox = QtGui.QCheckBox('Autolevel')
        self.initial_autolevel_state = True
        self.autolevel_tickbox.setChecked(self.initial_autolevel_state)
        self.autolevel_tickbox.setText('Autolevel')
        self.autolevel_tickbox.stateChanged.connect(self.autolevel)
        self.autolevel_bool = self.initial_autolevel_state

        # Working folder and filename
        self.working_dir_button = QtGui.QPushButton('Select directory')
        self.working_dir_button.clicked.connect(self.set_working_dir)
        self.working_dir_button.setStyleSheet(
            "QPushButton:pressed { background-color: red; }")
        self.working_dir_label = QtGui.QLabel('Working directory:')
        self.filepath = initial_filepath
        self.working_dir_path = QtGui.QLineEdit(self.filepath)
        self.working_dir_path.setReadOnly(True) 

        # Buttons and labels
        self.take_picture_button = QtGui.QPushButton('Take a picture')
        self.take_picture_button.setCheckable(False)
        self.take_picture_button.clicked.connect(self.take_picture_button_check)
        self.take_picture_button.setStyleSheet(
            "QPushButton:pressed { background-color: red; }")
        
        self.save_picture_button = QtGui.QPushButton('Save picture')
        self.save_picture_button.clicked.connect(self.save_button_check)
        self.save_picture_button.setStyleSheet(
            "QPushButton:pressed { background-color: red; }")
        
        self.live_view_button = QtGui.QPushButton('Live view')
        self.live_view_button.setCheckable(True)
        self.live_view_button.clicked.connect(self.liveview_button_check)
        self.live_view_button.setStyleSheet(
            "QPushButton:pressed { background-color: red; }"
            "QPushButton::checked { background-color: red; }")

        # Exposure time
        exp_time_label = QtGui.QLabel('Exposure time (ms):')
        self.exp_time_edit = QtGui.QLineEdit(str(initial_exp_time))
        self.exp_time_edit_previous = float(self.exp_time_edit.text())
        self.exp_time_edit.editingFinished.connect(self.exposure_changed_check)
        self.exp_time_edit.setValidator(QtGui.QDoubleValidator(0.01, 5000.00, 2))
        self.exp_time_edit.setToolTip('Minimum is 10 µs. Maximum is 5 s.')
        
        # Camera temperature timer checkbox       
        self.cam_temp_tickbox = QtGui.QCheckBox('Monitor camera temperature')
        self.initial_cam_temp_tickbox_state = False
        self.cam_temp_tickbox.setChecked(self.initial_cam_temp_tickbox_state)
        self.cam_temp_tickbox.setText('Monitor camera temp.')
        self.cam_temp_tickbox.stateChanged.connect(self.monitor_cam_temp)
        self.cam_temp_bool = self.initial_cam_temp_tickbox_state

        # Pixel size
        pixel_size_label = QtGui.QLabel('Pixel size (nm):')
        self.pixel_size_value = QtGui.QLabel(str(initial_pixel_size))
        self.pixel_size_value.setToolTip('Pixel size at sample plane.')
        self.pixel_size = int(self.pixel_size_value.text())

        # Binning
        binning_label = QtGui.QLabel('Binning (pixels):')
        self.binning_edit = QtGui.QLineEdit(str(initial_binning))
        self.binning_edit.setToolTip('Restricted to squared binning. Options are 1x1, 2x2 and 4x4.')
        self.binning_previous = int(self.binning_edit.text())
        self.binning_edit.editingFinished.connect(self.binning_changed_check)
        self.binning_edit.setValidator(QtGui.QIntValidator(1, 4))
        
        # Sensor ROI entry
        define_roi = QtGui.QLabel('Define ROI:')
        starting_col_label = QtGui.QLabel('Starting col (pixel):')
        final_col_label = QtGui.QLabel('Final col (pixel):')
        starting_row_label = QtGui.QLabel('Starting row (pixel):')
        final_row_label = QtGui.QLabel('Final row (pixel):')
        self.starting_col = QtGui.QLineEdit(str(initial_roi_list[0]))
        self.final_col = QtGui.QLineEdit(str(initial_roi_list[2]))
        self.starting_row = QtGui.QLineEdit(str(initial_roi_list[1]))
        self.final_row = QtGui.QLineEdit(str(initial_roi_list[3]))
        self.starting_col_previous = int(self.starting_col.text())
        self.final_col_previous = int(self.final_col.text())
        self.starting_row_previous = int(self.starting_row.text())
        self.final_row_previous = int(self.final_row.text())
        self.roi_list_previous = [self.starting_col_previous, self.starting_row_previous, \
                                  self.final_col_previous, self.final_row_previous]
        self.starting_col.editingFinished.connect(self.roi_changed_check)
        self.final_col.editingFinished.connect(self.roi_changed_check)
        self.starting_row.editingFinished.connect(self.roi_changed_check)
        self.final_row.editingFinished.connect(self.roi_changed_check)
        self.starting_col.setValidator(QtGui.QIntValidator(1, 2048))
        self.final_col.setValidator(QtGui.QIntValidator(1, 2048))
        self.starting_row.setValidator(QtGui.QIntValidator(1, 2048))
        self.final_row.setValidator(QtGui.QIntValidator(1, 2048))
        
        # tracking fiducials / ROIs
        number_of_fiducials_label = QtGui.QLabel('Number of fiducials:')
        self.number_of_fiducials_value = QtGui.QLineEdit(str(initial_number_of_boxes))
        box_size_label = QtGui.QLabel('Box size (pixels):')
        self.box_size_value = QtGui.QLineEdit(str(initial_bix_size))
        self.box_size_value.setValidator(QtGui.QIntValidator(1, 999))
        self.box_size_value.setToolTip('Restricted to odd numbers. Good starting point is box_size ~ 1 µm (use pixel size).')
        self.create_ROIs_button = QtGui.QPushButton('Create ROIs')
        self.create_ROIs_button.setCheckable(True)
        self.create_ROIs_button.clicked.connect(self.create_ROIs)
        self.create_ROIs_button.setStyleSheet(
            "QPushButton:pressed { background-color: red; }"
            "QPushButton::checked { background-color: steelblue; }")
        # lock and track the fiducials
        self.lock_ROIs_button = QtGui.QPushButton('Lock and Track')
        self.lock_ROIs_button.setToolTip('Lock ROIs\' position and start to track the fiducial markers.')
        self.lock_ROIs_button.setCheckable(True)
        self.lock_ROIs_button.clicked.connect(self.lock_and_track)
        self.lock_ROIs_button.setStyleSheet(
            "QPushButton:pressed { background-color: red; }"
            "QPushButton::checked { background-color: limegreen; }")
        self.correct_drift_button = QtGui.QPushButton('Stabilize xy position')
        self.correct_drift_button.setToolTip('If active, drift will be corrected. Leave inactive for tracking only.')
        self.correct_drift_button.setCheckable(True)
        self.correct_drift_button.clicked.connect(self.correct_drift_status)
        self.correct_drift_button.setStyleSheet(
            "QPushButton:pressed { background-color: red; }"
            "QPushButton::checked { background-color: orange; }")

        # tracking period
        self.tracking_period_label = QtGui.QLabel('Tracking period (s):')
        self.tracking_period_value = QtGui.QLineEdit(str(initial_tracking_period/1000))
        self.tracking_period = initial_tracking_period
        self.tracking_period_value.setToolTip('Period to measure fiducial markers\' position.')
        self.tracking_period_value.editingFinished.connect(self.tracking_period_changed_check)
        
        # drift threshold
        self.correction_threshold_label = QtGui.QLabel('Drift threshold (μm):')
        self.correction_threshold_value = QtGui.QLineEdit(str(initial_correction_threshold))
        self.correction_threshold_value.editingFinished.connect(self.correction_threshold_changed)
        self.correction_threshold_value.setToolTip('Above this threshold the drift correction will be applied.')
        self.correction_threshold = initial_correction_threshold
        
        # save drift trace button
        self.savedrift_tickbox = QtGui.QCheckBox('Save drift curve')
        self.initial_state_savedrift = False
        self.savedrift_tickbox.setChecked(self.initial_state_savedrift)
        self.savedrift_tickbox.setText('Save drift data when unlocking')
        self.savedrift_tickbox.stateChanged.connect(self.save_drift_trace)
        self.savedrift_bool = self.initial_state_savedrift
        
        # PID parameters
        self.pid_label = QtGui.QLabel('PID parameters')
        self.kp_label = QtGui.QLabel('K_proportional:')
        self.kp_value = QtGui.QLineEdit(str(initial_kp))
        self.kp_value.editingFinished.connect(self.pid_param_changed_check)
        self.ki_label = QtGui.QLabel('K_integrative:')
        self.ki_value = QtGui.QLineEdit(str(initial_ki))
        self.ki_value.editingFinished.connect(self.pid_param_changed_check)
        self.kd_label = QtGui.QLabel('K_derivative:')
        self.kd_value = QtGui.QLineEdit(str(initial_kd))
        self.kd_value.editingFinished.connect(self.pid_param_changed_check)
        self.pid_param_list = [initial_kp, initial_ki, initial_kd]
        # position vs time of fiducials
        driftWidget = pg.GraphicsLayoutWidget()
        self.driftPlot = driftWidget.addPlot(title = "XY drift (red X, blue Y)")
        self.driftPlot.showGrid(x = True, y = True)
        self.driftPlot.setLabel('left', 'Shift (μm)')
        self.driftPlot.setLabel('bottom', 'Time (s)')

        # Live view parameters dock
        self.liveviewWidget = QtGui.QWidget()
        layout_liveview = QtGui.QGridLayout()
        self.liveviewWidget.setLayout(layout_liveview)
        # folder and filename button
        layout_liveview.addWidget(self.working_dir_button, 0, 0, 1, 2)
        layout_liveview.addWidget(self.working_dir_label, 1, 0, 1, 2)
        layout_liveview.addWidget(self.working_dir_path, 2, 0, 1, 2)
        # place Live view button and Take a Picture button
        layout_liveview.addWidget(self.live_view_button, 5, 0, 1, 2)
        layout_liveview.addWidget(self.take_picture_button, 6, 0, 1, 2)
        layout_liveview.addWidget(self.save_picture_button, 7, 0, 1, 2)
        # Exposure time box
        layout_liveview.addWidget(exp_time_label,              8, 0)
        layout_liveview.addWidget(self.exp_time_edit,          8, 1)
        # auto level
        layout_liveview.addWidget(self.autolevel_tickbox,      9, 0)
        # Temp timer
        layout_liveview.addWidget(self.cam_temp_tickbox, 10, 0)
        # pixel size
        layout_liveview.addWidget(pixel_size_label,      11, 0)
        layout_liveview.addWidget(self.pixel_size_value,        11, 1)
        # binning
        layout_liveview.addWidget(binning_label,        12, 0)
        layout_liveview.addWidget(self.binning_edit,        12, 1)
        # ROI box
        layout_liveview.addWidget(define_roi,      13, 0)
        layout_liveview.addWidget(starting_col_label,      14, 0)
        layout_liveview.addWidget(self.starting_col,      14, 1)
        layout_liveview.addWidget(final_col_label,      15, 0)
        layout_liveview.addWidget(self.final_col,      15, 1)
        layout_liveview.addWidget(starting_row_label,      16, 0)
        layout_liveview.addWidget(self.starting_row,      16, 1)
        layout_liveview.addWidget(final_row_label,      17, 0)
        layout_liveview.addWidget(self.final_row,      17, 1)       

        # fiducials selection dock
        self.fiducialsWidget = QtGui.QWidget()
        layout_fiducials = QtGui.QGridLayout()
        self.fiducialsWidget.setLayout(layout_fiducials)
        # number of fiducials
        layout_fiducials.addWidget(number_of_fiducials_label,      0, 0)
        layout_fiducials.addWidget(self.number_of_fiducials_value,      0, 1)
        layout_fiducials.addWidget(box_size_label,      1, 0)
        layout_fiducials.addWidget(self.box_size_value,      1, 1)
        layout_fiducials.addWidget(self.create_ROIs_button,         2, 0, 1, 2)
        layout_fiducials.addWidget(self.lock_ROIs_button,         3, 0, 1, 2)
        layout_fiducials.addWidget(self.correct_drift_button,         4, 0, 1, 2)
        layout_fiducials.addWidget(self.tracking_period_label,         5, 0)
        layout_fiducials.addWidget(self.tracking_period_value,         5, 1)
        layout_fiducials.addWidget(self.correction_threshold_label,         6, 0)
        layout_fiducials.addWidget(self.correction_threshold_value,         6, 1)
        layout_fiducials.addWidget(self.pid_label,         7, 0)
        layout_fiducials.addWidget(self.kp_label,         8, 0)
        layout_fiducials.addWidget(self.kp_value,         8, 1)
        layout_fiducials.addWidget(self.ki_label,         9, 0)
        layout_fiducials.addWidget(self.ki_value,         9, 1)
        layout_fiducials.addWidget(self.kd_label,         10, 0)
        layout_fiducials.addWidget(self.kd_value,         10, 1)
        # save drift
        layout_fiducials.addWidget(self.savedrift_tickbox,      11, 0)
        
        # Place layouts and boxes
        dockArea = DockArea()
        hbox = QtGui.QHBoxLayout(self)

        viewDock = Dock('Camera', size = (20, 200)) # optical format is squared
        viewDock.addWidget(self.imageWidget)
        dockArea.addDock(viewDock)
        
        driftDock = Dock('Drift vs time', size = (20, 20))
        driftDock.addWidget(driftWidget)
        dockArea.addDock(driftDock, 'below', viewDock)
        
        liveview_paramDock = Dock('Live view parameters', size = (1, 20))
        liveview_paramDock.addWidget(self.liveviewWidget)
        dockArea.addDock(liveview_paramDock, 'right', viewDock)
        
        fiducialsDock = Dock('Fiducials selection', size = (20, 20))
        fiducialsDock.addWidget(self.fiducialsWidget)
        dockArea.addDock(fiducialsDock, 'right', liveview_paramDock)

        ## Add Piezo stage GUI module if asked
        self.piezoWidget = self.piezo_frontend
        if show_piezo_subGUI:
            piezoDock = Dock('Piezo stage')
            piezoDock.addWidget(self.piezoWidget)
            dockArea.addDock(piezoDock , 'right', fiducialsDock)
        
        hbox.addWidget(dockArea)
        self.setLayout(hbox)
        return
    
    def pid_param_changed_check(self):
        kp = float(self.kp_value.text())
        ki = float(self.ki_value.text())
        kd = float(self.kd_value.text())
        pid_param_list = [kp, ki, kd]
        if pid_param_list != self.pid_param_list:
            self.pid_param_list = pid_param_list
            if self.lock_ROIs_button.isChecked():
                self.pidParamChangedSignal.emit(True, pid_param_list)
            else:
                self.pidParamChangedSignal.emit(False, pid_param_list)
        return       
    
    def correction_threshold_changed(self):
        correction_threshold = float(self.correction_threshold_value.text()) # in nm
        if correction_threshold != self.correction_threshold:
            self.correction_threshold = correction_threshold
            self.correctionThresholdChangedSignal.emit(self.correction_threshold)
        return
    
    def create_ROIs(self):
        # create ROIs for the fiducial markers
        self.number_of_fiducials = int(self.number_of_fiducials_value.text())
        self.box_size = int(self.box_size_value.text())
        if self.create_ROIs_button.isChecked():
            for i in range(self.number_of_fiducials):
                x_pos = round(self.roi_list_previous[2]/2)
                y_pos = round(self.roi_list_previous[3]/2) + i*self.box_size
                ROIpos = (x_pos, y_pos) # (0.5*numberofPixels - 0.5*box_size, 0.5*numberofPixels - 0.5*box_size)
                self.roi[i] = viewbox_tools.ROI_squared(self.box_size, self.vb, ROIpos,
                                                 handlePos = (1, 1),
                                                 handleCenter = (0, 0),
                                                 scaleSnap = True,
                                                 translateSnap = True)
        else:
            for i in range(self.number_of_fiducials):
                self.vb.removeItem(self.roi[i])
                self.roi[i].hide()
            self.roi = {}
        return

    def lock_and_track(self):
        if self.lock_ROIs_button.isChecked():
            if self.create_ROIs_button.isChecked():
                self.driftPlot.clear()
                self.lockAndTrackSignal.emit(True)
                self.data_ROI = {}
                self.coord_ROI = {}
                N = int(driftbox_length*1000/self.tracking_period)
                self.error_to_plot = np.zeros((N, 2))
                self.time_to_plot = np.zeros(N)
            else:
                print('Warning! Lock and Track can only be used if fiducials\' ROIs have been created.')
        else:
            self.lockAndTrackSignal.emit(False)
            if self.savedrift_bool:
                self.savedriftSignal.emit()
            self.xy_fiducials.clear()
        return
    
    def correct_drift_status(self):
        if self.correct_drift_button.isChecked():
            self.correct_drift_flag = True
            self.correctDriftSignal.emit(self.correct_drift_flag)
            self.lock_and_track()
        else:
            self.correct_drift_flag = False
            self.correctDriftSignal.emit(self.correct_drift_flag)
        return
    
    def retrieve_fiducials_data(self):
        for i in range(self.number_of_fiducials):
            (self.data_ROI[i], \
             self.coord_ROI[i]) = self.roi[i].getArrayRegion(self.image, \
                                                            self.img, \
                                                            axis = (1, 0), \
                                                            returnMappedCoords = True)
        self.dataFiducialsSignal.emit(self.number_of_fiducials, self.coord_ROI, \
                                      self.savedrift_bool)
        return

    @pyqtSlot(dict, np.ndarray, float)
    def receive_fitted_data(self, xy_pos_pixel_relative, error, timestamp):
        array_of_x_pos_pixels = []
        array_of_y_pos_pixels = []
        # plot xy position of fiducials vs time
        self.error_to_plot = np.roll(self.error_to_plot, -1, axis = 0)
        self.time_to_plot = np.roll(self.time_to_plot, -1)
        self.error_to_plot[-1,:] = error
        self.time_to_plot[-1] = timestamp
        self.driftPlot.clear()
        self.driftPlot.plot(x = self.time_to_plot, y = self.error_to_plot[:, 0], \
                            pen = pg.mkPen('r'))
        self.driftPlot.plot(x = self.time_to_plot, y = self.error_to_plot[:, 1], \
                            pen = pg.mkPen('b'))
        self.driftPlot.setXRange(timestamp - driftbox_length, timestamp)
        ymin = min(np.mean(self.error_to_plot, axis=1) - 5*np.std(self.error_to_plot, ddof=1, axis=1))
        ymax = max(np.mean(self.error_to_plot, axis=1) + 5*np.std(self.error_to_plot, ddof=1, axis=1))
        self.driftPlot.setYRange(ymin, ymax)
        for i in range(self.number_of_fiducials):
            # draw center of fiducials, convert um to pixels
            pixel_size_um = self.pixel_size/1000
            array_of_x_pos_pixels.append(xy_pos_pixel_relative[i][1]/pixel_size_um)
            array_of_y_pos_pixels.append(xy_pos_pixel_relative[i][0]/pixel_size_um)
        self.xy_fiducials.setData(x = array_of_x_pos_pixels, y = array_of_y_pos_pixels)
        return

    def tracking_period_changed_check(self):
        new_tracking_period = int(float(self.tracking_period_value.text())*1000)
        if new_tracking_period != self.tracking_period:
            self.tracking_period = new_tracking_period
            if self.lock_ROIs_button.isChecked():
                self.trackingPeriodChangedSignal.emit(True, self.tracking_period)
            else:
                self.trackingPeriodChangedSignal.emit(False, self.tracking_period)
        return
    
    def roi_changed_check(self):
        starting_col = int(self.starting_col.text())
        final_col = int(self.final_col.text())
        starting_row = int(self.starting_row.text())
        final_row = int(self.final_row.text())
        roi_list = [starting_col, starting_row, final_col, final_row]
        if roi_list != self.roi_list_previous:
            self.roi_list_previous = roi_list
            if self.live_view_button.isChecked():
                self.roiChangedSignal.emit(True, roi_list)
            else:
                self.roiChangedSignal.emit(False, roi_list)
        return
    
    def exposure_changed_check(self):
        exposure_time_ms = float(self.exp_time_edit.text()) # in ms
        if exposure_time_ms != self.exp_time_edit_previous:
            self.exp_time_edit_previous = exposure_time_ms
            if self.live_view_button.isChecked():
                self.exposureChangedSignal.emit(True, exposure_time_ms)
            else:
                self.exposureChangedSignal.emit(False, exposure_time_ms)
        return
            
    def binning_changed_check(self):
        binning = int(self.binning_edit.text())
        if binning != self.binning_previous:
            self.binning_previous = binning
            self.pixel_size = initial_pixel_size*binning
            self.pixel_size_value.setText(str(self.pixel_size))
            new_starting_col = self.roi_list_previous[0]
            new_starting_row = self.roi_list_previous[1]
            new_width = int((self.roi_list_previous[2] - new_starting_col + 1)/binning) - 1
            new_height = int((self.roi_list_previous[3] - new_starting_row + 1)/binning) - 1
            new_final_col = self.roi_list_previous[0] + new_width
            new_final_row = self.roi_list_previous[1] + new_height
            self.starting_col.setText(str(new_starting_col))
            self.starting_row.setText(str(new_starting_row))
            self.final_col.setText(str(new_final_col))
            self.final_row.setText(str(new_final_row))
            if self.live_view_button.isChecked():
                self.binningChangedSignal.emit(True, binning, self.pixel_size)
            else:
                self.binningChangedSignal.emit(False, binning, self.pixel_size)
            self.roi_changed_check()
        return
    
    def take_picture_button_check(self):
        exposure_time_ms = float(self.exp_time_edit.text()) # in ms
        if self.live_view_button.isChecked():
            self.takePictureSignal.emit(True, exposure_time_ms)
        else:
            self.takePictureSignal.emit(False, exposure_time_ms)            
        return
        
    def save_button_check(self):
        if self.save_picture_button.isChecked:
           self.saveSignal.emit()
        return
    
    def liveview_button_check(self):
        exposure_time_ms = float(self.exp_time_edit.text()) # in ms
        if self.live_view_button.isChecked():
            self.liveViewSignal.emit(True, exposure_time_ms)
        else:
            self.liveViewSignal.emit(False, exposure_time_ms)
        return

    def set_working_dir(self):
        self.setWorkDirSignal.emit()
        return

    def autolevel(self):
        if self.autolevel_tickbox.isChecked():
            self.autolevel_bool = True
            print('Autolevel on')
        else:
            self.autolevel_bool = False
            print('Autolevel off')
        return
    
    def monitor_cam_temp(self):
        if self.cam_temp_tickbox.isChecked():
            self.cam_temp_bool = True
            print('Camera temp. monitor is ON')
        else:
            self.cam_temp_bool = False
            print('Camera temp. monitor is OFF')
        self.cameraTempMonitorSignal.emit(self.cam_temp_bool)
        return
    
    def save_drift_trace(self):
        if self.savedrift_tickbox.isChecked():
            self.savedrift_bool = True
            print('Drift cruve will be saved.')
        else:
            self.savedrift_bool = False
            print('Drift cruve will not be saved.')
        return
    
    @pyqtSlot(np.ndarray)
    def get_image(self, image):
        self.image = image
        self.img.setImage(self.image, autoLevels = self.autolevel_bool)
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
            print('Closing GUI...')
            self.close()
            self.closeSignal.emit(self.main_app)
            tm.sleep(1)
            app.quit()
        else:
            event.ignore()
            print('Back in business...')    
        return
    
    def make_connections(self, backend):
        backend.imageSignal.connect(self.get_image)
        backend.filePathSignal.connect(self.get_file_path)
        backend.getFiducialsDataSignal.connect(self.retrieve_fiducials_data)
        backend.sendFittedDataSignal.connect(self.receive_fitted_data)
        if self.connect_to_piezo_module:
            backend.piezoWorker.make_connections(self.piezoWidget)
        return
    
#=====================================

# Controls / Backend definition

#=====================================

class Backend(QtCore.QObject):

    imageSignal = pyqtSignal(np.ndarray)
    getFiducialsDataSignal = pyqtSignal()
    sendFittedDataSignal = pyqtSignal(dict, np.ndarray, float)
    filePathSignal = pyqtSignal(str)
    
    def __init__(self, piezo, piezo_backend, connect_to_piezo_module = True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect_to_piezo_module = connect_to_piezo_module
        self.piezo_stage = piezo
        self.piezoWorker = piezo_backend
        self.viewTimer = QtCore.QTimer()
        # configure the connection to allow queued executions to avoid interruption of previous calls
        self.viewTimer.timeout.connect(self.update_view, QtCore.Qt.QueuedConnection) 
        self.tempTimer = QtCore.QTimer()
        self.tempTimer.timeout.connect(self.update_temp)
        self.image_np = None
        self.binning = initial_binning
        self.pixel_size = initial_pixel_size
        self.exposure_time_ms = initial_exp_time
        self.file_path = initial_filepath
        self.trackingTimer = QtCore.QTimer()
        # configure the connection to allow queued executions to avoid interruption of previous calls
        self.trackingTimer.timeout.connect(self.call_pid, QtCore.Qt.QueuedConnection) 
        self.tracking_period = initial_tracking_period
        self.tracking_period_seconds = self.tracking_period/1000
        self.prop_correction = np.array([0, 0])
        self.int_correction = np.array([0, 0])
        self.dev_correction = np.array([0, 0])
        self.last_error_avg = np.array([0, 0])
        self.pid_param_list = [initial_kp, initial_ki, initial_kd]
        self.correct_drift_flag = False
        cam.set_binning(self.binning)
        cam.set_roi(initial_roi_list[0], \
                    initial_roi_list[1], \
                    initial_roi_list[2], \
                    initial_roi_list[3])
        self.correction_threshold = initial_correction_threshold
        self.time_since_epoch = '0'
        return
    
    @pyqtSlot(bool, list)    
    def change_roi(self, livebool, roi_list):
        print('\nROI changed to', roi_list)
        if livebool:
            self.stop_liveview()
            cam.set_roi(roi_list[0], roi_list[1], roi_list[2], roi_list[3])
            self.start_liveview(self.exposure_time_ms)
        else:
            cam.set_roi(roi_list[0], roi_list[1], roi_list[2], roi_list[3])
        return
    
    @pyqtSlot(bool, float)    
    def change_exposure(self, livebool, exposure_time_ms):
        print('\nExposure time changed to', exposure_time_ms, 'ms')
        if livebool:
            self.stop_liveview()
            self.exposure_time_ms = exposure_time_ms # in ms, is float
            self.start_liveview(self.exposure_time_ms)
        else:
            self.exposure_time_ms = exposure_time_ms
            cam.set_exp_time(self.exposure_time_ms)
        return
    
    @pyqtSlot(bool, int, float)    
    def change_binning(self, livebool, binning, pixel_size):
        print('\nBinning changed to %d x %d' % (binning, binning))
        self.binning = binning # is int
        self.pixel_size = pixel_size
        if livebool:
            self.stop_liveview()
            cam.set_binning(self.binning)
            self.start_liveview(self.exposure_time_ms)
        else:
            cam.set_binning(self.binning)
        return
    
    @pyqtSlot(bool, int)
    def change_tracking_period(self, lockbool, new_tracking_period):
        print('\nTracking period changed to {:.3f} s.'.format(new_tracking_period/1000))
        self.tracking_period = new_tracking_period
        if lockbool:
            print('Restarting QtTimer...')
            self.trackingTimer.stop()
            self.trackingTimer.start(self.tracking_period)
        return
    
    @pyqtSlot(bool, list)
    def new_pid_params(self, lockbool, pid_param_list):
        print('\nPID parameters changed to kp={} / ki={} / kd={}.'.format(pid_param_list[0], \
                                                                        pid_param_list[1], \
                                                                        pid_param_list[2]))
        self.pid_param_list = pid_param_list
        if lockbool:
            print('Restarting QtTimer...')
            self.trackingTimer.stop()
            self.trackingTimer.start(self.tracking_period)
        return
    
    @pyqtSlot(bool)
    def start_stop_tracking(self, trackbool):
        if trackbool:
            print('\nLocking and tracking fiducials...')
            # initiating variables
            self.centers = {}
            self.timeaxis = {}
            self.errors_to_save = []
            self.timeaxis_to_save = []
            self.int_correction = 0
            self.dev_correction = 0
            self.last_error_avg = 0
            # t0 initial time
            self.start_tracking_time = timer()
            # ask for ROI data and coordinates
            self.get_fiducials_data()
            # start timer
            self.trackingTimer.start(self.tracking_period)
            self.time_since_epoch = tm.time()
        else:
            self.trackingTimer.stop()
            print('\nUnlocking...')
        return
    
    def get_fiducials_data(self):
        self.getFiducialsDataSignal.emit()
        return
    
    @pyqtSlot(int, dict, bool)
    def receive_roi_fiducials(self, N, roi_coordinates_dict, append_drift_bool):
        self.number_of_fiducials = N
        self.save_drift_data = append_drift_bool
        # set indexes for ROIs
        self.x1 = {}
        self.x2 = {}
        self.y1 = {}
        self.y2 = {}
        self.frame_coordinates = {}
        for i in range(N):
            self.frame_coordinates[i] = roi_coordinates_dict[i]
            self.x1[i] = int(self.frame_coordinates[i][0,0,0])
            self.x2[i] = int(self.frame_coordinates[i][0,-1,0]) + 1
            self.y1[i] = int(self.frame_coordinates[i][1,0,0])
            self.y2[i] = int(self.frame_coordinates[i][1,0,-1]) + 1
            # then frame_intensity is self.image_np[x1:x2, y1:y2]
        print('\nFinding initial coordinates...')
        self.initial_centers, _ = self.fit_fiducials()
        print('Done.')
        return  
      
    def call_pid(self):
        error = {}
        centers, timeaxis = self.fit_fiducials()
        timestamp = timeaxis[0]
        # print(self.centers_previous)
        # print(centers)
        error_x_sum = 0
        error_y_sum = 0
        for i in range(self.number_of_fiducials):
            error_y = self.initial_centers[i][0] - centers[i][0]
            error_x = self.initial_centers[i][1] - centers[i][1]
            error[i] = [error_x, error_y]
            # print(error_x, error_y)
            error_x_sum += error_x
            error_y_sum += error_y
        error_x_avg = error_x_sum/self.number_of_fiducials
        error_y_avg = error_y_sum/self.number_of_fiducials
        error_avg = np.array([error_x_avg, error_y_avg])
        # uncomment for debugging
        # print('\n err_x %.0f nm / err_y %.0f nm' % (error_x_avg*1000, error_y_avg*1000))
        # send position of all fiducials to Frontend
        # first line is to check that all fiducials drift in the same way
        # be aware that if uncommented you should change the signal type slot also
        # self.sendFittedDataSignal.emit(centers, error, timeaxis)
        self.sendFittedDataSignal.emit(centers, error_avg, timestamp)
        # store data to save drift vs time when the Lock and Track option is released
        if self.save_drift_data:
            self.timeaxis_to_save.append(timestamp)
            self.errors_to_save.append(error_avg)
        # now correct drift if button is checked
        if self.correct_drift_flag:
            # PID calculation
            # assign parameters
            kp = self.pid_param_list[0]
            ki = self.pid_param_list[1]
            kd = self.pid_param_list[2]
            # proportional term
            self.prop_correction = kp*error_avg
            # integral term
            self.int_correction = self.int_correction + ki*error_avg*self.tracking_period_seconds
            # derivative term
            self.dev_correction = self.dev_correction + \
                kd*(error_avg - self.last_error_avg)/self.tracking_period_seconds
            self.last_error_avg = error_avg
            # calculate correction in um
            correction = self.prop_correction + self.int_correction + self.dev_correction
            # call function to correct
            self.correct_drift(error_avg, correction)
        return
    
    def fit_fiducials(self):
        centers = {}
        timeaxis = {}
        # find centers for all fiducials
        start_time = tm.time()
        for i in range(self.number_of_fiducials):
            x1 = self.x1[i]
            x2 = self.x2[i]
            y1 = self.y1[i]
            y2 = self.y2[i]
            frame_intensity = self.image_np[x1:x2, y1:y2]
            x_fitted, \
            y_fitted, \
            w0x_fitted, \
            w0y_fitted = drift.fit_with_gaussian(frame_intensity, \
                                                 self.frame_coordinates[i], \
                                                 self.pixel_size, \
                                                 self.pixel_size)
            centers[i] = np.array([x_fitted, y_fitted])
            timeaxis[i] = timer() - self.start_tracking_time
        end_time = tm.time()
        print(f'Single-threaded time: {end_time - start_time:.3f} s')
        return centers, timeaxis
    
    def correct_drift(self, error, correction):
        # make float32 to avoid crashing the module
        error_x = float(error[0])
        error_y = float(error[1])
        correction_x = float(correction[0])
        correction_y = float(correction[1])
        # use the worker to send the instructions
        # only if the drift correction is larger than a threshold
        if abs(error_x) > self.correction_threshold:
            # print('correction x %.0f nm ' % (correction_x*1000))
            self.piezoWorker.move_relative('x', correction_x)
        if abs(error_y) > self.correction_threshold:
            # print('correction y %.0f nm' % (correction_y*1000))
            self.piezoWorker.move_relative('y', correction_y)
        return
    
    @pyqtSlot(bool, float)
    def take_picture(self, livebool, exposure_time_ms):
        print('\nPicture taken at', datetime.now())
        self.exposure_time_ms = exposure_time_ms # in ms, is float
        if livebool:
            self.stop_liveview()
        cam.set_exp_time(self.exposure_time_ms)
        cam.config_recorder()
        self.image_np, metadata = cam.get_image()
        if self.image_np is not None:
            cam.stop()
            self.imageSignal.emit(self.image_np)            
        return
    
    @pyqtSlot(bool, float)
    def liveview(self, livebool, exposure_time_ms):
        self.exposure_time_ms = exposure_time_ms # in ms, is float
        if livebool:
            self.start_liveview(self.exposure_time_ms)
        else:
            self.stop_liveview()
        return
    
    def start_liveview(self, exposure_time_ms):
        print('\nLive view started at', datetime.now())
        self.exposure_time_ms = exposure_time_ms # in ms, is float
        cam.set_exp_time(self.exposure_time_ms)
        cam.config_recorder()
        self.viewTimer.start(round(self.exposure_time_ms)) # ms
        return
            
    def update_view(self):
        # Image update while in Live view mode
        self.image_np, metadata = cam.get_image()
        # stop sending the image to the frontend (no liveview available)
        # when the stabilization is ON. It is not needed actually
        if not self.correct_drift_flag:
            self.imageSignal.emit(self.image_np)
        return
    
    def update_temp(self):
        # Update temp of the camera
        sensor_temp, cam_temp, power_temp = cam.get_temp()
        print('\npco camera temperatures retrieved at', datetime.now())
        print('Sensor temp: %.1f °C' % sensor_temp)
        print('Camera temp: %.1f °C' % cam_temp)
        print('Electronics temp: %.1f °C' % power_temp)
        return
    
    @pyqtSlot(bool)   
    def camera_temp_timer(self, monitor_bool):
        if monitor_bool:
            print('Monitoring pco.camera temperature each {:.1f} s.'.format(tempTimer_update/1000))
            self.tempTimer.start(tempTimer_update) # ms
        else:
            self.tempTimer.stop()
        return
    
    def stop_liveview(self):
        print('\nLive view stopped at', datetime.now())
        cam.stop()
        self.viewTimer.stop()
        return
    
    @pyqtSlot()    
    def save_drift_curve(self):
        # prepare the array to be saved
        # structure of the file will be
        # first col = time, in s
        # second and third col = x and y average position error of all fiducials, in um
        M = np.array(self.timeaxis_to_save).shape[0]
        data_to_save = np.zeros((M, 3))
        data_to_save[:, 0] = self.timeaxis_to_save
        data_to_save[:, 1:] = self.errors_to_save
        # create filename
        timestr = datetime.today().strftime('%Y-%m-%d_%H-%M-%S')
        filename = "drift_curve_xy_" + timestr + ".dat"
        full_filename = os.path.join(self.file_path, filename)
        # save
        header_txt = 'time_since_epoch %s s\ntracking_period %i s\ntime x_avg_error y_avg_error\ns um um' % (str(self.time_since_epoch), self.tracking_period)
        np.savetxt(full_filename, data_to_save, fmt='%.3f', header=header_txt)
        print('Drift curve %s saved' % filename)
        return
    
    @pyqtSlot(bool)
    def set_correct_drift_flag(self, flag):
        self.correct_drift_flag = flag
        print('>>> xy stablization set to: %s' % flag)
        return    
    
    @pyqtSlot(float)
    def correction_threshold_changed(self, new_correction_threshold):
        print('Correction threshold changed to {:.0f} nm'.format(new_correction_threshold))
        self.correction_threshold = new_correction_threshold
        return
    
    @pyqtSlot()    
    def save_picture(self):
        timestr = datetime.today().strftime('%Y-%m-%d_%H-%M-%S')
        filename = "image_pco_" + timestr + ".tiff"
        full_filename = os.path.join(self.file_path, filename)
        image_to_save = Image.fromarray(self.image_np)
        image_to_save.save(full_filename) 
        print('Image %s saved' % filename)
        return
      
    @pyqtSlot()    
    def set_working_folder(self):
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askdirectory()
        if not file_path:
            print('No folder selected!')
        else:
            self.file_path = file_path
            self.filePathSignal.emit(self.file_path)
        return
    
    @pyqtSlot(bool)
    def close_backend(self, main_app = True):
        print('Stopping pco camera...')
        cam.stop()
        print('Stopping QtTimers...')
        self.viewTimer.stop()
        self.tempTimer.stop()
        if main_app:
            self.piezoWorker.updateTimer.stop()
            print('Shutting down piezo stage...')
            self.piezo_stage.shutdown()
            tm.sleep(5)
            print('Exiting thread...')
            workerThread.exit()
        return
    
    def make_connections(self, frontend):
        frontend.roiChangedSignal.connect(self.change_roi)
        frontend.cameraTempMonitorSignal.connect(self.camera_temp_timer)
        frontend.exposureChangedSignal.connect(self.change_exposure)
        frontend.binningChangedSignal.connect(self.change_binning)
        frontend.trackingPeriodChangedSignal.connect(self.change_tracking_period)
        frontend.liveViewSignal.connect(self.liveview) 
        frontend.takePictureSignal.connect(self.take_picture)
        frontend.closeSignal.connect(self.close_backend)
        frontend.saveSignal.connect(self.save_picture)
        frontend.setWorkDirSignal.connect(self.set_working_folder)
        frontend.lockAndTrackSignal.connect(self.start_stop_tracking)
        frontend.dataFiducialsSignal.connect(self.receive_roi_fiducials)
        frontend.savedriftSignal.connect(self.save_drift_curve)
        frontend.correctDriftSignal.connect(self.set_correct_drift_flag)
        frontend.pidParamChangedSignal.connect(self.new_pid_params)
        frontend.correctionThresholdChangedSignal.connect(self.correction_threshold_changed)
        if self.connect_to_piezo_module:
            frontend.piezoWidget.make_connections(self.piezoWorker)
        return
    
#=====================================

#  Main program

#=====================================        

if __name__ == '__main__':
    # make application
    app = QtGui.QApplication([])
    
    # init stage
    piezo = piezo_stage_xy_GUI.piezo_stage_xy     
    piezo_frontend = piezo_stage_xy_GUI.Frontend()
    piezo_backend = piezo_stage_xy_GUI.Backend(piezo)
    
    # create both classes
    gui = Frontend(piezo_frontend)
    worker = Backend(piezo, piezo_backend)
    
    # thread that run in background
    workerThread = QtCore.QThread()
    worker.viewTimer.moveToThread(workerThread)
    worker.tempTimer.moveToThread(workerThread)
    worker.trackingTimer.moveToThread(workerThread)
    worker.piezoWorker.updateTimer.moveToThread(workerThread)
    worker.piezoWorker.moveToThread(workerThread)
    worker.moveToThread(workerThread)
    
    # connect both classes 
    worker.make_connections(gui)
    gui.make_connections(worker)
    
    # start worker in a different thread (avoids GUI freezing)
    workerThread.start()
    
    gui.show()
    app.exec()