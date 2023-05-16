# -*- coding: utf-8 -*-
"""
Created on Fri April 8, 2022

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland
"""

import numpy as np
from timeit import default_timer as timer
import os
# import sys
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
# import pyqtgraph.ptime as ptime
from pyqtgraph.dockarea import Dock, DockArea
from PyQt5.QtCore import pyqtSignal, pyqtSlot
import daq_board_toolbox as daq
from tkinter import filedialog
import tkinter as tk
import time as tm
# import asyncio

#=====================================

# Initialize DAQ board

#=====================================

print('\nInitializing DAQ board...')
daq_board = daq.init_daq()
# set measure and update trace plot period
updateTrace_period = 30 # in ms
# set measurement range
initial_voltage_range = 2.0
daq.check_voltage_range(daq_board, initial_voltage_range)
# set sampling rate
max_sampling_rate = daq_board.ai_max_single_chan_rate # set to maximum, here 2 MS/s    
initial_sampling_rate = 1e3 # in S/s
# duration of the traces in s
initial_duration = 1
# set acquisition mode to measure continuosly
acquisition_mode = 'continuous'
# number of analog input channels to read
number_of_channels = 2

# function that calculates the number of datapoins to be measured
def calculate_num_of_points(duration, sampling_rate):
    number_of_points = int(duration*sampling_rate)
    print('\nAt {:.3f} MS/s sampling rate, a duration of {} s means:'.format(sampling_rate*1e-6, \
                                                                       duration))
    print('{} datapoints per trace'.format(number_of_points))
    return number_of_points

# define a fixed length (in s) for the time axis of viewbox signal vs time
initial_viewbox_length = 2 # in s
# define a downsampling period for visualization purposes
initial_downsampling_period = 1
# initial Y range
initial_min_y_range = -0.01
initial_max_y_range = 0.03
initial_mean_value = 0
initial_sd_value = 0.2
# initial filepath and filename
initial_filepath = 'D:\\daily_data\\apd_traces' # save in SSD for fast and daily use
initial_filename = 'signal_XX'

#=====================================

# Fast Plot Class definition

#=====================================

class FastLine(pg.QtGui.QGraphicsPathItem):
    def __init__(self, x, y, color = 'w'):
        # from https://stackoverflow.com/questions/17103698/plotting-large-arrays-in-pyqtgraph?rq=1
        """x and y are 1D arrays"""
        self.path = pg.arrayToQPath(x, y, connect = 'all', finiteCheck = True)
        pg.QtGui.QGraphicsPathItem.__init__(self, self.path)
        self.setPen(pg.mkPen(color))
    def shape(self): # override because QGraphicsPathItem.shape is too expensive.
        return pg.QtGui.QGraphicsItem.shape(self)
    def boundingRect(self):
        return self.path.boundingRect()

#=====================================

# GUI / Frontend definition

#=====================================

