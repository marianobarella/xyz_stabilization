# -*- coding: utf-8 -*-
"""
Created on Thu May 31, 2023

pyLock is a control software of the 2nd gen Plasmonic Optical Tweezer setup that
allows the user to stabilize the system in xyz using a closed-loop system made 
of the piezostage and two cameras
Here, the Graphical User Interface of pyLock integrates the following modules:
    - piezostage control
    - xy stabilization
    - z stabilization 

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland
"""

import time as tm
from pyqtgraph.Qt import QtGui, QtCore
from pyqtgraph.dockarea import DockArea, Dock
from PyQt5.QtCore import pyqtSignal, pyqtSlot
import numpy as np
import piezo_stage_GUI
import z_stabilization_GUI
import xy_stabilization_GUI


# # time interval to check state of the specturm acquisition button
# check_button_state = 100 # in ms
# initial_filename = 'spectrum'
# spectra_path = 'D:\\daily_data\\spectra\\self_generated_spectra'

#=====================================

# GUI / Frontend definition

#=====================================

class Frontend(QtGui.QMainWindow):
    
    closeSignal = pyqtSignal(bool)
    # process_acquired_spectrum_signal = pyqtSignal()
    # filenameSignal = pyqtSignal(str)
    
    def __init__(self, piezo_frontend, main_app = True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cwidget = QtGui.QWidget()
        self.setCentralWidget(self.cwidget)
        self.setWindowTitle('pyLock')
        self.setGeometry(5, 30, 1900, 800) # x pos, y pos, width, height
        self.main_app = main_app
        # import frontend modules
        # piezo widget (frontend) must be imported in the main
        # hide piezo GUI on the xy and z widgets
        self.piezoWidget = piezo_frontend
        self.zWidget = z_stabilization_GUI.Frontend(piezo_frontend, \
                                                    show_piezo_subGUI = False, \
                                                    main_app = False, \
                                                    connect_to_piezo_module = False)
        self.xyWidget = xy_stabilization_GUI.Frontend(piezo_frontend, \
                                                    show_piezo_subGUI = False, \
                                                    main_app = False, \
                                                    connect_to_piezo_module = False)
        self.setUpGUI()
        return
    
    def setUpGUI(self):
        # # modify from laser's GUI the spectrum acquisition buttons
        # self.lasersWidget.integration_time_label.setText('Integration time (s):')
        # self.lasersWidget.acquire_spectrum_button.setCheckable(True)
        # self.lasersWidget.acquire_spectrum_button.clicked.connect(self.lasersWidget.acquire_spectrum_button_check)
        # self.lasersWidget.acquire_spectrum_button.setStyleSheet(
        #         "QPushButton { background-color: lightgrey; }"
        #         "QPushButton::checked { background-color: red; }")
        # self.lasersWidget.integration_time_comment.setText('Attention: It overrides Duration variable of the APD trace.')
        # self.lasersWidget.process_spectrum_button.clicked.connect(self.process_spectrum_button_check)
        # self.lasersWidget.process_spectrum_button.setStyleSheet(
        #         "QPushButton { background-color: lightgrey; }"
        #         "QPushButton::checked { background-color: lightgreen; }")
        # self.lasersWidget.filename_label.setText('Filename (.dat)')
        # self.lasersWidget.filename_name.setFixedWidth(200)
        # self.lasersWidget.filename = initial_filename
        # self.lasersWidget.filename_name.setText(self.lasersWidget.filename)
        # self.lasersWidget.filename_name.editingFinished.connect(self.set_filename)
        
        # GUI layout
        grid = QtGui.QGridLayout()
        self.cwidget.setLayout(grid)
        # Dock Area
        dockArea = DockArea()
        self.dockArea = dockArea
        grid.addWidget(self.dockArea)
        
        ## Add piezo module
        piezoDock = Dock('Piezostage control')
        piezoDock.addWidget(self.piezoWidget)
        self.dockArea.addDock(piezoDock)
        
        ## Add xy stabilization module
        xyDock = Dock('xy stabilization')
        xyDock.addWidget(self.xyWidget)
        self.dockArea.addDock(xyDock, 'bottom', piezoDock)
        
        ## Add z stabilization module
        zDock = Dock('z stabilization')
        zDock.addWidget(self.zWidget)
        self.dockArea.addDock(zDock, 'left', xyDock)
        return
       
    # def process_spectrum_button_check(self):
    #     self.process_acquired_spectrum_signal.emit()
    #     return
    
    # @pyqtSlot()    
    # def apd_acq_started(self):
    #     self.apdWidget.traceButton.setChecked(True)
    #     self.apdWidget.get_trace()
    #     return
    
    # @pyqtSlot()    
    # def apd_acq_stopped(self):
    #     self.apdWidget.acquisition_stopped()
    #     return    
    
    # @pyqtSlot()    
    # def spectrum_finished(self):
    #     self.lasersWidget.acquire_spectrum_button.setChecked(False)
    #     return
    
    # def set_filename(self):
    #     filename = self.lasersWidget.filename_name.text()
    #     if filename != self.lasersWidget.filename:
    #         self.lasersWidget.filename = filename
    #         self.filenameSignal.emit(self.lasersWidget.filename)    
    #     return
    
    # re-define the closeEvent to execute an specific command
    def closeEvent(self, event, *args, **kwargs):
        super().closeEvent(event, *args, **kwargs)
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
    
    def make_modules_connections(self, backend):    
        # connect Frontend modules with their respectives Backend modules
        backend.piezoWorker.make_connections(self.piezoWidget)
        backend.xyWorker.make_connections(self.xyWidget)
        backend.zWorker.make_connections(self.zWidget)
        # backend.spectrum_finished_signal.connect(self.spectrum_finished)
        # backend.apd_acq_started_signal.connect(self.apd_acq_started)
        # backend.apd_acq_stopped_signal.connect(self.apd_acq_stopped)
        return
            
#=====================================

# Controls / Backend definition

#===================================== 
        
class Backend(QtCore.QObject):
    
    # apd_acq_started_signal = pyqtSignal()
    # apd_acq_stopped_signal = pyqtSignal()
    # spectrum_finished_signal = pyqtSignal()
    
    def __init__(self, piezo_stage, piezo_backend, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.piezo_stage = piezo_stage
        self.piezoWorker = piezo_backend
        self.zWorker = z_stabilization_GUI.Backend(self.piezo_stage, \
                                                   self.piezoWorker, \
                                                   connect_to_piezo_module = False)
        self.xyWorker = xy_stabilization_GUI.Backend(self.piezo_stage, \
                                                     self.piezoWorker, \
                                                     connect_to_piezo_module = False)
        # self.scanTimer = QtCore.QTimer()
        # self.scanTimer.timeout.connect(self.continue_scan) # funciton to connect after each interval
        # self.scanTimer.setInterval(check_button_state) # in ms
        # self.list_of_transmission_files = []
        # self.list_of_monitor_files = []
        # self.filename = initial_filename
        return
        
    # @pyqtSlot(bool)    
    # def acquire_spectrum(self, acq_spec_flag):
    #     # acq_spec_flag varaiable is the state of the button
    #     self.acquiring_spectrum_flag = acq_spec_flag
    #     if self.acquiring_spectrum_flag:
    #         print('\n!!!!!! ------ !!!!!! Starting acquisition of the spectrum...')
    #         self.apdWorker.change_duration(self.lasersWorker.integration_time)
    #         self.scanTimer.start()
    #         self.spectrum_counter = 0
    #     else:
    #         self.scanTimer.stop()
    #         self.apd_acq_stopped_signal.emit()
    #         self.spectrum_finished_signal.emit()
    #         self.spectrum_counter = 0
    #         print('\nAborting acquisition of the spectrum...')
    #     return

    # def continue_scan(self):
    #     # check if button is checked or counter continues to increase
    #     if self.acquiring_spectrum_flag:
    #         # check if transmission APD is acquiring first
    #         # if not, continue with the spectrum
    #         if not self.apdWorker.acquisition_flag:
    #             # close shutter of Ti:Sa if open
    #             self.lasersWorker.shutterTisa(False)
    #             # check status of Ti:Sa
    #             # if Ti:Sa is not changing wavelength continue with the spectrum
    #             status = self.lasersWorker.update_tisa_status()
    #             if status == 1:
    #                 # try to measure or check if we're done
    #                 if self.spectrum_counter < len(self.lasersWorker.wavelength_scan_array):
    #                     # still scanning
    #                     # get and change wavelength
    #                     wavelength = self.lasersWorker.wavelength_scan_array[self.spectrum_counter]
    #                     self.lasersWorker.change_wavelength(wavelength)
    #                     # set suffix for saving the intensity trace
    #                     self.apdWorker.spectrum_suffix = '_{:04d}nm'.format(int(round(wavelength,0)))
    #                     # increment counter for next step
    #                     self.spectrum_counter += 1
    #                     # open shutter
    #                     self.lasersWorker.shutterTisa(True)
    #                     # emit pyqtSignal to frontend to enable trace displaying
    #                     # and start signal acquisition
    #                     self.apd_acq_started_signal.emit()
    #                     # set acquisition variable of APD backend to True
    #                     self.apdWorker.acquisition_flag = True
    #                 else:
    #                     # no more points to scan
    #                     self.acquire_spectrum(False)
    #             else:
    #                 print('\nWavelength has not been changed.')
    #                 print('Ti:Sa status: ', status)
            
    #         # - apd acquisiition, save, name definition
    #         # - start over
    #     return
    
    # @pyqtSlot(str, str)
    # def append_saved_file(self, full_filepath_data, full_filepath_monitor):
    #     self.list_of_transmission_files.append(full_filepath_data)
    #     self.list_of_monitor_files.append(full_filepath_monitor)
    #     return
    
    # def process_signals(self, list_of_files):
    #     mean_array = np.zeros(len(list_of_files))
    #     std_dev_array = np.zeros(len(list_of_files))
    #     for i in range(len(list_of_files)):
    #         f = list_of_files[i]
    #         data = np.load(f)
    #         mean_array[i] = np.mean(data)
    #         std_dev_array[i] = np.std(data, ddof = 1)
    #     return mean_array, std_dev_array
    
    # @pyqtSlot()
    # def process_acquired_spectrum(self):
    #     print('Processing all spectra...')
    #     # preapre arrays
    #     wavelength = self.lasersWorker.wavelength_scan_array
    #     mean_data, std_dev_data = self.process_signals(self.list_of_transmission_files)
    #     mean_monitor, std_dev_monitor = self.process_signals(self.list_of_monitor_files)
    #     # set filename
    #     filename_spectrum = self.filename
    #     timestr = tm.strftime("_%Y%m%d_%H%M%S")
    #     filename_spectrum = filename_spectrum + timestr
    #     # it will save an ASCII encoded text file
    #     data_to_save = np.transpose(np.vstack((wavelength, \
    #                                            mean_data, std_dev_data, \
    #                                            mean_monitor, std_dev_monitor)))
    #     header_txt = 'wavelength transmission_mean transmission_std_dev monitor_mean monitor_std_dev\nnm V V V V'
    #     ascii_full_filepath = spectra_path + '\\' + filename_spectrum + '.dat'
    #     np.savetxt(ascii_full_filepath, data_to_save, fmt='%.6f', header=header_txt)
    #     print('Spectrum has been generated and saved with filename %s.dat' % filename_spectrum)
    #     return
    
    # @pyqtSlot(str)
    # def set_filename(self, new_filename):
    #     self.filename = new_filename
    #     print('New filename has been set:', self.filename)
    #     return
    
    @pyqtSlot(bool)
    def close_all_backends(self, main_app = True):
        print('Closing all backends...')
        self.piezoWorker.close_backend(main_app = False)
        self.xyWorker.close_backend(main_app = False)
        self.zWorker.close_backend(main_app = False)
        # print('Stopping updater (QtTimer)...')
        # self.scanTimer.stop()
        if main_app:
            print('Exiting thread...')
            tm.sleep(1)
            workerThread.exit()
        return
    
    def make_modules_connections(self, frontend):
        frontend.closeSignal.connect(self.close_all_backends)
        # connect Backend modules with their respectives Frontend modules
        frontend.piezoWidget.make_connections(self.piezoWorker)
        frontend.xyWidget.make_connections(self.xyWorker)
        frontend.zWidget.make_connections(self.zWorker)
        # # connection that triggers the measurement of the spectrum
        # frontend.lasersWidget.acquire_spectrum_button_signal.connect(self.acquire_spectrum)
        # # connection that process the acquired data
        # frontend.process_acquired_spectrum_signal.connect(self.process_acquired_spectrum)
        # frontend.filenameSignal.connect(self.set_filename)
        # # from backend
        # self.apdWorker.fileSavedSignal.connect(self.append_saved_file)
        return
    
#=====================================

#  Main program

#=====================================
      
if __name__ == '__main__':
    # make application
    app = QtGui.QApplication([])
    
    # init stage
    piezo = piezo_stage_GUI.piezo_stage  
    piezo_frontend = piezo_stage_GUI.Frontend(main_app = False)
    piezo_backend = piezo_stage_GUI.Backend(piezo)
    
    # create both classes
    gui = Frontend(piezo_frontend)
    worker = Backend(piezo, piezo_backend)
       
    ###################################
    # move backend to another thread
    workerThread = QtCore.QThread()
    # move the timer of the piezo and its main worker
    worker.piezoWorker.updateTimer.moveToThread(workerThread)
    worker.piezoWorker.moveToThread(workerThread)
    # move the timers of the xy and its main worker
    worker.xyWorker.viewTimer.moveToThread(workerThread)
    worker.xyWorker.tempTimer.moveToThread(workerThread)
    worker.xyWorker.trackingTimer.moveToThread(workerThread)
    worker.xyWorker.moveToThread(workerThread)
    # move the timers of the z and its main worker
    worker.zWorker.trackingTimer.moveToThread(workerThread)
    worker.zWorker.viewTimer.moveToThread(workerThread)
    worker.zWorker.moveToThread(workerThread)
    # move the main worker
    worker.moveToThread(workerThread)

    ###################################

    # connect both classes 
    worker.make_modules_connections(gui)
    gui.make_modules_connections(worker)
    
    # start thread
    workerThread.start()
    
    gui.show()
    app.exec()
    
    