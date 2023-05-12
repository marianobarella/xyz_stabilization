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

# import os
import time as tm
# from tkinter import filedialog
# import tkinter as tk
# import numpy as np
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
        self.setGeometry(5, 30, 1800, 1000) # x pos, y pos, width, height
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
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lasersWorker = laser_control_GUI.Backend()
        self.apdWorker = apd_trace_GUI.Backend()
        return
            
    @pyqtSlot()
    def close_all_backends(self):
        print('Closing all Backends...')
        self.lasersWorker.closeBackend()
        self.apdWorker.closeBackend()
        # print('Shutting down piezo stage...')
        # self.piezo_stage.shutdown()
        # laser_control_GUI.laser488.close()
        # laser_control_GUI.laser532.close()
        # laser_control_GUI.flipperMirror.close()
        # print('Laser\'s shutters closed.') 
        # self.apdWorker.APD_task.close()
        # print('Task closed.') 
        # print('Stopping timers...')
        # self.lasersWorker.updateTimer.stop()
        # self.apdWorker.updateTimer.stop()
        # self.piezoWorker.updateTimer.stop()
        print('Exiting threads...')
        lasersThread.exit()
        apdThread.exit()
        return
    
    def make_modules_connections(self, frontend):
        frontend.closeSignal.connect(self.close_all_backends)
        # connect Backend modules with their respectives Frontend modules
        frontend.apdWidget.make_connections(self.apdWorker)
        frontend.lasersWidget.make_connections(self.lasersWorker)
        return
      
if __name__ == '__main__':
    # make application
    app = QtGui.QApplication([])

    # create both classes
    gui = Frontend()
    worker = Backend()
       
    ###################################
    # move modules and their timers to different threads
    
    # for lasers
    lasersThread = QtCore.QThread()
    worker.lasersWorker.moveToThread(lasersThread)
    worker.lasersWorker.scanTimer.moveToThread(lasersThread)  
    
    # for APD signal displaying
    apdThread = QtCore.QThread()
    worker.apdWorker.moveToThread(apdThread)
    worker.apdWorker.updateTimer.moveToThread(apdThread)

    ###################################

    # connect both classes 
    worker.make_modules_connections(gui)
    gui.make_modules_connections(worker)
    
    # start threads
    lasersThread.start()
    apdThread.start()
    
    gui.show()
    app.exec()
    