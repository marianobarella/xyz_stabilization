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
import sys
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph.ptime as ptime
from pyqtgraph.dockarea import Dock, DockArea
from PyQt5.QtCore import pyqtSignal, pyqtSlot
import daq_board_toolbox as daq
from tkinter import filedialog
import tkinter as tk
import time as tm

#=====================================

# Initialize DAQ board

#=====================================

print('\nInitializing DAQ board...')
daq_board = daq.init_daq()
# set update trace plot period
updateTrace_period = 20 # in ms
# set measurement range
initial_voltage_range = 2.0
daq.check_voltage_range(daq_board, initial_voltage_range)
# set sampling rate
max_sampling_rate = daq_board.ai_max_single_chan_rate # set to maximum, here 2 MS/s    
initial_sampling_rate = 1e3 # in S/s
# duration of the traces in s
initial_duration = 20
# set acquisition mode to measure continuosly
acquisition_mode = 'continuous'
# function that calculates the number of datapoins to be measured
def calculate_num_of_points(duration, sampling_rate):
    number_of_points = int(duration*sampling_rate)
    print('At {:.3f} MS/s sampling rate, a duration of {} s means:'.format(sampling_rate*1e-6, \
                                                                       duration))
    print('{} datapoints per trace'.format(number_of_points))  
    return number_of_points

#=====================================

# GUI / Frontend definition

#=====================================

