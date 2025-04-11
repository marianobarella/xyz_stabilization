# -*- coding: utf-8 -*-
"""
Created on Mon March 17, 2025

pyTrap is a control software of the 2nd gen Plasmonic Optical Tweezer setup that
allows the user to stabilize the system in xyz using a closed-loop system made 
of the piezostage, two cameras, lasers, shutters, flippers, etc.

pyTrap Graphical User Interface integrates the following modules:
    - laser control minimalist
    - apd trace GUI
    - piezostage control
    - xy stabilization
    - z stabilization 

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland
"""

import os
from tkinter import filedialog
import tkinter as tk
import time as tm
from timeit import default_timer as timer
import numpy as np
import scipy.signal as sig
import scipy.interpolate as interp
from pyqtgraph.Qt import QtGui, QtCore
from pyqtgraph.dockarea import DockArea, Dock
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QPushButton, QLabel, QLineEdit, QDialog
import pyqtgraph as pg
import piezo_stage_GUI_two_controllers
import xy_stabilization_GUI_v2
import z_stabilization_GUI_v2
import laser_control_GUI_minimalist
import apd_trace_GUI
import drift_correction_toolbox as drift

# Initial raster scan parameters
initial_scan_range_xy = 4 # in um
initial_scan_range_pixels_xy = 20 # number of pixels
initial_scan_range_z = 16 # in um
initial_scan_range_pixels_z = 64 # number of pixels
x_array = np.linspace(0, initial_scan_range_xy, initial_scan_range_pixels_xy)
y_array = np.linspace(0, initial_scan_range_xy, initial_scan_range_pixels_xy)
xv, yv = np.meshgrid(x_array, y_array)
xy_tuple = (xv, yv)
gaussian_example_spot = drift.gaussian_2D(xy_tuple, 1, 0.8, 1.5, 1, 1, 0)
initial_confocal_image_np = gaussian_example_spot.reshape((initial_scan_range_pixels_xy, initial_scan_range_pixels_xy))
initial_scan_step_time = 50 # in ms
initial_threshold = 0.3 # to filter the confocal image and find the CM
initial_confocal_filepath = 'D:\\daily_data\\confocal_data' # save in SSD for fast and daily use
initial_confocal_filename = 'confocal_scan'

#=====================================

# Autocorrelation Window definition

#===================================== 

class ChildWindow(QDialog):

    closeChildSignal = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__( *args, **kwargs)
        self.setUpGUI()
        # set the title of the window
        self.setWindowTitle("Z scan profile")
        self.setGeometry(150, 150, 800, 600)
        self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, True)
        return

    def setUpGUI(self):
        # widget for the data
        self.viewProfileWidget = pg.GraphicsLayoutWidget()
        self.profile_plot = self.viewProfileWidget.addPlot(row = 1, col = 1)
        self.profile_plot.setYRange(-1, 1)
        self.profile_plot.enableAutoRange(x = True, y = True)
        self.profile_plot.showGrid(x = True, y = True)
        self.profile_plot.setLabel('left', 'Mean transmission (V)')
        self.profile_plot.setLabel('bottom', 'z position (um)')

        # Docks
        gridbox = QtGui.QGridLayout(self)
        dockArea = DockArea()
        viewProfileDock = Dock('Z scan profile viewbox')
        viewProfileDock.addWidget(self.viewProfileWidget)
        dockArea.addDock(viewProfileDock)
        gridbox.addWidget(dockArea, 0, 0) 
        self.setLayout(gridbox)
        return

    def plot_z_profile(self, z_scan_array, z_profile, clear = True, color = 'w', width = 1):
        if clear:
            self.profile_plot.clear()
        self.profile_plot.plot(x = z_scan_array, y = z_profile, \
                                    pen = pg.mkPen(color, width = width))
        return

    # re-define the closeEvent to execute an specific command
    def closeEvent(self, event, *args, **kwargs):
        super(QDialog, self).closeEvent(event, *args, **kwargs)
        self.close()
        self.closeChildSignal.emit()
        return   

#=====================================

# GUI / Frontend definition

#=====================================

