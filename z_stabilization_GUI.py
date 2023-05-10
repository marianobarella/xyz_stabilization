# -*- coding: utf-8 -*-
"""
Created on mon May 16, 2022

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland
"""

import os
import numpy as np
from datetime import datetime
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
from PyQt5.QtWidgets import QFrame
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from pyqtgraph.dockarea import Dock, DockArea
import thorlabs_camera_toolbox as tl_cam
from PIL import Image
from tkinter import filedialog
import tkinter as tk
import time as tm
from timeit import default_timer as timer
import piezo_stage_GUI
import viewbox_tools
from scipy import ndimage

#=====================================

# Initialize cameras

#=====================================

camera_constructor = tl_cam.load_Thorlabs_SDK_cameras()
mono_cam, \
mono_cam_flag, \
mono_cam_sensor_width_pixels, \
mono_cam_sensor_height_pixels, \
mono_cam_sensor_pixel_width_um, \
mono_cam_sensor_pixel_height_um = tl_cam.init_Thorlabs_mono_camera(camera_constructor)

camera = mono_cam
pixel_size_um = mono_cam_sensor_pixel_width_um
initial_filepath = 'D:\\daily_data\\z_stabilization_cam' # save in SSD for fast and daily use
initial_filename = 'image_z_drift'
viewTimer_update = 25 # in ms (makes no sense to go lower than the refresh rate of the screen)
initial_tracking_period = 200 # in ms
initial_exp_time = 10 # in ms
driftbox_length = 5 # in s

# inital ROI definition
initial_vertical_pos = 450
initial_horizontal_pos = 0
initial_vertical_size = 300
initial_horizontal_size = 1440

# for center of mass estimation, float between 0.00 and 1.00
initial_threshold = 0.8

# PID constants
# tested with a 200 ms tracking period
initial_kp = 0.75 # proportinal factor of the PID
initial_ki = 0.005 # integral factor of the PID
initial_kd = 0.01 # derivative factor of the PID
# correction threshold in um
# above this value (distance) the software starts to apply a correction
# to compensate the drift
correction_threshold = 0.020

# conversion factor from camera pixels to nm in z drift
# calibration of 05/05/2023 gives (see origin file)
# slope = -40.76 px/um so
# conversion factor is 0.0245 (take the absolute value)
# initial_conversion_factor = 0.0245 # nm/px
initial_conversion_factor = 0.0245 # nm/px

#=====================================

# GUI / Frontend definition

#=====================================
    