class Frontend(QtGui.QFrame):

    traceSignal = pyqtSignal(bool)
    traceContSignal = pyqtSignal(bool)
    # stopSignal = pyqtSignal()
    # playSignal = pyqtSignal()
    # saveSignal = pyqtSignal()
    setVoltageRange = pyqtSignal(float)
    setSamplingRate = pyqtSignal(int)
    setDuration = pyqtSignal(float)
    closeSignal = pyqtSignal()
    setWorkDirSignal = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setUpGUI()
        # set the title of thw window
        title = "APD signal module"
        self.setWindowTitle(title)

    def setUpGUI(self):

        # Single acquisition button
        self.traceButton = QtGui.QPushButton('► Acquire single / ◘ Stop')
        self.traceButton.setCheckable(True)
        self.traceButton.clicked.connect(self.get_trace)
        self.traceButton.setToolTip('Play or Stop a single APD signal acquisition')
        self.traceButton.setStyleSheet(
            "QPushButton { background-color: lightgray; }"
            "QPushButton:pressed { background-color: red; }"
            "QPushButton::checked { background-color: lightcoral; }")

        # Continuous acquisition button
        self.traceContinuouslyButton = QtGui.QPushButton('► Acquire continuously / ◘ Stop')
        self.traceContinuouslyButton.setCheckable(True)
        self.traceContinuouslyButton.clicked.connect(self.get_trace_continuously)
        self.traceContinuouslyButton.setToolTip('Play or Stop continuously APD signal acquisition')
        self.traceContinuouslyButton.setStyleSheet(
            "QPushButton { background-color: sandybrown; }"
            "QPushButton:pressed { background-color: red; }"
            "QPushButton::checked { background-color: lightcoral; }")

        # Save data button
        self.saveButton = QtGui.QPushButton('Save trace')
        self.saveButton.clicked.connect(self.get_save_trace)
        self.saveButton.setStyleSheet(
            "QPushButton { background-color: lightgray; }"
            "QPushButton:pressed { background-color: cornflowerblue; }")
        
        # Working folder
        self.working_dir_button = QtGui.QPushButton('Select directory')
        self.working_dir_button.clicked.connect(self.set_working_dir)
        self.working_dir_button.setStyleSheet(
            "QPushButton { background-color: lightgray; }"
            "QPushButton:pressed { background-color: palegreen; }")
        self.working_dir_label = QtGui.QLabel('Working directory')
        self.file_path = ''
        self.working_dir_path = QtGui.QLineEdit(self.file_path)
        self.working_dir_path.setReadOnly(True)
        self.filename_label = QtGui.QLabel('Filename (.dat)')
        self.filename = ''
        self.filename_name = QtGui.QLineEdit(self.filename)
        
        # Comments box
        self.comments_label = QtGui.QLabel('Comments:')
        self.comment = ''
        self.comments = QtGui.QLineEdit(self.comment)
        self.comments.setPlaceholderText('Enter your comments here. They will be saved with the trace data.')

        # Voltage range
        voltage_ranges_option = ['0.1', '0.2', '0.5', '1.0', '2.0', '5.0', '10.0']
        self.maxVoltageRangeLabel = QtGui.QLabel('Max voltage range (V): ')
        self.maxVoltageRangeList = QtGui.QComboBox()
        self.maxVoltageRangeList.addItems(voltage_ranges_option)
        self.maxVoltageRangeList.setCurrentText(str(initial_voltage_range))
        self.maxVoltageRangeList.currentTextChanged.connect(self.voltage_range_changed)
        
        # Sampling rate
        self.samplingRateLabel = QtGui.QLabel('Sampling rate (kS/s): ')
        self.samplingRateValue = QtGui.QLineEdit(str(int(initial_sampling_rate/1e3)))
        self.samplingRateValue_previous = int(self.samplingRateValue.text())
        self.samplingRateValue.editingFinished.connect(self.sampling_rate_changed)
        self.samplingRateValue.setValidator(QtGui.QIntValidator(1, 2000))
        
        # Duration of the measurement
        self.durationValue_initial = initial_duration
        self.durationLabel = QtGui.QLabel('Duration (s): ')
        self.durationValue = QtGui.QLineEdit(str(self.durationValue_initial))
        self.durationValue_previous = float(self.durationValue.text())
        self.durationValue.editingFinished.connect(self.duration_value_changed)
        # self.durationValue.setValidator(QtGui.QIntValidator(1, 2000))
        
        # display mean and std of the signal using labels
        fontsize = 20
        font_family = 'Serif'
        self.MeanValueLabel = QtGui.QLabel('Mean (V): ')
        self.MeanValueLabel.setFont(QtGui.QFont(font_family, fontsize))
        self.signalMeanValue = QtGui.QLabel('0.000')
        self.signalMeanValue.setFont(QtGui.QFont(font_family, fontsize))
        self.StdValueLabel = QtGui.QLabel('Std dev (mV): ')
        self.StdValueLabel.setFont(QtGui.QFont(font_family, fontsize))
        self.signalStdValue = QtGui.QLabel('0.000')
        self.signalStdValue.setFont(QtGui.QFont(font_family, fontsize))
        
        # Layout
        self.paramWidget = QtGui.QWidget()
        subgrid_layout = QtGui.QGridLayout()
        self.paramWidget.setLayout(subgrid_layout)
        subgrid_layout.addWidget(self.traceButton, 0, 0)
        subgrid_layout.addWidget(self.traceContinuouslyButton, 0, 1)
        subgrid_layout.addWidget(self.saveButton, 0, 2)
        subgrid_layout.addWidget(self.working_dir_button, 0, 3)
        subgrid_layout.addWidget(self.working_dir_label, 1, 0, 1, 3)
        subgrid_layout.addWidget(self.working_dir_path, 1, 1, 1, 3)
        subgrid_layout.addWidget(self.filename_label, 2, 0, 1, 3)
        subgrid_layout.addWidget(self.filename_name, 2, 1, 1, 3)
        subgrid_layout.addWidget(self.maxVoltageRangeLabel, 3, 0)
        subgrid_layout.addWidget(self.maxVoltageRangeList, 3, 1)
        subgrid_layout.addWidget(self.samplingRateLabel, 4, 0)
        subgrid_layout.addWidget(self.samplingRateValue, 4, 1)
        subgrid_layout.addWidget(self.durationLabel, 5, 0)
        subgrid_layout.addWidget(self.durationValue, 5, 1)
        subgrid_layout.addWidget(self.MeanValueLabel, 6, 0)
        subgrid_layout.addWidget(self.signalMeanValue, 6, 1)
        subgrid_layout.addWidget(self.StdValueLabel, 6, 2)
        subgrid_layout.addWidget(self.signalStdValue, 6, 3)
        subgrid_layout.addWidget(self.comments_label, 7, 0)
        subgrid_layout.addWidget(self.comments, 8, 0, 1, 3)
          
        # widget for the data
        self.traceWidget = pg.GraphicsLayoutWidget()
        self.signal_plot = self.traceWidget.addPlot(row = 1, col = 1, title = 'APD signal')
        self.signal_plot.setAutoPan(x = True, y = None)
        self.signal_plot.enableAutoRange(axis = 'y', enable = True)
        # self.signal_plot.setXRange(0, 10)
        self.signal_plot.showGrid(x = True, y = True)
        self.signal_plot.setLabel('left', 'Voltage (V)')
        self.signal_plot.setLabel('bottom', 'Time (s)')
        self.raw_data_curve = self.signal_plot.PlotCurveItem(skipFiniteCheck = True, \
                                                    pen = pg.mkPen('w'))
        self.mean_curve = self.signal_plot.PlotCurveItem(skipFiniteCheck = True, \
                                                pen = pg.mkPen('b'))
        self.sd_plus_curve = self.signal_plot.PlotCurveItem(skipFiniteCheck = True, \
                                                   pen = pg.mkPen('g'))
        self.sd_minus_curve = self.signal_plot.PlotCurveItem(skipFiniteCheck = True, \
                                                    pen = pg.mkPen('g'))
        
        # Docks
        hbox = QtGui.QHBoxLayout(self)
        dockArea = DockArea()
        traceDock = Dock('Acquisition controls', size = (100,1))
        traceDock.addWidget(self.paramWidget)
        dockArea.addDock(traceDock)
      
        viewDock = Dock('Trace viewbox', size = (100,4))
        viewDock.addWidget(self.traceWidget)
        dockArea.addDock(viewDock, 'bottom', traceDock)

        hbox.addWidget(dockArea) 
        self.setLayout(hbox)
        return

    def set_working_dir(self):
        self.setWorkDirSignal.emit()
        return
    
    @pyqtSlot(str)
    def get_file_path(self, file_path):
        self.file_path = file_path
        self.working_dir_path.setText(self.file_path)
        return
    
    def voltage_range_changed(self, selected_range):
        # Note that changing the QtComboBox option
        # will emit a signal that contains the selected option
        self.voltage_range = float(selected_range)
        self.setVoltageRange.emit(self.voltage_range)
        return
    
    def sampling_rate_changed(self):
        self.selected_rate = int(self.samplingRateValue.text())
        if self.selected_rate != self.samplingRateValue_previous:
            self.samplingRateValue_previous = self.selected_rate
            self.setSamplingRate.emit(self.selected_rate)
        return
    
    def duration_value_changed(self):
        self.duration = float(self.durationValue.text())
        if self.duration != self.durationValue_previous:
            self.durationValue_previous = self.duration
            self.setDuration.emit(self.duration)
        return
    
    def get_trace(self):
        if self.traceButton.isChecked():
            self.traceSignal.emit(True)
        else:
            self.traceSignal.emit(False) 
        return
    
    def get_trace_continuously(self):
        if self.traceContinuouslyButton.isChecked():
            self.traceContSignal.emit(True)
        else:
            self.traceContSignal.emit(False) 
        return
    
    def get_play(self):
        self.playSignal.emit()
        return
    
    def get_stop(self):
        self.stopSignal.emit()
        return
    
    def get_save_trace(self):
        if self.saveButton.isChecked:
            self.saveSignal.emit()
        return
    
    @pyqtSlot(np.ndarray, np.ndarray, np.ndarray, np.ndarray)
    def get_data(self, time_array, data_array, mean_array, sd_array): 
        # plot raw
        self.raw_data_curve.setData(time_array, data_array)
        # plot mean
        self.mean_curve.setData(time_array, mean_array)
        # plot sd
        sd_plus_array = mean_array + sd_array
        self.sd_plus_curve.setData(time_array, sd_plus_array)
        sd_minus_array = mean_array - sd_array        
        self.sd_minus_curve.setData(time_array, sd_minus_array)
        
        
        # path_raw_data_curve = pg.arrayToQPath(time_array, data_array, connect = 'all', finiteCheck = False)
        # path_raw_mean_curve = pg.arrayToQPath(time_array, mean_array, connect = 'all', finiteCheck = False)
        # path_raw_sd_plus_curve = pg.arrayToQPath(time_array, sd_plus_array, connect = 'all', finiteCheck = False)
        # path_raw_sd_minus_curve = pg.arrayToQPath(time_array, sd_minus_array, connect = 'all', finiteCheck = False)
        
        # item = QtGui.QGraphicsPathItem(path)
        # item.setPen(pg.mkPen('w'))
        # plt.addItem(item)
        
        # update value labels
        mean = mean_array[-1]
        sd = sd_array[-1]
        sd_mV = sd*1000 # to mV
        self.signalMeanValue.setText('{:.3f}'.format(mean))
        self.signalStdValue.setText('{:.3f}'.format(sd_mV))
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
            self.closeSignal.emit()
            tm.sleep(1)
            print('Closing GUI...')
            self.close()
            app.quit()
        else:
            event.ignore()
            print('Back in business...')    
        return
    

    def make_connections(self, backend):
        backend.dataSignal.connect(self.get_data)
        backend.filePathSignal.connect(self.get_file_path)
        backend.acqStopped.connect(self.acquisition_stopped)
        return
    
