# -*- coding: utf-8 -*-
"""
Created on Fri April 8, 2022
Modified on Mon March 17, 2025

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland
"""

import numpy as np
from timeit import default_timer as timer
import os
# import sys
import scipy.signal as sig
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
from queue import Queue
from pyqtgraph.dockarea import Dock, DockArea
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QThread, QProcess
from PyQt5.QtWidgets import QMessageBox, QPushButton, QLabel, QDialog
import daq_board_toolbox as daq
from tkinter import filedialog
import tkinter as tk
import time as tm

# enable OpenGL for fast rendering
# The PC has a 12th Gen Interl Core i9-12900K
# and  GPU Intel UHD Graphics 770 that supports OpenGL 3.0
# https://www.intel.com/content/www/us/en/support/articles/000005524/graphics.html
pg.setConfigOptions(antialias = False, useOpenGL = True)

#=====================================

# Initialize DAQ board

#=====================================

print('\nInitializing DAQ board...')
daq_board = daq.init_daq()
# set measure period
acquireTrace_period = 20 # in ms
# set display/plot period 
displayTrace_period = 40 # in ms
# ratio between periods
periods_ratio = int(round(displayTrace_period/acquireTrace_period))
print('\nRatio between acquisition and displaying periods: %i' % periods_ratio)
# set queue size for allocate data before plotting
queue_size = 1000
max_sampling_rate = daq_board.ai_max_single_chan_rate # set to maximum, here 2 MS/s    
# number of analog input channels to read
number_of_channels = 2

############ INITIAL PARAMETERS #############
# set sampling rate
initial_sampling_rate = 100e3 # in S/s
# duration of the traces in s
initial_duration = 4
# define a fixed length (in s) for the time axis of viewbox signal vs time
initial_viewbox_length = 2 # in s
# define a downsampling period for visualization purposes
initial_downsampling_period = 100
# initial Y range
initial_min_y_range = -0.01
initial_max_y_range = 0.03
initial_mean_value = 0
initial_sd_value = 0.2
# initial filepath and filename
initial_filepath = 'D:\\daily_data\\apd_traces' # save in SSD for fast and daily use
initial_filename = 'signal'
# set measurement range
initial_voltage_range = 2.0
daq.check_voltage_range(daq_board, initial_voltage_range)

# power calibration factor
power_calibration_factor = 0.42 # in mW/V
power_calibration_offset = 0.00 # in mW

# creating data Queue object
data_queue = Queue(maxsize = queue_size)

#=====================================

# Function definition for numerical calculations

#=====================================

# function that calculates the number of datapoins to be measured
def calculate_num_of_points(duration, sampling_rate):
    # duration in seconds
    number_of_points = int(duration*sampling_rate)
    print('\nAt {:.3f} MS/s sampling rate, a duration of {} s means:'.format(sampling_rate*1e-6, \
                                                                       duration))
    print('{} datapoints per trace'.format(number_of_points))
    return number_of_points