class Frontend(QtGui.QFrame):

    liveViewSignal = pyqtSignal(bool, float)
    exposureChangedSignal = pyqtSignal(bool, float)
    takePictureSignal = pyqtSignal(bool, float)
    saveSignal = pyqtSignal()
    setWorkDirSignal = pyqtSignal()
    trackingPeriodChangedSignal = pyqtSignal(bool, int)
    lockAndTrackSignal = pyqtSignal(bool)
    dataReflectionSignal = pyqtSignal(np.ndarray, bool)
    savedriftSignal = pyqtSignal()
    roiChangedSignal = pyqtSignal(bool, list)
    thresholdChangedSignal = pyqtSignal(float)
    pidParamChangedSignal = pyqtSignal(bool, list)
    stabilizationStatusChangedSignal = pyqtSignal(bool)
    conversionFactorChangedSignal = pyqtSignal(float)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setUpGUI()
        # set the title of thw window
        title = "Z stabilization module"
        self.setWindowTitle(title)
        self.setGeometry(5, 30, 1900, 600)
        self.roi = {}
        self.image = np.array([])
        self.stabilize = False
        return
            
    def setUpGUI(self):
        
        optical_format = mono_cam_sensor_width_pixels/mono_cam_sensor_height_pixels
        
        # Image
        imageWidget = pg.GraphicsLayoutWidget()
        self.vb = imageWidget.addPlot()
        self.img = pg.ImageItem()
        self.img.setOpts(axisOrder = 'row-major')
        self.vb.addItem(self.img)
        self.hist = pg.HistogramLUTItem(image = self.img, levelMode = 'mono')
        self.hist.gradient.loadPreset('grey')
        self.hist.disableAutoHistogramRange()
        # 'thermal', 'flame', 'yellowy', 'bipolar', 'spectrum',
        # 'cyclic', 'greyclip', 'grey'
        self.hist.vb.setLimits(yMin = 0, yMax = 1024) # 10-bit camera
        imageWidget.addItem(self.hist, row = 0, col = 1)
        # add center of reflection over camera image
        self.z_reflection = pg.ScatterPlotItem(size = 5, pen = pg.mkPen('r', width = 1), 
                                         symbol = 'o', brush = pg.mkBrush('r'))
        self.z_reflection.setZValue(2) # Ensure scatterPlotItem is always at top
        self.vb.addItem(self.z_reflection)
        

        self.autolevel_tickbox = QtGui.QCheckBox('Autolevel')
        self.initial_autolevel_state = True
        self.autolevel_tickbox.setChecked(self.initial_autolevel_state)
        self.autolevel_tickbox.setText('Autolevel')
        self.autolevel_tickbox.stateChanged.connect(self.autolevel)
        self.autolevel_bool = self.initial_autolevel_state

        # Buttons and labels
        
        # Working folder and filename
        self.working_dir_button = QtGui.QPushButton('Select directory')
        self.working_dir_button.clicked.connect(self.set_working_dir)
        self.working_dir_button.setStyleSheet(
            "QPushButton { background-color: lightgray; }"
            "QPushButton:pressed { background-color: palegreen; }")
        self.working_dir_label = QtGui.QLabel('Working directory:')
        self.filepath = initial_filepath
        self.working_dir_path = QtGui.QLineEdit(self.filepath)
        self.working_dir_path.setReadOnly(True) 

        self.take_picture_button = QtGui.QPushButton('Take a picture')
        self.take_picture_button.setCheckable(False)
        self.take_picture_button.clicked.connect(self.take_picture_button_check)
        self.take_picture_button.setStyleSheet(
                "QPushButton:pressed { background-color: red; }")
        
        self.save_picture_button = QtGui.QPushButton('Save picture')
        self.save_picture_button.clicked.connect(self.save_button_check)
        self.save_picture_button.setStyleSheet(
                "QPushButton:pressed { background-color: blue; }")
        
        self.live_view_button = QtGui.QPushButton('Live view')
        self.live_view_button.setCheckable(True)
        self.live_view_button.clicked.connect(self.liveview_button_check)
        self.live_view_button.setStyleSheet(
                "QPushButton { background-color: yellow; }"
                "QPushButton:pressed { background-color: red; }"
                "QPushButton::checked { background-color: red; }")

        # Exposure time
        exp_time_label = QtGui.QLabel('Exposure time (ms):')
        self.exp_time_edit = QtGui.QLineEdit(str(initial_exp_time))
        self.exp_time_edit_previous = float(self.exp_time_edit.text())
        self.exp_time_edit.editingFinished.connect(self.exposure_changed_check)
        self.exp_time_edit.setValidator(QtGui.QIntValidator(1, 26843))
        
        # lock and track the z reflection position
        self.lock_z_position_button = QtGui.QPushButton('Lock and Track')
        self.lock_z_position_button.setToolTip('Lock ROI\' position and start to track the laser reflection.')
        self.lock_z_position_button.setCheckable(True)
        self.lock_z_position_button.clicked.connect(self.lock_and_track)
        self.lock_z_position_button.setStyleSheet(
            "QPushButton { background-color: lightgray; }"
            "QPushButton:pressed { background-color: red; }"
            "QPushButton::checked { background-color: limegreen; }")
        # tracking period
        self.tracking_period_label = QtGui.QLabel('Tracking period (s):')
        self.tracking_period_value = QtGui.QLineEdit(str(initial_tracking_period/1000))
        self.tracking_period = initial_tracking_period
        self.tracking_period_value.setToolTip('Period to measure fiducial markers\' position.')
        self.tracking_period_value.editingFinished.connect(self.tracking_period_changed_check)
        
        # stabilize
        self.stabilize_z_button = QtGui.QPushButton('Stabilize z axis')
        self.stabilize_z_button.setToolTip('Stabilize sample in z axis.')
        self.stabilize_z_button.setCheckable(True)
        self.stabilize_z_button.clicked.connect(self.stabilize_status)
        self.stabilize_z_button.setStyleSheet(
            "QPushButton { background-color: lightgray; }"
            "QPushButton:pressed { background-color: red; }"
            "QPushButton::checked { background-color: orange; }")
        
        # save drift trace button
        self.savedrift_tickbox = QtGui.QCheckBox('Save drift curve')
        self.initial_state_savedrift = False
        self.savedrift_tickbox.setChecked(self.initial_state_savedrift)
        self.savedrift_tickbox.setText('Save drift data when unlocking')
        self.savedrift_tickbox.stateChanged.connect(self.save_drift_trace)
        self.savedrift_bool = self.initial_state_savedrift
        # set ROI for tracking position and size
        self.ROIbox = QtGui.QLabel('ROI definition')
        self.ROIbox_vertical_pos_label = QtGui.QLabel('Vertical position (px):')
        self.ROIbox_vertical_pos = QtGui.QLineEdit(str(initial_vertical_pos))
        self.ROIbox_vertical_pos.setValidator(QtGui.QIntValidator(1, 1080))
        self.ROIbox_horizontal_pos_label = QtGui.QLabel('Horizontal position (px):')
        self.ROIbox_horizontal_pos = QtGui.QLineEdit(str(initial_horizontal_pos))
        self.ROIbox_horizontal_pos.setValidator(QtGui.QIntValidator(1, 1440))
        self.ROIbox_vertical_size_label = QtGui.QLabel('Vertical size (px):')
        self.ROIbox_vertical_size = QtGui.QLineEdit(str(initial_vertical_size))
        self.ROIbox_vertical_size.setValidator(QtGui.QIntValidator(1, 1440))
        self.ROIbox_horizontal_size_label = QtGui.QLabel('Horizontal size (px):')
        self.ROIbox_horizontal_size = QtGui.QLineEdit(str(initial_horizontal_size))
        self.ROIbox_horizontal_size.setValidator(QtGui.QIntValidator(1, 1080))
        self.ROIbox_vertical_pos.editingFinished.connect(self.roi_changed_check)
        self.ROIbox_horizontal_pos.editingFinished.connect(self.roi_changed_check)
        self.ROIbox_vertical_size.editingFinished.connect(self.roi_changed_check)
        self.ROIbox_horizontal_size.editingFinished.connect(self.roi_changed_check)
        self.vertical_pos_previous = int(self.ROIbox_vertical_pos.text())
        self.horizontal_pos_previous = int(self.ROIbox_horizontal_pos.text())
        self.vertical_size_previous = int(self.ROIbox_vertical_size.text())
        self.horizontal_size_previous = int(self.ROIbox_horizontal_size.text())
        self.roi_list_previous = [self.vertical_pos_previous, self.horizontal_pos_previous, \
                                  self.vertical_size_previous, self.horizontal_size_previous]
            
        self.intensity_threshold_label = QtGui.QLabel('Intensity threshold:')
        self.intensity_threshold_value = QtGui.QLineEdit(str(initial_threshold))
        self.intensity_threshold_value.setToolTip('Above which fraction of the maximum intensity is going to look for the center of mass.')
        self.intensity_threshold_value.setValidator(QtGui.QDoubleValidator(0, 1, 2))
        self.intensity_threshold_value.editingFinished.connect(self.threshold_changed_check)
        self.threshold = initial_threshold
            
        # create ROI button
        self.create_ROI_button = QtGui.QPushButton('Create ROI')
        self.create_ROI_button.setCheckable(True)
        self.create_ROI_button.clicked.connect(self.create_ROI)
        self.create_ROI_button.setStyleSheet(
            "QPushButton { background-color: lightgray; }"
            "QPushButton:pressed { background-color: red; }"
            "QPushButton::checked { background-color: steelblue; }")
        
        # conversion from camera pixel to drift in z
        self.conversion_label = QtGui.QLabel('Conversion factor (nm/px):')
        self.conversion_value = QtGui.QLineEdit(str(initial_conversion_factor))
        self.conversion_value.editingFinished.connect(self.conversion_factor_changed)
        self.conversion_factor = initial_conversion_factor

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
        # position vs time of z position
        driftWidget = pg.GraphicsLayoutWidget()
        self.driftPlot = driftWidget.addPlot(title = "Z drift")
        self.driftPlot.showGrid(x = True, y = True)
        self.driftPlot.setLabel('left', 'Shift (μm)') # μ
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

        # Z tracking selection dock
        self.zLockWidget = QtGui.QWidget()
        layout_zLock = QtGui.QGridLayout()
        self.zLockWidget.setLayout(layout_zLock)
        layout_zLock.addWidget(self.ROIbox,         0, 0)
        layout_zLock.addWidget(self.ROIbox_vertical_pos_label,         1, 0)
        layout_zLock.addWidget(self.ROIbox_vertical_pos,         1, 1)
        layout_zLock.addWidget(self.ROIbox_horizontal_pos_label,         2, 0)
        layout_zLock.addWidget(self.ROIbox_horizontal_pos,         2, 1)
        layout_zLock.addWidget(self.ROIbox_vertical_size_label,         3, 0)
        layout_zLock.addWidget(self.ROIbox_vertical_size,         3, 1)
        layout_zLock.addWidget(self.ROIbox_horizontal_size_label,         4, 0)
        layout_zLock.addWidget(self.ROIbox_horizontal_size,         4, 1)
        layout_zLock.addWidget(self.create_ROI_button,         5, 0, 1, 2)
        layout_zLock.addWidget(self.intensity_threshold_label,         6, 0)
        layout_zLock.addWidget(self.intensity_threshold_value,         6, 1)
        # # lock and track buttons
        # layout_zLock.addWidget(self.lock_z_position_button,         7, 0, 1, 2)
        # layout_zLock.addWidget(self.conversion_label,         8, 0)
        # layout_zLock.addWidget(self.conversion_value,         8, 1)
        # layout_zLock.addWidget(self.tracking_period_label,         9, 0)
        # layout_zLock.addWidget(self.tracking_period_value,         9, 1)
        # layout_zLock.addWidget(self.stabilize_z_button,         10, 0, 1, 2)
        # layout_zLock.addWidget(self.pid_label,         11, 0)
        # layout_zLock.addWidget(self.kp_label,         12, 0)
        # layout_zLock.addWidget(self.kp_value,         12, 1)
        # layout_zLock.addWidget(self.ki_label,         13, 0)
        # layout_zLock.addWidget(self.ki_value,         13, 1)
        # layout_zLock.addWidget(self.kd_label,         14, 0)
        # layout_zLock.addWidget(self.kd_value,         14, 1)

        # lock and track buttons
        self.separatorLine = QFrame()
        self.separatorLine.setFrameShape(QFrame.VLine)
        self.separatorLine.setFrameShadow(QFrame.Raised)
        layout_zLock.addWidget(self.separatorLine, 0, 2, 9, 1)
        layout_zLock.addWidget(self.lock_z_position_button,         0, 3, 1, 2)
        layout_zLock.addWidget(self.conversion_label,         1, 3)
        layout_zLock.addWidget(self.conversion_value,         1, 4)
        layout_zLock.addWidget(self.tracking_period_label,         2, 3)
        layout_zLock.addWidget(self.tracking_period_value,         2, 4)
        layout_zLock.addWidget(self.stabilize_z_button,         3, 3, 1, 2)
        layout_zLock.addWidget(self.pid_label,         4, 3)
        layout_zLock.addWidget(self.kp_label,         5, 3)
        layout_zLock.addWidget(self.kp_value,         5, 4)
        layout_zLock.addWidget(self.ki_label,         6, 3)
        layout_zLock.addWidget(self.ki_value,         6, 4)
        layout_zLock.addWidget(self.kd_label,         7, 3)
        layout_zLock.addWidget(self.kd_value,         7, 4)
        
        # save drift
        layout_zLock.addWidget(self.savedrift_tickbox,      8, 3)
        
        # Place layouts and boxes
        dockArea = DockArea()
        hbox = QtGui.QHBoxLayout(self)
        
        viewDock = Dock('Camera', size = (200*optical_format, 200) )
        viewDock.addWidget(imageWidget)
        dockArea.addDock(viewDock)
        
        driftDock = Dock('Drift vs time', size = (20, 20))
        driftDock.addWidget(driftWidget)
        dockArea.addDock(driftDock, 'right', viewDock)
        
        liveview_paramDock = Dock('Live view parameters')
        liveview_paramDock.addWidget(self.liveviewWidget)
        dockArea.addDock(liveview_paramDock, 'bottom', driftDock)

        zLockDock = Dock('Axial stabilization control', size = (20, 20))
        zLockDock.addWidget(self.zLockWidget)
        dockArea.addDock(zLockDock, 'right', liveview_paramDock)
        
        ## Add Piezo stage GUI module
        piezoDock = Dock('Piezo stage')
        self.piezoWidget = piezo_stage_GUI.Frontend()
        piezoDock.addWidget(self.piezoWidget)
        dockArea.addDock(piezoDock , 'right', zLockDock)
        
        hbox.addWidget(dockArea)
        self.setLayout(hbox)
        return

    def conversion_factor_changed(self):
        conversion_factor = float(self.conversion_value.text())
        if conversion_factor != self.conversion_factor:
            self.conversion_factor = conversion_factor
            self.conversionFactorChangedSignal.emit(self.conversion_factor)
        return

    def threshold_changed_check(self):
        threshold = float(self.intensity_threshold_value.text())
        if threshold != self.threshold:
            self.threshold = threshold
            self.thresholdChangedSignal.emit(self.threshold)
        return

    def roi_changed_check(self):
        vertical_pos = int(self.ROIbox_vertical_pos.text())
        horizontal_pos = int(self.ROIbox_horizontal_pos.text())
        vertical_size = int(self.ROIbox_vertical_size.text())
        horizontal_size = int(self.ROIbox_horizontal_size.text())
        roi_list = [vertical_pos, horizontal_pos, vertical_size, horizontal_size]
        if roi_list != self.roi_list_previous:
            self.roi_list_previous = roi_list
            print('ROI has been changed.')
            # remove previous ROI if any
            if self.create_ROI_button.isChecked():
                self.vb.removeItem(self.roi)
                self.roi.hide()
                self.roi = {}
                self.create_ROI()
        return
    
    def create_ROI(self):
        # create ROI for tracking z reflection
        if self.create_ROI_button.isChecked():
            x_pos = self.roi_list_previous[1]
            y_pos = self.roi_list_previous[0]
            box_size = (self.roi_list_previous[3], self.roi_list_previous[2])
            ROIpos = (x_pos, y_pos) # (0.5*numberofPixels - 0.5*box_size, 0.5*numberofPixels - 0.5*box_size)
            self.roi = viewbox_tools.ROI_rect(box_size, self.vb, ROIpos,
                                              handlePos = (1, 1),
                                              handleCenter = (0, 0), 
                                              scaleSnap = False,
                                              translateSnap = True)
        else:
            self.vb.removeItem(self.roi)
            self.roi.hide()
            self.roi = {}
        return

    def save_drift_trace(self):
        if self.savedrift_tickbox.isChecked():
            self.savedrift_bool = True
            print('Drift cruve will be saved.')
        else:
            self.savedrift_bool = False
            print('Drift cruve will not be saved.')
        return

    def exposure_changed_check(self):
        exposure_time_ms = float(self.exp_time_edit.text()) # in ms
        if exposure_time_ms != self.exp_time_edit_previous:
            print('\nExposure time changed to', exposure_time_ms, 'ms')
            self.exp_time_edit_previous = exposure_time_ms
            if self.live_view_button.isChecked():
                self.exposureChangedSignal.emit(True, exposure_time_ms)
            else:
                self.exposureChangedSignal.emit(False, exposure_time_ms)

    def take_picture_button_check(self):
        exposure_time_ms = float(self.exp_time_edit.text()) # in ms
        if self.live_view_button.isChecked():
            self.takePictureSignal.emit(True, exposure_time_ms)
        else:
            self.takePictureSignal.emit(False, exposure_time_ms)            

    def save_button_check(self):
        if self.save_picture_button.isChecked:
           self.saveSignal.emit()

    def liveview_button_check(self):
        exposure_time_ms = float(self.exp_time_edit.text()) # in ms
        if self.live_view_button.isChecked():
            self.liveViewSignal.emit(True, exposure_time_ms)
        else:
            self.liveViewSignal.emit(False, exposure_time_ms)

    def set_working_dir(self):
        self.setWorkDirSignal.emit()

    def autolevel(self):
        if self.autolevel_tickbox.isChecked():
            self.autolevel_bool = True
            print('Autolevel on')
        else:
            self.autolevel_bool = False
            print('Autolevel off')
        return

    def stabilize_status(self):
        if self.stabilize_z_button.isChecked():
            self.stabilize = True
            self.lock_and_track()
        else:
            self.stabilize = False
        self.stabilizationStatusChangedSignal.emit(self.stabilize)
        return    

    def tracking_period_changed_check(self):
        new_tracking_period = int(float(self.tracking_period_value.text())*1000)
        if new_tracking_period != self.tracking_period:
            self.tracking_period = new_tracking_period
            if self.lock_z_position_button.isChecked():
                self.trackingPeriodChangedSignal.emit(True, self.tracking_period)
            else:
                self.trackingPeriodChangedSignal.emit(False, self.tracking_period)
        return
    
    def lock_and_track(self):
        if self.lock_z_position_button.isChecked():
            if self.create_ROI_button.isChecked():
                self.driftPlot.clear()
                self.lockAndTrackSignal.emit(True)
                N = int(driftbox_length*1000/self.tracking_period)
                self.error_to_plot = np.empty(N)
                self.error_to_plot[:] = np.nan
                self.time_to_plot = np.empty(N)
                self.time_to_plot[:] = np.nan
            else:
                print('Warning! Lock and Track can only be used if the ROI has been created.')
        else:
            self.lockAndTrackSignal.emit(False)
            if self.savedrift_bool:
                self.savedriftSignal.emit()
            self.z_reflection.clear()
        return
    
    def retrieve_reflection_data(self):
        (self.data_ROI, \
         self.coord_ROI) = self.roi.getArrayRegion(self.image, \
                                                   self.img, \
                                                   axis = (1, 0), \
                                                   returnMappedCoords = True)
        self.dataReflectionSignal.emit(self.coord_ROI, self.savedrift_bool)
        return
    
    @pyqtSlot(np.ndarray, np.ndarray, float)
    def receive_cm_data(self, xy_pos_pixel_relative, error, timestamp):
        # plot xy position of fiducials vs time
        self.error_to_plot = np.roll(self.error_to_plot, -1, axis = 0)
        self.time_to_plot = np.roll(self.time_to_plot, -1)
        # only plot x coordinate and convert to nm using calibration
        self.error_to_plot[-1] = error[0]*self.conversion_factor
        self.time_to_plot[-1] = timestamp
        self.driftPlot.clear()
        self.driftPlot.plot(x = self.time_to_plot, y = self.error_to_plot, \
                            pen = pg.mkPen('r', width = 1))
        self.driftPlot.setXRange(timestamp - driftbox_length, timestamp)
        # draw center of refkectuib, convert um to pixels
        xy_pos_absolute = xy_pos_pixel_relative + (self.roi_list_previous[1], 
                                                   self.roi_list_previous[0])
        self.z_reflection.setData(x = [xy_pos_absolute[0]], y = [xy_pos_absolute[1]])        
        return
    
    def pid_param_changed_check(self):
        kp = float(self.kp_value.text())
        ki = float(self.ki_value.text())
        kd = float(self.kd_value.text())
        pid_param_list = [kp, ki, kd]
        if pid_param_list != self.pid_param_list:
            self.pid_param_list = pid_param_list
            if self.lock_z_position_button.isChecked():
                self.pidParamChangedSignal.emit(True, pid_param_list)
            else:
                self.pidParamChangedSignal.emit(False, pid_param_list)
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
            tl_cam.dispose_cam(mono_cam)
            tl_cam.dispose_sdk(camera_constructor)
            event.accept()
            print('Closing GUI...')
            self.close()
            tm.sleep(1)
            app.quit()
        else:
            event.ignore()
            print('Back in business...')    
        return
  
    def make_connections(self, backend):
        backend.imageSignal.connect(self.get_image)
        backend.filePathSignal.connect(self.get_file_path)
        backend.piezoWorker.make_connections(self.piezoWidget)
        backend.getReflectionDataSignal.connect(self.retrieve_reflection_data)
        backend.sendFittedDataSignal.connect(self.receive_cm_data)
        return

