# -*- coding: utf-8 -*-
"""
Created on Thu April 22, 2022

pyTrap is the control software of the 2nd gen Plasmonic Optical Tweezer setup
Here, the Graphical User Interface of pyTrap integrates all microscope modules:
    - lasers control
    - APD signal acquisition

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland
"""

import time as tm
from pyqtgraph.Qt import QtGui, QtCore
from pyqtgraph.dockarea import DockArea, Dock
from PyQt5.QtCore import pyqtSignal, pyqtSlot
import apd_trace_GUI
import laser_control_GUI
import numpy as np

# time interval to check state of the specturm acquisition button
check_button_state = 100 # in ms
initial_filename = 'spectrum'
spectra_path = 'D:\\daily_data\\spectra\\self_generated_spectra'

#=====================================

# GUI / Frontend definition

#=====================================

class Frontend(QtGui.QMainWindow):
    
    closeSignal = pyqtSignal()
    process_acquired_spectrum_signal = pyqtSignal()
    filenameSignal = pyqtSignal(str)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.cwidget = QtGui.QWidget()
        self.setCentralWidget(self.cwidget)
        self.setWindowTitle('pyTrap')
        self.setUpGUI()
        self.setGeometry(150, 30, 1500, 950) # x pos, y pos, width, height
        return
    
    def setUpGUI(self):
        # import front end modules
        self.apdWidget = apd_trace_GUI.Frontend()
        self.lasersWidget = laser_control_GUI.Frontend()
        
        # modify from laser's GUI the spectrum acquisition buttons
        self.lasersWidget.integration_time_label.setText('Integration time (s):')
        self.lasersWidget.acquire_spectrum_button.setCheckable(True)
        self.lasersWidget.acquire_spectrum_button.clicked.connect(self.lasersWidget.acquire_spectrum_button_check)
        self.lasersWidget.acquire_spectrum_button.setStyleSheet(
                "QPushButton { background-color: lightgrey; }"
                "QPushButton::checked { background-color: red; }")
        self.lasersWidget.integration_time_comment.setText('Attention: It overrides Duration variable of the APD trace.')
        self.lasersWidget.process_spectrum_button.clicked.connect(self.process_spectrum_button_check)
        self.lasersWidget.process_spectrum_button.setStyleSheet(
                "QPushButton { background-color: lightgrey; }"
                "QPushButton::checked { background-color: lightgreen; }")
        self.lasersWidget.filename_label.setText('Filename (.dat)')
        self.lasersWidget.filename_name.setFixedWidth(200)
        self.lasersWidget.filename = initial_filename
        self.lasersWidget.filename_name.setText(self.lasersWidget.filename)
        self.lasersWidget.filename_name.editingFinished.connect(self.set_filename)
        
        # GUI layout
        grid = QtGui.QGridLayout()
        self.cwidget.setLayout(grid)
        # Dock Area
        dockArea = DockArea()
        self.dockArea = dockArea
        grid.addWidget(self.dockArea)
        
        ## Add APD trace GUI module
        apdDock = Dock('APD signal')
        apdDock.addWidget(self.apdWidget)
        self.dockArea.addDock(apdDock)
        
        ## Add Lasers GUI module
        lasersDock = Dock('Lasers')
        lasersDock.addWidget(self.lasersWidget)
        self.dockArea.addDock(lasersDock , 'right', apdDock)       
        return
       
    def process_spectrum_button_check(self):
        self.process_acquired_spectrum_signal.emit()
        return
    
    @pyqtSlot()    
    def apd_acq_started(self):
        self.apdWidget.traceButton.setChecked(True)
        self.apdWidget.get_trace()
        return
    
    @pyqtSlot()    
    def apd_acq_stopped(self):
        self.apdWidget.acquisition_stopped()
        return    
    
    @pyqtSlot()    
    def spectrum_finished(self):
        self.lasersWidget.acquire_spectrum_button.setChecked(False)
        return
    
    def set_filename(self):
        filename = self.lasersWidget.filename_name.text()
        if filename != self.lasersWidget.filename:
            self.lasersWidget.filename = filename
            self.filenameSignal.emit(self.lasersWidget.filename)    
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
            print('Closing GUI...')
            self.close()
            self.closeSignal.emit()
            tm.sleep(1)
            app.quit()
        else:
            event.ignore()
            print('Back in business...')    
        return
    
    def make_modules_connections(self, backend):    
        # connect Frontend modules with their respectives Backend modules
        backend.apdWorker.make_connections(self.apdWidget)
        backend.lasersWorker.make_connections(self.lasersWidget)
        backend.spectrum_finished_signal.connect(self.spectrum_finished)
        backend.apd_acq_started_signal.connect(self.apd_acq_started)
        backend.apd_acq_stopped_signal.connect(self.apd_acq_stopped)
        return
            
#=====================================

# Controls / Backend definition

#===================================== 
        