class Frontend(QtGui.QMainWindow):
    
    closeSignal = pyqtSignal(bool)
    sendParametersSignal = pyqtSignal(list)
    goToCMSignal = pyqtSignal()
    goToMaxZSignal = pyqtSignal()
    rasterScanSignal = pyqtSignal(bool)
    zScanSignal = pyqtSignal(bool)
    send_go_to_cm_auto_signal = pyqtSignal(bool)
    send_go_to_max_z_auto_signal = pyqtSignal(bool)
    saveConfocalSignal = pyqtSignal()
    autoSaveConfocalSignal = pyqtSignal(bool)
    setConfocalWorkDirSignal = pyqtSignal()
    confocalFilenameSignal = pyqtSignal(str)
    
    def __init__(self, piezo_frontend, main_app = True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cwidget = QtGui.QWidget()
        self.setCentralWidget(self.cwidget)
        self.setWindowTitle('pyTrap')
        self.setGeometry(5, 30, 1900, 900) # x pos, y pos, width, height
        self.main_app = main_app
        # import frontend modules
        # piezo widget (frontend) must be imported in the main
        # hide piezo GUI on the xy and z widgets
        self.piezoWidget = piezo_frontend
        self.xyWidget = xy_stabilization_GUI_v2.Frontend(piezo_frontend, \
                                                    show_piezo_subGUI = False, \
                                                    main_app = False, \
                                                    connect_to_piezo_module = False)
        self.zWidget = z_stabilization_GUI_v2.Frontend(piezo_frontend, \
                                                       show_piezo_subGUI = False, \
                                                       main_app = False, \
                                                       connect_to_piezo_module = False)
        self.apdTraceWidget = apd_trace_GUI.Frontend()
        self.laserControlWidget = laser_control_GUI_minimalist.Frontend()
        self.confocal_filename = initial_confocal_filename
        self.confocal_filepath = initial_confocal_filepath
        self.setUpGUI()
        self.set_parameters()
        self.get_confocal_image(initial_confocal_image_np)
        self.go_to_cm_auto_flag = True
        self.go_to_max_z_auto_flag = True
        # Create an instance of the child window
        self.child_window = ChildWindow()
        self.save_confocal_flag = True
        return
    
    def setUpGUI(self):
        
        # Raster scan button
        self.rasterScanButton = QtGui.QPushButton('Raster Scan')
        self.rasterScanButton.setCheckable(True)
        self.rasterScanButton.clicked.connect(self.play_pause_confocal_scan)
        self.rasterScanButton.setToolTip('Acquire a raster scan around the nanostructure.')
        self.rasterScanButton.setStyleSheet(
            "QPushButton:pressed { background-color: red; }"
            "QPushButton::checked { background-color: lightcoral; }")
        
        # Scanning parameters
        scanRangeLabel_x = QtGui.QLabel('Range x (µm)')
        self.scanRangeEdit_x = QtGui.QLineEdit(str(initial_scan_range_xy))
        self.scanRangeEdit_x.setFixedWidth(50)
        self.scanRangeEdit_x.setValidator(QtGui.QDoubleValidator(0.0, 20.0, 3))

        NxLabel = QtGui.QLabel('Number of pixels x')
        self.NxEdit = QtGui.QLineEdit(str(initial_scan_range_pixels_xy))
        self.NxEdit.setFixedWidth(50)
        self.NxEdit.setValidator(QtGui.QIntValidator(0, 100))

        scanRangeLabel_y = QtGui.QLabel('Range y (µm)')        
        self.scanRangeEdit_y = QtGui.QLineEdit(str(initial_scan_range_xy))
        self.scanRangeEdit_y.setFixedWidth(50)
        self.scanRangeEdit_y.setValidator(QtGui.QDoubleValidator(0.0, 20.0, 3))

        NyLabel = QtGui.QLabel('Number of pixels y')
        self.NyEdit = QtGui.QLineEdit(str(initial_scan_range_pixels_xy))
        self.NyEdit.setFixedWidth(50)
        self.NyEdit.setValidator(QtGui.QIntValidator(0, 100))
        
        scanRangeLabel_z = QtGui.QLabel('Range z (µm)')        
        self.scanRangeEdit_z = QtGui.QLineEdit(str(initial_scan_range_z))
        self.scanRangeEdit_z.setFixedWidth(50)
        self.scanRangeEdit_z.setValidator(QtGui.QDoubleValidator(0.0, 20.0, 3))

        NzLabel = QtGui.QLabel('Number of pixels z')
        self.NzEdit = QtGui.QLineEdit(str(initial_scan_range_pixels_z))
        self.NzEdit.setFixedWidth(50)
        self.NzEdit.setValidator(QtGui.QIntValidator(0, 100))

        pixel_time_label = QtGui.QLabel('Pixel time (ms)')
        self.pixel_time_edit = QtGui.QLineEdit(str(initial_scan_step_time))
        self.pixel_time_edit.setFixedWidth(50)

        # Z scan button
        self.zScanButton = QtGui.QPushButton('Z Scan')
        self.zScanButton.setCheckable(True)
        self.zScanButton.clicked.connect(self.play_pause_z_scan)
        self.zScanButton.setToolTip('Acquire a scan along z axis at the current position.')
        self.zScanButton.setStyleSheet(
            "QPushButton:pressed { background-color: red; }"
            "QPushButton::checked { background-color: lightcoral; }")
        
        # Interface and Buttons of CM and Z
        self.goToZMaxButton = QtGui.QPushButton('Go to max Z')
        self.goToZMaxButton.clicked.connect(self.go_to_max_z)        

        # Interface and Buttons of CM and Gauss
        self.goToCMButton = QtGui.QPushButton('Go to CM')
        self.goToCMButton.clicked.connect(self.go_to_CM)

        # go to CM always tick button
        self.alwaysCMTickBox = QtGui.QCheckBox('Always Go-to-CM?')
        self.alwaysCMTickBox.setChecked(True)
        self.alwaysCMTickBox.stateChanged.connect(self.enable_autoCM)
        self.alwaysCMTickBox.setToolTip('Set/Tick to enable Go-to-CM after scanning.')

        # go to max z always tick button
        self.alwaysZTickBox = QtGui.QCheckBox('Always Go-to-Max-Z?')
        self.alwaysZTickBox.setChecked(True)
        self.alwaysZTickBox.stateChanged.connect(self.enable_auto_max_z)
        self.alwaysZTickBox.setToolTip('Set/Tick to enable Go-to-Max-Z after scanning.')

        threshold_label = QtGui.QLabel('Threshold for CM:')        
        self.thresholdEdit = QtGui.QLineEdit(str(initial_threshold))
        self.thresholdEdit.setFixedWidth(50)
        self.thresholdEdit.setValidator(QtGui.QDoubleValidator(0.0, 1.0, 2))
        self.thresholdEdit.setToolTip('Find the CM using only pixels above this level (normalized confocal image).')

        self.scanRangeEdit_x.editingFinished.connect(self.set_parameters)
        self.scanRangeEdit_y.editingFinished.connect(self.set_parameters) 
        self.scanRangeEdit_z.editingFinished.connect(self.set_parameters) 
        self.NxEdit.editingFinished.connect(self.set_parameters) 
        self.NyEdit.editingFinished.connect(self.set_parameters)
        self.NzEdit.editingFinished.connect(self.set_parameters)
        self.pixel_time_edit.editingFinished.connect(self.set_parameters)
        self.thresholdEdit.editingFinished.connect(self.set_parameters)

        self.saveConfocalButton = QtGui.QPushButton('Save confocal data')
        self.saveConfocalButton.clicked.connect(self.save_confocal_data) 
        self.saveConfocalButton.setToolTip('Saves the confocal image and the traces.')

        self.saveConfocalTickBox = QtGui.QCheckBox('Automatically save?')
        self.saveConfocalTickBox.stateChanged.connect(self.enable_confocal_autosave) 
        self.saveConfocalTickBox.setChecked(True)
        self.saveConfocalTickBox.setToolTip('Set/Tick to automatically save the confocal data.')

        coord_x_label = QtGui.QLabel('Center x (µm):')
        coord_y_label = QtGui.QLabel('Center y (µm):')        

        self.coord_x_value = QtGui.QLabel('NaN')
        self.coord_y_value = QtGui.QLabel('NaN')

        # Working folder
        self.confocal_working_dir_button = QtGui.QPushButton('Select directory')
        self.confocal_working_dir_button.clicked.connect(self.set_working_dir)
        self.confocal_working_dir_button.setStyleSheet(
            "QPushButton:pressed { background-color: lightcoral; }")
        self.confocal_working_dir_label = QtGui.QLabel('Working directory')
        self.confocal_working_dir_path = QtGui.QLineEdit(self.confocal_filepath)
        self.confocal_working_dir_path.setFixedWidth(300)
        self.confocal_working_dir_path.setReadOnly(True)
        self.confocal_filename_label = QtGui.QLabel('Filename (.npy)')
        self.confocal_filename_edit = QtGui.QLineEdit(self.confocal_filename)
        self.confocal_filename_edit.setFixedWidth(300)
        self.confocal_filename_edit.editingFinished.connect(self.set_filename)

        # Image raster scan
        self.confocalImageWidget = pg.GraphicsLayoutWidget()
        self.confocalImageWidget.setAspectLocked(True)
        
        # Confocal Image
        self.confocal_img_item = pg.ImageItem()
        self.confocal_img_item.setOpts(axisOrder = 'row-major')
        self.point_graph_CM = pg.ScatterPlotItem(size = 10, \
                                                 symbol = 'x', \
                                                 color = 'b')
        self.xlabel = pg.AxisItem(orientation = 'bottom')
        labelStyle = {'color': '#FFF', 'font-size': '8pt'}
        self.xlabel.setLabel('x', units = 'um',**labelStyle)
        self.ylabel = pg.AxisItem(orientation = 'left')
        self.ylabel.setLabel('y', units = 'um',**labelStyle)
        initial_pixel_size_xy = round(initial_scan_range_xy/initial_scan_range_pixels_xy, 3) # in um
        self.get_view_scale(initial_pixel_size_xy, initial_pixel_size_xy)
        self.vb = self.confocalImageWidget.addPlot(axisItems={'left': self.ylabel, \
                                                         'bottom': self.xlabel} )
        self.vb.addItem(self.confocal_img_item)
        self.vb.addItem(self.point_graph_CM)
        self.vb.invertY()
        self.vb.setAspectLocked(True)
        self.hist = pg.HistogramLUTItem(image = self.confocal_img_item)
        # Select among 'thermal', 'flame', 'yellowy', 'bipolar', 'spectrum', 'cyclic', 'greyclip', 'grey'
        self.hist.gradient.loadPreset('plasma')
        #self.hist.vb.setLimits(yMin=0, yMax=66000)
        for tick in self.hist.gradient.ticks:
            tick.hide()
        self.confocalImageWidget.addItem(self.hist, row = 0, col = 1)

        # organize buttons
        self.confocalButtonsWidget = QtGui.QWidget()
        layout_confocal = QtGui.QGridLayout()
        self.confocalButtonsWidget.setLayout(layout_confocal) 
        layout_confocal.addWidget(self.rasterScanButton,            0, 0, 1, 2)
        layout_confocal.addWidget(self.goToCMButton,                1, 0)
        layout_confocal.addWidget(self.alwaysCMTickBox,             1, 1)
        layout_confocal.addWidget(threshold_label,                  2, 0)
        layout_confocal.addWidget(self.thresholdEdit,               2, 1)
        layout_confocal.addWidget(coord_x_label,                    3, 0)
        layout_confocal.addWidget(self.coord_x_value,               3, 1)
        layout_confocal.addWidget(coord_y_label,                    4, 0)        
        layout_confocal.addWidget(self.coord_y_value,               4, 1)
        layout_confocal.addWidget(scanRangeLabel_x,                 0, 2)        
        layout_confocal.addWidget(self.scanRangeEdit_x,             0, 3)
        layout_confocal.addWidget(scanRangeLabel_y,                 1, 2)        
        layout_confocal.addWidget(self.scanRangeEdit_y,             1, 3)
        layout_confocal.addWidget(NxLabel,                          2, 2)        
        layout_confocal.addWidget(self.NxEdit,                      2, 3)
        layout_confocal.addWidget(NyLabel,                          3, 2)        
        layout_confocal.addWidget(self.NyEdit,                      3, 3)
        layout_confocal.addWidget(pixel_time_label,                 4, 2)
        layout_confocal.addWidget(self.pixel_time_edit,             4, 3)
        layout_confocal.addWidget(scanRangeLabel_z,                 5, 2)
        layout_confocal.addWidget(self.scanRangeEdit_z,             5, 3)
        layout_confocal.addWidget(NzLabel,                          6, 2)
        layout_confocal.addWidget(self.NzEdit,                      6, 3)
        layout_confocal.addWidget(self.zScanButton,                 5, 0, 1, 2)
        layout_confocal.addWidget(self.goToZMaxButton,              6, 0)
        layout_confocal.addWidget(self.alwaysZTickBox,              6, 1)
        layout_confocal.addWidget(self.saveConfocalButton,          7, 0)
        layout_confocal.addWidget(self.saveConfocalTickBox,         7, 1)
        layout_confocal.addWidget(self.confocal_working_dir_button, 7, 2)
        layout_confocal.addWidget(self.confocal_working_dir_label,  8, 0)
        layout_confocal.addWidget(self.confocal_working_dir_path,   8, 1, 1, 3)
        layout_confocal.addWidget(self.confocal_filename_label,     9, 0)
        layout_confocal.addWidget(self.confocal_filename_edit,      9, 1, 1, 3)

        # GUI layout
        grid = QtGui.QGridLayout()
        self.cwidget.setLayout(grid)
        # Dock Area
        dockArea = DockArea()
        self.dockArea = dockArea
        grid.addWidget(self.dockArea)
        
        # Start with the transmission module
        transDock = Dock('Transmission', size = (100, 1))
        transDock.addWidget(self.apdTraceWidget)
        self.dockArea.addDock(transDock)

        # Add piezo module
        piezoDock = Dock('Piezostage control', size = (20, 1))
        piezoDock.addWidget(self.piezoWidget)
        self.dockArea.addDock(piezoDock, 'right', transDock)

        # Add xy stabilization module
        xyDock = Dock('xy stabilization', size = (1, 1))
        xyDock.addWidget(self.xyWidget)
        self.dockArea.addDock(xyDock, 'right', piezoDock)

        # Add confocal scan module: Image
        confocalImageDock = Dock('Confocal scan', size = (50, 1))
        confocalImageDock.addWidget(self.confocalImageWidget)
        # Add confocal scan module: Parameters
        confocalImageDock.addWidget(self.confocalButtonsWidget)
        dockArea.addDock(confocalImageDock, 'bottom', piezoDock)

        # Add lasers and shutters module
        laserControlDock = Dock('Lasers and shutters', size = (1, 1))
        laserControlDock.addWidget(self.laserControlWidget)
        laserControlDock.hideTitleBar()
        self.dockArea.addDock(laserControlDock, 'bottom', confocalImageDock)

        # Add z stabilization module
        zDock = Dock('z stabilization', size = (1, 1))
        zDock.addWidget(self.zWidget)
        self.dockArea.addDock(zDock, 'bottom', xyDock)
        return
           
    def go_to_CM(self):
        self.goToCMSignal.emit()
        return

    def go_to_max_z(self):
        self.goToMaxZSignal.emit()
        return

    def save_confocal_data(self):
        self.saveConfocalSignal.emit()
        return

    def enable_autoCM(self, enablebool):
        if enablebool:
            self.go_to_cm_auto_flag = True
        else:
            self.go_to_cm_auto_flag = False
        self.send_go_to_cm_auto_signal.emit(self.go_to_cm_auto_flag)
        return

    def enable_auto_max_z(self, enablebool):
        if enablebool:
            self.go_to_max_z_auto_flag = True
        else:
            self.go_to_max_z_auto_flag = False
        self.send_go_to_max_z_auto_signal.emit(self.go_to_max_z_auto_flag)
        return

    def enable_confocal_autosave(self, enablebool):
        if enablebool:
            self.save_confocal_flag = True
        else:
            self.save_confocal_flag = False
        self.autoSaveConfocalSignal.emit(self.save_confocal_flag)
        return

    @pyqtSlot(list) 
    def plot_CM(self, cm_position_list):
        self.coord_x_value.setText('{:.3f}'.format(cm_position_list[0]))
        self.coord_y_value.setText('{:.3f}'.format(cm_position_list[1]))
        x_point = cm_position_list[2] + 0.5 # add half-pixel to correctly plot
        y_point = cm_position_list[3] + 0.5 # add half-pixel to correctly plot
        self.point_graph_CM.clear()
        self.point_graph_CM.setData([x_point], [y_point])
        self.point_graph_CM.show()
        return

    @pyqtSlot(np.ndarray)
    def get_confocal_image(self, confocal_image):
        self.confocal_img_item.setImage(confocal_image)
        return

    @pyqtSlot(float, float)
    def get_view_scale(self, px, py):
       self.xlabel.setScale(scale = px)
       self.ylabel.setScale(scale = py)
       return

    def set_parameters(self):
        self.parameters_list = [float(self.scanRangeEdit_x.text()), \
                                float(self.scanRangeEdit_y.text()), \
                                int(self.NxEdit.text()), \
                                int(self.NyEdit.text()), \
                                int(self.pixel_time_edit.text()), \
                                float(self.scanRangeEdit_z.text()), \
                                int(self.NzEdit.text()), \
                                float(self.thresholdEdit.text())]
        self.sendParametersSignal.emit(self.parameters_list)
        return

    def play_pause_confocal_scan(self):
        if self.rasterScanButton.isChecked():
            # set the paramters for the scan
            self.set_parameters()
            # clear image and send signal to perform the scan
            self.confocal_img_item.clear()
            self.point_graph_CM.clear()
            self.rasterScanSignal.emit(True)
        else:
            # send signal to stop the scan
            self.rasterScanSignal.emit(False)
        return

    def play_pause_z_scan(self):
        if self.zScanButton.isChecked():
            # set the paramters for the scan
            self.set_parameters()
            self.zScanSignal.emit(True)
        else:
            # send signal to stop the scan
            self.zScanSignal.emit(False)
        return

    @pyqtSlot()
    def confocal_scan_stopped(self):
        # uncheck scan button
        self.rasterScanButton.setChecked(False)
        return

    @pyqtSlot()
    def z_scan_stopped(self):
        # uncheck scan button
        self.zScanButton.setChecked(False)
        return

    @pyqtSlot(np.ndarray, np.ndarray, bool, str, int)
    def get_z_profile(self, z_scan_array, z_profile, clear_flag, color, width):
        # show the child window
        self.child_window.plot_z_profile(z_scan_array, z_profile, clear_flag, color, width)
        self.child_window.show()
        return

    @pyqtSlot(float, float, float)
    def get_z_max(self, z_max, min_transmission, max_transmission):
        # show the child window
        self.child_window.plot_z_profile([z_max, z_max], [min_transmission, max_transmission], False, 'g', 2)
        self.child_window.show()
        return

    def set_working_dir(self):
        self.setConfocalWorkDirSignal.emit()
        return

    def set_filename(self):
        filename = self.confocal_filename_edit.text()
        if filename != self.confocal_filename:
            self.confocal_filename = filename
            self.confocalFilenameSignal.emit(self.confocal_filename)    
        return

    @pyqtSlot(str)
    def get_confocal_filepath(self, filepath):
        self.confocal_filepath = filepath
        self.confocal_working_dir_path.setText(self.confocal_filepath)
        return

    # re-define the closeEvent to execute an specific command
    def closeEvent(self, event, *args, **kwargs):
        super().closeEvent(event, *args, **kwargs)
        # dialog box
        reply = QtGui.QMessageBox.question(self, 'Exit', 'Are you sure you want to exit the program?',
                                           QtGui.QMessageBox.No |
                                           QtGui.QMessageBox.Yes)
        if reply == QtGui.QMessageBox.Yes:
            event.accept()
            print('\nClosing GUI...')
            self.close()
            self.closeSignal.emit(self.main_app)
            tm.sleep(1)
            app.quit()
        else:
            event.ignore()
            print('Back in business...')    
        return
    
    def make_modules_connections(self, backend):
        backend.sendConfocalImageSignal.connect(self.get_confocal_image)
        backend.sendZProfileSignal.connect(self.get_z_profile)
        backend.sendZMaxValueSignal.connect(self.get_z_max)
        backend.sendCMSignal.connect(self.plot_CM)
        backend.confocalScanStopped.connect(self.confocal_scan_stopped)
        backend.zScanStopped.connect(self.z_scan_stopped)
        backend.confocalFilepathSignal.connect(self.get_confocal_filepath)
        # connect Frontend modules with their respectives Backend modules
        backend.piezoWorker.make_connections(self.piezoWidget)
        backend.xyWorker.make_connections(self.xyWidget)
        backend.zWorker.make_connections(self.zWidget)
        backend.apdTraceWorker.make_connections(self.apdTraceWidget)
        backend.laserControlWorker.make_connections(self.laserControlWidget)
        return
            
#=====================================

# Controls / Backend definition

#===================================== 
        
class Backend(QtCore.QObject):

    sendCMSignal = pyqtSignal(list)
    confocalScanStopped = pyqtSignal()
    zScanStopped = pyqtSignal()
    confocalScanStoppedInnerSignal = pyqtSignal()
    zScanStoppedInnerSignal = pyqtSignal()
    sendConfocalImageSignal = pyqtSignal(np.ndarray)
    sendZProfileSignal = pyqtSignal(np.ndarray, np.ndarray, bool, str, int)
    sendZMaxValueSignal = pyqtSignal(float, float, float)
    confocalFilepathSignal = pyqtSignal(str)
    
    def __init__(self, piezo_stage_xy, piezo_stage_z, piezo_backend, \
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.piezo_stage_xy = piezo_stage_xy
        self.piezo_stage_z = piezo_stage_z
        # there's only one backend in the piezo_stage_GUI_two_controllers
        self.piezoWorker = piezo_backend
        self.xyWorker = xy_stabilization_GUI_v2.Backend(piezo_stage_xy, \
                                                     piezo_backend, \
                                                     connect_to_piezo_module = False)
        self.zWorker = z_stabilization_GUI_v2.Backend(piezo_stage_z, \
                                                   piezo_backend, \
                                                   connect_to_piezo_module = False)
        self.apdTraceWorker = apd_trace_GUI.Backend()
        self.laserControlWorker = laser_control_GUI_minimalist.Backend()
        self.scan_flag = False
        self.scan_range_x = initial_scan_range_xy
        self.scan_range_y = initial_scan_range_xy
        self.scan_range_z = initial_scan_range_z
        self.scan_range_pixels_x = initial_scan_range_pixels_xy
        self.scan_range_pixels_y = initial_scan_range_pixels_xy
        self.scan_range_pixels_z = initial_scan_range_pixels_z
        self.pixel_size_x = self.scan_range_x/self.scan_range_pixels_x # in um
        self.pixel_size_y = self.scan_range_y/self.scan_range_pixels_y # in um
        self.pixel_size_z = self.scan_range_z/self.scan_range_pixels_z # in um
        self.cm_position_x = np.nan # in um
        self.cm_position_y = np.nan # in um
        self.go_to_cm_auto_flag = True
        self.go_to_z_max_auto_flag = True
        self.confocal_image = initial_confocal_image_np
        self.update_position()
        # set timer to do the confocal scan
        self.confocalTimer = QtCore.QTimer()
        # configure the connection to allow queued executions to avoid interruption of previous calls
        self.confocalTimer.timeout.connect(self.execute_confocal_scan, QtCore.Qt.QueuedConnection)
        # set timer to do the z scan
        self.zTimer = QtCore.QTimer()
        # configure the connection to allow queued executions to avoid interruption of previous calls
        self.zTimer.timeout.connect(self.execute_z_scan, QtCore.Qt.QueuedConnection)
        self.scan_step_time = initial_scan_step_time
        self.x0 = 10 # in um
        self.y0 = 10 # in um
        self.z0 = 10 # in um
        self.threshold_for_cm = initial_threshold
        self.number_of_points_confocal = 0
        self.save_confocal_flag = False
        self.confocal_filename = initial_confocal_filename
        self.confocal_filepath = initial_confocal_filepath
        self.save_counter = 0
        return

    @pyqtSlot(list)
    def set_confocal_scan_parameters(self, parameters_list):
        self.scan_range_x = parameters_list[0]
        self.scan_range_y = parameters_list[1]
        self.scan_range_pixels_x = parameters_list[2]
        self.scan_range_pixels_y = parameters_list[3]
        self.scan_step_time = parameters_list[4]
        self.scan_range_z = parameters_list[5]
        self.scan_range_pixels_z = parameters_list[6]
        self.threshold_for_cm = parameters_list[7]
        self.pixel_size_x = self.scan_range_x/self.scan_range_pixels_x # in um
        self.pixel_size_y = self.scan_range_y/self.scan_range_pixels_y # in um
        self.pixel_size_z = self.scan_range_z/self.scan_range_pixels_z # in um
        print('\nConfocal scan parameters has been set to:')
        print('Range x (um): {:.3f}\nRange y (um): {:.3f}'.format(self.scan_range_x, self.scan_range_y))
        print('Pixels x: {:d}\nPixels y: {:d}'.format(self.scan_range_pixels_x, self.scan_range_pixels_y))
        print('Pixel size x (um): {:.3f}\nPixel size y (um): {:.3f}'.format(self.pixel_size_x, self.pixel_size_y))
        print('Pixel time (ms): {:d}'.format(self.scan_step_time))
        print('Range z (um): {:.3f}\nPixels z: {:.3f}'.format(self.scan_range_z, self.scan_range_pixels_z))
        print('Pixel size z (um): {:.3f}'.format(self.pixel_size_z))
        print('Threhsold for filtering: {:.2f}'.format(self.threshold_for_cm))
        return

    def update_position(self):
        self.x_pos, self.y_pos, self.z_pos = self.piezoWorker.read_position()
        return

    ############ Z SCAN ############
    ############ Z SCAN ############
    ############ Z SCAN ############

    @pyqtSlot(bool)
    def do_z_scan(self, enable_scan):
        if enable_scan:
            self.start_z_scan()
        else:
            self.stop_z_scan()
        return 

    def start_z_scan(self):
        # prepare for the scan
        self.prepare_z_scan()
        self.laserControlWorker.shutterTrappingLaser(True)
        # set timer interval to avoid excesive and unnecessary calls
        self.zTimer.setInterval(self.scan_step_time) # in ms
        # set scan flag to True and start Timer
        self.zTimer.start()
        self.z_scan_flag = True
        self.init_time = timer()
        print('\nz scan started at {}'.format(self.init_time))
        return

    def prepare_z_scan(self):
        print('\nPreparing for z scan...')
        # allocate profile and counter
        self.z_profile = np.zeros((self.scan_range_pixels_z))
        self.counter_z_steps = 0   
        # create z array
        # update piezostage position
        self.update_position()
        self.z0 = round(self.z_pos - self.scan_range_z/2 + self.pixel_size_z/2, 3)
        self.z_scan_array = np.arange(self.z0, self.z0 + self.scan_range_z, self.pixel_size_z)
        self.z_scan_array = self.z_scan_array[0:self.scan_range_pixels_z] # limit to the right size
        # print('\nArray of scanning positions:')
        # print('z:', self.z_scan_array)
        # move to scan's origin
        self.piezoWorker.move_absolute([self.x_pos, self.y_pos, self.z0])
        # prepare APD for signal acquisition during the scan
        scan_step_time_seconds = self.scan_step_time/1000 # to s
        self.apdTraceWorker.arm_for_confocal(scan_step_time_seconds)
        return

    @pyqtSlot()
    def stop_z_scan(self):
        self.total_time = timer() - self.init_time
        # stop timer signal
        self.zTimer.stop()
        # set flag to false to indicate acquisition has finished
        self.z_scan_flag = False
        # close shutter
        self.laserControlWorker.shutterTrappingLaser(False)
        print('\nz scan stopped at {}'.format(timer()))
        print('Total time scanning: {:.3f} s'.format(self.total_time))
        # close z's APD task 
        self.apdTraceWorker.disarm_confocal_task() # it's called confocal but is the same!
        # move before exiting the function
        # either to the last (initial) position or the CM
        # emit signal scan has ended
        self.zScanStopped.emit()
        if self.go_to_z_max_auto_flag:
            self.move_to_max_z()
        else:
            # back to initial position
            self.piezoWorker.move_absolute([self.x_pos, self.y_pos, self.z_pos])
        return

    def execute_z_scan(self):
        if self.z_scan_flag:
            # move in rows
            if self.counter_z_steps < self.scan_range_pixels_z:
                current_z_pos = self.z_scan_array[self.counter_z_steps]
                # print(self.counter_z_steps, current_z_pos)
                self.piezoWorker.move_absolute([self.x_pos, self.y_pos, current_z_pos])
                # acquire first
                point_trace_data = self.apdTraceWorker.acquire_confocal_trace()
                # assign the mean value to a point in the profile
                self.z_profile[self.counter_z_steps] = np.mean(point_trace_data)
                # move step in z
                self.counter_z_steps += 1
            else:
                # stop confocal scan
                self.zScanStoppedInnerSignal.emit()
                self.sendZProfileSignal.emit(self.z_scan_array, self.z_profile, True, 'w', 2)
        return

    pyqtSlot()
    def move_to_max_z(self):
        # smooth z profile
        self.z_profile_smooth = sig.savgol_filter(self.z_profile, 3, 1) # array, window, poly-order
        new_z_array = np.arange(self.z_scan_array[0], self.z_scan_array[-1] - 0.001, 0.001)
        # interpolate to 1 nm steps
        self.z_profile_interp_fun = interp.interp1d(self.z_scan_array, self.z_profile_smooth)
        self.z_profile_interp = self.z_profile_interp_fun(new_z_array)
        self.max_z_pos = new_z_array[np.argmax(self.z_profile_interp)]
        # send data to Frontend and plot
        self.sendZProfileSignal.emit(new_z_array, self.z_profile_interp, False, 'm', 2)
        self.sendZMaxValueSignal.emit(self.max_z_pos, 0.95*min(self.z_profile_interp), 1.05*max(self.z_profile_interp))
        if not np.isnan(self.max_z_pos):
            self.piezoWorker.move_absolute([self.x_pos, \
                                            self.y_pos, \
                                            self.max_z_pos])
            print('\nz position is now {:.3f} um'.format(self.max_z_pos))
        return

    @pyqtSlot(bool)
    def set_go_to_max_z_auto(self, go_to_z_max_auto_flag):
        self.go_to_z_max_auto_flag = go_to_z_max_auto_flag
        print('\nAutomatic Go-to-Max-Z:', go_to_z_max_auto_flag)
        return

    ############ CONFOCAL SCAN ############
    ############ CONFOCAL SCAN ############
    ############ CONFOCAL SCAN ############

    @pyqtSlot(bool)
    def do_confocal_scan(self, enable_scan):
        if enable_scan:
            self.start_confocal_scan()
        else:
            self.stop_confocal_scan()
        return 

    def start_confocal_scan(self):
        # prepare for the scan
        self.prepare_confocal_scan()
        self.laserControlWorker.shutterTrappingLaser(True)
        # set timer interval to avoid excesive and unnecessary calls
        self.confocalTimer.setInterval(self.scan_step_time) # in ms
        # set scan flag to True and start Timer
        self.confocalTimer.start()
        self.confocal_scan_flag = True
        self.init_time = timer()
        print('\nConfocal scan started at {}'.format(self.init_time))
        return

    def prepare_confocal_scan(self):
        print('\nPreparing for confocal scan...')
        # create array of positions to be scanned
        self.create_position_grid()        
        # move to scan's origin
        self.piezoWorker.move_absolute([self.x0, self.y0, self.z_pos])
        # prepare APD for signal acquisition during the scan
        scan_step_time_seconds = self.scan_step_time/1000 # to s
        self.number_of_points_confocal = self.apdTraceWorker.arm_for_confocal(scan_step_time_seconds)
        # allocate image and counters
        self.confocal_image = np.zeros((self.scan_range_pixels_x, \
                                        self.scan_range_pixels_y))
        self.traces_array = np.zeros((self.scan_range_pixels_x, \
                                      self.scan_range_pixels_y, \
                                      self.number_of_points_confocal))
        self.counter_x_steps = 0
        self.counter_y_steps = 0
        return

    def create_position_grid(self):
        # update piezostage position
        self.update_position()
        # define arrays of positions for x and y
        self.x0 = round(self.x_pos - self.scan_range_x/2 + self.pixel_size_x/2, 3)
        self.y0 = round(self.y_pos - self.scan_range_y/2 + self.pixel_size_y/2, 3)
        self.x_scan_array = np.arange(self.x0, self.x0 + self.scan_range_x, self.pixel_size_x)
        self.y_scan_array = np.arange(self.y0, self.y0 + self.scan_range_y, self.pixel_size_y)
        self.x_scan_array = self.x_scan_array[0:self.scan_range_pixels_x] # limit to the right size
        self.y_scan_array = self.y_scan_array[0:self.scan_range_pixels_y] # limit to the right size
        # print('\nArrays of scanning positions:')
        # print('x:', self.x_scan_array)
        # print('y:', self.y_scan_array)
        return

    @pyqtSlot()
    def stop_confocal_scan(self):
        self.total_time = timer() - self.init_time
        # stop timer signal
        self.confocalTimer.stop()
        # set flag to false to indicate acquisition has finished
        self.confocal_scan_flag = False
        # close shutter
        self.laserControlWorker.shutterTrappingLaser(False)
        print('\nConfocal scan stopped at {}'.format(timer()))
        print('Total time scanning: {:.3f} s'.format(self.total_time))
        # close confocal's APD task 
        self.apdTraceWorker.disarm_confocal_task()
        # move before exiting the function
        # either to the last (initial) position or the CM
        # emit signal scan has ended
        self.confocalScanStopped.emit()
        if self.go_to_cm_auto_flag:
            try:
                self.move_to_cm()
            except:
                # back to initial position
                self.piezoWorker.move_absolute([self.x_pos, self.y_pos, self.z_pos])
        else:
            # back to initial position
            self.piezoWorker.move_absolute([self.x_pos, self.y_pos, self.z_pos])
        if self.save_confocal_flag:
            self.save_confocal()
        return

    def execute_confocal_scan(self):
        if self.confocal_scan_flag:
            # move in rows
            if self.counter_y_steps < self.scan_range_pixels_y:
                # move in columns
                if self.counter_x_steps < self.scan_range_pixels_x:
                    # move to the target position
                    current_x_pos = self.x_scan_array[self.counter_x_steps]
                    current_y_pos = self.y_scan_array[self.counter_y_steps]
                    # print(self.counter_x_steps, self.counter_y_steps, current_x_pos, current_y_pos)
                    self.piezoWorker.move_absolute([current_x_pos, current_y_pos, self.z_pos])
                    # acquire first
                    pixel_trace_data = self.apdTraceWorker.acquire_confocal_trace()
                    # assign the mean value to a pixel in the image
                    self.confocal_image[self.counter_y_steps, self.counter_x_steps] = np.mean(pixel_trace_data)
                    self.traces_array[self.counter_y_steps, self.counter_x_steps, :] = pixel_trace_data
                    self.sendConfocalImageSignal.emit(self.confocal_image)
                    # move step in x
                    self.counter_x_steps += 1
                else:
                    # a row has been scanned, re-initialize the x counter
                    self.counter_x_steps = 0
                    self.counter_y_steps += 1
            else:
                # stop confocal scan
                self.confocalScanStoppedInnerSignal.emit()
        return

    @pyqtSlot()
    def move_to_cm(self):
        cm_position_list = self.calculate_cm()
        self.absolute_cm_position_x = cm_position_list[0] + self.x0
        self.absolute_cm_position_y = cm_position_list[1] + self.y0
        if (not np.isnan(self.absolute_cm_position_x)) and (not np.isnan(self.absolute_cm_position_y)):
            self.piezoWorker.move_absolute([self.absolute_cm_position_x, \
                                            self.absolute_cm_position_y, \
                                            self.z_pos])
            print('\nxy position centered at the...')
            print('\nCenter of Mass at:  x={:.3f} um  /  y={:.3f} um'.format(self.absolute_cm_position_x, self.absolute_cm_position_y))
        return

    def calculate_cm(self):
        x_array = np.arange(self.scan_range_pixels_x)
        y_array = np.arange(self.scan_range_pixels_y)
        # x_cm_fitted_in_pixels, \
        # y_cm_fitted_in_pixels = drift.fit_with_gaussian_confocal(self.confocal_image, \
        #                                                          x_array, y_array, \
        #                                                          self.threshold_for_cm)
        x_cm_fitted_in_pixels, \
        y_cm_fitted_in_pixels = drift.meas_center_of_mass_confocal(self.confocal_image, \
                                                                  self.threshold_for_cm)
        x_cm_fitted = x_cm_fitted_in_pixels*self.pixel_size_x
        y_cm_fitted = y_cm_fitted_in_pixels*self.pixel_size_y
        cm_position_list = [x_cm_fitted, y_cm_fitted, x_cm_fitted_in_pixels, y_cm_fitted_in_pixels]
        self.sendCMSignal.emit(cm_position_list)
        return cm_position_list

    @pyqtSlot(bool)
    def set_go_to_cm_auto(self, go_to_cm_auto_flag):
        self.go_to_cm_auto_flag = go_to_cm_auto_flag
        print('\nAutomatic Go-to-CM:', go_to_cm_auto_flag)
        return

    @pyqtSlot(bool)
    def set_autosave_confocal(self, save_confocal_flag):
        self.save_confocal_flag = save_confocal_flag
        print('\nConfocal data will be saved:', save_confocal_flag)
        return

    @pyqtSlot()
    def save_confocal(self):
        # define paths
        full_confocal_filepath = os.path.join(self.confocal_filepath, self.confocal_filename)
        full_filepath_confocal_image = full_confocal_filepath + '_image_%04d.npy' % self.save_counter
        full_filepath_traces_array = full_confocal_filepath + '_traces_%04d.npy' % self.save_counter
        full_filepath_xy_array = full_confocal_filepath + '_coords_%04d.npy' % self.save_counter
        # save data
        xy_array = np.transpose([self.x_scan_array, self.y_scan_array])
        np.save(full_filepath_confocal_image, self.confocal_image, allow_pickle = False)
        np.save(full_filepath_traces_array, self.traces_array, allow_pickle = False)
        np.save(full_filepath_xy_array, xy_array, allow_pickle = False)
        print('Confocal data has been saved.')
        self.save_counter += 1
        return

    @pyqtSlot()    
    def set_confocal_working_folder(self):
        root = tk.Tk()
        root.withdraw()
        filepath = filedialog.askdirectory()
        if not filepath:
            print('No folder selected!')
        else:
            self.confocal_filepath = filepath
            print('New folder selected:', self.confocal_filepath)
            self.confocalFilepathSignal.emit(self.confocal_filepath)
        return

    @pyqtSlot(str)
    def set_confocal_filename(self, new_filename):
        self.confocal_filename = new_filename
        print('A new filename for confocal data has been set:', self.confocal_filename)
        return

    @pyqtSlot(bool)
    def close_all_backends(self, main_app = True):
        print('\nClosing all backends...')
        self.piezoWorker.close_backend(main_app = False)
        self.xyWorker.close_backend(main_app = False)
        self.zWorker.close_backend(main_app = False)
        self.apdTraceWorker.close_backend()
        self.laserControlWorker.close_backend()
        print('Stopping QtTimers...')
        self.confocalTimer.stop()
        if main_app:
            print('Exiting thread...')
            tm.sleep(1)
            workerThread.exit()
        return
    
    def make_modules_connections(self, frontend, data_processor):
        self.confocalScanStoppedInnerSignal.connect(self.stop_confocal_scan)
        self.zScanStoppedInnerSignal.connect(self.stop_z_scan)
        frontend.rasterScanSignal.connect(self.do_confocal_scan)
        frontend.zScanSignal.connect(self.do_z_scan)
        frontend.goToCMSignal.connect(self.move_to_cm)
        frontend.goToMaxZSignal.connect(self.move_to_max_z)
        frontend.send_go_to_cm_auto_signal.connect(self.set_go_to_cm_auto)
        frontend.send_go_to_max_z_auto_signal.connect(self.set_go_to_max_z_auto)
        frontend.autoSaveConfocalSignal.connect(self.set_autosave_confocal)
        frontend.saveConfocalSignal.connect(self.save_confocal)
        frontend.sendParametersSignal.connect(self.set_confocal_scan_parameters)
        frontend.setConfocalWorkDirSignal.connect(self.set_confocal_working_folder)
        frontend.confocalFilenameSignal.connect(self.set_confocal_filename)
        frontend.closeSignal.connect(self.close_all_backends)
        # connect Backend modules with their respectives Frontend modules
        frontend.piezoWidget.make_connections(self.piezoWorker)
        frontend.xyWidget.make_connections(self.xyWorker)
        frontend.zWidget.make_connections(self.zWorker)
        frontend.apdTraceWidget.make_connections(self.apdTraceWorker, data_processor)
        frontend.laserControlWidget.make_connections(self.laserControlWorker)
        return
    
#=====================================

#  Main program

#=====================================
      
if __name__ == '__main__':
    # make application
    app = QtGui.QApplication([])
    
    # init stage
    piezo_xy = piezo_stage_GUI_two_controllers.piezo_stage_xy
    piezo_z = piezo_stage_GUI_two_controllers.piezo_stage_z
    piezo_frontend = piezo_stage_GUI_two_controllers.Frontend(main_app = False)
    piezo_backend = piezo_stage_GUI_two_controllers.Backend(piezo_xy, piezo_z)
    
    # create both classes
    gui = Frontend(piezo_frontend)
    worker = Backend(piezo_xy, piezo_z, piezo_backend)
       
    ###################################
    # Thread instances
    # move backend to another thread
    workerThread = QtCore.QThread()
    # move the timer of the piezo and its main worker
    worker.piezoWorker.updateTimer.moveToThread(workerThread)
    worker.piezoWorker.moveToThread(workerThread)
    # move the timers of the xy and its main worker
    worker.xyWorker.viewTimer.moveToThread(workerThread)
    worker.xyWorker.trackingTimer.moveToThread(workerThread)
    worker.xyWorker.tempTimer.moveToThread(workerThread)
    worker.xyWorker.moveToThread(workerThread)
    # move the timers of the z and its main worker
    worker.zWorker.trackingTimer.moveToThread(workerThread)
    worker.zWorker.viewTimer.moveToThread(workerThread)
    worker.zWorker.moveToThread(workerThread)
    # move APD tranmission signal and its timers worker 
    worker.apdTraceWorker.acquireTimer.moveToThread(workerThread)
    worker.apdTraceWorker.moveToThread(workerThread)
    # Instance the data processor thread
    data_processor = apd_trace_GUI.DataProcessorThread()
    # move lasers and shutters worker 
    worker.laserControlWorker.moveToThread(workerThread)
    # move the scan xy and z timers to the main worker
    worker.confocalTimer.moveToThread(workerThread)
    worker.zTimer.moveToThread(workerThread)
    # move the main worker
    worker.moveToThread(workerThread)


    ###################################

    # connect both classes
    data_processor.make_connections(gui.apdTraceWidget)
    worker.make_modules_connections(gui, data_processor)
    gui.make_modules_connections(worker)
    
    # start thread
    workerThread.start()
    data_processor.start()

    gui.show()
    app.exec()
    
    