#=====================================

# Controls / Backend definition

#=====================================

class Backend(QtCore.QObject):

    imageSignal = pyqtSignal(np.ndarray)
    filePathSignal = pyqtSignal(str)
    getReflectionDataSignal = pyqtSignal()
    sendFittedDataSignal = pyqtSignal(np.ndarray, np.ndarray, float)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewTimer = QtCore.QTimer()
        self.viewTimer.timeout.connect(self.update_view)   
        self.image_np = None
        self.trackingTimer = QtCore.QTimer()
        self.trackingTimer.timeout.connect(self.call_pid)
        self.tracking_period = initial_tracking_period
        self.piezo_stage = piezo_stage_GUI.piezo_stage     
        self.piezoWorker = piezo_stage_GUI.Backend(self.piezo_stage)
        self.threshold = initial_threshold
        self.file_path = initial_filepath
        self.pid_param_list = [initial_kp, initial_ki, initial_kd]
        self.stabilization_flag = False
        self.conversion_factor = initial_conversion_factor
        return
    
    @pyqtSlot(bool, float)    
    def change_exposure(self, livebool, exposure_time_ms):
        if livebool:
            self.stop_liveview()
            self.exposure_time_ms = exposure_time_ms # in ms, is float
            self.start_liveview(self.exposure_time_ms)
        else:
            self.exposure_time_ms = exposure_time_ms
        return
    
    @pyqtSlot(bool, float)
    def take_picture(self, livebool, exposure_time_ms):
        print('\nPicture taken at', datetime.now())
        self.exposure_time_ms = exposure_time_ms # in ms, is float
        if livebool:
            self.stop_liveview()
        tl_cam.set_camera_one_picture_mode(camera)
        self.frame_time = tl_cam.set_exp_time(camera, self.exposure_time_ms)
        self.image_np, _ = tl_cam.get_mono_image(camera)
        if self.image_np is not None:
            tl_cam.stop_camera(camera)
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
        tl_cam.set_camera_continuous_mode(camera)
        self.exposure_time_ms = exposure_time_ms # in ms, is float
        self.frame_time = tl_cam.set_exp_time(camera, self.exposure_time_ms)
        self.viewTimer.start(round(self.frame_time)) # ms
        # self.viewTimer.start(viewTimer_update) # ms
        return
                
    def update_view(self):
        # Image update while in Live view mode
        self.image_np, _ = tl_cam.get_mono_image(camera)
        self.imageSignal.emit(self.image_np)
        return
        
    def stop_liveview(self):
        print('\nLive view stopped at', datetime.now())
        tl_cam.stop_camera(camera)
        self.viewTimer.stop()
        return

    @pyqtSlot(bool, int)
    def change_tracking_period(self, lockbool, new_tracking_period):
        print('Tracking period changed to {:.3f} s.'.format(new_tracking_period/1000))
        self.tracking_period = new_tracking_period
        if lockbool:
            print('Restarting QtTimer...')
            self.trackingTimer.stop()
            self.trackingTimer.start(self.tracking_period)
        return
    
    def call_pid(self):
        center, timestamp = self.calculate_center_of_mass()
        error_x_px = self.initial_center[0] - center[0]
        error_y_px = self.initial_center[1] - center[1]
        error_px =  np.array([error_x_px, error_y_px])
        error = error_px*self.conversion_factor # in nm
        # send position of the reflection to Frontend
        self.sendFittedDataSignal.emit(center, error_px, timestamp)
        # store data to save drift vs time when the Lock and Track option is released
        if self.save_drift_data:
            self.timeaxis_to_save.append(timestamp)
            self.errors_to_save.append(error)
        # now correct drift if button is checked
        if self.stabilization_flag:
            # PID calculation
            # assign parameters
            kp = self.pid_param_list[0]
            ki = self.pid_param_list[1]
            kd = self.pid_param_list[2]
            # proportional term
            self.prop_correction = kp*error
            # integral term
            self.int_correction = self.int_correction + ki*error*self.tracking_period
            # derivative term
            self.dev_correction = self.dev_correction + \
                kd*(error - self.last_error)/self.tracking_period
            self.last_error = error
            # calculate correction in um
            correction = self.prop_correction + self.int_correction + self.dev_correction
            # call function to correct
            self.correct_drift(error, correction)
        return

    def correct_drift(self, error, correction):
        # y axis will be ignored cause the setup uses only lateral shifts
        # make float32 to avoid crashing the module
        error_x = float(error[0])
        error_y = float(error[1])
        correction_x = float(correction[0])
        correction_y = float(correction[1])
        # use the worker to send the instructions
        # only if the drift correction is larger than a threshold
        if abs(error_x) > correction_threshold:
            print(error_x)
            print('correction z %.0f nm ' % (correction_x*1000))
            self.piezoWorker.move_relative('z', correction_x)
        return

    @pyqtSlot(bool)
    def start_stop_tracking(self, trackbool):
        if trackbool:
            print('Locking and tracking z reflection...')
            # initiating variables
            self.center = {}
            self.timeaxis = {}
            self.errors_to_save = []
            self.timeaxis_to_save = []
            self.int_correction = 0
            self.dev_correction = 0
            self.last_error = 0
            # t0 initial time
            self.start_tracking_time = timer()
            # ask for ROI data and coordinates
            self.get_reflection_data()
            # start timer
            self.trackingTimer.start(self.tracking_period)
        else:
            self.trackingTimer.stop()
            print('Unlocking...')
        return
    
    def get_reflection_data(self):
        self.getReflectionDataSignal.emit()
        return
    
    @pyqtSlot(np.ndarray, bool)
    def receive_roi_data(self, roi_coordinates, append_drift_bool):
        self.save_drift_data = append_drift_bool
        # set indexes for ROI
        self.x1 = int(roi_coordinates[0,0,0])
        self.x2 = int(roi_coordinates[0,-1,0]) + 1
        self.y1 = int(roi_coordinates[1,0,0])
        self.y2 = int(roi_coordinates[1,0,-1]) + 1
        # then frame_intensity is self.image_np[x1:x2, y1:y2]
        print('Finding initial coordinates...')
        self.initial_center, _ = self.calculate_center_of_mass()
        print('Done.')
        return
    
    def calculate_center_of_mass(self):
        # find center of mass
        frame_roi_intensity = self.image_np[self.x1:self.x2, self.y1:self.y2]
        roi_threshold = self.threshold*np.max(frame_roi_intensity)
        frame_roi_th = np.where(frame_roi_intensity > roi_threshold, frame_roi_intensity, 0)
        cm_y, cm_x = ndimage.center_of_mass(frame_roi_th) # vertical, horizontal
        # print(cm_y, cm_x)
        center = np.array([cm_x, cm_y])
        timeaxis = timer() - self.start_tracking_time
        return center, timeaxis

    @pyqtSlot(float)
    def new_threshold(self, new_threshold):
        self.threshold = new_threshold
        print('Intesity threshold has been changed to %.2f.' % self.threshold)        
        return

    @pyqtSlot()    
    def save_drift_curve(self):
        # prepare the array to be saved
        # structure of the file will be
        # first col = time, in s
        # second and third col = x and y position of the reflection
        # fourth and fifth col = x and y position of 2nd NP, respectively, in um 
        # etc...
        M = np.array(self.timeaxis_to_save).shape[0]
        data_to_save = np.zeros((M, 3))
        data_to_save[:, 0] = np.array(self.timeaxis_to_save)
        data_to_save[:, 1:] = np.array(self.errors_to_save)*self.conversion_factor
        # create filename
        timestr = datetime.today().strftime('%Y-%m-%d_%H-%M-%S')
        filename = "drift_curve_z_" + timestr + ".dat"
        full_filename = os.path.join(self.file_path, filename)
        # save
        np.savetxt(full_filename, data_to_save, fmt='%.3e')
        print('Drift curve %s saved' % filename)
        return

    @pyqtSlot(bool, list)
    def new_pid_params(self, lockbool, pid_param_list):
        print('PID parameters changed to kp={} / ki={} / kd={}.'.format(pid_param_list[0], \
                                                                        pid_param_list[1], \
                                                                        pid_param_list[2]))
        self.pid_param_list = pid_param_list
        if lockbool:
            print('Restarting QtTimer...')
            self.trackingTimer.stop()
            self.trackingTimer.start(self.tracking_period)
        return
    
    @pyqtSlot(float)
    def new_conversion_factor(self, new_conv_factor):
        print('Conversion factor changed to {:.1f} nm/px'.format(new_conv_factor))
        self.conversion_factor = new_conv_factor
        return

    @pyqtSlot(bool)
    def set_stabilization(self, stabilizebool):
        if stabilizebool:
            print('Stabilization ON.')
            self.stabilization_flag = True
        else:
            print('Stabilization OFF.')
            self.stabilization_flag = False
        return

    @pyqtSlot()    
    def save_picture(self):
        timestr = datetime.today().strftime('%Y-%m-%d_%H-%M-%S')
        filename = "inspec_cam_pic_" + timestr + ".jpg"
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
            self.filePathSignal.emit(self.file_path) # TODO Lo reciben los módulos de traza, confocal y printing
        return

    @pyqtSlot()
    def close_all_backends(self):
        # print('Shutting down piezo stage...')
        # self.piezo_stage.shutdown()
        print('Stopping timers...')
        self.piezoWorker.updateTimer.stop()
        self.viewTimer.stop()
        self.trackingTimer.stop()
        print('Exiting threads...')
        tm.sleep(1)
        workerThread.exit()
        return

    def make_connections(self, frontend):
        frontend.exposureChangedSignal.connect(self.change_exposure)
        frontend.liveViewSignal.connect(self.liveview) 
        frontend.takePictureSignal.connect(self.take_picture) 
        frontend.saveSignal.connect(self.save_picture)
        frontend.setWorkDirSignal.connect(self.set_working_folder)
        frontend.savedriftSignal.connect(self.save_drift_curve)
        frontend.lockAndTrackSignal.connect(self.start_stop_tracking)
        frontend.trackingPeriodChangedSignal.connect(self.change_tracking_period)
        frontend.dataReflectionSignal.connect(self.receive_roi_data)
        frontend.thresholdChangedSignal.connect(self.new_threshold)
        frontend.piezoWidget.make_connections(self.piezoWorker)
        frontend.pidParamChangedSignal.connect(self.new_pid_params)
        frontend.stabilizationStatusChangedSignal.connect(self.set_stabilization)
        frontend.conversionFactorChangedSignal.connect(self.new_conversion_factor)
        return
      
#=====================================

# Main program

#=====================================
         
if __name__ == '__main__':
    # make application
    app = QtGui.QApplication([])
    
    # create classes
    gui = Frontend()
    worker = Backend()
    
    # for tracking and z camera
    workerThread = QtCore.QThread()
    worker.moveToThread(workerThread)
    worker.trackingTimer.moveToThread(workerThread)
    worker.viewTimer.moveToThread(workerThread)
    worker.piezoWorker.updateTimer.moveToThread(workerThread)
    
    # connect both classes
    worker.make_connections(gui)
    gui.make_connections(worker)
    
    # start threads
    workerThread.start()
    
    gui.show()    
    app.exec()
    