class Backend(QtCore.QObject):
    
    apd_acq_started_signal = pyqtSignal()
    apd_acq_stopped_signal = pyqtSignal()
    spectrum_finished_signal = pyqtSignal()
    
    def __init__(self, common_variable = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.common_variable = common_variable
        self.lasersWorker = laser_control_GUI.Backend(self.common_variable)
        self.apdWorker = apd_trace_GUI.Backend(self.common_variable)
        self.scanTimer = QtCore.QTimer()
        self.scanTimer.timeout.connect(self.continue_scan) # funciton to connect after each interval
        self.scanTimer.setInterval(check_button_state) # in ms
        self.list_of_transmission_files = []
        self.filename = initial_filename
        return
        
    @pyqtSlot(bool)    
    def acquire_spectrum(self, acq_spec_flag):
        # acq_spec_flag varaiable is the state of the button
        self.acquiring_spectrum_flag = acq_spec_flag
        if self.acquiring_spectrum_flag:
            print('\n!!!!!! ------ !!!!!! Starting acquisition of the spectrum...')
            self.apdWorker.change_duration(self.lasersWorker.integration_time)
            self.scanTimer.start()
            self.spectrum_counter = 0
        else:
            self.scanTimer.stop()
            self.apd_acq_stopped_signal.emit()
            self.spectrum_finished_signal.emit()
            self.spectrum_counter = 0
            print('\nAborting acquisition of the spectrum...')
        return

    def continue_scan(self):
        # check if button is checked or counter continues to increase
        if self.acquiring_spectrum_flag:
            # check if transmission APD is acquiring first
            # if not, continue with the spectrum
            if not self.apdWorker.acquisition_flag:
                # close shutter of Ti:Sa if open
                self.lasersWorker.shutterTisa(False)
                # check status of Ti:Sa
                # if Ti:Sa is not changing wavelength continue with the spectrum
                status = self.lasersWorker.update_tisa_status()
                if status == 1:
                    # try to measure or check if we're done
                    if self.spectrum_counter < len(self.lasersWorker.wavelength_scan_array):
                        # still scanning
                        # get and change wavelength
                        wavelength = self.lasersWorker.wavelength_scan_array[self.spectrum_counter]
                        self.lasersWorker.change_wavelength(wavelength)
                        # set suffix for saving the intensity trace
                        self.apdWorker.spectrum_suffix = '_{:04d}nm'.format(int(round(wavelength,0)))
                        # increment counter for next step
                        self.spectrum_counter += 1
                        # open shutter
                        self.lasersWorker.shutterTisa(True)
                        # emit pyqtSignal to frontend to enable trace displaying
                        # and start signal acquisition
                        self.apd_acq_started_signal.emit()
                        # set acquisition variable of APD backend to True
                        self.apdWorker.acquisition_flag = True
                    else:
                        # no more points to scan
                        self.acquire_spectrum(False)
                else:
                    print('\nWavelength has not been changed.')
                    print('Ti:Sa status: ', status)
            
            # - apd acquisiition, save, name definition
            # - start over
        return
    
    @pyqtSlot(str)
    def append_saved_file(self, full_filepath):
        self.list_of_transmission_files.append(full_filepath)
        return
    
    def process_transmission_signals(self, list_of_files):
        mean_array = np.zeros(len(list_of_files))
        std_dev_array = np.zeros(len(list_of_files))
        for i in range(len(list_of_files)):
            f = list_of_files[i]
            data = np.load(f)
            mean_array[i] = np.mean(data)
            std_dev_array[i] = np.std(data, ddof = 1)
        return mean_array, std_dev_array
    
    @pyqtSlot()
    def process_acquired_spectrum(self):
        print('Processing all spectra...')
        # preapre arrays
        x = self.lasersWorker.wavelength_scan_array
        mean_y, std_dev_y = self.process_transmission_signals(self.list_of_transmission_files)
        # set filename
        filename_spectrum = self.filename
        timestr = tm.strftime("_%Y%m%d_%H%M%S")
        filename_spectrum = filename_spectrum + timestr
        # it will save an ASCII encoded text file
        data_to_save = np.transpose(np.vstack((x, mean_y, std_dev_y)))
        header_txt = 'wavelength mean std_dev\nnm V V'
        ascii_full_filepath = spectra_path + '\\' + filename_spectrum + '.dat'
        np.savetxt(ascii_full_filepath, data_to_save, fmt='%.6f', header=header_txt)
        print('Spectrum has been generated and saved with filename %s.dat' % filename_spectrum)
        return
    
    @pyqtSlot(str)
    def set_filename(self, new_filename):
        self.filename = new_filename
        print('New filename has been set:', self.filename)
        return
    
    @pyqtSlot()
    def close_all_backends(self):
        print('Exiting thread...')
        workerThread.exit()
        print('Closing all Backends...')
        self.lasersWorker.closeBackend()
        self.apdWorker.closeBackend()
        print('Stopping updater (QtTimer)...')
        self.scanTimer.stop()
        return
    
    def make_modules_connections(self, frontend):
        frontend.closeSignal.connect(self.close_all_backends)
        # connect Backend modules with their respectives Frontend modules
        frontend.apdWidget.make_connections(self.apdWorker)
        frontend.lasersWidget.make_connections(self.lasersWorker)
        # connection that triggers the measurement of the spectrum
        frontend.lasersWidget.acquire_spectrum_button_signal.connect(self.acquire_spectrum)
        # connection that process the acquired data
        frontend.process_acquired_spectrum_signal.connect(self.process_acquired_spectrum)
        frontend.filenameSignal.connect(self.set_filename)
        # from backend
        self.apdWorker.fileSavedSignal.connect(self.append_saved_file)
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
       
    ###################################
    # move backend to another thread
    workerThread = QtCore.QThread()
    worker.scanTimer.moveToThread(workerThread)
    worker.moveToThread(workerThread)
    # for APD signal displaying
    worker.apdWorker.updateTimer.moveToThread(workerThread)
    worker.apdWorker.moveToThread(workerThread)
    # for lasers
    worker.lasersWorker.moveToThread(workerThread)

    ###################################

    # connect both classes 
    worker.make_modules_connections(gui)
    gui.make_modules_connections(worker)
    
    # start thread
    workerThread.start()
    
    gui.show()
    app.exec()
    
    