class Frontend(QtGui.QFrame):

    traceSignal = pyqtSignal(bool)
    makeTraceContSignal = pyqtSignal(bool)
    saveTraceContSignal = pyqtSignal(bool)
    saveTraceASCIISignal = pyqtSignal(bool)
    setVoltageRangeSignal = pyqtSignal(float)
    setSamplingRateSignal = pyqtSignal(int)
    setDurationSignal = pyqtSignal(float)
    saveSignal = pyqtSignal()
    closeSignal = pyqtSignal()
    setWorkDirSignal = pyqtSignal()
    filenameSignal = pyqtSignal(str)
    commentSignal = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setUpGUI()
        # set the title of thw window
        title = "Acquisition module"
        self.setWindowTitle(title)
        self.setGeometry(850, 30, 700, 1000) # x pos, y pos, width, height
        self.set_y_range()
        self.mean_value = initial_mean_value # in V
        self.sd_value = initial_sd_value # in V
        self.set_working_dir()
        self.set_filename()
        self.sampling_rate_changed()
        return
    
    def setUpGUI(self):

        # Single acquisition button
        self.traceButton = QtGui.QPushButton('► Acquire single / ◘ Stop')
        self.traceButton.setCheckable(True)
        self.traceButton.clicked.connect(self.get_trace)
        self.traceButton.setToolTip('Play or Stop a single APD signal acquisition.')
        self.traceButton.setStyleSheet(
            "QPushButton { background-color: lightgray; }"
            "QPushButton:pressed { background-color: red; }"
            "QPushButton::checked { background-color: lightcoral; }")

        # Continuous acquisition tick box
        self.traceContinuouslyBox = QtGui.QCheckBox('Acquire continuously?')
        self.traceContinuouslyBox.setChecked(False)
        self.traceContinuouslyBox.stateChanged.connect(self.set_trace_continuously)
        self.traceContinuouslyBox.setToolTip('Set/Tick to acquire continuously APD signal.')

        # Save data button
        self.saveButton = QtGui.QPushButton('Save last trace')
        self.saveButton.clicked.connect(self.get_save_trace)
        self.saveButton.setStyleSheet(
            "QPushButton { background-color: lightgray; }"
            "QPushButton:pressed { background-color: cornflowerblue; }")
        self.saveButton.setToolTip('Save the trace that was <b>fully</b> acquired in the last seconds (defined by <b>duration</b> variable).')
        
        # Save continuously tick box
        self.saveContinuouslyBox = QtGui.QCheckBox('Save automatically?')
        self.saveContinuouslyBox.setChecked(True)
        self.saveContinuouslyBox.stateChanged.connect(self.set_save_continuously)
        self.saveContinuouslyBox.setToolTip('Set/Tick to save data continuously. Filenames will be sequential.')
        
        # Save in ASCII tick box
        self.saveASCIIBox = QtGui.QCheckBox('Save in ASCII (not recommended)')
        self.saveASCIIBox.setChecked(False)
        self.saveASCIIBox.stateChanged.connect(self.set_save_in_ascii)
        self.saveASCIIBox.setToolTip('Set/Tick to save data in ASCII. WARNING: files will be heavier than in binary (4.5 times more).')
                
        # Working folder
        self.working_dir_button = QtGui.QPushButton('Select directory')
        self.working_dir_button.clicked.connect(self.set_working_dir)
        self.working_dir_button.setStyleSheet(
            "QPushButton { background-color: lightgray; }"
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
        
        # Voltage range
        voltage_ranges_option = ['0.1', '0.2', '0.5', '1.0', '2.0', '5.0', '10.0']
        self.maxVoltageRangeLabel = QtGui.QLabel('Max voltage range (V): ')
        self.maxVoltageRangeList = QtGui.QComboBox()
        self.maxVoltageRangeList.setFixedWidth(100)
        self.maxVoltageRangeList.addItems(voltage_ranges_option)
        self.maxVoltageRangeList.setCurrentText(str(initial_voltage_range))
        self.maxVoltageRangeList.currentTextChanged.connect(self.voltage_range_changed)
        
        # Sampling rate
        self.samplingRateLabel = QtGui.QLabel('Sampling rate (kS/s): ')
        self.samplingRateValue = QtGui.QLineEdit(str(int(initial_sampling_rate/1e3)))
        self.samplingRateValue.setFixedWidth(100)
        self.sampling_rate = int(initial_sampling_rate/1e3)
        self.time_base = 1/initial_sampling_rate
        self.samplingRateValue.editingFinished.connect(self.sampling_rate_changed)
        self.samplingRateValue.setValidator(QtGui.QIntValidator(1, 2000))

        # Duration of the measurement
        self.duration = initial_duration
        self.durationLabel = QtGui.QLabel('Duration (s) [max 10 min]: ')
        self.durationValue = QtGui.QLineEdit(str(self.duration))
        self.durationValue.setFixedWidth(100)
        self.durationValue.setValidator(QtGui.QDoubleValidator(1.0, 600.0, 1))
        self.durationValue.editingFinished.connect(self.duration_value_changed)
        self.durationValue.setToolTip('Maximum duration set to 600 s (10 min).')
        
        # Comments box
        self.comments_label = QtGui.QLabel('Comments:')
        self.comment = ''
        self.comments = QtGui.QLineEdit(self.comment)
        self.comments.setFixedWidth(300)
        self.comments.setPlaceholderText('Enter your comments here. They will be saved with the trace data.')
        self.comments.editingFinished.connect(self.transmit_comments)
        
        # display mean and std of the signals using labels
        fontsize = 16
        font_family = 'Serif'
        header_col_0 = QtGui.QLabel('Signal (APD)')
        header_col_0.setFont(QtGui.QFont(font_family, 14))
        header_col_1 = QtGui.QLabel('Mean (V)')
        header_col_1.setFont(QtGui.QFont(font_family, 14))
        header_col_2 = QtGui.QLabel('Std dev (mV)')
        header_col_2.setFont(QtGui.QFont(font_family, 14))
        # for transmission APD
        self.label_apd = QtGui.QLabel('Transmission')
        self.label_apd.setFont(QtGui.QFont(font_family, fontsize))
        self.signalMeanValue_apd = QtGui.QLabel('0.000')
        self.signalMeanValue_apd.setFont(QtGui.QFont(font_family, 18, weight=QtGui.QFont.Bold))
        self.signalStdValue_apd = QtGui.QLabel('0.000')
        self.signalStdValue_apd.setFont(QtGui.QFont(font_family, 18, weight=QtGui.QFont.Bold))
        # for monitor APD
        self.label_monitor = QtGui.QLabel('Monitor')
        self.label_monitor.setFont(QtGui.QFont(font_family, fontsize))
        self.signalMeanValue_monitor = QtGui.QLabel('0.000')
        self.signalMeanValue_monitor.setFont(QtGui.QFont(font_family, 18, weight=QtGui.QFont.Bold))
        self.signalStdValue_monitor = QtGui.QLabel('0.000')
        self.signalStdValue_monitor.setFont(QtGui.QFont(font_family, 18, weight=QtGui.QFont.Bold))
        
        # Y range 
        self.min_y_range = initial_min_y_range
        self.max_y_range = initial_max_y_range
        self.minmax_apd_RangeLabel = QtGui.QLabel('Transmission - Min/Max Y range (V): ')
        self.minmax_monitor_RangeLabel = QtGui.QLabel('Monitor - Min/Max Y range (V): ')
        self.minYRangeValue_apd = QtGui.QLineEdit(str(self.min_y_range))
        self.minYRangeValue_apd.setFixedWidth(100)
        self.minYRangeValue_apd.setValidator(QtGui.QDoubleValidator(-10, 10, 6))
        self.maxYRangeValue_apd = QtGui.QLineEdit(str(self.max_y_range))
        self.maxYRangeValue_apd.setFixedWidth(100)
        self.maxYRangeValue_apd.setValidator(QtGui.QDoubleValidator(-10, 10, 6))
        self.minYRangeValue_apd.editingFinished.connect(self.set_y_range)
        self.maxYRangeValue_apd.editingFinished.connect(self.set_y_range)
        self.minYRangeValue_monitor = QtGui.QLineEdit(str(self.min_y_range))
        self.minYRangeValue_monitor.setFixedWidth(100)
        self.minYRangeValue_monitor.setValidator(QtGui.QDoubleValidator(-10, 10, 6))
        self.maxYRangeValue_monitor = QtGui.QLineEdit(str(self.max_y_range))
        self.maxYRangeValue_monitor.setFixedWidth(100)
        self.maxYRangeValue_monitor.setValidator(QtGui.QDoubleValidator(-10, 10, 6))
        self.minYRangeValue_monitor.editingFinished.connect(self.set_y_range)
        self.maxYRangeValue_monitor.editingFinished.connect(self.set_y_range)

        # Downsampling
        self.downsamplingLabel = QtGui.QLabel('Downsampling/averaging (int): ')
        self.downsamplingValue = QtGui.QLineEdit(str(int(initial_downsampling_period)))
        self.downsamplingValue.setFixedWidth(100)
        self.downsamplingValue.setToolTip('For displaying purposes. Number of points to average. The higher the better the performance. Advice: use only for Sampling rates higher than 100 kS/s.')
        self.downsampling_period = initial_downsampling_period
        self.downsamplingValue.editingFinished.connect(self.downsampling_changed)
        self.downsamplingValue.setValidator(QtGui.QIntValidator(1, 1000))
        
        # Time window length
        self.viewbox_length = initial_viewbox_length
        self.timeViewboxLength_label = QtGui.QLabel('Time window length (s): ')
        self.timeViewboxLength_value = QtGui.QLineEdit(str(self.viewbox_length))
        self.timeViewboxLength_value.setFixedWidth(100)
        self.timeViewboxLength_value.setValidator(QtGui.QDoubleValidator(0.1, 10.0, 1))
        self.timeViewboxLength_value.setToolTip('For displaying purposes. Set the time length of the viewbox in seconds.')
        self.timeViewboxLength_value.editingFinished.connect(self.time_viewbox_length_changed)

        # Displaying effective sampling rate a.k.a. display rate
        fontsize = 14
        font_family = 'Serif'
        self.display_rate = self.sampling_rate/self.downsampling_period
        self.points_displayed = np.floor(self.display_rate*1e3*self.viewbox_length)
        display_rate_text = 'Display rate: {:.3f} kS/s    Display period: {:.3f} ms \nPoints displayed: {:.0f}'.format(self.display_rate, 1/self.display_rate, self.points_displayed)
        self.displayRateLabel = QtGui.QLabel(display_rate_text)
        self.displayRateLabel.setFont(QtGui.QFont(font_family, fontsize))
        
        # center-on-the-mean-value-of-the-signal button
        self.centerOnMeanButton = QtGui.QPushButton('Center signals')
        self.centerOnMeanButton.clicked.connect(self.center_signal)
        self.centerOnMeanButton.setStyleSheet(
            "QPushButton { background-color: lightgray; }"
            "QPushButton:pressed { background-color: plum; }")
        self.centerOnMeanButton.setToolTip('For displaying purposes. Center Y axis over the mean of the signal ±5 std dev.')
        
        # Layout for the acquisition widget
        self.paramAcqWidget = QtGui.QWidget()
        subgridAcq_layout = QtGui.QGridLayout()
        self.paramAcqWidget.setLayout(subgridAcq_layout)
        subgridAcq_layout.addWidget(self.traceButton, 0, 0)
        subgridAcq_layout.addWidget(self.traceContinuouslyBox, 0, 1)
        subgridAcq_layout.addWidget(self.saveButton, 1, 0)
        subgridAcq_layout.addWidget(self.saveContinuouslyBox, 1, 1)
        subgridAcq_layout.addWidget(self.saveASCIIBox, 1, 2)
        subgridAcq_layout.addWidget(self.working_dir_label, 3, 0)
        subgridAcq_layout.addWidget(self.working_dir_path, 3, 1, 1, 2)
        subgridAcq_layout.addWidget(self.working_dir_button, 2, 0)
        subgridAcq_layout.addWidget(self.filename_label, 4, 0)
        subgridAcq_layout.addWidget(self.filename_name, 4, 1, 1, 2)
        subgridAcq_layout.addWidget(self.maxVoltageRangeLabel, 5, 0)
        subgridAcq_layout.addWidget(self.maxVoltageRangeList, 5, 1)
        subgridAcq_layout.addWidget(self.samplingRateLabel, 6, 0)
        subgridAcq_layout.addWidget(self.samplingRateValue, 6, 1)
        subgridAcq_layout.addWidget(self.durationLabel, 7, 0)
        subgridAcq_layout.addWidget(self.durationValue, 7, 1)
        subgridAcq_layout.addWidget(self.comments_label, 8, 0)
        subgridAcq_layout.addWidget(self.comments, 8, 1, 1, 2)
         
        # Layout for display controls widget
        self.paramDisplayWidget = QtGui.QWidget()
        subgridDisp_layout = QtGui.QGridLayout()
        self.paramDisplayWidget.setLayout(subgridDisp_layout)
        # transmission APD
        subgridDisp_layout.addWidget(header_col_0, 0, 0)
        subgridDisp_layout.addWidget(header_col_1, 0, 1)
        subgridDisp_layout.addWidget(header_col_2, 0, 2)
        subgridDisp_layout.addWidget(self.label_apd, 1, 0)
        subgridDisp_layout.addWidget(self.signalMeanValue_apd, 1, 1)
        subgridDisp_layout.addWidget(self.signalStdValue_apd, 1, 2)
        # monitor APD
        subgridDisp_layout.addWidget(self.label_monitor, 2, 0)
        subgridDisp_layout.addWidget(self.signalMeanValue_monitor, 2, 1)
        subgridDisp_layout.addWidget(self.signalStdValue_monitor, 2, 2)
        # display ranges
        subgridDisp_layout.addWidget(self.minmax_apd_RangeLabel, 3, 0)
        subgridDisp_layout.addWidget(self.minYRangeValue_apd, 3, 1)
        subgridDisp_layout.addWidget(self.maxYRangeValue_apd, 3, 2)
        subgridDisp_layout.addWidget(self.minmax_monitor_RangeLabel, 4, 0)
        subgridDisp_layout.addWidget(self.minYRangeValue_monitor, 4, 1)
        subgridDisp_layout.addWidget(self.maxYRangeValue_monitor, 4, 2)
        subgridDisp_layout.addWidget(self.centerOnMeanButton, 5, 0, 1, 3)
        subgridDisp_layout.addWidget(self.downsamplingLabel, 6, 0)
        subgridDisp_layout.addWidget(self.downsamplingValue, 6, 1)
        subgridDisp_layout.addWidget(self.timeViewboxLength_label, 7, 0)
        subgridDisp_layout.addWidget(self.timeViewboxLength_value, 7, 1)
        subgridDisp_layout.addWidget(self.displayRateLabel, 8, 0, 1, 3)
        
        # widget for the data
        self.viewTraceWidget = pg.GraphicsLayoutWidget()
        self.signal_plot = self.viewTraceWidget.addPlot(row = 1, col = 1, title = 'APD signal')
        self.signal_plot.enableAutoRange(False, False)
        self.signal_plot.showGrid(x = True, y = True)
        self.signal_plot.setLabel('left', 'Voltage (V)')
        self.signal_plot.setLabel('bottom', 'Time (s)')
        
        # widget for the laser power monitor
        self.monitorTraceWidget = pg.GraphicsLayoutWidget()
        self.monitor_plot = self.monitorTraceWidget.addPlot(row = 1, col = 1, title = 'Monitor power signal')
        self.monitor_plot.enableAutoRange(False, False)
        self.monitor_plot.showGrid(x = True, y = True)
        self.monitor_plot.setLabel('left', 'Voltage (V)')
        self.monitor_plot.setLabel('bottom', 'Time (s)')
        
        # Docks
        gridbox = QtGui.QGridLayout(self)
        dockArea1 = DockArea()
        dockArea2 = DockArea()
        
        acqTraceDock = Dock('Acquisition controls', size=(10,1))
        acqTraceDock.addWidget(self.paramAcqWidget)
        dockArea1.addDock(acqTraceDock)

        displayCtrlDock = Dock('Display controls', size=(10,1))
        displayCtrlDock.addWidget(self.paramDisplayWidget)
        dockArea1.addDock(displayCtrlDock, 'right', acqTraceDock)        

        viewTraceDock = Dock('Trace viewbox', size=(1,1000))
        viewTraceDock.addWidget(self.viewTraceWidget)
        dockArea2.addDock(viewTraceDock)

        monitorTraceDock = Dock('Trace viewbox', size=(1,1000))
        monitorTraceDock.addWidget(self.monitorTraceWidget)
        dockArea2.addDock(monitorTraceDock, 'bottom', viewTraceDock)

        gridbox.addWidget(dockArea1, 0, 0) 
        gridbox.addWidget(dockArea2, 1, 0) 
        self.setLayout(gridbox)
        return

    def set_working_dir(self):
        self.setWorkDirSignal.emit()
        return
    
    @pyqtSlot(str)
    def get_filepath(self, filepath):
        self.filepath = filepath
        self.working_dir_path.setText(self.filepath)
        return
    
    def voltage_range_changed(self, selected_range):
        # Note that changing the QtComboBox option
        # will emit a signal that contains the selected option
        self.voltage_range = float(selected_range)
        self.setVoltageRangeSignal.emit(self.voltage_range)
        return
    
    def sampling_rate_changed(self):
        selected_rate = int(self.samplingRateValue.text())
        if selected_rate != self.sampling_rate:
            self.sampling_rate = selected_rate
            self.time_base = 1/(selected_rate*1e3)
            self.setSamplingRateSignal.emit(selected_rate)
            self.change_downsampling(self.downsampling_period)
        return
    
    def duration_value_changed(self):
        duration = float(self.durationValue.text())
        if duration != self.duration:
            self.duration = duration
            self.setDurationSignal.emit(self.duration)
        return
    
    def time_viewbox_length_changed(self):
        time_viewbox_length = float(self.timeViewboxLength_value.text())
        if time_viewbox_length != self.viewbox_length:
            print('Time length of the viewbox changed to {:.1f} s'.format(time_viewbox_length))
            self.viewbox_length = time_viewbox_length
            self.change_downsampling(self.downsampling_period)
        return
    
    def get_trace(self):
        if self.traceButton.isChecked():
            self.signal_plot.clear()
            # allocate arrays to plot them with improved performance
            # sampling_rate is in kS/s
            # viewbox_length is in s
            # so multiply by 1000 to obtain the right size of N
            N = int(self.viewbox_length*self.sampling_rate*1e3)
            # data array
            self.data_apd_array_to_plot = np.empty(N)
            self.data_apd_array_to_plot[:] = np.nan
            # monitor array
            self.monitor_array_to_plot = np.empty(N)
            self.monitor_array_to_plot[:] = np.nan
            # mean array
            self.mean_apd_array_to_plot = np.empty(N)
            self.mean_apd_array_to_plot[:] = np.nan
            self.mean_monitor_array_to_plot = np.empty(N)
            self.mean_monitor_array_to_plot[:] = np.nan
            # std dev +/- array
            self.std_apd_plus_array_to_plot = np.empty(N)
            self.std_apd_plus_array_to_plot[:] = np.nan
            self.std_apd_minus_array_to_plot = np.empty(N)
            self.std_apd_minus_array_to_plot[:] = np.nan
            self.std_monitor_plus_array_to_plot = np.empty(N)
            self.std_monitor_plus_array_to_plot[:] = np.nan
            self.std_monitor_minus_array_to_plot = np.empty(N)
            self.std_monitor_minus_array_to_plot[:] = np.nan
            # time array
            self.time_array_to_plot = np.empty(N)
            self.time_array_to_plot[:] = np.nan
            # trigger signal
            self.traceSignal.emit(True)
        else:
            self.traceSignal.emit(False) 
        return
    
    def set_trace_continuously(self):
        if self.traceContinuouslyBox.isChecked():
            self.makeTraceContSignal.emit(True)
        else:
            self.makeTraceContSignal.emit(False) 
        return
    
    def set_save_continuously(self):
        if self.saveContinuouslyBox.isChecked():
            self.saveTraceContSignal.emit(True)
        else:
            self.saveTraceContSignal.emit(False) 
        return
    
    def set_save_in_ascii(self):
        if self.saveASCIIBox.isChecked():
            self.saveTraceASCIISignal.emit(True)
        else:
            self.saveTraceASCIISignal.emit(False) 
        return
    
    def downsampling_changed(self):
        downsampling_period = int(self.downsamplingValue.text())
        if downsampling_period != self.downsampling_period:
            print('Downsampling has changed to {} points'.format(downsampling_period))
            self.change_downsampling(downsampling_period)            
        return

    def change_downsampling(self, downsampling_period):
        self.display_rate = self.sampling_rate/downsampling_period
        self.points_displayed = np.floor(self.display_rate*1e3*self.viewbox_length)
        print('\nDisplaying at {} kS/s'.format(self.display_rate))
        new_text = 'Display rate: {:.3f} kS/s    Display period: {:.3f} ms \nPoints displayed: {:.0f}'.format(self.display_rate, 1/self.display_rate, self.points_displayed)
        self.displayRateLabel.setText(new_text)
        self.downsampling_period = downsampling_period
        return
    
    def get_save_trace(self):
        if self.saveButton.isChecked:
            self.saveSignal.emit()
        return
    
    def transmit_comments(self):
        new_comment = self.comments.text()
        if new_comment != self.comment:
            self.comment = new_comment
            self.commentSignal.emit(self.comment)    
        return
    
    def set_filename(self):
        filename = self.filename_name.text()
        if filename != self.filename:
            self.filename = filename
            self.filenameSignal.emit(self.filename)    
        return
    
    def set_y_range(self):
        self.signal_plot.setYRange(float(self.minYRangeValue_apd.text()), 
                                   float(self.maxYRangeValue_apd.text()))
        self.monitor_plot.setYRange(float(self.minYRangeValue_monitor.text()), 
                                   float(self.maxYRangeValue_monitor.text()))
        return
    
    def center_signal(self):
        self.signal_plot.setYRange(self.mean_value_apd - 10*self.sd_value_apd, 
                                   self.mean_value_apd + 10*self.sd_value_apd)
        self.monitor_plot.setYRange(self.mean_value_monitor - 10*self.sd_value_monitor, 
                                   self.mean_value_monitor + 10*self.sd_value_monitor)
        return
    
    @pyqtSlot(np.ndarray, int, int)
    def get_data(self, data, i, n_read):
        data_apd_array = data[0,:]
        monitor_array = data[1,:]
        # do some minor stats
        # use nanmean and nanstd, allocation is performed with nan values
        self.mean_value_apd = np.nanmean(data_apd_array)
        self.sd_value_apd = np.nanstd(data_apd_array, ddof = 0)
        self.mean_value_monitor = np.nanmean(monitor_array)
        self.sd_value_monitor = np.nanstd(monitor_array, ddof = 0)
        # update value labels
        # transmission APD
        sd_mV_apd = self.sd_value_apd*1000 # to mV
        self.signalMeanValue_apd.setText('{:.3f}'.format(self.mean_value_apd))
        self.signalStdValue_apd.setText('{:.3f}'.format(sd_mV_apd))
        # monnitor APD
        sd_mV_monitor = self.sd_value_monitor*1000 # to mV
        self.signalMeanValue_monitor.setText('{:.3f}'.format(self.mean_value_monitor))
        self.signalStdValue_monitor.setText('{:.3f}'.format(sd_mV_monitor))
        
        # build time array
        start = i
        end = i + n_read
        time_array = np.arange(start, end)*self.time_base
        # for visualizing purposes
        if self.downsampling_period != 1:
            # crop and resize data for later averaging as downsampling method
            data_array_length = data_apd_array.size
            remainder = np.mod(data_array_length, self.downsampling_period)
            round_size = data_array_length - remainder
            # crop
            data_apd_array = data_apd_array[:round_size]
            monitor_array = monitor_array[:round_size]
            time_array = time_array[:round_size]
            # reshape
            new_size = int(round_size/self.downsampling_period)
            data_apd_array = data_apd_array.reshape([self.downsampling_period, new_size], order = 'F')
            monitor_array = monitor_array.reshape([self.downsampling_period, new_size], order = 'F')
            time_array = time_array.reshape([self.downsampling_period, new_size], order = 'F')
            # average
            data_apd_array = np.mean(data_apd_array, axis = 0)
            monitor_array = np.mean(monitor_array, axis = 0)
            time_array = np.mean(time_array, axis = 0)
            n_roll = new_size
        else:
            # no downsampling/averaging
            n_roll = n_read
        # prepare arrays to plot    
        self.time_array_to_plot = np.roll(self.time_array_to_plot, -n_roll)
        self.data_apd_array_to_plot = np.roll(self.data_apd_array_to_plot, -n_roll)
        self.mean_apd_array_to_plot = np.roll(self.mean_apd_array_to_plot, -n_roll)
        self.std_apd_plus_array_to_plot = np.roll(self.std_apd_plus_array_to_plot, -n_roll)
        self.std_apd_minus_array_to_plot = np.roll(self.std_apd_minus_array_to_plot, -n_roll)
        self.monitor_array_to_plot = np.roll(self.monitor_array_to_plot, -n_roll)
        self.mean_monitor_array_to_plot = np.roll(self.mean_monitor_array_to_plot, -n_roll)
        self.std_monitor_plus_array_to_plot = np.roll(self.std_monitor_plus_array_to_plot, -n_roll)
        self.std_monitor_minus_array_to_plot = np.roll(self.std_monitor_minus_array_to_plot, -n_roll)

        # plot raw data (with or without downsampling)
        self.time_array_to_plot[-n_roll:] = time_array
        self.data_apd_array_to_plot[-n_roll:] = data_apd_array
        self.monitor_array_to_plot[-n_roll:] = monitor_array
        item_raw_apd_data_curve = FastLine(self.time_array_to_plot, self.data_apd_array_to_plot, 'w')
        item_raw_monitor_data_curve = FastLine(self.time_array_to_plot, self.monitor_array_to_plot, 'w')
        
        # plot mean of data (using previous arrays)
        self.mean_apd_array_to_plot[-n_roll:] = self.mean_value_apd
        item_mean_apd_data_curve = FastLine(self.time_array_to_plot, self.mean_apd_array_to_plot, 'b')
        self.mean_monitor_array_to_plot[-n_roll:] = self.mean_value_monitor
        item_mean_monitor_data_curve = FastLine(self.time_array_to_plot, self.mean_monitor_array_to_plot, 'y')
        
        # plot std dev of the data (using previous arrays)
        self.std_apd_plus_array_to_plot[-n_roll:] = self.mean_value_apd + 3*self.sd_value_apd # 3 sigma means 99.73%
        self.std_apd_minus_array_to_plot[-n_roll:] = self.mean_value_apd - 3*self.sd_value_apd # 3 sigma means 99.73%
        item_std_apd_plus_data_curve = FastLine(self.time_array_to_plot, self.std_apd_plus_array_to_plot, 'g')
        item_std_apd_minus_data_curve = FastLine(self.time_array_to_plot, self.std_apd_minus_array_to_plot, 'g')
        self.std_monitor_plus_array_to_plot[-n_roll:] = self.mean_value_monitor + 3*self.sd_value_monitor # 3 sigma means 99.73%
        self.std_monitor_minus_array_to_plot[-n_roll:] = self.mean_value_monitor - 3*self.sd_value_monitor # 3 sigma means 99.73%
        item_std_monitor_plus_data_curve = FastLine(self.time_array_to_plot, self.std_monitor_plus_array_to_plot, 'y')
        item_std_monitor_minus_data_curve = FastLine(self.time_array_to_plot, self.std_monitor_minus_array_to_plot, 'y')
        
        # add plots
        # APD
        self.signal_plot.clear()
        self.signal_plot.addItem(item_raw_apd_data_curve, skipFiniteCheck = False)
        self.signal_plot.addItem(item_mean_apd_data_curve, skipFiniteCheck = False)
        self.signal_plot.addItem(item_std_apd_plus_data_curve, skipFiniteCheck = False)
        self.signal_plot.addItem(item_std_apd_minus_data_curve, skipFiniteCheck = False)
        # monitor
        self.monitor_plot.clear()
        self.monitor_plot.addItem(item_raw_monitor_data_curve, skipFiniteCheck = False)
        self.monitor_plot.addItem(item_mean_monitor_data_curve, skipFiniteCheck = False)
        self.monitor_plot.addItem(item_std_monitor_plus_data_curve, skipFiniteCheck = False)
        self.monitor_plot.addItem(item_std_monitor_minus_data_curve, skipFiniteCheck = False)
        
        # set range and fix rolling window length
        x_viewbox = time_array[-1]
        self.signal_plot.setXRange(x_viewbox - self.viewbox_length, x_viewbox)
        self.monitor_plot.setXRange(x_viewbox - self.viewbox_length, x_viewbox)
        return
        
    @pyqtSlot()
    def acquisition_stopped(self):
        # uncheck Acquire button
        self.traceButton.setChecked(False)
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
            tm.sleep(1) # needed to close properly all modules
            app.quit()
        else:
            event.ignore()
            print('Back in business...')    
        return

    def make_connections(self, backend):
        backend.dataSignal.connect(self.get_data)
        backend.filepathSignal.connect(self.get_filepath)
        backend.acqStopped.connect(self.acquisition_stopped)
        return
    
#=====================================

# Controls / Backend definition

#===================================== 
       
class Backend(QtCore.QObject):

    dataSignal = pyqtSignal(np.ndarray, int, int)
    filepathSignal = pyqtSignal(str)
    acqStopped = pyqtSignal()
    startTimerSignal = pyqtSignal()
    stopTimerSignal = pyqtSignal()

    def __init__(self, common_variable = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.common_variable = common_variable
        # set timer to plot the data and check buttons
        self.updateTimer = QtCore.QTimer()
        self.updateTimer.timeout.connect(self.trace_update) 
        self.updateTimer.setInterval(updateTrace_period) # in ms
        # set APD acquisition channel
        self.sampling_rate = initial_sampling_rate
        self.time_base = 1/self.sampling_rate
        self.duration = initial_duration
        self.number_of_points = calculate_num_of_points(self.duration, self.sampling_rate)
        self.voltage_range = initial_voltage_range
        print('Setting up task...')
        # APD task
        self.APD_task, self.time_to_finish = daq.set_task(number_of_channels, \
                                                          self.sampling_rate, \
                                                            self.number_of_points, \
                                                            -self.voltage_range, \
                                                            +self.voltage_range, \
                                                            acquisition_mode, \
                                                            debug = True)
        self.acquire_continuously_bool = False
        self.save_continuously_bool = True
        self.filepath = initial_filepath
        self.filename = initial_filename
        self.params_to_be_saved = ''
        self.comment = ''
        self.acquisition_flag = False
        self.save_in_ascii = False
        return

    @pyqtSlot(bool)
    def play_pause(self, tracebool):
        if tracebool:
            self.start_trace()
        else:
            self.stop_trace()
        return 
    
    @pyqtSlot(bool)
    def acquire_continuously_check(self, acq_cont_bool):
        if acq_cont_bool:
            print('Signal acquisition will run continuously.')
            self.acquire_continuously_bool = True
        else:
            print('Signal acquisition will run only once.')
            self.acquire_continuously_bool = False
        return
    
    @pyqtSlot(bool)
    def save_continuously_check(self, save_bool):
        if save_bool:
            print('Signal will be saved automatically.')
            self.save_continuously_bool = True
        else:
            print('Signal will not be saved automatically.')
            self.save_continuously_bool = False
        return
    
    @pyqtSlot(bool)
    def save_ascii(self, save_ascii_bool):
        if save_ascii_bool:
            print('Signal will be saved in ASCII also.')
            self.save_in_ascii = True
        else:
            print('Signal will not be saved in ASCII.')
            self.save_in_ascii = False
        return
      
    def start_trace(self):
        # allocate arrays
        self.data_array_filepath, self.data_array = daq.allocate_datafile(self.number_of_points)
        self.monitor_array_filepath, self.monitor_array = daq.allocate_datafile(self.number_of_points)
        self.time_array_filepath, self.time_array = daq.allocate_datafile(self.number_of_points)
        # counter to account for the number of points already measured
        self.i = 0
        self.i_to_send = 0
        self.trace_number = 0
        # prepare stream reader
        self.APD_stream_reader = daq.arm_measurement_in_loop(self.APD_task, number_of_channels)
        # start task
        if not self.APD_task.is_task_done():
            self.APD_task.stop()
        self.APD_task.start()
        # start timer to retrieve data periodically
        self.start_timer()
        return
    
    @pyqtSlot()
    def start_timer(self):
        self.init_time = timer()
        print('\nAcquisition started at {}'.format(self.init_time))
        self.updateTimer.start()
        self.acquisition_flag = True
        return
    
    def stop_trace(self):
        self.acquisition_flag = False
        # stop timer signal
        self.stopTimerSignal.emit()
        # flush DAQ buffer
        self.data_array.flush()
        self.monitor_array.flush()
        print('\nStopping acquisition at {}'.format(timer()))
        print('Total time recording: {:.3f} s'.format(self.total_time))
        if not self.APD_task.is_task_done():
            self.APD_task.stop()
        # emit signal acquisition has ended
        self.acqStopped.emit()
        return
                    
    def trace_update(self):
        if self.acquisition_flag:
            # perform the measurement 
            if ( not self.APD_task.is_task_done() and self.i < self.number_of_points ):
                # read a short stream
                n_available_per_ch, data = daq.measure_one_loop(self.APD_stream_reader, \
                                                         number_of_channels, \
                                                         self.number_of_points, \
                                                         self.i)
                data_APD = data[0,:]
                data_monitor = data[1,:]
                # assign 
                self.data_array[self.i:self.i + n_available_per_ch] = data_APD
                self.monitor_array[self.i:self.i + n_available_per_ch] = data_monitor
                # send all channels
                self.dataSignal.emit(data, self.i_to_send, n_available_per_ch)
                self.i += n_available_per_ch
                self.i_to_send += n_available_per_ch
            else:
                if self.save_continuously_bool:
                    # flush array at buffer into the disk (because it was a memmap array)
                    self.data_array.flush()
                    self.monitor_array.flush()
                    self.save_trace()
                if self.acquire_continuously_bool:
                    # reset counter
                    self.i = 0
                    self.trace_number += 1
                else:                
                    self.acquisition_flag = False
                    self.stop_trace()
                    print('\n--- Acquisition finished at {}\n'.format(timer()))
        return
    
    @pyqtSlot()
    def stop_timer(self):
        self.updateTimer.stop()
        self.total_time = timer() - self.init_time
        return
    
    @pyqtSlot()
    def save_trace(self):
        # check if all data has been written correctly from DAQ board to RAM
        assert np.all(self.data_array > -1000), 'data_array was not written correctly'
        assert np.all(self.monitor_array > -1000), 'monitor_array was not written correctly'
        # prepare full filepath
        filepath = self.filepath
        if self.save_continuously_bool:
            self.filename += '_{:03d}'.format(self.trace_number)
        # add time string to the filename
        timestr = tm.strftime("_%Y%m%d_%H%M%S")
        self.filename += timestr
        filename_data = self.filename + '_transmission'
        filename_monitor = self.filename + '_monitor'
        filename_params = self.filename + '_params.txt'
        # save data
        full_filepath_data = os.path.join(filepath, filename_data)
        full_filepath_monitor = os.path.join(filepath, filename_monitor)
        full_filepath_params = os.path.join(filepath, filename_params)
        # save data
        np.save(full_filepath_data, np.transpose(self.data_array), allow_pickle = False)
        np.save(full_filepath_monitor, np.transpose(self.monitor_array), allow_pickle = False)
        # save measurement parameters and comments
        self.params_to_be_saved = self.get_params_to_be_saved()
        with open(full_filepath_params, 'w') as f:
            print(self.params_to_be_saved, file = f)
        print('Data %s has been saved.' % filename_data)
        if self.save_in_ascii:
            # it will save an ASCII encoded text file
            data_to_save = np.transpose(np.vstack((self.data_array, self.monitor_array)))
            header_txt = 'transmission monitor\n%d Hz' % self.sampling_rate
            ascii_full_filepath = full_filepath_data + '.dat'
            np.savetxt(ascii_full_filepath, data_to_save, fmt='%.6f', header=header_txt)
        return
    
    @pyqtSlot(float)    
    def change_voltage_range(self, voltage_range):
        if not self.APD_task.is_task_done():
            print('\nStopping task in progress...')
            self.APD_task.stop()
            self.acqStopped.emit()
        print('\nClosing task...')
        self.APD_task.close()
        daq.check_voltage_range(daq_board, voltage_range)
        print('Changing voltage ranges...')
        self.voltage_range = voltage_range # in V, is float
        print('Setting up new task...')
        self.APD_task, self.time_to_finish = daq.set_task(number_of_channels, \
                                                          self.sampling_rate, \
                                                            self.number_of_points, \
                                                            -self.voltage_range, \
                                                            +self.voltage_range, \
                                                            acquisition_mode, \
                                                            debug = False)
        return

    @pyqtSlot(int)    
    def change_sampling_rate(self, sampling_rate):
        if not self.APD_task.is_task_done():
            print('\nStopping task in progress...')
            self.APD_task.stop()
            self.acqStopped.emit()
        print('\nClosing task...')
        self.APD_task.close()
        self.sampling_rate = sampling_rate*1e3 # in S/s, is int
        self.time_base = 1/self.sampling_rate
        print('Sampling rate changed to', sampling_rate, 'kS/s')
        self.number_of_points = calculate_num_of_points(self.duration, self.sampling_rate)
        print('Setting up new task...')
        self.APD_task, self.time_to_finish = daq.set_task(number_of_channels, \
                                                          self.sampling_rate, \
                                                            self.number_of_points, \
                                                            -self.voltage_range, \
                                                            +self.voltage_range, \
                                                            acquisition_mode, \
                                                            debug = False)
        return
    
    @pyqtSlot(float)    
    def change_duration(self, duration):
        if not self.APD_task.is_task_done():
            print('\nStopping task in progress...')
            self.APD_task.stop()
            self.acqStopped.emit()
        print('\nClosing task...')
        self.APD_task.close()
        self.duration = duration
        print('Duration of the measurement changed to', duration, 's')
        self.number_of_points = calculate_num_of_points(self.duration, self.sampling_rate) 
        print('Setting up new task...')
        self.APD_task, self.time_to_finish = daq.set_task(number_of_channels, \
                                                          self.sampling_rate, \
                                                            self.number_of_points, \
                                                            -self.voltage_range, \
                                                            +self.voltage_range, \
                                                            acquisition_mode, \
                                                            debug = False)
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
    
    def get_params_to_be_saved(self):
        dict_to_be_saved = {}
        dict_to_be_saved['Voltage range (V)'] = self.voltage_range
        dict_to_be_saved['Sampling rate (S/s)'] = self.sampling_rate
        dict_to_be_saved['Duration (s)'] = self.duration
        dict_to_be_saved['Number of points'] = self.number_of_points
        dict_to_be_saved['Comments'] = self.comment
        return dict_to_be_saved
    
    @pyqtSlot(str)
    def set_filename(self, new_filename):
        self.filename = new_filename
        print('New filename has been set:', self.filename)
        return
    
    @pyqtSlot(str)
    def set_comment(self, new_comment):
        self.comment = new_comment
        print('New comment written down.')
        return
    
    @pyqtSlot()
    def closeBackend(self):
        self.APD_task.close()
        print('Task closed.') 
        self.updateTimer.stop()
        print('Exiting thread...')
        workerThread.exit()
        return
    
    def make_connections(self, frontend):
        frontend.traceSignal.connect(self.play_pause)
        frontend.makeTraceContSignal.connect(self.acquire_continuously_check)
        frontend.saveTraceContSignal.connect(self.save_continuously_check)
        frontend.saveTraceASCIISignal.connect(self.save_ascii)
        frontend.setSamplingRateSignal.connect(self.change_sampling_rate) 
        frontend.setDurationSignal.connect(self.change_duration) 
        frontend.setVoltageRangeSignal.connect(self.change_voltage_range)
        frontend.closeSignal.connect(self.closeBackend)
        frontend.saveSignal.connect(self.save_trace)
        frontend.setWorkDirSignal.connect(self.set_working_folder)
        frontend.filenameSignal.connect(self.set_filename)
        frontend.commentSignal.connect(self.set_comment)
        self.startTimerSignal.connect(self.start_timer)
        self.stopTimerSignal.connect(self.stop_timer)
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
    worker.updateTimer.moveToThread(workerThread)
    
    # connect both classes 
    worker.make_connections(gui)
    gui.make_connections(worker)
    
    # start worker in a different thread (avoids GUI freezing)
    workerThread.start()
    
    gui.show()
    app.exec()
    