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
import pco_camera_toolbox as pco
import drift_correction_toolbox as drift
from PIL import Image
from tkinter import filedialog
import tkinter as tk
import time as tm
import viewbox_tools

#=====================================

# Initialize camera and useful variables

#=====================================

cam = pco.pco_camera()
initial_pixel_size = 65 # in nm (with 1x1 binning)
initial_filepath = 'D:\\daily_data' # save in SSD for fast and daily use
initial_filename = 'image_pco_test'
viewTimer_update = 25 # in ms (makes no sense to go lower than the refresh rate of the screen)
tempTimer_update = 5000 # in ms
initial_tracking_period = 2000 # in ms
driftbox_length = 10.0 # in seconds

#=====================================

# GUI / Frontend definition

#=====================================
   
class Frontend(QtGui.QFrame):

    liveViewSignal = pyqtSignal(bool, float)
    closeSignal = pyqtSignal()
    roiChangedSignal = pyqtSignal(bool, list)
    exposureChangedSignal = pyqtSignal(bool, float)
    binningChangedSignal = pyqtSignal(bool, int, float)
    trackingPeriodChangedSignal = pyqtSignal(bool, int)
    takePictureSignal = pyqtSignal(bool, float)
    saveSignal = pyqtSignal()
    setWorkDirSignal = pyqtSignal()
    lockAndTrackSignal = pyqtSignal(bool)
    fitFiducialsSignal = pyqtSignal(int, dict, dict)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setUpGUI()
        # set the title of the window
        title = "XY stabilization module"
        self.setWindowTitle(title)
        self.sensor_temp = 0.00
        self.cam_temp = 0.00
        self.power_temp = 0.00
        self.image = np.array([])
        self.roi = {}
        return
            
    def setUpGUI(self):
        
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
        self.hist.vb.setLimits(yMin = 0, yMax = 65536) # 16-bit camera
        imageWidget.addItem(self.hist, row = 0, col = 1)
        # TODO: if performance is an issue, try scaleToImage
        # add centers of fiducials over camera image
        self.xy_fiducials = pg.ScatterPlotItem(size = 5, pen = pg.mkPen('r', width = 1), 
                                         symbol = 'o', brush = pg.mkBrush('r'))
        self.xy_fiducials.setZValue(2) # Ensure scatterPlotItem is always at top
        self.vb.addItem(self.xy_fiducials)

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
            "QPushButton { background-color: lightgray; }"
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
            "QPushButton { background-color: lightgray; }"
            "QPushButton:pressed { background-color: red; }")
        
        self.save_picture_button = QtGui.QPushButton('Save picture')
        self.save_picture_button.clicked.connect(self.save_button_check)
        self.save_picture_button.setStyleSheet(
            "QPushButton { background-color: lightgray; }"
            "QPushButton:pressed { background-color: red; }")
        
        self.live_view_button = QtGui.QPushButton('Live view')
        self.live_view_button.setCheckable(True)
        self.live_view_button.clicked.connect(self.liveview_button_check)
        self.live_view_button.setStyleSheet(
            "QPushButton { background-color: yellow; }"
            "QPushButton:pressed { background-color: red; }"
            "QPushButton::checked { background-color: red; }")

        # Exposure time
        exp_time_label = QtGui.QLabel('Exposure time (ms):')
        self.exp_time_edit = QtGui.QLineEdit('100')
        self.exp_time_edit_previous = float(self.exp_time_edit.text())
        self.exp_time_edit.editingFinished.connect(self.exposure_changed_check)
        self.exp_time_edit.setValidator(QtGui.QDoubleValidator(0.01, 5000.00, 2))
        self.exp_time_edit.setToolTip('Minimum is 10 µs. Maximum is 5 s.')
        
        # Temp labels
        self.sensor_temp_label = QtGui.QLabel('Sensor temp (°C):')
        self.cam_temp_label = QtGui.QLabel('Camera temp (°C):')
        self.power_temp_label = QtGui.QLabel('Electronics temp (°C):')
        self.sensor_temp_value = QtGui.QLabel('-')
        self.cam_temp_value = QtGui.QLabel('-')
        self.power_temp_value = QtGui.QLabel('-')

        # Pixel size
        pixel_size_label = QtGui.QLabel('Pixel size (nm):')
        self.pixel_size_value = QtGui.QLabel(str(initial_pixel_size))
        self.pixel_size_value.setToolTip('Pixel size at sample plane.')
        self.pixel_size = int(self.pixel_size_value.text())

        # Binning
        binning_label = QtGui.QLabel('Binning (pixels):')
        self.binning_edit = QtGui.QLineEdit('1')
        self.binning_edit.setToolTip('Restricted to squared binning. Options are 1x1, 2x2 and 4x4.')
        self.binning_previous = float(self.binning_edit.text())
        self.binning_edit.editingFinished.connect(self.binning_changed_check)
        self.binning_edit.setValidator(QtGui.QIntValidator(1, 4))
        
        # Sensor ROI entry
        define_roi = QtGui.QLabel('Define ROI:')
        starting_col_label = QtGui.QLabel('Starting col (pixel):')
        final_col_label = QtGui.QLabel('Final col (pixel):')
        starting_row_label = QtGui.QLabel('Starting row (pixel):')
        final_row_label = QtGui.QLabel('Final row (pixel):')
        self.starting_col = QtGui.QLineEdit('1')
        self.final_col = QtGui.QLineEdit('2048')
        self.starting_row = QtGui.QLineEdit('1')
        self.final_row = QtGui.QLineEdit('2048')
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
        self.number_of_fiducials_value = QtGui.QLineEdit('1')
        box_size_label = QtGui.QLabel('Box size (pixels):')
        self.box_size_value = QtGui.QLineEdit('201')
        self.box_size_value.setValidator(QtGui.QIntValidator(1, 999))
        self.box_size_value.setToolTip('Restricted to odd numbers. Good starting point is box_size ~ 1 µm (use pixel size).')
        self.create_ROIs_button = QtGui.QPushButton('Create ROIs')
        self.create_ROIs_button.setCheckable(True)
        self.create_ROIs_button.clicked.connect(self.create_ROIs)
        self.create_ROIs_button.setStyleSheet(
            "QPushButton { background-color: lightgray; }"
            "QPushButton:pressed { background-color: red; }"
            "QPushButton::checked { background-color: steelblue; }")
        # lock and track the fiducials
        self.lock_ROIs_button = QtGui.QPushButton('Lock and Track')
        self.lock_ROIs_button.setToolTip('Lock ROIs\' position and start to track the fiducial markers.')
        self.lock_ROIs_button.setCheckable(True)
        self.lock_ROIs_button.clicked.connect(self.lock_and_track)
        self.lock_ROIs_button.setStyleSheet(
            "QPushButton { background-color: lightgray; }"
            "QPushButton:pressed { background-color: red; }"
            "QPushButton::checked { background-color: limegreen; }")
        self.tracking_period_label = QtGui.QLabel('Tracking period (s):')
        self.tracking_period_value = QtGui.QLineEdit(str(initial_tracking_period/1000))
        self.tracking_period = initial_tracking_period
        self.tracking_period_value.setToolTip('Period to measure fiducial markers\' position.')
        self.tracking_period_value.editingFinished.connect(self.tracking_period_changed_check)

        # position vs time of fiducials
        driftWidget = pg.GraphicsLayoutWidget()
        self.driftPlot = driftWidget.addPlot(title = "Drift")
        self.driftPlot.showGrid(x = True, y = True)
        self.driftPlot.setLabel('left', 'Position (μm)')
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
        # Temp status
        layout_liveview.addWidget(self.sensor_temp_label, 10, 0)
        layout_liveview.addWidget(self.cam_temp_label, 11, 0)
        layout_liveview.addWidget(self.power_temp_label, 12, 0)
        layout_liveview.addWidget(self.sensor_temp_value, 10, 1)
        layout_liveview.addWidget(self.cam_temp_value, 11, 1)
        layout_liveview.addWidget(self.power_temp_value, 12, 1)
        # pixel size
        layout_liveview.addWidget(pixel_size_label,      13, 0)
        layout_liveview.addWidget(self.pixel_size_value,        13, 1)
        # binning
        layout_liveview.addWidget(binning_label,        14, 0)
        layout_liveview.addWidget(self.binning_edit,        14, 1)
        # ROI box
        layout_liveview.addWidget(define_roi,      15, 0)
        layout_liveview.addWidget(starting_col_label,      16, 0)
        layout_liveview.addWidget(self.starting_col,      16, 1)
        layout_liveview.addWidget(final_col_label,      17, 0)
        layout_liveview.addWidget(self.final_col,      17, 1)
        layout_liveview.addWidget(starting_row_label,      18, 0)
        layout_liveview.addWidget(self.starting_row,      18, 1)
        layout_liveview.addWidget(final_row_label,      19, 0)
        layout_liveview.addWidget(self.final_row,      19, 1)       

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
        layout_fiducials.addWidget(self.tracking_period_label,         4, 0)
        layout_fiducials.addWidget(self.tracking_period_value,         4, 1)
        
        # Place layouts and boxes
        dockArea = DockArea()
        hbox = QtGui.QHBoxLayout(self)

        viewDock = Dock('Camera', size = (20, 20)) # optical format is squared
        viewDock.addWidget(imageWidget)
        dockArea.addDock(viewDock)
        
        liveview_paramDock = Dock('Live view parameters', size = (1, 20))
        liveview_paramDock.addWidget(self.liveviewWidget)
        dockArea.addDock(liveview_paramDock, 'right', viewDock)
        
        fiducialsDock = Dock('Fiducials selection', size = (20, 20))
        fiducialsDock.addWidget(self.fiducialsWidget)
        dockArea.addDock(fiducialsDock, 'right', liveview_paramDock)
        
        driftDock = Dock('Drift vs time', size = (20, 20))
        driftDock.addWidget(driftWidget)
        dockArea.addDock(driftDock, 'bottom', fiducialsDock)
        
        hbox.addWidget(dockArea)
        self.setLayout(hbox)
        return
    
    def create_ROIs(self):
        # create ROIs for the fiducial markers
        self.number_of_fiducials = int(self.number_of_fiducials_value.text())
        self.box_size = int(self.box_size_value.text())
        if self.create_ROIs_button.isChecked():
            for i in range(self.number_of_fiducials):
                x_pos = 0
                y_pos = 0 + i*self.box_size
                ROIpos = (x_pos, y_pos) # (0.5*numberofPixels - 0.5*box_size, 0.5*numberofPixels - 0.5*box_size)
                self.roi[i] = viewbox_tools.ROI(self.box_size, self.vb, ROIpos,
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
                self.lockAndTrackSignal.emit(True)
                self.data_ROI = {}
                self.coord_ROI = {}
            else:
                print('Warning! Lock and Track can only be used if fiducials\' ROIs have been created.')
        else:
            self.lockAndTrackSignal.emit(False)
            self.driftPlot.clear()
            self.xy_fiducials.clear()
        return
    
    def retrieve_fiducials_data(self):
        for i in range(self.number_of_fiducials):
            (self.data_ROI[i], \
             self.coord_ROI[i]) = self.roi[i].getArrayRegion(self.image, \
                                                            self.img, \
                                                            axis = (1, 0), \
                                                            returnMappedCoords = True)
        self.fitFiducialsSignal.emit(self.number_of_fiducials, self.data_ROI, self.coord_ROI)
        return

    @pyqtSlot(dict, dict)
    def receive_fitted_data(self, xy_pos, timestamp):
        for i in range(self.number_of_fiducials):
            # plot xy position of fiducials vs time
            self.driftPlot.plot(x = [timestamp[i]], y = [xy_pos[i][1]], size = 8, \
                                symbol = 'o', pen = pg.mkPen('w', width = 1))
            self.driftPlot.plot(x = [timestamp[i]], y = [xy_pos[i][0]], size = 8, \
                                symbol = 's', pen = pg.mkPen('w', width = 1))
            self.driftPlot.setXRange(timestamp[i] - driftbox_length, timestamp[i])
            # draw center of fiducials, xy are inverted and in um
            xy_roi_origin = np.array([self.coord_ROI[i][0,0,0], self.coord_ROI[i][1,0,0]])
            print('frontend', xy_roi_origin)
            pixel_size_um = self.pixel_size/1000
            xy_pos_pixels = xy_pos[i]/pixel_size_um + xy_roi_origin
            print('frontend', xy_pos[i][0], xy_pos[i][1], xy_pos[i]/pixel_size_um)
            print('frontend', xy_pos_pixels)
            self.xy_fiducials.setData(x = [xy_pos_pixels[1]], y = [xy_pos_pixels[0]])
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
    
    @pyqtSlot(np.ndarray)
    def get_image(self, image):
        self.image = image
        self.img.setImage(self.image, autoLevels = self.autolevel_bool)
        return
    
    @pyqtSlot(list)
    def show_temp(self, list_of_temps):
        self.sensor_temp = list_of_temps[0]
        self.cam_temp = list_of_temps[1]
        self.power_temp = list_of_temps[2]
        self.sensor_temp_value.setText('{:.1f}'.format(self.sensor_temp))
        self.cam_temp_value.setText('{:.1f}'.format(self.cam_temp))
        self.power_temp_value.setText('{:.1f}'.format(self.power_temp))
        return
    
    @pyqtSlot(str)
    def get_file_path(self, file_path):
        self.file_path = file_path
        self.working_dir_label.setText(self.file_path)
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
            self.closeSignal.emit()
            tm.sleep(1)
            app.quit()
        else:
            event.ignore()
            print('Back in business...')    
        return
    
    def make_connections(self, backend):
        backend.imageSignal.connect(self.get_image)
        backend.tempSignal.connect(self.show_temp)
        backend.filePathSignal.connect(self.get_file_path)
        backend.getFiducialsDataSignal.connect(self.retrieve_fiducials_data)
        backend.sendFittedDataSignal.connect(self.receive_fitted_data)
        return
    
#=====================================

# Controls / Backend definition

#=====================================

class Backend(QtCore.QObject):

    imageSignal = pyqtSignal(np.ndarray)
    getFiducialsDataSignal = pyqtSignal()
    sendFittedDataSignal = pyqtSignal(dict, dict)
    tempSignal = pyqtSignal(list)
    filePathSignal = pyqtSignal(str)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewTimer = QtCore.QTimer()
        self.viewTimer.timeout.connect(self.update_view)   
        self.tempTimer = QtCore.QTimer()
        self.tempTimer.timeout.connect(self.update_temp)
        print('Monitoring pco.camera temperature each {:.1f} s.'.format(tempTimer_update/1000))
        self.tempTimer.start(tempTimer_update) # ms
        self.image_np = None
        self.binning = 1
        self.exposure_time_ms = 100
        self.file_path = initial_filepath
        self.trackingTimer = QtCore.QTimer()
        self.trackingTimer.timeout.connect(self.get_fiducials_data)
        self.tracking_period = initial_tracking_period
        self.pixel_size = initial_pixel_size
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
        print('\nBinning changed to {}x{}'.format(binning, binning))
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
        print('Tracking period changed to {:.3f} s.'.format(new_tracking_period/1000))
        self.tracking_period = new_tracking_period
        if lockbool:
            print('Restarting QtTimer...')
            self.trackingTimer.stop()
            self.trackingTimer.start(self.tracking_period)
        return
    
    @pyqtSlot(bool)
    def start_stop_tracking(self, trackbool):
        self.center = {}
        self.timeaxis = {}
        if trackbool:
            print('Locking and tracking fiducials...')
            self.start_tracking_time = timer()
            self.trackingTimer.start(self.tracking_period)
        else:
            self.trackingTimer.stop()
            print('Unlocking...')
        return
    
    def get_fiducials_data(self):
        self.getFiducialsDataSignal.emit()
        return
    
    @pyqtSlot(int, dict, dict)
    def fit_fiducials(self, N, roi_intensity_dict, roi_coordinates_dict):
        for i in range(N):
            frame_intensity = roi_intensity_dict[i]
            frame_coordinates = roi_coordinates_dict[i]
            x_fitted, y_fitted, w0x_fitted, w0y_fitted = drift.fit_with_gaussian(frame_intensity, \
                                                                                 frame_coordinates, \
                                                                                 self.pixel_size, \
                                                                                 self.pixel_size)
            self.center[i] = np.array([x_fitted, y_fitted])
            self.timeaxis[i] = timer() - self.start_tracking_time
            print('backend', x_fitted)
            print('backend', y_fitted)
        self.sendFittedDataSignal.emit(self.center, self.timeaxis)
        return
    
    @pyqtSlot(bool, float)
    def take_picture(self, livebool, exposure_time_ms):
        print('\nPicture taken at', datetime.now())
        self.exposure_time_ms = exposure_time_ms # in ms, is float
        if livebool:
            self.stop_liveview()
        cam.set_exp_time(self.exposure_time_ms)
        cam.config_recorder()
        image_np, metadata = cam.get_image()
        if image_np is not None:
            self.image_np = image_np # assign to class to be able to save it later
            cam.stop()
            self.imageSignal.emit(image_np)            
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
        self.viewTimer.start(viewTimer_update) # ms
        return
            
    def update_view(self):
        # Image update while in Live view mode
        image_np, metadata = cam.get_image()
        self.imageSignal.emit(image_np)
        return
    
    def update_temp(self):
        # Update temp of the camera
        self.sensor_temp, self.cam_temp, self.power_temp = cam.get_temp()
        self.tempSignal.emit([self.sensor_temp, self.cam_temp, self.power_temp])
        return
    
    def stop_liveview(self):
        print('\nLive view stopped at', datetime.now())
        cam.stop()
        self.viewTimer.stop()
        return
    
    @pyqtSlot()    
    def save_picture(self):
        timestr = datetime.today().strftime('%Y-%m-%d_%H-%M-%S')
        filename = "image_pco_test" + timestr + ".tiff"
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
    
    @pyqtSlot()
    def closeBackend(self):
        # laser488.close()
        # laser532.close()
        # flipperMirror.close()
        cam.stop()
        print('Stopping QtTimers...')
        self.viewTimer.stop()
        self.tempTimer.stop()
        print('Exiting thread...')
        workerThread.exit()
        return
    
    def make_connections(self, frontend):
        frontend.roiChangedSignal.connect(self.change_roi)
        frontend.exposureChangedSignal.connect(self.change_exposure)
        frontend.binningChangedSignal.connect(self.change_binning)
        frontend.trackingPeriodChangedSignal.connect(self.change_tracking_period)
        frontend.liveViewSignal.connect(self.liveview) 
        frontend.takePictureSignal.connect(self.take_picture)
        frontend.closeSignal.connect(self.closeBackend)
        frontend.saveSignal.connect(self.save_picture)
        frontend.setWorkDirSignal.connect(self.set_working_folder)
        frontend.lockAndTrackSignal.connect(self.start_stop_tracking)
        frontend.fitFiducialsSignal.connect(self.fit_fiducials)
        return
    
#=====================================

#  Main program

#=====================================        

if __name__ == '__main__':
    # make application
    app = QtGui.QApplication([])
    
    # create both classes
    gui = Frontend()
    worker = Backend()
    
    # thread that run in background
    workerThread = QtCore.QThread()
    worker.moveToThread(workerThread)
    worker.viewTimer.moveToThread(workerThread)
    worker.tempTimer.moveToThread(workerThread)
    worker.trackingTimer.moveToThread(workerThread)
    
    # connect both classes 
    worker.make_connections(gui)
    gui.make_connections(worker)
    
    # start worker in a different thread (avoids GUI freezing)
    workerThread.start()
    
    gui.show()
    app.exec()