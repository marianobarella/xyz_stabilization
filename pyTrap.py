# -*- coding: utf-8 -*-
"""
Created on Thu April 22, 2022

pyTrap is the control software of the 2nd gen Plasmonic Optical Tweezer setup
Here, the Graphical User Interface of pyTrap integrates all microscope modules:
    - lasers control
    - xy and z stabilization modules
    - APD signal acquisition

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland
"""

from queue import Queue
import time as tm
from pyqtgraph.Qt import QtGui, QtCore
from pyqtgraph.dockarea import DockArea, Dock
from PyQt5.QtCore import pyqtSignal, pyqtSlot
import apd_trace_GUI
import laser_control_GUI

#=====================================

# GUI / Frontend definition

#=====================================

class Frontend(QtGui.QMainWindow):
    
    closeSignal = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.cwidget = QtGui.QWidget()
        self.setCentralWidget(self.cwidget)
        self.setWindowTitle('pyTrap')
        self.setUpGUI()
        self.setGeometry(150, 30, 1500, 950) # x pos, y pos, width, height
        return
    
    def setUpGUI(self):
        # GUI layout
        grid = QtGui.QGridLayout()
        self.cwidget.setLayout(grid)
        # Dock Area
        dockArea = DockArea()
        self.dockArea = dockArea
        grid.addWidget(self.dockArea)
        
        ## Add APD trace GUI module
        apdDock = Dock('APD signal')
        self.apdWidget = apd_trace_GUI.Frontend()
        apdDock.addWidget(self.apdWidget)
        self.dockArea.addDock(apdDock)
        
        ## Add Lasers GUI module
        lasersDock = Dock('Lasers')
        self.lasersWidget = laser_control_GUI.Frontend()
        lasersDock.addWidget(self.lasersWidget)
        self.dockArea.addDock(lasersDock , 'right', apdDock)       


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
        return
            
#=====================================

# Controls / Backend definition

#===================================== 
        
class Backend(QtCore.QObject):
    
    def __init__(self, common_variable = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.common_variable = common_variable
        self.lasersWorker = laser_control_GUI.Backend(self.common_variable)
        self.apdWorker = apd_trace_GUI.Backend(self.common_variable)
        self.scanTimer = QtCore.QTimer()
        # self.scanTimer.timeout.connect(self.scan) # funciton to connect after each interval
        # self.scanTimer.setInterval(self.integration_time_ms) # in ms
        return
        
    @pyqtSlot(bool)    
    def acquire_spectrum(self, acq_spec_flag):
        if acq_spec_flag:
            print('\nStarting acquisition of the spectrum...')
            # self.apdWorker.change_duration(self.lasersWorker.integration_time)
            # self.start_trace()
        else:
            print('\nAbort acquisition of the spectrum...')
        return

    
    @pyqtSlot()
    def close_all_backends(self):
        print('Closing all Backends...')
        self.lasersWorker.closeBackend()
        self.apdWorker.closeBackend()
        print('Stopping updater (QtTimer)...')
        self.scanTimer.stop()
        print('Exiting threads...')
        lasersThread.exit()
        apdThread.exit()
        return
    
    def make_modules_connections(self, frontend):
        frontend.closeSignal.connect(self.close_all_backends)
        # connect Backend modules with their respectives Frontend modules
        frontend.apdWidget.make_connections(self.apdWorker)
        frontend.lasersWidget.make_connections(self.lasersWorker)
        # connection that triggers measurement
        frontend.lasersWidget.acquire_spectrum_button_signal.connect(self.acquire_spectrum)
        return
    
#=====================================

#  Main program

#=====================================
      
if __name__ == '__main__':
    # make application
    app = QtGui.QApplication([])

    # create common variable for both threads
    scanning_flag = Queue()
    # create both classes
    gui = Frontend()
    worker = Backend(common_variable = scanning_flag)
       
    ###################################
    # move modules and their timers to different threads
        
    # for APD signal displaying
    apdThread = QtCore.QThread()
    worker.apdWorker.moveToThread(apdThread)
    worker.apdWorker.updateTimer.moveToThread(apdThread)
    # worker.apdWorker.started.connect(start_timer)
    # worker.apdWorker.finished.connect(stop_timer)

    # for lasers
    lasersThread = QtCore.QThread()
    worker.lasersWorker.moveToThread(apdThread)
    # worker.lasersWorker.scanTimer.moveToThread(lasersThread)
    
    # worker.scanTimer.moveToThread(workerThread)


    ###################################

    # connect both classes 
    worker.make_modules_connections(gui)
    gui.make_modules_connections(worker)
    
    # start threads
    lasersThread.start()
    apdThread.start()
    
    gui.show()
    app.exec()
    
    