def autocorr(x):
    # actually, is the time-dependant Pearson correlation coefficient (read below)
    x_avg = np.mean(x)
    x_new = x - x_avg
    N = len(x)
    var = np.var(x)
    autocovariance = sig.correlate(x_new, x_new, mode='full', method='fft')
    corr_coef = (1/N)*autocovariance/var
    # fft method is faster and same method used by autocorr.m Matlab function (if no NaN are present)
    # see https://ch.mathworks.com/help/econ/autocorr.html#btzjcln-4
    # also, becuase autocorr.m subtracts the mean it becomes the autocovariance
    # also, because it normalizes with the variance, it becomes the time-dependant Pearson correlation coefficient
    # see https://en.wikipedia.org/wiki/Autocorrelation
    z = corr_coef[corr_coef.size//2:] # get half of the array, positive lag times only
    lag = np.arange(0, corr_coef.size//2+1)
    return z, lag

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

# Autocorrelation Window definition

#===================================== 

class AutocorrelationChildWindow(QDialog):

    closeChildSignal = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__( *args, **kwargs)
        self.setUpGUI()
        # set the title of the window
        self.setWindowTitle("Live autocorrelation")
        self.setGeometry(150, 150, 800, 600)
        return

    def setUpGUI(self):
        # widget for the data
        self.viewAutocorrWidget = pg.GraphicsLayoutWidget()
        self.autocorr_plot = self.viewAutocorrWidget.addPlot(row = 1, col = 1)
        self.autocorr_plot.setYRange(-1, 1)
        self.autocorr_plot.enableAutoRange(x = False, y = True)
        self.autocorr_plot.showGrid(x = True, y = True)
        self.autocorr_plot.setLabel('left', 'Autocorrelation normalized')
        self.autocorr_plot.setLabel('bottom', 'Lag time (s)')

        # Docks
        gridbox = QtGui.QGridLayout(self)
        dockArea = DockArea()
        viewAutocorrDock = Dock('Autocorrelation viewbox')
        viewAutocorrDock.addWidget(self.viewAutocorrWidget)
        dockArea.addDock(viewAutocorrDock)
        gridbox.addWidget(dockArea, 0, 0) 
        self.setLayout(gridbox)
        return

    def plot_autocorr(self, transmission_signal, lag, sampling_rate):
        time_step = 1/sampling_rate
        lag_time = lag*time_step
        self.autocorr_plot.clear()
        self.autocorr_plot.plot(x = lag_time, y = transmission_signal, \
                                    pen = pg.mkPen('w', width = 1))
        self.autocorr_plot.setXRange(lag_time[0], lag_time[-1])
        #self.autocorr_plot.setLogMode(x=True)
        return

    # re-define the closeEvent to execute an specific command
    def closeEvent(self, event, *args, **kwargs):
        super(QDialog, self).closeEvent(event, *args, **kwargs)
        self.close()
        self.closeChildSignal.emit()
        return    


#=====================================

# Power calibration Dialog

#===================================== 

class PowerCalibrationChildWindow(QDialog):

    closeChildSignal = pyqtSignal()
    calibrationParamsSignal = pyqtSignal(float, float)

    def __init__(self, *args, **kwargs):
        super().__init__( *args, **kwargs)
        # set the title of the window
        self.setWindowTitle("Power calibration")
        self.setGeometry(100, 100, 100, 100)
        self.power_calibration_factor = power_calibration_factor
        self.power_calibration_offset = power_calibration_offset
        self.setUpGUI()
        return

    def setUpGUI(self):
        # labels and edits
        # factor
        self.factor_label = QtGui.QLabel('Factor (mW/V): ')
        self.factor_value = QtGui.QLineEdit(str(self.power_calibration_factor))
        self.factor_value.setFixedWidth(50)
        self.factor_value.setValidator(QtGui.QDoubleValidator(0.000, 10000.000, 3))
        self.factor_value.editingFinished.connect(self.factor_value_changed)
        # offset
        self.offset_label = QtGui.QLabel('Offset (mW): ')
        self.offset_value = QtGui.QLineEdit(str(self.power_calibration_offset))
        self.offset_value.setFixedWidth(50)
        self.offset_value.setValidator(QtGui.QDoubleValidator(-10000.000, 10000.000, 3))
        self.offset_value.editingFinished.connect(self.offset_value_changed)

        # done button
        self.done_button = QtGui.QPushButton('Done')
        self.done_button.clicked.connect(self.send_parameters)
        self.done_button.setStyleSheet(
            "QPushButton:pressed { background-color: palegreen; }")

        # grid layout
        gridbox_layout = QtGui.QGridLayout(self)
        gridbox_layout.addWidget(self.factor_label, 0, 0)
        gridbox_layout.addWidget(self.factor_value, 0, 1)
        gridbox_layout.addWidget(self.offset_label, 1, 0)
        gridbox_layout.addWidget(self.offset_value, 1, 1)
        gridbox_layout.addWidget(self.done_button, 2, 0)
        self.setLayout(gridbox_layout)
        return

    def factor_value_changed(self):
        self.power_calibration_factor = float(self.factor_value.text())
        return
    
    def offset_value_changed(self):
        self.power_calibration_offset = float(self.offset_value.text())
        return
    
    def send_parameters(self):
        self.calibrationParamsSignal.emit(self.power_calibration_factor, self.power_calibration_offset)
        self.close()
        return

    # re-define the closeEvent to execute an specific command
    def closeEvent(self, event, *args, **kwargs):
        super(QDialog, self).closeEvent(event, *args, **kwargs)
        self.close()
        self.closeChildSignal.emit()
        return    

#=====================================

# Process for Data Processing definition

#=====================================

class DataProcessor(QProcess):

    dataReadySignal = pyqtSignal(np.ndarray, \
                                 pg.QtGui.QGraphicsPathItem, pg.QtGui.QGraphicsPathItem, \
                                 pg.QtGui.QGraphicsPathItem, pg.QtGui.QGraphicsPathItem, \
                                 pg.QtGui.QGraphicsPathItem, pg.QtGui.QGraphicsPathItem, \
                                 pg.QtGui.QGraphicsPathItem, pg.QtGui.QGraphicsPathItem)

    updateLabelsSignal = pyqtSignal(float, float, float, float)

    def __init__(self):
        super().__init__()
        self.viewbox_length = 0
        self.sampling_rate = 0
        self.downsampling_period = 0
        self.downsampling_by_average = False
        self.mean_value_apd = 0
        self.sd_value_apd = 0
        self.mean_value_monitor = 0
        self.sd_value_monitor = 0
        self.running = False
        self.displayDataTimer = QtCore.QTimer()
        # configure the connection to allow queued executions to avoid interruption of previous calls
        self.displayDataTimer.setInterval(displayTrace_period) # in ms
        return

    @pyqtSlot(float, float, int, bool)
    def get_displaying_parameters(self, viewbox_length, sampling_rate, downsampling_period, downsampling_by_average):
        print('\nDataProcessor: setting displaying parameters...')
        self.viewbox_length = viewbox_length
        self.sampling_rate = sampling_rate
        self.downsampling_period = downsampling_period
        self.time_base = 1/(self.sampling_rate*1e3)
        self.downsampling_by_average = downsampling_by_average
        # allocate arrays to plot them with improved performance
        print('DataProcessor: allocating data arrays...')
        # sampling_rate is in kS/s
        # viewbox_length is in s
        # so multiply by 1000 to obtain the right size of "points_to_be_displayed"
        self.points_to_be_displayed = int(self.viewbox_length*self.sampling_rate*1e3/self.downsampling_period)
        # data array
        self.data_apd_array_to_plot = np.empty(self.points_to_be_displayed)
        self.data_apd_array_to_plot[:] = np.nan
        # monitor array
        self.monitor_array_to_plot = np.empty(self.points_to_be_displayed)
        self.monitor_array_to_plot[:] = np.nan
        # mean array
        self.mean_apd_array_to_plot = np.empty(self.points_to_be_displayed)
        self.mean_apd_array_to_plot[:] = np.nan
        self.mean_monitor_array_to_plot = np.empty(self.points_to_be_displayed)
        self.mean_monitor_array_to_plot[:] = np.nan
        # std dev +/- array
        self.std_apd_plus_array_to_plot = np.empty(self.points_to_be_displayed)
        self.std_apd_plus_array_to_plot[:] = np.nan
        self.std_apd_minus_array_to_plot = np.empty(self.points_to_be_displayed)
        self.std_apd_minus_array_to_plot[:] = np.nan
        self.std_monitor_plus_array_to_plot = np.empty(self.points_to_be_displayed)
        self.std_monitor_plus_array_to_plot[:] = np.nan
        self.std_monitor_minus_array_to_plot = np.empty(self.points_to_be_displayed)
        self.std_monitor_minus_array_to_plot[:] = np.nan
        # time array
        self.time_array_to_plot = np.empty(self.points_to_be_displayed)
        self.time_array_to_plot[:] = np.nan
        return

    @pyqtSlot()
    def get_data_from_queue(self):
        if self.running:
            if data_queue.qsize() > 0:
                # initialize arrays
                data_apd_array = np.array([])
                monitor_array = np.array([])
                read_samples_list = []
                n_available_per_ch_list = []
                # retrieve data from the queue
                for i in range(periods_ratio):
                    if not data_queue.empty():
                        # get data
                        [data, read_samples, n_available_per_ch] = data_queue.get(block = False)
                        data_apd_array = np.concatenate((data_apd_array, data[0,:]))
                        monitor_array = np.concatenate((monitor_array, data[1,:]))
                        read_samples_list.append(read_samples)
                        n_available_per_ch_list.append(n_available_per_ch)
                # do some minor stats
                # use nanmean and nanstd, allocation is performed with nan values
                self.mean_value_apd = np.nanmean(data_apd_array)
                self.sd_value_apd = np.nanstd(data_apd_array, ddof = 0)
                self.mean_value_monitor = np.nanmean(monitor_array)
                self.sd_value_monitor = np.nanstd(monitor_array, ddof = 0)
                # send stats using signal
                self.updateLabelsSignal.emit(self.mean_value_apd, self.sd_value_apd, \
                                        self.mean_value_monitor, self.sd_value_monitor)

                # build time array
                n_retrieved_samples = sum(n_available_per_ch_list)
                start = read_samples_list[0]
                end = read_samples_list[0] + n_retrieved_samples
                time_array = np.arange(start, end)*self.time_base
                # for visualizing purposes
                if self.downsampling_period != 1:
                    if self.downsampling_by_average:
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
                    else:
                        # reduce the number of samples to show
                        data_apd_array = data_apd_array[::self.downsampling_period]
                        monitor_array = monitor_array[::self.downsampling_period]
                        time_array = time_array[::self.downsampling_period]
                        # reshape
                        new_size = data_apd_array.size
                    n_roll = new_size
                else:
                    # no downsampling or averaging
                    n_roll = n_retrieved_samples
                # prepare arrays to queue    
                self.time_array_to_plot = np.roll(self.time_array_to_plot, -n_roll)
                self.data_apd_array_to_plot = np.roll(self.data_apd_array_to_plot, -n_roll)
                self.mean_apd_array_to_plot = np.roll(self.mean_apd_array_to_plot, -n_roll)
                self.std_apd_plus_array_to_plot = np.roll(self.std_apd_plus_array_to_plot, -n_roll)
                self.std_apd_minus_array_to_plot = np.roll(self.std_apd_minus_array_to_plot, -n_roll)
                self.monitor_array_to_plot = np.roll(self.monitor_array_to_plot, -n_roll)
                self.mean_monitor_array_to_plot = np.roll(self.mean_monitor_array_to_plot, -n_roll)
                self.std_monitor_plus_array_to_plot = np.roll(self.std_monitor_plus_array_to_plot, -n_roll)
                self.std_monitor_minus_array_to_plot = np.roll(self.std_monitor_minus_array_to_plot, -n_roll)

                # prepare objects to plot raw data (with or without downsampling)
                self.time_array_to_plot[-n_roll:] = time_array
                self.data_apd_array_to_plot[-n_roll:] = data_apd_array
                self.monitor_array_to_plot[-n_roll:] = monitor_array
                item_raw_apd_data_curve = FastLine(self.time_array_to_plot, self.data_apd_array_to_plot, 'w')
                item_raw_monitor_data_curve = FastLine(self.time_array_to_plot, self.monitor_array_to_plot, 'w')
                
                # prepare objects to plot the mean (using previous arrays)
                self.mean_apd_array_to_plot[-n_roll:] = self.mean_value_apd
                item_mean_apd_data_curve = FastLine(self.time_array_to_plot, self.mean_apd_array_to_plot, 'b')
                self.mean_monitor_array_to_plot[-n_roll:] = self.mean_value_monitor
                item_mean_monitor_data_curve = FastLine(self.time_array_to_plot, self.mean_monitor_array_to_plot, 'm')
                
                # prepare objects to plot the std dev (using previous arrays)
                self.std_apd_plus_array_to_plot[-n_roll:] = self.mean_value_apd + 3*self.sd_value_apd # 3 sigma means 99.73%
                self.std_apd_minus_array_to_plot[-n_roll:] = self.mean_value_apd - 3*self.sd_value_apd # 3 sigma means 99.73%
                item_std_apd_plus_data_curve = FastLine(self.time_array_to_plot, self.std_apd_plus_array_to_plot, 'g')
                item_std_apd_minus_data_curve = FastLine(self.time_array_to_plot, self.std_apd_minus_array_to_plot, 'g')
                self.std_monitor_plus_array_to_plot[-n_roll:] = self.mean_value_monitor + 3*self.sd_value_monitor # 3 sigma means 99.73%
                self.std_monitor_minus_array_to_plot[-n_roll:] = self.mean_value_monitor - 3*self.sd_value_monitor # 3 sigma means 99.73%
                item_std_monitor_plus_data_curve = FastLine(self.time_array_to_plot, self.std_monitor_plus_array_to_plot, 'y')
                item_std_monitor_minus_data_curve = FastLine(self.time_array_to_plot, self.std_monitor_minus_array_to_plot, 'y')

                # send data using signal
                self.dataReadySignal.emit(time_array, item_raw_apd_data_curve, item_mean_apd_data_curve, \
                                        item_std_apd_plus_data_curve, item_std_apd_minus_data_curve, \
                                        item_raw_monitor_data_curve, item_mean_monitor_data_curve, \
                                        item_std_monitor_plus_data_curve, item_std_monitor_minus_data_curve)
        return

    @pyqtSlot(bool)
    def start_stop(self, run):
        if run:
            self.running = True
            self.displayDataTimer.start()
        else:
            self.running = False
            self.displayDataTimer.stop()
            with data_queue.mutex:
                data_queue.queue.clear()
        return

    def make_connections(self, frontend):
        frontend.parametersSignal.connect(self.get_displaying_parameters)
        frontend.retrieveDataSignal.connect(self.start_stop)
        return

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
    parametersSignal = pyqtSignal(float, float, int, bool)
    retrieveDataSignal = pyqtSignal(bool)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setUpGUI()
        # set the title of the window
        title = "Acquisition module"
        self.setWindowTitle(title)
        self.setGeometry(800, 30, 600, 1000) # x pos, y pos, width, height
        self.set_y_range()
        self.mean_value = initial_mean_value # in V
        self.sd_value = initial_sd_value # in V
        self.downsampling_by_average = False
        self.set_working_dir()
        self.set_filename()
        self.sampling_rate_changed()
        # Create an instance of the child window
        self.autocorrelation_child_window = AutocorrelationChildWindow()
        self.power_calibration_child_window = PowerCalibrationChildWindow()
        self.power_calibration_factor = power_calibration_factor
        self.power_calibration_offset = power_calibration_offset
        return
    
    def setUpGUI(self):

        # Single acquisition button
        self.traceButton = QtGui.QPushButton('► Acquire single / ◘ Stop')
        self.traceButton.setCheckable(True)
        self.traceButton.clicked.connect(self.get_trace)
        self.traceButton.setToolTip('Play or Stop a single APD signal acquisition.')
        self.traceButton.setStyleSheet(
            "QPushButton:pressed { background-color: red; }"
            "QPushButton::checked { background-color: lightcoral; }")

        # Continuous acquisition tick box
        self.traceContinuouslyBox = QtGui.QCheckBox('Acquire continuously?')
        self.traceContinuouslyBox.setChecked(True)
        self.traceContinuouslyBox.stateChanged.connect(self.set_trace_continuously)
        self.traceContinuouslyBox.setToolTip('Set/Tick to acquire continuously APD signal.')

        # Save data button
        self.saveButton = QtGui.QPushButton('Save last trace')
        self.saveButton.clicked.connect(self.get_save_trace)
        self.saveButton.setStyleSheet(
            "QPushButton:pressed { background-color: cornflowerblue; }")
        self.saveButton.setToolTip('Save the trace that was <b>fully</b> acquired in the last seconds (defined by <b>duration</b> variable).')
        
        # Save continuously tick box
        self.saveAutomaticallyBox = QtGui.QCheckBox('Save automatically?')
        self.saveAutomaticallyBox.setChecked(False)
        self.saveAutomaticallyBox.stateChanged.connect(self.set_save_continuously)
        self.saveAutomaticallyBox.setToolTip('Set/Tick to save data continuously. Filenames will be sequential.')
        
        # Save in ASCII tick box
        self.saveASCIIBox = QtGui.QCheckBox('Save in ASCII (not recommended)')
        self.saveASCIIBox.setChecked(False)
        self.saveASCIIBox.stateChanged.connect(self.set_save_in_ascii)
        self.saveASCIIBox.setToolTip('Set/Tick to save data in ASCII. WARNING: files will be heavier than in binary (4.5 times more).')
                
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
        
        # Voltage range
        voltage_ranges_option = ['0.1', '0.2', '0.5', '1.0', '2.0', '5.0', '10.0']
        self.maxVoltageRangeLabel = QtGui.QLabel('Max voltage range (V): ')
        self.maxVoltageRangeList = QtGui.QComboBox()
        self.maxVoltageRangeList.setFixedWidth(100)
        self.maxVoltageRangeList.addItems(voltage_ranges_option)
        self.maxVoltageRangeList.setCurrentText(str(initial_voltage_range))
        self.maxVoltageRangeList.currentTextChanged.connect(self.voltage_range_changed)
        
        # Sampling rate
        self.samplingRateLabel = QtGui.QLabel('Sampling rate (kHz) [max. 500 kHz]: ')
        self.samplingRateValue = QtGui.QLineEdit(str(int(initial_sampling_rate/1e3)))
        self.samplingRateValue.setFixedWidth(100)
        self.sampling_rate = int(initial_sampling_rate/1e3)
        self.time_base = 1/initial_sampling_rate
        self.samplingRateValue.editingFinished.connect(self.sampling_rate_changed)
        self.samplingRateValue.setValidator(QtGui.QIntValidator(1, 2000))
        self.samplingRateValue.setToolTip('Maximum sampling rate 1 MHz divided by the number of channels. Here, we are using 2, so it is 500 kHz.')

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
        header_col_0 = QtGui.QLabel('Signal')
        header_col_0.setFont(QtGui.QFont(font_family, 14))
        header_col_1 = QtGui.QLabel('Mean (V)')
        header_col_1.setFont(QtGui.QFont(font_family, 14))
        header_col_2 = QtGui.QLabel('Std dev (mV)')
        header_col_2.setFont(QtGui.QFont(font_family, 14))
        # for transmission APD
        self.label_apd = QtGui.QLabel('Transmission (APD)')
        self.label_apd.setFont(QtGui.QFont(font_family, fontsize))
        self.signalMeanValue_apd = QtGui.QLabel('0.000')
        self.signalMeanValue_apd.setFont(QtGui.QFont(font_family, 18, weight=QtGui.QFont.Bold))
        self.signalStdValue_apd = QtGui.QLabel('0.000')
        self.signalStdValue_apd.setFont(QtGui.QFont(font_family, 18, weight=QtGui.QFont.Bold))
        # for monitor PD
        self.label_monitor = QtGui.QLabel('Monitor (PD)')
        self.label_monitor.setFont(QtGui.QFont(font_family, fontsize))
        self.signalMeanValue_monitor = QtGui.QLabel('0.000')
        self.signalMeanValue_monitor.setFont(QtGui.QFont(font_family, 18, weight=QtGui.QFont.Bold))
        self.signalStdValue_monitor = QtGui.QLabel('0.000')
        self.signalStdValue_monitor.setFont(QtGui.QFont(font_family, 18, weight=QtGui.QFont.Bold))
        self.power_label = QtGui.QLabel('Power at sample (mW)')
        self.power_label.setFont(QtGui.QFont(font_family, fontsize))
        self.power_value = QtGui.QLabel('0.000')
        self.power_value.setFont(QtGui.QFont(font_family, 18, weight=QtGui.QFont.Bold))
        # power calibration button
        self.powerCalibrationButton = QtGui.QPushButton('Calibrate')
        self.powerCalibrationButton.clicked.connect(self.open_power_calibration_window)
        self.powerCalibrationButton.setStyleSheet(
            "QPushButton:pressed { background-color: darkgrey; }")
        self.powerCalibrationButton.setToolTip('Power calibration window. Input factor and offset.')
        
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
        
        # downsampling by average
        self.enableAveragingTickBox = QtGui.QCheckBox('Averaging')
        self.enableAveragingTickBox.setChecked(False)
        self.enableAveragingTickBox.stateChanged.connect(self.enable_averaging)
        self.enableAveragingTickBox.setToolTip('Set/Tick to enable downsampling using averaging instead of reduced sampling rate.')

        # Time window length
        self.viewbox_length = initial_viewbox_length
        self.timeViewboxLength_label = QtGui.QLabel('Time window length (s): ')
        self.timeViewboxLength_value = QtGui.QLineEdit(str(self.viewbox_length))
        self.timeViewboxLength_value.setFixedWidth(100)
        self.timeViewboxLength_value.setValidator(QtGui.QDoubleValidator(0.01, 10.0, 2))
        self.timeViewboxLength_value.setToolTip('For displaying purposes. Set the time length of the viewbox in seconds.')
        self.timeViewboxLength_value.editingFinished.connect(self.time_viewbox_length_changed)

        # Displaying effective sampling rate
        fontsize = 14
        font_family = 'Serif'
        self.eff_sampling_rate = self.sampling_rate/self.downsampling_period
        self.points_displayed = np.floor(self.eff_sampling_rate*1e3*self.viewbox_length)
        sampling_rate_text = 'Eff. sampling rate: {:.3f} kS/s \nEff. sampling period: {:.3f} ms \nPoints displayed: {:.0f}'.format(self.eff_sampling_rate, 1/self.eff_sampling_rate, self.points_displayed)
        self.effSamplingRateLabel = QtGui.QLabel(sampling_rate_text)
        self.effSamplingRateLabel.setFont(QtGui.QFont(font_family, fontsize))
        
        # center-on-the-mean-value-of-the-signal button
        self.centerOnMeanButton = QtGui.QPushButton('Center signals')
        self.centerOnMeanButton.clicked.connect(self.center_signal)
        self.centerOnMeanButton.setStyleSheet(
            "QPushButton:pressed { background-color: plum; }")
        self.centerOnMeanButton.setToolTip('For displaying purposes. Center Y axis over the mean of the signal ±5 std dev.')
        
        # enable auto range tick button
        self.enableAutoRageTickBox = QtGui.QCheckBox('Autorange')
        self.enableAutoRageTickBox.setChecked(True)
        self.enableAutoRageTickBox.stateChanged.connect(self.enable_autorange)
        self.enableAutoRageTickBox.setToolTip('Set/Tick to enable autorange.')

        # Create a button to open the autocorrelation child window
        self.open_autocorrelation_child_button = QtGui.QPushButton("Open live autocorrelation window", self)
        self.open_autocorrelation_child_button.setCheckable(True)
        self.open_autocorrelation_child_button.clicked.connect(self.open_autocorrelation_child_window)
        self.open_autocorrelation_child_button.setToolTip('Calculate the autocorrelation of the transmission signal in live mode.')
        self.open_autocorrelation_child_button.setStyleSheet(
            "QPushButton:pressed { background-color: green; }"
            "QPushButton::checked { background-color: lightgreen; }")

        # Layout for the acquisition widget
        self.paramAcqWidget = QtGui.QWidget()
        subgridAcq_layout = QtGui.QGridLayout()
        self.paramAcqWidget.setLayout(subgridAcq_layout)
        subgridAcq_layout.addWidget(self.traceButton, 0, 0)
        subgridAcq_layout.addWidget(self.traceContinuouslyBox, 0, 1)
        subgridAcq_layout.addWidget(self.saveButton, 1, 0)
        subgridAcq_layout.addWidget(self.saveAutomaticallyBox, 1, 1)
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
        subgridDisp_layout.addWidget(self.power_label, 3, 0)
        subgridDisp_layout.addWidget(self.power_value, 3, 1)
        subgridDisp_layout.addWidget(self.powerCalibrationButton, 3, 2)
        # display ranges
        subgridDisp_layout.addWidget(self.minmax_apd_RangeLabel, 4, 0)
        subgridDisp_layout.addWidget(self.minYRangeValue_apd, 4, 1)
        subgridDisp_layout.addWidget(self.maxYRangeValue_apd, 4, 2)
        subgridDisp_layout.addWidget(self.minmax_monitor_RangeLabel, 5, 0)
        subgridDisp_layout.addWidget(self.minYRangeValue_monitor, 5, 1)
        subgridDisp_layout.addWidget(self.maxYRangeValue_monitor, 5, 2)
        subgridDisp_layout.addWidget(self.centerOnMeanButton, 6, 0, 1, 2)
        subgridDisp_layout.addWidget(self.enableAutoRageTickBox, 6, 2)
        subgridDisp_layout.addWidget(self.downsamplingLabel, 7, 0)
        subgridDisp_layout.addWidget(self.downsamplingValue, 7, 1)
        subgridDisp_layout.addWidget(self.enableAveragingTickBox, 7, 2)
        subgridDisp_layout.addWidget(self.timeViewboxLength_label, 8, 0)
        subgridDisp_layout.addWidget(self.timeViewboxLength_value, 8, 1)
        subgridDisp_layout.addWidget(self.effSamplingRateLabel, 9, 0, 1, 3)
        subgridDisp_layout.addWidget(self.open_autocorrelation_child_button, 10, 0, 1, 3)

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
        
        acqTraceDock = Dock('Acquisition controls', size=(1,10))
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

    def open_autocorrelation_child_window(self):
        # show the autocorrelation child window
        self.autocorrelation_child_window.show()
        return

    def set_working_dir(self):
        self.setWorkDirSignal.emit()
        return
    
    def open_power_calibration_window(self):
        # open the power calibration child window
        self.power_calibration_child_window.show()
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
    
    def downsampling_changed(self):
        downsampling_period = int(self.downsamplingValue.text())
        if downsampling_period != self.downsampling_period:
            print('Downsampling has changed to {} points'.format(downsampling_period))
            self.change_downsampling(downsampling_period)            
        return

    def change_downsampling(self, downsampling_period):
        self.eff_sampling_rate = self.sampling_rate/downsampling_period
        self.points_displayed = np.floor(self.eff_sampling_rate*1e3*self.viewbox_length)
        print('\nEff. sampling rate {} kS/s'.format(self.eff_sampling_rate))
        new_text = 'Eff. sampling rate: {:.3f} kS/s \nEff. sampling period: {:.3f} ms \
                    \nPoints displayed: {:.0f}'.format(self.eff_sampling_rate, \
                    1/self.eff_sampling_rate, self.points_displayed)
        self.effSamplingRateLabel.setText(new_text)
        self.downsampling_period = downsampling_period
        # emit signal to DataProcessor
        self.parametersSignal.emit(self.viewbox_length, self.sampling_rate, \
                                       self.downsampling_period, self.downsampling_by_average)
        return

    def get_trace(self):
        if self.traceButton.isChecked():
            self.signal_plot.clear()
            self.parametersSignal.emit(self.viewbox_length, self.sampling_rate, \
                                       self.downsampling_period, self.downsampling_by_average)
            # trigger signal
            self.traceSignal.emit(True)
            # start displaying data
            self.retrieveDataSignal.emit(True)
        else:
            # send signal to stop acquisition
            self.traceSignal.emit(False) 
            # stop displaying data
            self.retrieveDataSignal.emit(False)
        return
    
    def set_trace_continuously(self):
        if self.traceContinuouslyBox.isChecked():
            self.makeTraceContSignal.emit(True)
        else:
            self.makeTraceContSignal.emit(False) 
        return
    
    def set_save_continuously(self):
        if self.saveAutomaticallyBox.isChecked():
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
    
    def enable_autorange(self, enablebool):
        if enablebool:
            print('Autorange ON')
            self.signal_plot.enableAutoRange(True, True)
            self.monitor_plot.enableAutoRange(True, True)
        else:
            print('Autorange OFF')
            self.signal_plot.enableAutoRange(False, False)
            self.monitor_plot.enableAutoRange(False, False)
        return

    def enable_averaging(self, enablebool):
        if enablebool:
            self.downsampling_by_average = True
            print('Downsampling by average enabled. Displaying data at a reduced sampling rate. One data point is the average of %i samples.' % self.downsampling_period)
        else:
            self.downsampling_by_average = False
            print('Downsampling by average disabled. Displaying data at a reduced sampling rate. One data point every %i samples.' % self.downsampling_period)
        self.parametersSignal.emit(self.viewbox_length, self.sampling_rate, \
                                       self.downsampling_period, self.downsampling_by_average)
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

    @pyqtSlot(float, float, float, float)
    def update_label_values(self, mean_value_apd, sd_value_apd, \
                                  mean_value_monitor, sd_value_monitor):
        # assign self variables for other functions
        self.mean_value_apd = mean_value_apd
        self.sd_value_apd = sd_value_apd
        self.mean_value_monitor = mean_value_monitor
        self.sd_value_monitor = sd_value_monitor
        # update value labels
        # transmission APD
        self.sd_mV_apd = sd_value_apd*1000 # to mV
        self.signalMeanValue_apd.setText('{:.3f}'.format(self.mean_value_apd))
        self.signalStdValue_apd.setText('{:.3f}'.format(self.sd_mV_apd))
        # monitor PD
        self.sd_mV_monitor = sd_value_monitor*1000 # to mV
        self.signalMeanValue_monitor.setText('{:.3f}'.format(self.mean_value_monitor))
        self.signalStdValue_monitor.setText('{:.3f}'.format(self.sd_mV_monitor))
        # power value
        self.power_at_sample_plane = mean_value_monitor*self.power_calibration_factor + self.power_calibration_offset
        self.power_value.setText('{:.3f}'.format(self.power_at_sample_plane))
        return

    @pyqtSlot(np.ndarray, \
             pg.QtGui.QGraphicsPathItem, pg.QtGui.QGraphicsPathItem, \
             pg.QtGui.QGraphicsPathItem, pg.QtGui.QGraphicsPathItem, \
             pg.QtGui.QGraphicsPathItem, pg.QtGui.QGraphicsPathItem, \
             pg.QtGui.QGraphicsPathItem, pg.QtGui.QGraphicsPathItem)
    def displayTrace(self, time_array, item_raw_apd_data_curve, item_mean_apd_data_curve, \
            item_std_apd_plus_data_curve, item_std_apd_minus_data_curve, \
            item_raw_monitor_data_curve, item_mean_monitor_data_curve, \
            item_std_monitor_plus_data_curve, item_std_monitor_minus_data_curve):   
        # Add plots
        # Tranmissoin APD
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

    @pyqtSlot()
    def autocorrelation_child_window_close(self):
        # uncheck Autocorrelation button
        self.open_autocorrelation_child_button.setChecked(False)
        return

    @pyqtSlot(float, float)
    def set_power_calibration_params(self, factor, offset):
        self.power_calibration_factor = factor
        self.power_calibration_offset = offset
        print('\nPower calibration factor: {:.3f} mW/V'.format(self.power_calibration_factor))
        print('Power calibration offset: {:.3f} mW'.format(self.power_calibration_offset))
        return

    @pyqtSlot(str)
    def pop_up_window_error(self, filename):
        msg = QMessageBox()
        msg.setWindowTitle("Error")
        msg.setText("Error while saving data.\nFilename: %s" % filename)
        x = msg.exec_()  # this will show our messagebox
        return

    @pyqtSlot(np.ndarray, np.ndarray, float)
    def update_autocorr(self, transmission_signal, lag, sampling_rate):
        if self.open_autocorrelation_child_button.isChecked():
            self.autocorrelation_child_window.plot_autocorr(transmission_signal, lag, sampling_rate)
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

    def make_connections(self, backend, processing_thread):
        backend.filepathSignal.connect(self.get_filepath)
        backend.acqStoppedSignal.connect(self.acquisition_stopped)
        backend.saving_data_error_signal.connect(self.pop_up_window_error)
        backend.autocorrSignal.connect(self.update_autocorr)
        processing_thread.updateLabelsSignal.connect(self.update_label_values)
        processing_thread.dataReadySignal.connect(self.displayTrace)
        self.autocorrelation_child_window.closeChildSignal.connect(self.autocorrelation_child_window_close)
        self.power_calibration_child_window.calibrationParamsSignal.connect(self.set_power_calibration_params)
        return

#=====================================

# Controls / Backend definition

#===================================== 
       
class Backend(QtCore.QObject):

    dataSignal = pyqtSignal(np.ndarray, int, int)
    autocorrSignal = pyqtSignal(np.ndarray, np.ndarray, float)
    filepathSignal = pyqtSignal(str)
    acqStoppedSignal = pyqtSignal()
    acqStoppedInnerSignal = pyqtSignal()
    fileSavedSignal = pyqtSignal(str, str)
    saving_data_error_signal = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # set timer to plot the data and check buttons
        self.acquireTimer = QtCore.QTimer()
        # configure the connection to allow queued executions to avoid interruption of previous calls
        self.acquireTimer.setInterval(acquireTrace_period) # in ms
        # set APD acquisition channel
        self.sampling_rate = initial_sampling_rate
        self.time_base = 1/self.sampling_rate
        self.duration = initial_duration
        self.number_of_points = calculate_num_of_points(self.duration, self.sampling_rate)
        self.voltage_range = initial_voltage_range
        # set acquisition mode to measure continuosly
        self.acquisition_mode = 'continuous'
        print('Setting up task...')
        # APD task
        self.APD_task, self.time_to_finish = daq.set_task('APD_task', \
                                                          number_of_channels, \
                                                          self.sampling_rate, \
                                                          self.number_of_points, \
                                                          -self.voltage_range, \
                                                          +self.voltage_range, \
                                                          self.acquisition_mode, \
                                                          debug = True)
        self.acquire_continuously_bool = True
        self.save_automatically_bool = False
        self.filepath = initial_filepath
        self.filename = initial_filename
        self.params_to_be_saved = ''
        self.comment = ''
        self.acquisition_flag = False
        self.save_in_ascii = False
        self.spectrum_suffix = '' # for integration with specturm acquisition
        self.time_since_epoch = '0'
        return

    @pyqtSlot(bool)
    def play_pause(self, tracebool):
        if tracebool:
            self.start_trace()
        else:
            self.stop_acquisition()
        return 
    
    @pyqtSlot(bool)
    def acquire_continuously_check(self, acq_cont_bool):
        if acq_cont_bool:
            print('Signal acquisition will run continuously.')
            self.acquire_continuously_bool = True
            # set acquisition mode to measure continuosly
            self.acquisition_mode = 'continuous'
        else:
            print('Signal acquisition will run only once.')
            self.acquire_continuously_bool = False
            self.acquisition_mode = 'finite'
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
        self.read_samples = 0
        self.read_samples_to_send = 0
        self.trace_number = 0
        # prepare stream reader
        self.APD_stream_reader = daq.arm_measurement_in_loop(self.APD_task, number_of_channels)
        # stop (just in case) and start task
        self.APD_task.stop()
        self.APD_task.start()
        self.start_acquisition()
        return
    
    @pyqtSlot()
    def start_acquisition(self):
        self.acquireTimer.start()
        self.acquisition_flag = True
        self.init_time = timer()
        print('\nAcquisition started at {}'.format(self.init_time))
        self.time_since_epoch = tm.time()
        return

    @pyqtSlot()    
    def stop_acquisition(self):
        # stop timer signal
        self.total_time = timer() - self.init_time
        self.acquireTimer.stop()        
        # set flag to false to indicate acquisition has finished
        self.acquisition_flag = False
        # flush DAQ buffer
        self.data_array.flush()
        self.monitor_array.flush()
        print('\nStopping acquisition at {}'.format(timer()))
        print('Total time recording: {:.3f} s'.format(self.total_time))
        if not self.APD_task.is_task_done():
            self.APD_task.stop()
        # emit signal acquisition has ended
        self.acqStoppedSignal.emit()
        return
                    
    def acquire_trace(self):
        if self.acquisition_flag:
            # perform the measurement if measurements are yet to be done (the allocated
            # arracy need to be filled with read data
            if self.read_samples < self.number_of_points:
                # read a short stream
                n_available_per_ch, data = daq.measure_one_loop(self.APD_stream_reader, \
                                                         number_of_channels, \
                                                         self.number_of_points, \
                                                         self.read_samples)
                data_APD = data[0,:]
                data_monitor = data[1,:]
                # assign data to backend arrays (raw data, to be saved)
                self.data_array[self.read_samples:self.read_samples + n_available_per_ch] = data_APD
                self.monitor_array[self.read_samples:self.read_samples + n_available_per_ch] = data_monitor
                # put data in the queue
                data_queue.put([data, self.read_samples_to_send, n_available_per_ch])
                self.read_samples += n_available_per_ch
                self.read_samples_to_send += n_available_per_ch
            else:
                if self.acquire_continuously_bool:
                    # reset counter
                    self.read_samples = 0
                    self.trace_number += 1
                else:                
                    self.acqStoppedInnerSignal.emit()
                if self.save_automatically_bool:
                    # flush array at buffer into the disk (because it was a memmap array)
                    self.data_array.flush()
                    self.monitor_array.flush()
                    self.save_trace(message_box = False)
            # send data for autocorrelation
            # self.calculate_autorrelation(self.data_array)
        return
    
    def arm_for_confocal(self, pixel_time_confocal):
        # pixel_time_confocal in seconds
        self.number_of_points_confocal = calculate_num_of_points(pixel_time_confocal, \
                                                                 self.sampling_rate) 
        self.confocal_acquisition_mode = 'finite'
        print('Setting up new task...')
        self.APD_task_confocal, \
        self.time_to_finish_confocal = daq.set_task('APD_confocal_task', \
                                                    1, 
                                                    self.sampling_rate, \
                                                    self.number_of_points_confocal, \
                                                    -self.voltage_range, \
                                                    +self.voltage_range, \
                                                    self.confocal_acquisition_mode, \
                                                    debug = True)
        return self.number_of_points_confocal

    def acquire_confocal_trace(self):
        # measure a finite number of samples 
        meas_finite_array = daq.measure_data_one_time(self.APD_task_confocal, \
                                                                     self.number_of_points_confocal, \
                                                                     self.time_to_finish_confocal)
        return meas_finite_array

    def disarm_confocal_task(self):
        print('\nStopping task in progress...')
        self.APD_task_confocal.stop()
        print('\nClosing task...')
        self.APD_task_confocal.close()
        return

    def calculate_autorrelation(self, transmission_signal):
        z, lag = autocorr(transmission_signal)
        self.autocorrSignal.emit(z, lag, self.sampling_rate)
        return
    
    @pyqtSlot()
    def save_trace(self, message_box = False):
        # prepare full filepath
        filepath = self.filepath
        if self.save_automatically_bool:
            if self.acquire_continuously_bool:
                self.suffix = '_{:04d}'.format(self.trace_number)
            else:
                self.suffix = self.spectrum_suffix
        else:
            self.suffix = ''
        filename = self.filename + self.suffix
        # add time string to the filename
        timestr = tm.strftime("%Y%m%d_%H%M%S_")
        filename_timestamped = timestr + filename
        filename_data = filename_timestamped + '_transmission'
        filename_monitor = filename_timestamped + '_monitor'
        filename_params = filename_timestamped + '_params.txt'
        # save data
        full_filepath_data = os.path.join(filepath, filename_data)
        full_filepath_monitor = os.path.join(filepath, filename_monitor)
        full_filepath_params = os.path.join(filepath, filename_params)
        # before saving assert that all data has been stored correctly onto RAM
        # check if all data has been written correctly from DAQ board to RAM
        try:
            assert np.all(self.data_array > -1000), 'transmission data was not written correctly'
            assert np.all(self.monitor_array > -1000), 'monitor data was not written correctly'
            # save data
            np.save(full_filepath_data, np.transpose(self.data_array), allow_pickle = False)
            np.save(full_filepath_monitor, np.transpose(self.monitor_array), allow_pickle = False)
            # save measurement parameters and comments
            self.params_to_be_saved = self.get_params_to_be_saved()
            with open(full_filepath_params, 'w') as f:
                print(self.params_to_be_saved, file = f)
            print('Data %s has been saved.' % filename_timestamped)
            # emit signal for any other module that is importing this function
            self.fileSavedSignal.emit(full_filepath_data + '.npy', full_filepath_monitor + '.npy')
            if self.save_in_ascii:
                # it will save an ASCII encoded text file
                data_to_save = np.transpose(np.vstack((self.data_array, self.monitor_array)))
                header_txt = 'time_since_epoch %s s\nsampling_rate %s Hz\ntransmission monitor\nV V' % (str(self.time_since_epoch), self.sampling_rate)
                ascii_full_filepath = full_filepath_data + '.dat'
                np.savetxt(ascii_full_filepath, data_to_save, fmt='%.6f', header=header_txt)
        except AssertionError as err:
            print('\n ------------------------> WARNING!', err)
            return
            #if message_box:
            #    self.saving_data_error_signal.emit(filename)
        finally:
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
        self.APD_task, self.time_to_finish = daq.set_task('APD_task', \
                                                          number_of_channels, \
                                                          self.sampling_rate, \
                                                          self.number_of_points, \
                                                          -self.voltage_range, \
                                                          +self.voltage_range, \
                                                          self.acquisition_mode, \
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
        self.APD_task, self.time_to_finish = daq.set_task('APD_task', \
                                                          number_of_channels, \
                                                          self.sampling_rate, \
                                                          self.number_of_points, \
                                                          -self.voltage_range, \
                                                          +self.voltage_range, \
                                                          self.acquisition_mode, \
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
        self.APD_task, self.time_to_finish = daq.set_task('APD_task', \
                                                          number_of_channels, \
                                                          self.sampling_rate, \
                                                          self.number_of_points, \
                                                          -self.voltage_range, \
                                                          +self.voltage_range, \
                                                          self.acquisition_mode, \
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
        dict_to_be_saved["Voltage range (V)"] = self.voltage_range
        dict_to_be_saved["Sampling rate (S/s)"] = self.sampling_rate
        dict_to_be_saved["Duration (s)"] = self.duration
        dict_to_be_saved["Number of points"] = self.number_of_points
        dict_to_be_saved["Time since epoch (s)"] = self.time_since_epoch
        dict_to_be_saved["Comments"] = self.comment
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
    def close_backend(self, main_app = True):
        # data_queue.shutdown(immediate = True)
        self.APD_task.close()
        print('Task closed.')
        print('Stopping QTimer...')    
        self.acquireTimer.stop()
        if main_app:
            print('Exiting thread...')
            workerThread.exit()
            data_processor.kill()
            tm.sleep(5) # needed to close properly all modules
            # delete temporary files
            print('Removing temporary files...')
            os.remove(self.data_array_filepath), 
            os.remove(self.monitor_array_filepath)
            os.remove(self.time_array_filepath)
        return
    
    def make_connections(self, frontend):
        self.acqStoppedInnerSignal.connect(self.stop_acquisition)
        frontend.traceSignal.connect(self.play_pause)
        frontend.makeTraceContSignal.connect(self.acquire_continuously_check)
        frontend.saveTraceContSignal.connect(self.save_automatically_check)
        frontend.saveTraceASCIISignal.connect(self.save_ascii)
        frontend.setSamplingRateSignal.connect(self.change_sampling_rate) 
        frontend.setDurationSignal.connect(self.change_duration) 
        frontend.setVoltageRangeSignal.connect(self.change_voltage_range)
        frontend.closeSignal.connect(self.close_backend)
        frontend.saveSignal.connect(self.save_trace)
        frontend.setWorkDirSignal.connect(self.set_working_folder)
        frontend.filenameSignal.connect(self.set_filename)
        frontend.commentSignal.connect(self.set_comment)
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

    # threads that run in background
    workerThread = QThread()
    worker.acquireTimer.moveToThread(workerThread)
    worker.acquireTimer.timeout.connect(worker.acquire_trace, QtCore.Qt.QueuedConnection)
    worker.moveToThread(workerThread)
    
    data_processor = DataProcessor()
    data_processor.displayDataTimer.timeout.connect(data_processor.get_data_from_queue, QtCore.Qt.QueuedConnection)

    # connect both classes 
    worker.make_connections(gui)
    gui.make_connections(worker, data_processor)
    data_processor.make_connections(gui)
    
    # start worker in a different thread (avoids GUI freezing)
    workerThread.start()
    data_processor.start()
    
    gui.show()
    app.exec()
    