#=====================================

# Controls / Backend definition

#===================================== 
       
class Backend(QtCore.QObject):

    dataSignal = pyqtSignal(np.ndarray, np.ndarray, np.ndarray, np.ndarray)
    filePathSignal = pyqtSignal(str)
    acqStopped = pyqtSignal()
    # data_printingSignal = pyqtSignal(list)
    # data_printingSignal_dimers = pyqtSignal(list)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # set timer to plot the data and check buttons
        self.updateTimer = QtCore.QTimer()
        self.updateTimer.timeout.connect(self.trace_update) 
        self.updateTimer.setInterval(updateTrace_period) # in ms
        self.trace_state = False
        # set APD acquisition channel
        self.sampling_rate = initial_sampling_rate
        self.time_base = 1/self.sampling_rate
        self.duration = initial_duration
        self.number_of_points = calculate_num_of_points(self.duration, self.sampling_rate)
        self.voltage_range = initial_voltage_range
        self.APD_task, self.time_to_finish = daq.set_ch_APD(self.sampling_rate, \
                                                            self.number_of_points, \
                                                            -self.voltage_range, \
                                                            +self.voltage_range, \
                                                            acquisition_mode, \
                                                            debug = True)
        return

    @pyqtSlot(bool)
    def play_pause(self, tracebool):
        if tracebool:
            self.start_trace()
        else:
            self.stop_trace()
        return 
    
    def start_trace(self):
        print('\nAcquisition started at {}'.format(timer()))
        # allocate arrays
        self.data_array_filepath, self.data_array = daq.allocate_datafile(self.number_of_points)
        self.time_array_filepath, self.time_array = daq.allocate_datafile(self.number_of_points)
        self.mean_array_filepath, self.mean_array = daq.allocate_datafile(self.number_of_points)
        self.sd_array_filepath, self.sd_array = daq.allocate_datafile(self.number_of_points)
        # counter to account for the number of points already measured
        self.i = 0
        # prepare stream reader
        self.APD_stream_reader = daq.arm_measurement_in_loop(self.APD_task)
        # start task
        self.APD_task.start()
        # start timer to retrieve data periodically
        self.updateTimer.start()
        # perform the measurement 
        # self.meas_cont_array = daq.measure_data_continuously(self.APD_task, \
        #                                                      self.number_of_points, \
        #                                                      self.data_array, \
        #                                                      debug = True)
        # self.meas_cont_array = daq.measure_in_loop_continuously(self.APD_task, \
        #                                                         self.APD_stream_reader, \
        #                                                         self.number_of_points, \
        #                                                         self.data_array)
        # # emit signal acquisition has ended
        # self.APD_task.stop()
        # print('\nAcquisition finished at {}'.format(timer()))
        # self.acqStopped.emit()
        return
    
    def stop_trace(self):
        # stop timer
        self.updateTimer.stop()
        # flush DAQ buffer
        self.data_array.flush()
        # reset counter
        self.i = 0
        if not self.APD_task.is_task_done():
            print('\nStopping acquisition at {}'.format(timer()))
            self.APD_task.stop()
        # emit signal acquisition has ended
        self.acqStopped.emit()
        # closeShutter(self.laser)
        # self.timer_real = round(self.timer_end- self.timer_inicio, 2)
        #print(self.timer_real, self.ptr1*self.time, 'tiempo')         
        # print('Time trace', self.timer_real, 'tiempo no real', round(self.timeaxis[-1], 2))
        # self.save_trace()
        return

    # @pyqtSlot(bool)    
    # def play_continuously(self, tracebool):
    #     print('\nAcquisition started')
    #     # start timer to retrieve data periodically
    #     self.updateTimer.start()
    #     # allocate array
    #     self.data_array_filepath, self.data_array = daq.allocate_datafile(self.number_of_points)
    #     # prepare stream reader
    #     self.APD_stream_reader = daq.arm_measurement_in_loop(self.APD_task)
    #     # start task
    #     self.APD_task.start()
    #     # perform the measurement 
    #     while self.trace_state:
    #         self.meas_cont_array = daq.measure_in_loop_continuously(self.APD_task, \
    #                                                                 self.APD_stream_reader, \
    #                                                                 self.number_of_points, \
    #                                                                 self.data_array)
    #         print('Continuous measurement of {} points ended.'.format(self.number_of_points))
    #         print('Done.')
    #     return
                    
    def trace_update(self):
        # perform the measurement 
        if ( not self.APD_task.is_task_done() and self.i < self.number_of_points ):
            # read a short stream
            n_available, data = daq.measure_one_loop(self.APD_stream_reader, \
                                                     self.number_of_points, \
                                                     self.i)
            time = np.arange(self.i, self.i + n_available)*self.time_base
            # do some minor stats
            mean_value = np.mean(data)
            sd_value = np.std(data, ddof = 1)
            # assign
            self.data_array[self.i:self.i + n_available] = data
            self.time_array[self.i:self.i + n_available] = time
            self.mean_array[self.i:self.i + n_available] = mean_value
            self.sd_array[self.i:self.i + n_available] = sd_value
            # preapre data to pass to frontend
            data_array_to_pass = self.data_array[:self.i + n_available]
            time_array_to_pass = self.time_array[:self.i + n_available]
            mean_array_to_pass = self.mean_array[:self.i + n_available]
            sd_array_to_pass = self.sd_array[:self.i + n_available]
            self.i += n_available
            # send
            self.dataSignal.emit(time_array_to_pass, data_array_to_pass, \
                                 mean_array_to_pass, sd_array_to_pass)
        else:
            # stop timer
            self.updateTimer.stop()
            # flush DAQ buffer
            self.data_array.flush()
            # check if all data has been written correctly
            assert np.all(self.data_array > -1000)
            print('\nAcquisition finished at {}'.format(timer()))
            self.stop_trace()
        return

    # @pyqtSlot(str)        
    # def direction(self, file_name):
    #     self.file_path = file_name
        
    # @pyqtSlot()
    # def save_trace(self):
        
    #     filepath = self.file_path
    #     timestr = time.strftime("%Y%m%d-%H%M%S")
    #     name = str(filepath + "/" + "timetrace-"  + timestr + ".txt")
        
    #     f = open(name, "w")
            
    #     time_real = list(np.linspace(0.01, self.timer_real, self.ptr))
        
    #     np.savetxt(name, np.transpose([time_real, self.data1]), fmt='%.3e')
                       
    #        # np.savetxt(name,
    #                  #   np.transpose([self.timeaxis[:self.ptr1],
    #                                  # self.data1[:self.ptr1]]))
    
    #     f.close()
    #     print("\n Save the trace.")
    
    @pyqtSlot(float)    
    def change_voltage_range(self, voltage_range):
        if not self.APD_task.is_task_done():
            print('\nStopping task in progress...')
            self.APD_task.stop()
        print('\nClosing task...')
        self.APD_task.close()
        daq.check_voltage_range(daq_board, voltage_range)
        print('Changing voltage ranges...')
        self.voltage_range = voltage_range # in V, is float
        print('Setting up new task...')
        self.APD_task, self.time_to_finish = daq.set_ch_APD(self.sampling_rate, \
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
        print('\nClosing task...')
        self.APD_task.close()
        self.sampling_rate = sampling_rate*1e3 # in S/s, is int
        self.time_base = 1/self.sampling_rate
        print('Sampling rate changed to', sampling_rate, 'kS/s')
        self.number_of_points = calculate_num_of_points(self.duration, self.sampling_rate)
        print('Setting up new task...')
        self.APD_task, self.time_to_finish = daq.set_ch_APD(self.sampling_rate, \
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
        print('\nClosing task...')
        self.APD_task.close()
        self.duration = duration
        print('Duration of the measurement changed to', duration, 's')
        self.number_of_points = calculate_num_of_points(self.duration, self.sampling_rate) 
        print('Setting up new task...')
        self.APD_task, self.time_to_finish = daq.set_ch_APD(self.sampling_rate, \
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
        file_path = filedialog.askdirectory()
        if not file_path:
            print('No folder selected!')
        else:
            self.file_path = file_path
            self.filePathSignal.emit(self.file_path) # TODO Lo reciben los módulos de traza, confocal y printing
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
        frontend.traceContSignal.connect(self.play_pause)
    #     frontend.stopSignal.connect(self.stop_trace)
    #     frontend.playSignal.connect(self.start_trace)
    #     frontend.saveSignal.connect(self.save_trace)
        frontend.setSamplingRate.connect(self.change_sampling_rate) 
        frontend.setDuration.connect(self.change_duration) 
        frontend.setVoltageRange.connect(self.change_voltage_range)
        frontend.closeSignal.connect(self.closeBackend)
        frontend.setWorkDirSignal.connect(self.set_working_folder)
        return
    
if __name__ == '__main__':
    # make application
    app = QtGui.QApplication([])
    
    # connect both classes
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
    